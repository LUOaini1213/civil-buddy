"""Calendar task plans with bounded, atomic storage and optimistic revisions.

The caller supplies its server-selected workspace, never a client path. This
module records user dates; it does not calculate CPM or resource levelling.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
import stat
from uuid import uuid4

from packing_assistant.runtime.cancel import check
from packing_assistant.sandbox import SandboxProfile, assert_open, assert_write

SCHEMA = "civil-buddy.schedule.v1"
MAX_TASKS = 250
MAX_HISTORY = 50
MAX_PROJECTS = 100
MAX_BYTES = 8 * 1024 * 1024
PROJECT_ID = re.compile(r"[0-9a-f]{32}\Z")
TASK_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class ScheduleConflict(ValueError):
    pass


class ScheduleNotFound(ValueError):
    pass


def _name(value, label="计划名称"):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{label}须为 1–100 个字符，不得含控制字符。")
    return value.strip()


def _date(value):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError("日期必须使用 YYYY-MM-DD 格式。")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"日期不存在：{value}") from None
    if not 1900 <= parsed.year <= 2100:
        raise ValueError("日期年份须在 1900–2100 之间。")
    return parsed


def validate_tasks(tasks):
    """Return a normalized copy; reject invalid references and cyclic graphs."""
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValueError(f"任务须为列表，最多 {MAX_TASKS} 项。")
    clean, ids, dates = [], set(), []
    for task in tasks:
        check()
        if not isinstance(task, dict) or set(task) != {"id", "name", "start", "end", "progress", "dependencies"}:
            raise ValueError("任务必须且只能包含 id、name、start、end、progress、dependencies。")
        ident = task["id"]
        if not isinstance(ident, str) or not TASK_ID.fullmatch(ident):
            raise ValueError("任务编号须以英文字母开头，仅含字母、数字、下划线或连字符，最多 64 字符。")
        if ident in ids:
            raise ValueError(f"任务编号重复：{ident}")
        ids.add(ident)
        start, end = _date(task["start"]), _date(task["end"])
        if end < start:
            raise ValueError(f"{ident}：结束日期早于开始日期。")
        progress = task["progress"]
        if type(progress) not in (int, float) or not math.isfinite(progress) or not 0 <= progress <= 100:
            raise ValueError(f"{ident}：进度必须为 0–100 的有限数值。")
        deps = task["dependencies"]
        if not isinstance(deps, list) or len(deps) > MAX_TASKS or any(not isinstance(d, str) for d in deps):
            raise ValueError(f"{ident}：依赖必须为任务编号列表。")
        if len(set(deps)) != len(deps):
            raise ValueError(f"{ident}：依赖编号重复。")
        if ident in deps:
            raise ValueError(f"{ident}：不能依赖自身。")
        clean.append(dict(task, name=_name(task["name"], "任务名称"), dependencies=list(deps)))
        dates.extend((start, end))
    if dates and (max(dates) - min(dates)).days > 3653:
        raise ValueError("单个计划的总日期跨度最多 10 年，请拆分计划。")
    for task in clean:
        unknown = set(task["dependencies"]) - ids
        if unknown:
            raise ValueError(f"{task['id']}：未知依赖 {', '.join(sorted(unknown))}")
    graph = {t["id"]: t["dependencies"] for t in clean}
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise ValueError(f"依赖存在循环，涉及任务 {node}。")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for ident in graph:
        visit(ident)
    return clean


def task_warnings(tasks):
    by_id = {t["id"]: t for t in tasks}
    warnings, total = [], 0
    for task in tasks:
        for dep in task["dependencies"]:
            if task["start"] <= by_id[dep]["end"]:
                total += 1
                if len(warnings) < 50:
                    warnings.append(f"{task['id']} 开始日期未晚于依赖任务 {dep} 的结束日期；请核对搭接关系。")
    if total > 50:
        warnings.append(f"共有 {total} 项搭接提醒，先显示前 50 项。")
    return warnings


class ScheduleStore:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).absolute()
        self.root = self.workspace / ".civil-buddy" / "out" / "engineering" / "schedules"
        self.profile = SandboxProfile(allowed_write_roots=[self.workspace / ".civil-buddy" / "out"])

    def _path(self, ident=None):
        if ident is not None and (not isinstance(ident, str) or not PROJECT_ID.fullmatch(ident)):
            raise ValueError("计划编号无效。")
        path = self.root / f"{ident}.json" if ident else self.root
        for parent in (path, *path.parents):
            try:
                metadata = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError("计划存储路径不能包含链接或目录联接。")
        path.resolve().relative_to(self.workspace.resolve())
        return path

    def _writable(self):
        from packing_assistant.runtime.civil_config import load_config
        if load_config().sandbox == "read-only":
            raise PermissionError("当前工作台只读，不能保存或撤销计划。")
        assert_write(self._path() / "_index" / "projects.lock", profile=self.profile)
        check()

    def _read(self, ident):
        path = assert_open(self._path(ident), profile=self.profile)
        if not path.is_file():
            raise ScheduleNotFound("施工计划不存在。")
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("施工计划文件过大。")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or set(record) != {"schema", "id", "name", "tasks", "revision", "created_at", "updated_at", "history"}:
                raise ValueError("字段无效")
            if record["schema"] != SCHEMA or record["id"] != ident:
                raise ValueError("编号或格式无效")
            if type(record["revision"]) is not int or record["revision"] < 1:
                raise ValueError("修订号无效")
            _name(record["name"])
            validate_tasks(record["tasks"])
            for key in ("created_at", "updated_at"):
                datetime.fromisoformat(record[key])
            history = record["history"]
            if not isinstance(history, list) or len(history) > MAX_HISTORY:
                raise ValueError("历史无效")
            last = 0
            for row in history:
                if not isinstance(row, dict) or set(row) != {"name", "tasks", "revision", "updated_at"}:
                    raise ValueError("历史字段无效")
                if type(row["revision"]) is not int or not last < row["revision"] < record["revision"]:
                    raise ValueError("历史修订号无效")
                last = row["revision"]
                _name(row["name"])
                validate_tasks(row["tasks"])
                datetime.fromisoformat(row["updated_at"])
            return record
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            raise ValueError("施工计划记录损坏，未覆盖原文件。") from exc

    @staticmethod
    def _public(record):
        result = {key: deepcopy(value) for key, value in record.items() if key != "history"}
        result["versions"] = [{"revision": r["revision"], "updated_at": r["updated_at"], "task_count": len(r["tasks"])} for r in record["history"]]
        result["can_undo"] = bool(record["history"])
        result["warnings"] = task_warnings(record["tasks"])
        return result

    def list_projects(self):
        root = self._path()
        if not root.exists():
            return []
        result = []
        for file in root.glob("*.json"):
            if PROJECT_ID.fullmatch(file.stem):
                try:
                    record = self._read(file.stem)
                    result.append({k: record[k] for k in ("id", "name", "revision", "updated_at")} | {"task_count": len(record["tasks"])})
                except (ValueError, OSError, PermissionError) as exc:
                    result.append({"id": file.stem, "name": "无法读取的施工计划", "revision": 0, "updated_at": "", "task_count": 0, "error": str(exc)})
        return sorted(result, key=lambda r: r["updated_at"], reverse=True)

    def open(self, ident):
        return self._public(self._read(ident))

    def _write(self, record):
        from demo.projects import _write_atomic
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_BYTES:
            raise ValueError("施工计划及历史超过存储上限，请另存副本。")
        path = assert_write(self._path(record["id"]), profile=self.profile)
        _write_atomic(path, payload, before_replace=check)

    @staticmethod
    def _expected(record, revision):
        if type(revision) is not int or revision != record["revision"]:
            raise ScheduleConflict("计划已被其他页面修改，请重新打开后再操作；当前编辑仍保留在页面。")

    def save(self, *, name, tasks, project_id=None, expected_revision=None):
        from demo.projects import _mutation
        name, tasks = _name(name), validate_tasks(tasks)
        self._writable()
        with _mutation(self._path()):
            check()
            now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            if project_id is not None:
                record = self._read(project_id)
                self._expected(record, expected_revision)
                snapshot = {k: deepcopy(record[k]) for k in ("name", "tasks", "revision", "updated_at")}
                record["history"] = (record["history"] + [snapshot])[-MAX_HISTORY:]
                record["revision"] += 1
            else:
                if expected_revision is not None:
                    raise ValueError("新计划不能携带旧修订号。")
                if len(list(self.root.glob("*.json"))) >= MAX_PROJECTS:
                    raise ValueError("施工计划数量已达上限。")
                record = {"schema": SCHEMA, "id": uuid4().hex, "created_at": now, "revision": 1, "history": []}
            record.update(name=name, tasks=tasks, updated_at=now)
            self._write(record)
            return self._public(record)

    def undo(self, ident, expected_revision):
        from demo.projects import _mutation
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            if not record["history"]:
                raise ValueError("当前计划没有可撤销的已保存修改。")
            previous = record["history"].pop()
            record.update(name=previous["name"], tasks=previous["tasks"], revision=record["revision"] + 1,
                          updated_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
            self._write(record)
            return self._public(record)
