"""Explicitly saved analysis inputs and successful results, one atomic manifest."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
from uuid import uuid4

from packing_assistant.sandbox import assert_open, assert_write

ID = re.compile(r"[0-9a-f]{32}\Z")
SCHEMA = "civil-buddy.engineering.v1"
MAX_BYTES = 64 * 1024 * 1024
KINDS = frozenset({"frame", "section", "ifc_check", "ifc_diff"})


class RecordConflict(ValueError):
    pass


class RecordNotFound(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _name(value):
    return isinstance(value, str) and 1 <= len(value.strip()) <= 100 and not any(ord(c) < 32 for c in value)


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("无效的记录时间。")
    if datetime.fromisoformat(value).tzinfo is None:
        raise ValueError("记录时间缺少时区。")


def _snapshot(value, kind=None):
    if (not isinstance(value, dict) or set(value) != {"kind", "inputs", "result"}
            or not isinstance(value["kind"], str) or value["kind"] not in KINDS
            or (kind is not None and value["kind"] != kind)
            or not isinstance(value["inputs"], dict) or not isinstance(value["result"], dict)
            or value["result"].get("ok") is False
            or value["result"].get("kind", value["kind"]) != value["kind"]):
        raise ValueError("分析记录无效。")
    # Reject NaN, infinity and unsupported values before creating any file.
    try:
        encode(value)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("分析记录包含无效数值或结构。") from exc


def _manifest(record, identifier):
    if (not isinstance(record, dict) or record.get("schema") != SCHEMA
            or record.get("id") != identifier or not isinstance(record.get("kind"), str)
            or record["kind"] not in KINDS or not _name(record.get("name"))
            or type(record.get("revision")) is not int
            or not isinstance(record.get("versions"), list)
            or record["revision"] != len(record["versions"]) or not 1 <= record["revision"] <= 20):
        raise ValueError("无效的项目元数据。")
    _timestamp(record.get("updated_at"))
    for index, row in enumerate(record["versions"], 1):
        if not isinstance(row, dict) or type(row.get("version")) is not int or row["version"] != index:
            raise ValueError("无效的版本元数据。")
        _timestamp(row.get("created_at"))
        _snapshot(row.get("snapshot"), record["kind"])
        if hashlib.sha256(encode(row["snapshot"]).encode()).hexdigest() != row.get("sha256"):
            raise ValueError("分析版本校验失败。")
    if record["updated_at"] != record["versions"][-1]["created_at"]:
        raise ValueError("项目时间与最后版本不一致。")


class AnalysisStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()

    def path(self, identifier=None):
        if identifier is not None and (not isinstance(identifier, str) or not ID.fullmatch(identifier)):
            raise ValueError("分析项目编号无效。")
        target = self.root / (identifier + ".json") if identifier else self.root
        for path in (target, *target.parents):
            # pathlib.is_junction is unavailable on the supported Python 3.11.
            try:
                reparse = bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
            except FileNotFoundError:
                reparse = False
            if reparse or path.is_symlink():
                raise ValueError("分析项目路径不能是链接或目录联接。")
        target.resolve().relative_to(self.root.resolve())
        return target

    @staticmethod
    def summary(record):
        return {key: record[key] for key in ("id", "name", "kind", "revision", "updated_at")} | {
            "versions": [{"version": row["version"], "created_at": row["created_at"]} for row in record["versions"]]}

    def open(self, identifier, version=None):
        path = assert_open(self.path(identifier))
        if not path.is_file():
            raise RecordNotFound("分析项目不存在。")
        try:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError()
            record = json.loads(path.read_text(encoding="utf-8"))
            _manifest(record, identifier)
        except (ValueError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
            raise ValueError("分析项目记录损坏，原文件保留，未覆盖。") from exc
        if version is not None and (type(version) is not int or not 1 <= version <= len(record["versions"])):
            raise ValueError("分析版本不存在。")
        row = record["versions"][(version or record["revision"]) - 1]
        return {"project": self.summary(record), "version": row["version"], "snapshot": deepcopy(row["snapshot"])}

    def list_projects(self):
        root = assert_open(self.path())
        rows = []
        if root.exists():
            for path in root.glob("*.json"):
                if ID.fullmatch(path.stem):
                    try:
                        rows.append(self.open(path.stem)["project"])
                    except (ValueError, OSError, PermissionError):
                        rows.append({"id": path.stem, "name": "无法读取的分析项目", "error": "记录损坏或不可读", "updated_at": ""})
        return sorted(rows, key=lambda row: row["updated_at"], reverse=True)

    def save(self, name, snapshot, identifier=None, expected_revision=None):
        from demo.projects import _mutation, _write_atomic
        from packing_assistant.runtime.cancel import check
        from packing_assistant.runtime.civil_config import load_config
        if not load_config().allow_write():
            raise PermissionError("当前只读，不能保存分析项目。")
        if not _name(name):
            raise ValueError("项目名须为 1–100 个字符。")
        _snapshot(snapshot)
        if identifier is not None:
            self.path(identifier)
        assert_write(self.path() / "index.lock")
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        with _mutation(self.path()):
            if identifier:
                old = self.open(identifier)
                if type(expected_revision) is not int or expected_revision != old["project"]["revision"]:
                    raise RecordConflict("项目已更新，请重新打开后再保存。当前修改未覆盖。")
                record = json.loads(self.path(identifier).read_text(encoding="utf-8"))
                if record["kind"] != snapshot["kind"]:
                    raise ValueError("不能更换项目计算类型，请另存为新项目。")
            else:
                if expected_revision is not None:
                    raise ValueError("新项目不能指定旧修订号。")
                if len(self.list_projects()) >= 100:
                    raise ValueError("分析项目数量已达 100 个。")
                identifier = uuid4().hex
                record = {"schema": SCHEMA, "id": identifier, "kind": snapshot["kind"], "versions": []}
            if len(record["versions"]) >= 20:
                raise ValueError("单项目最多 20 个分析版本，请保存为新项目。")
            revision = len(record["versions"]) + 1
            record.update(name=name.strip(), revision=revision, updated_at=now)
            record["versions"].append({"version": revision, "created_at": now, "snapshot": deepcopy(snapshot),
                                       "sha256": hashlib.sha256(encode(snapshot).encode()).hexdigest()})
            data = encode(record)
            if len(data.encode()) > MAX_BYTES:
                raise ValueError("分析项目超过 64 MiB，请另存为新项目。")
            total = sum(path.stat().st_size for path in self.path().glob("*.json") if path.stem != identifier)
            if total + len(data.encode()) > 512 * 1024 * 1024:
                raise ValueError("分析项目存储超过 512 MiB，请备份整理后保存。")
            check()
            _write_atomic(assert_write(self.path(identifier)), data, before_replace=check)
        return self.open(identifier)
