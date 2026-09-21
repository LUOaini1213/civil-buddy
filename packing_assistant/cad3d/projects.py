"""Versioned CAD recipes. Original DXF bytes are immutable; meshes are rebuilt.

One atomic manifest is the transaction boundary. Portable bundles contain only
the source and validated recipes, never trusted client geometry or approvals.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import stat
from uuid import uuid4
import zipfile
import zlib

from packing_assistant.sandbox import assert_open, assert_write

SCHEMA = "civil-buddy.cad3d.project.v1"
BUNDLE_SCHEMA = "civil-buddy.cad3d.project-bundle.v1"
MAX_SOURCE = 10 * 1024 * 1024
MAX_MANIFEST = 24 * 1024 * 1024
MAX_BUNDLE = 16 * 1024 * 1024
MAX_PROJECTS = 100
MAX_VERSIONS = 50
MAX_STORE = 512 * 1024 * 1024
ID = re.compile(r"[0-9a-f]{32}\Z")


class ProjectConflict(ValueError):
    pass


class ProjectNotFound(ValueError):
    pass


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _integer(value, label: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} 必须是大于等于 {minimum} 的整数。")
    return value


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100 or any(ord(c) < 32 for c in value):
        raise ValueError("项目名须为 1–100 个字符，不得含控制字符。")
    return value.strip()


def _draft(document: dict, value: dict) -> dict:
    """Incomplete dimensions may be saved, but never arbitrary payloads or IDs."""
    if not isinstance(value, dict) or set(value) - {"mode", "unit", "layers", "parameters", "overrides", "confirmed_solid", "curve_tolerance_mm"}:
        raise ValueError("项目参数字段无效。")
    if len(_json(value).encode("utf-8")) > 512 * 1024:
        raise ValueError("项目参数过大。")
    if value.get("mode") not in ("building", "section") or value.get("unit", "") not in ("", "mm", "cm", "m", "in", "ft"):
        raise ValueError("建模模式或单位无效。")
    if type(value.get("confirmed_solid")) is not bool:
        raise ValueError("实体轮廓确认必须是布尔值。")
    layers = {row["name"] for row in document["layers"]}
    roles = {"wall", "column", "slab", "section"}
    mapping = value.get("layers")
    if not isinstance(mapping, dict) or any(k not in layers or not isinstance(v, str) or v not in roles | {"ignore"} for k, v in mapping.items()):
        raise ValueError("图层映射包含不存在的图层或用途。")
    ids = {row["id"] for row in document["entities"]}
    for row in document["entities"]:
        ids.update(row.get("source_entity_ids", []))
    for field, allowed in (("parameters", roles), ("overrides", ids)):
        rows = value.get(field, {})
        if not isinstance(rows, dict) or any(key not in allowed for key in rows):
            raise ValueError(f"{field} 包含未知对象。")
        for params in rows.values():
            if not isinstance(params, dict) or set(params) - {"height_m", "base_m"}:
                raise ValueError("只可保存高度、长度和底标高参数。")
            for number in params.values():
                if number is not None and (type(number) not in {int, float} or abs(number) > 1e6 or not math.isfinite(number)):
                    raise ValueError("尺寸必须为有限数值或未填写。")
    tolerance = value.get("curve_tolerance_mm", 0.1)
    if type(tolerance) not in {int, float} or not 0.001 <= tolerance <= 10 or not math.isfinite(tolerance):
        raise ValueError("曲线弦高误差须在 0.001–10 mm 之间。")
    return deepcopy(value)


def _recipe(model: dict) -> dict:
    return {"config": deepcopy(model["config"]), "objects": len(model["objects"]),
            "report": deepcopy(model.get("report", [])), "transform": deepcopy(model.get("transform", {}))}


class CadProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()

    def _path(self, project_id: str | None = None) -> Path:
        if project_id is not None and (not isinstance(project_id, str) or ID.fullmatch(project_id) is None):
            raise ValueError("CAD 项目编号无效。")
        path = self.root / project_id / "project.json" if project_id else self.root
        for parent in (path, *path.parents):
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ValueError("CAD 项目路径不能是链接或目录联接。")
        path.resolve().relative_to(self.root.resolve())
        return path

    def _writable(self) -> None:
        from packing_assistant.runtime.civil_config import load_config
        if load_config().sandbox == "read-only":
            raise PermissionError("当前工作台只读，不能保存或导入 CAD 项目。")
        assert_write(self._path() / "_index" / "projects.lock")

    def _read(self, project_id: str) -> dict:
        path = assert_open(self._path(project_id))
        if not path.is_file():
            raise ProjectNotFound("CAD 项目不存在。")
        if path.stat().st_size > MAX_MANIFEST:
            raise ValueError("CAD 项目文件超过上限。")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            _json(record)
            if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("id") != project_id:
                raise ValueError("项目格式不匹配")
            _integer(record["revision"], "项目修订号")
            _name(record["name"])
            for field in ("created_at", "updated_at"):
                if not isinstance(record[field], str):
                    raise ValueError("项目日期无效")
                datetime.fromisoformat(record[field])
            if not isinstance(record["source"], dict) or set(record["source"]) != {"filename", "sha256", "data"}:
                raise ValueError("原图记录无效")
            if not isinstance(record["versions"], list) or len(record["versions"]) > MAX_VERSIONS:
                raise ValueError("版本数量无效")
            for index, version in enumerate(record["versions"], 1):
                if not isinstance(version, dict):
                    raise ValueError("版本记录无效")
                if version["version"] != index or type(version["version"]) is not int:
                    raise ValueError("版本顺序无效")
                _integer(version["objects"], "构件数量")
                if not isinstance(version["created_at"], str):
                    raise ValueError("版本日期无效")
                datetime.fromisoformat(version["created_at"])
            return record
        except (KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
            raise ValueError("CAD 项目记录损坏；原文件已保留，未覆盖。") from exc

    @staticmethod
    def _document(record: dict) -> tuple[bytes, dict]:
        from .geometry import inspect_dxf
        try:
            filename = record["source"]["filename"]
            if not isinstance(filename, str) or len(filename) > 200 or not filename.lower().endswith(".dxf") or "/" in filename or "\\" in filename:
                raise ValueError("原图名称必须是 200 字符以内的 DXF 文件名")
            source = base64.b64decode(record["source"]["data"], validate=True)
            if not source or len(source) > MAX_SOURCE or hashlib.sha256(source).hexdigest() != record["source"]["sha256"]:
                raise ValueError("图纸摘要或大小不匹配")
            document = inspect_dxf(source, filename)
            _draft(document, record["draft_config"])
            for version in record["versions"]:
                _draft(document, version["config"])
            return source, document
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            raise ValueError("CAD 原图或参数校验失败：" + str(exc)) from exc

    @staticmethod
    def _summary(record: dict) -> dict:
        return {key: record[key] for key in ("id", "name", "revision", "created_at", "updated_at")} | {
            "versions": [{key: row[key] for key in ("version", "created_at", "objects")} for row in record["versions"]]}

    def list_projects(self) -> list[dict]:
        root = self._path()
        if not root.exists():
            return []
        rows = []
        for directory in root.iterdir():
            if ID.fullmatch(directory.name):
                try:
                    rows.append(self._summary(self._read(directory.name)))
                except (ValueError, OSError, PermissionError) as exc:
                    rows.append({"id": directory.name, "name": "无法读取的 CAD 项目", "revision": 0,
                                 "updated_at": "", "versions": [], "error": str(exc)})
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

    def _write(self, record: dict) -> None:
        from demo.projects import _write_atomic
        from packing_assistant.runtime import cancel
        encoded = _json(record)
        size = len(encoded.encode("utf-8"))
        if size > MAX_MANIFEST:
            raise ValueError("CAD 项目超过存储上限，请另存项目包。")
        path = self._path(record["id"])
        total = 0
        for directory in self.root.iterdir() if self.root.exists() else []:
            if ID.fullmatch(directory.name):
                other = self._path(directory.name)
                if other != path and other.is_file():
                    total += other.stat().st_size
        if total + size > MAX_STORE:
            raise ValueError("CAD 项目存储已满，请先备份并整理项目。")
        assert_write(path)
        cancel.check()
        _write_atomic(path, encoded, before_replace=cancel.check)

    def save(self, *, name: str, document: dict, source: bytes, draft_config: dict, model: dict | None = None,
             project_id: str | None = None, expected_revision: int | None = None) -> dict:
        from demo.projects import _mutation
        from .geometry import inspect_dxf
        self._writable()
        name = _name(name)
        if not isinstance(source, bytes) or not source or len(source) > MAX_SOURCE:
            raise ValueError("原始 DXF 缺失或超过 10 MiB。")
        sha = hashlib.sha256(source).hexdigest()
        if document.get("sha256") != sha:
            raise ValueError("缓存原图与待保存图纸不一致，请重新上传。")
        filename = str(document.get("filename", "drawing.dxf")).replace("\\", "/").split("/")[-1][:200]
        checked = inspect_dxf(source, filename)
        draft = _draft(checked, draft_config)
        if model is not None:
            saved_cfg, model_cfg = deepcopy(draft), deepcopy(model.get("config", {}))
            saved_cfg.setdefault("curve_tolerance_mm", 0.1); model_cfg.setdefault("curve_tolerance_mm", 0.1)
            if saved_cfg != model_cfg or model.get("source", {}).get("sha256") != sha or not model.get("objects"):
                raise ValueError("模型与当前图纸或参数不一致，请先生成当前版本。")
        with _mutation(self._path()):
            if project_id:
                record = self._read(project_id)
                # Validate old source and recipes before replacing any part of
                # the record; a corrupt history is not an empty project.
                self._document(record)
                if _integer(expected_revision, "预期修订号") != record["revision"]:
                    raise ProjectConflict("项目已被其他页面更新，请重新打开后再保存；当前修改未覆盖。")
                if record["source"]["sha256"] != sha:
                    raise ValueError("项目原图不可替换，请保存为新项目。")
                record = deepcopy(record)
                record["revision"] += 1
            else:
                if expected_revision is not None:
                    raise ValueError("新项目不能指定旧修订号。")
                if len(self.list_projects()) >= MAX_PROJECTS:
                    raise ValueError("CAD 项目数量已达上限。")
                record = {"schema": SCHEMA, "id": uuid4().hex, "revision": 1, "created_at": _now(), "versions": [],
                          "source": {"filename": filename, "sha256": sha, "data": base64.b64encode(source).decode("ascii")}}
            record.update(name=name, updated_at=_now(), draft_config=draft)
            if model is not None and (not record["versions"] or record["versions"][-1]["config"] != model["config"]):
                if len(record["versions"]) >= MAX_VERSIONS:
                    raise ValueError("模型已达 50 个版本，请保存为新项目。")
                record["versions"].append({"version": len(record["versions"]) + 1, "created_at": _now(), **_recipe(model)})
            self._write(record)
            return self._summary(record)

    def update(self, project_id: str, *, expected_revision: int, draft_config: dict, model: dict | None = None) -> dict:
        record = self._read(project_id)
        source, document = self._document(record)
        return self.save(name=record["name"], document=document, source=source, draft_config=draft_config, model=model,
                         project_id=project_id, expected_revision=expected_revision)

    def open(self, project_id: str, version: int | None = None) -> dict:
        from .geometry import build_model
        record = self._read(project_id)
        _, document = self._document(record)
        chosen = record["versions"][-1] if record["versions"] else None
        if version is not None:
            _integer(version, "模型版本")
            chosen = next((row for row in record["versions"] if row["version"] == version), None)
            if chosen is None:
                raise ProjectNotFound("指定的 CAD 模型版本不存在。")
        result = {"project": self._summary(record), "document": document,
                  "draft_config": deepcopy(chosen["config"] if version is not None else record["draft_config"]),
                  "confirmation_reset": True}
        if chosen:
            model = build_model(document, chosen["config"])
            if not model.get("objects") or len(model["objects"]) != chosen["objects"]:
                raise ValueError("保存的版本无法完整重建，原始项目保持不变。")
            model["source"] = {key: document[key] for key in ("filename", "sha256", "units")}
            result.update(model=model, applied_config=deepcopy(model["config"]), version=chosen["version"])
        return result

    def source(self, project_id: str) -> bytes:
        return self._document(self._read(project_id))[0]

    def export_bundle(self, project_id: str, expected_revision: int | None = None) -> bytes:
        record = self._read(project_id)
        if expected_revision is not None and _integer(expected_revision, "预期修订号") != record["revision"]:
            raise ProjectConflict("项目已被其他页面更新，请重新打开并核对后导出。")
        source, _ = self._document(record)
        portable = deepcopy(record)
        portable["schema"] = BUNDLE_SCHEMA
        portable["source"].pop("data")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json(portable).encode("utf-8"))
            archive.writestr("drawing.dxf", source)
        payload = buffer.getvalue()
        if len(payload) > MAX_BUNDLE:
            raise ValueError("项目包过大。")
        return payload

    def import_bundle(self, data: bytes) -> dict:
        from demo.projects import _mutation
        from .geometry import build_model
        self._writable()
        if not data or len(data) > MAX_BUNDLE:
            raise ValueError("项目包不能为空或超过 16 MiB。")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.infolist()
                if len(info) != 2 or {entry.filename for entry in info} != {"manifest.json", "drawing.dxf"}:
                    raise ValueError("项目包只能包含 manifest.json 和 drawing.dxf。")
                if any(entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16) for entry in info):
                    raise ValueError("项目包不能包含加密或链接文件。")
                if sum(entry.file_size for entry in info) > MAX_MANIFEST + MAX_SOURCE:
                    raise ValueError("项目包解压大小超过上限。")
                with archive.open("manifest.json") as handle:
                    raw = handle.read(MAX_MANIFEST + 1)
                with archive.open("drawing.dxf") as handle:
                    source = handle.read(MAX_SOURCE + 1)
                if len(raw) > MAX_MANIFEST or len(source) > MAX_SOURCE:
                    raise ValueError("项目包内容过大。")
                record = json.loads(raw)
                if not isinstance(record, dict) or record.get("schema") != BUNDLE_SCHEMA:
                    raise ValueError("不支持此项目包格式。")
                if set(record) != {"schema", "id", "revision", "name", "created_at", "updated_at", "source", "draft_config", "versions"}:
                    raise ValueError("项目包含未知字段。")
                if set(record["source"]) != {"filename", "sha256"} or not isinstance(record["versions"], list) or len(record["versions"]) > MAX_VERSIONS:
                    raise ValueError("原图或版本记录格式无效。")
                record["source"]["data"] = base64.b64encode(source).decode("ascii")
                _, document = self._document(record)
                versions = []
                for row in record["versions"]:
                    model = build_model(document, row["config"])
                    if not model.get("objects"):
                        raise ValueError("项目包中的模型版本无法重建。")
                    versions.append({"version": len(versions) + 1, "created_at": _now(), **_recipe(model)})
                record.update(schema=SCHEMA, id=uuid4().hex, revision=1, name=_name(record["name"]),
                              created_at=_now(), updated_at=_now(), versions=versions)
                # Never restore approvals, session state, paths or user identity.
                with _mutation(self._path()):
                    if len(self.list_projects()) >= MAX_PROJECTS:
                        raise ValueError("CAD 项目数量已达上限。")
                    self._write(record)
                return self.open(record["id"])
        except (zipfile.BadZipFile, zlib.error, NotImplementedError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
            raise ValueError("项目包损坏或缺少必要字段，未导入。") from exc
