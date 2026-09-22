"""Versioned construction plans: atomic commits, independent baselines and PPC."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import json
import re

from .schedule import ScheduleStore, ScheduleConflict, ScheduleNotFound, _name, _date, MAX_HISTORY
from packing_assistant.runtime.cancel import check

SCHEMA = "civil-buddy.planning.v1"
MAX_RECORD = 64 * 1024 * 1024
MAX_SOURCE = 8 * 1024 * 1024
MAX_SOURCE_FILES = 32
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_FORMATS = frozenset({"json", "csv", "xlsx", "xml", "mpp", "xer", "pmxml"})


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_source(source):
    if source is None:
        return
    if not isinstance(source, dict) or set(source) != {"source", "original_dates", "report"}:
        raise ValueError("原文件来源结构无效。")
    meta = source["source"]
    if (not isinstance(meta, dict) or set(meta) != {"filename", "format", "sha256"}
            or not isinstance(meta["filename"], str) or not meta["filename"].strip()
            or len(meta["filename"]) > 200 or any(c in meta["filename"] for c in "/\\\x00")
            or meta["filename"] in {".", ".."} or not isinstance(meta["format"], str)
            or meta["format"] not in SOURCE_FORMATS or not isinstance(meta["sha256"], str)
            or not SHA256.fullmatch(meta["sha256"])):
        raise ValueError("原文件名称、格式或 SHA-256 无效。")
    dates = source["original_dates"]
    if not isinstance(dates, dict) or len(dates) > 250:
        raise ValueError("原文件日期记录无效。")
    from .planning import TASK_ID
    for ident, values in dates.items():
        if not isinstance(ident, str) or not TASK_ID.fullmatch(ident) or not isinstance(values, dict) or set(values) - {"start", "end"}:
            raise ValueError("原文件任务日期结构无效。")
        for value in values.values():
            _date(value)
        if values.get("start") and values.get("end") and values["end"] < values["start"]:
            raise ValueError("原文件结束早于开始。")
    if not isinstance(source["report"], list) or len(source["report"]) > 500:
        raise ValueError("原文件处理报告无效。")
    for item in source["report"]:
        if (not isinstance(item, dict) or {"code", "message", "severity"} - set(item)
                or set(item) - {"code", "message", "severity", "entity_id"}
                or not isinstance(item["code"], str) or not 1 <= len(item["code"]) <= 100
                or not isinstance(item["message"], str) or len(item["message"]) > 4000
                or item["severity"] not in ("warning", "error", "info")
                or "entity_id" in item and (not isinstance(item["entity_id"], str) or len(item["entity_id"]) > 200)):
            raise ValueError("原文件处理报告字段无效。")


def decode_source_file(sha, item):
    if (not isinstance(sha, str) or not SHA256.fullmatch(sha) or not isinstance(item, dict)
            or set(item) != {"data", "size"} or type(item["size"]) is not int
            or not 0 < item["size"] <= MAX_SOURCE or not isinstance(item["data"], str)
            or len(item["data"]) > 4 * ((MAX_SOURCE + 2) // 3)):
        raise ValueError("原始文件记录无效或超过 8 MiB。")
    try:
        data = base64.b64decode(item["data"], validate=True)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("原始文件编码无效。") from exc
    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError("原始文件大小或 SHA-256 不匹配。")
    return data


def bundle_status(record):
    files, missing = record.get("source_files", {}), {}
    for item in [*record.get("history", []), record]:
        source = item.get("import_source")
        if source and source["source"]["sha256"] not in files:
            meta = source["source"]
            missing[(meta["sha256"], meta["filename"])] = {"sha256": meta["sha256"], "filename": meta["filename"]}
    return {"complete": not missing, "source_file_count": len(files), "missing_sources": list(missing.values())}


def validate_weekly(rows, plan):
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError("周承诺最多 2000 条。")
    ids, seen, clean = {t["id"] for t in plan["tasks"]}, set(), []
    parents = {t["parent_id"] for t in plan["tasks"] if t["parent_id"]}
    for row in rows:
        check()
        if not isinstance(row, dict) or set(row) != {"id", "task_id", "week_start", "status", "reason", "constraints"}:
            raise ValueError("周承诺字段无效。")
        ident = _name(row["id"], "承诺编号")
        if ident in seen:
            raise ValueError("周承诺编号重复。")
        seen.add(ident)
        if not isinstance(row["task_id"], str) or row["task_id"] not in ids or row["task_id"] in parents:
            raise ValueError("周承诺须引用已有的具体工序。")
        if _date(row["week_start"]).weekday() != 0:
            raise ValueError("周计划起始日期须为星期一。")
        if not isinstance(row["status"], str) or row["status"] not in {"planned", "done", "missed"}:
            raise ValueError("周承诺状态无效。")
        for key in ("reason", "constraints"):
            value = row[key]
            if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 32 and c not in "\n\t" for c in value):
                raise ValueError("原因和约束须为不超过 1000 字的文本。")
        if row["status"] == "missed" and not row["reason"].strip():
            raise ValueError("未完成的周承诺须记录原因。")
        clean.append(deepcopy(row))
    return clean


def weekly_report(rows):
    groups = {}
    for row in rows:
        group = groups.setdefault(row["week_start"], {"week_start": row["week_start"], "total": 0,
                                                       "done": 0, "missed": 0, "planned": 0})
        group["total"] += 1
        group[row["status"]] += 1
    for group in groups.values():
        group["ppc_percent"] = round(100 * group["done"] / group["total"], 2)
        group["finalized"] = group["planned"] == 0
    return sorted(groups.values(), key=lambda g: g["week_start"], reverse=True)


def baseline_comparison(baseline, result):
    if not baseline:
        return []
    old = {t["id"]: t for t in baseline["result"]["tasks"]}
    new = {t["id"]: t for t in result["tasks"]}
    rows = []
    for ident in dict.fromkeys([*new, *old]):
        before, after = old.get(ident), new.get(ident)
        rows.append({"id": ident, "status": "added" if not before else "removed" if not after else "existing",
                     "baseline_start": before["start"] if before else None,
                     "baseline_end": before["end"] if before else None,
                     "start": after["start"] if after else None, "end": after["end"] if after else None,
                     "finish_variance_calendar_days": (_date(after["end"]) - _date(before["end"])).days
                     if before and after else None})
    return rows


def _validate_result(plan, result):
    """Inspect stored structure without silently rerunning a historical engine."""
    if not isinstance(result, dict) or not isinstance(result.get("tasks"), list):
        raise ValueError("结果结构无效")
    ids = [t["id"] for t in plan["tasks"]]
    if len(result["tasks"]) != len(ids):
        raise ValueError("结果任务数量无效")
    seen = set()
    for row in result["tasks"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in seen or row["id"] not in ids:
            raise ValueError("结果任务编号无效")
        seen.add(row["id"])
        if _date(row["end"]) < _date(row["start"]):
            raise ValueError("结果日期无效")
        if type(row.get("start_offset")) is not int or type(row.get("finish_offset")) is not int or not 0 <= row["start_offset"] <= row["finish_offset"] <= 3654:
            raise ValueError("结果时间偏移无效")
    if type(result.get("duration_workdays")) is not int or not 0 <= result["duration_workdays"] <= 3654:
        raise ValueError("结果总工期无效")
    if result.get("finish_date") != max(row["end"] for row in result["tasks"]):
        raise ValueError("结果完成日期无效")


class PlanningStore(ScheduleStore):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.root = self.workspace / ".civil-buddy" / "out" / "engineering" / "plans"

    def _read(self, ident):
        from packing_assistant.sandbox import assert_open
        from .planning import validate_plan
        path = assert_open(self._path(ident), profile=self.profile)
        if not path.is_file():
            raise ScheduleNotFound("施工排程项目不存在。")
        if path.stat().st_size > MAX_RECORD:
            raise ValueError("施工排程项目文件过大。")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            checksum = record.pop("checksum")
            if checksum != digest(record) or record["schema"] != SCHEMA or record["id"] != ident:
                raise ValueError("摘要或编号错误")
            required = {"schema", "id", "name", "plan", "result", "method", "weekly", "baseline", "revision",
                        "created_at", "updated_at", "history", "synthetic", "import_source"}
            if required - set(record) or set(record) - required - {"source_files", "bundle_origin"}:
                raise ValueError("未知项目字段")
            files = record.get("source_files", {})
            if not isinstance(files, dict) or len(files) > MAX_SOURCE_FILES:
                raise ValueError("原文件数量无效")
            for sha, item in files.items():
                check()
                decode_source_file(sha, item)
            if type(record["revision"]) is not int or record["revision"] < 1:
                raise ValueError("修订号错误")
            if len(record["history"]) > MAX_HISTORY:
                raise ValueError("历史过长")
            previous = 0
            for item in [*record["history"], record]:
                _name(item["name"])
                validate_plan(item["plan"])
                validate_weekly(item["weekly"], item["plan"])
                if type(item["synthetic"]) is not bool or item["import_source"] is not None and not isinstance(item["import_source"], dict):
                    raise ValueError("来源记录无效")
                validate_source(item["import_source"])
                if type(item["revision"]) is not int or not previous < item["revision"]:
                    raise ValueError("历史顺序错误")
                previous = item["revision"]
                if item["method"] not in {"cpm", "resource"} or not isinstance(item["result"], dict):
                    raise ValueError("结果错误")
                _validate_result(item["plan"], item["result"])
                if item["baseline"] is not None:
                    baseline = item["baseline"]
                    if not isinstance(baseline, dict) or set(baseline) != {"created_at", "revision", "plan", "result"}:
                        raise ValueError("基线记录无效")
                    validate_plan(baseline["plan"])
                    _validate_result(baseline["plan"], baseline["result"])
                    datetime.fromisoformat(baseline["created_at"])
                    if type(baseline["revision"]) is not int or not 0 < baseline["revision"] <= item["revision"]:
                        raise ValueError("基线修订无效")
                datetime.fromisoformat(item["updated_at"])
            return record
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
            raise ValueError("施工排程记录损坏，未覆盖原文件。") from exc

    def _write(self, record):
        from demo.projects import _write_atomic
        from packing_assistant.sandbox import assert_write
        signed = deepcopy(record)
        signed["checksum"] = digest(record)
        payload = json.dumps(signed, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_RECORD:
            raise ValueError("项目、历史与原文件超过 64 MiB 存储上限；旧记录未覆盖。")
        path = assert_write(self._path(record["id"]), profile=self.profile)
        _write_atomic(path, payload, before_replace=check)

    @staticmethod
    def _public(record):
        result = {k: deepcopy(v) for k, v in record.items() if k not in {"history", "source_files"}}
        result["versions"] = [{"revision": r["revision"], "updated_at": r["updated_at"],
                               "task_count": len(r["plan"]["tasks"])} for r in record["history"]]
        result["can_undo"] = bool(record["history"])
        result["weekly_report"] = weekly_report(record["weekly"])
        result["baseline_comparison"] = baseline_comparison(record["baseline"], record["result"])
        result["bundle_status"] = bundle_status(record)
        return result

    def list_projects(self):
        result = []
        from .schedule import PROJECT_ID
        for path in self._path().glob("*.json"):
            if not PROJECT_ID.fullmatch(path.stem):
                continue
            try:
                record = self._read(path.stem)
                result.append({k: record[k] for k in ("id", "name", "revision", "updated_at")} |
                              {"task_count": len(record["plan"]["tasks"]), "method": record["method"]})
            except (ValueError, OSError, PermissionError) as exc:
                result.append({"id": path.stem, "name": "无法读取的排程项目", "revision": 0,
                               "updated_at": "", "task_count": 0, "error": str(exc)})
        return sorted(result, key=lambda r: r["updated_at"], reverse=True)

    def open(self, ident, version=None):
        record = self._read(ident)
        if version is not None and version != record["revision"]:
            found = next((r for r in record["history"] if r["revision"] == version), None)
            if found is None:
                raise ScheduleNotFound("指定修订已不存在。")
            result = self._public(record)
            result.update(deepcopy(found))
            result["current_revision"] = record["revision"]
            result["historical"] = True
            result["can_undo"] = False
            result["weekly_report"] = weekly_report(found["weekly"])
            result["baseline_comparison"] = baseline_comparison(found["baseline"], found["result"])
            return result
        return self._public(record)

    @staticmethod
    def _snapshot(record):
        return {k: deepcopy(record[k]) for k in ("name", "plan", "result", "method", "weekly", "baseline",
                                                "revision", "updated_at", "synthetic", "import_source")}

    def save(self, *, name, plan, result, method="cpm", weekly=None, project_id=None, expected_revision=None,
             synthetic=None, import_source=None):
        from demo.projects import _mutation
        from .planning import validate_plan
        from uuid import uuid4
        plan = validate_plan(plan)
        _validate_result(plan, result)
        name = _name(name)
        self._writable()
        with _mutation(self._path()):
            check()
            now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            if project_id:
                record = self._read(project_id)
                self._expected(record, expected_revision)
                rows = record["weekly"] if weekly is None else weekly
                record["history"] = (record["history"] + [self._snapshot(record)])[-20:]
                record["revision"] += 1
            else:
                if expected_revision is not None:
                    raise ValueError("新计划不能携带旧修订号。")
                if len(list(self.root.glob("*.json"))) >= 100:
                    raise ValueError("排程项目达到 100 个上限。")
                record = {"schema": SCHEMA, "id": uuid4().hex, "created_at": now, "revision": 1,
                          "history": [], "baseline": None, "synthetic": False, "import_source": None, "source_files": {}}
                rows = weekly or []
            rows = validate_weekly(rows, plan)
            if synthetic is not None:
                if type(synthetic) is not bool:
                    raise ValueError("合成来源标记须为布尔值。")
                record["synthetic"] = synthetic
            if import_source is not None:
                source = deepcopy(import_source)
                blob = source.pop("source_file", None)
                validate_source(source)
                if blob is not None:
                    sha = source["source"]["sha256"]
                    decode_source_file(sha, blob)
                    files = record.setdefault("source_files", {})
                    if sha not in files and len(files) >= MAX_SOURCE_FILES:
                        raise ValueError("项目原始文件最多 32 份，请另存新项目。")
                    files[sha] = blob
                record["import_source"] = source
            record.update(name=name, plan=plan, result=deepcopy(result), method=method, weekly=rows, updated_at=now)
            self._write(record)
            return self._public(record)

    def source_file(self, ident, sha):
        if not isinstance(sha, str) or not SHA256.fullmatch(sha):
            raise ValueError("原文件 SHA-256 无效。")
        return deepcopy(self._read(ident).get("source_files", {}).get(sha))

    def attach_source(self, ident, data, expected_revision):
        from demo.projects import _mutation
        if not isinstance(data, bytes) or not data or len(data) > MAX_SOURCE:
            raise ValueError("补齐原文件须非空且不超过 8 MiB。")
        self._writable()
        sha = hashlib.sha256(data).hexdigest()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            if sha not in {item["sha256"] for item in bundle_status(record)["missing_sources"]}:
                raise ValueError("上传文件 SHA-256 不匹配任何缺失原文件；项目未修改。")
            files = record.setdefault("source_files", {})
            if len(files) >= MAX_SOURCE_FILES:
                raise ValueError("项目原始文件最多 32 份。")
            record["history"] = (record["history"] + [self._snapshot(record)])[-20:]
            files[sha] = {"data": base64.b64encode(data).decode("ascii"), "size": len(data)}
            record.update(revision=record["revision"] + 1, updated_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
            self._write(record)
            return self._public(record)

    def set_baseline(self, ident, expected_revision):
        from demo.projects import _mutation
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            record["history"] = (record["history"] + [self._snapshot(record)])[-20:]
            now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            record["baseline"] = {"created_at": now, "revision": record["revision"],
                                  "plan": deepcopy(record["plan"]), "result": deepcopy(record["result"])}
            record.update(revision=record["revision"] + 1, updated_at=now)
            self._write(record)
            return self._public(record)

    def undo(self, ident, expected_revision):
        from demo.projects import _mutation
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            if not record["history"]:
                raise ValueError("没有可撤销的已保存修改。")
            revision = record["revision"] + 1
            previous = record["history"].pop()
            record.update(previous)
            record.update(revision=revision, updated_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
            self._write(record)
            return self._public(record)
