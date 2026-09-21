"""Atomic, versioned logistics ledgers; raw source bytes never follow user paths."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from packing_assistant.engineering.schedule import ScheduleStore, ScheduleConflict, ScheduleNotFound, PROJECT_ID, _name
from packing_assistant.runtime.cancel import check

SCHEMA = "civil.logistics.project.v1"
MAX_SOURCE = 8 * 1024 * 1024
MAX_RECORD = 48 * 1024 * 1024
MAX_HISTORY = 20


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def source_bytes(record):
    item = record["source_file"]
    if not isinstance(item, dict) or set(item) != {"data", "sha256", "bytes"} or type(item["bytes"]) is not int or not 0 < item["bytes"] <= MAX_SOURCE:
        raise ValueError("原件记录无效。")
    if not isinstance(item["data"], str) or len(item["data"]) > 4 * ((MAX_SOURCE + 2) // 3):
        raise ValueError("原件编码超限。")
    try:
        data = base64.b64decode(item["data"], validate=True)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("原件编码损坏。") from exc
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("原件 SHA-256 或大小不符。")
    return data


def validate_record(record):
    from .ledger import validate_document
    required = {"schema", "id", "name", "revision", "document", "confirmation", "created_at", "updated_at", "history", "source_file"}
    if (not isinstance(record, dict) or set(record) not in (required, required | {"undo_stack"})
            or record["schema"] != SCHEMA or not isinstance(record["id"], str) or not PROJECT_ID.fullmatch(record["id"])):
        raise ValueError("台账记录结构无效。")
    source_bytes(record)
    if not isinstance(record["history"], list) or len(record["history"]) > MAX_HISTORY:
        raise ValueError("历史数量无效。")
    last = 0
    for item in [*record["history"], record]:
        check()
        if item is not record and set(item) != {"name", "revision", "document", "updated_at"}:
            raise ValueError("历史字段无效。")
        _name(item["name"])
        if type(item["revision"]) is not int or not last < item["revision"]:
            raise ValueError("历史修订号无效。")
        last = item["revision"]
        datetime.fromisoformat(item["updated_at"])
        doc = validate_document(item["document"])
        if doc["source"]["sha256"] != record["source_file"]["sha256"] or doc["source"]["bytes"] != record["source_file"]["bytes"]:
            raise ValueError("台账与原件摘要不一致。")
    datetime.fromisoformat(record["created_at"])
    # Old v1 records used history itself as the undo stack and removed snapshots
    # on undo. Migrate only the snapshots still present; deleted ones cannot be
    # reconstructed from a later document.
    history_revisions = {item["revision"] for item in record["history"]}
    undo_stack = record.get("undo_stack", [item["revision"] for item in record["history"]])
    if not isinstance(undo_stack, list) or len(undo_stack) > MAX_HISTORY:
        raise ValueError("撤销修订栈无效。")
    previous_revision = 0
    for revision in undo_stack:
        if type(revision) is not int or revision <= previous_revision or revision not in history_revisions:
            raise ValueError("撤销目标必须按顺序引用保留的历史修订。")
        previous_revision = revision
    confirmation = record["confirmation"]
    if confirmation is not None and (not isinstance(confirmation, dict) or set(confirmation) != {"revision", "digest", "at"}
                                    or confirmation["revision"] != record["revision"] or confirmation["digest"] != digest(record["document"])):
        raise ValueError("台账确认记录不对应当前版本。")
    normalized = deepcopy(record)
    normalized["undo_stack"] = deepcopy(undo_stack)
    return normalized


class LogisticsStore(ScheduleStore):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.root = self.workspace / ".civil-buddy" / "out" / "logistics" / "projects"

    def _read(self, ident):
        from packing_assistant.sandbox import assert_open
        path = assert_open(self._path(ident), profile=self.profile)
        if not path.is_file():
            raise ScheduleNotFound("箱单项目不存在。")
        if path.stat().st_size > MAX_RECORD:
            raise ValueError("箱单项目记录超限。")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            checksum = record.pop("checksum")
            if checksum != digest(record) or record.get("id") != ident:
                raise ValueError("摘要不符")
            return validate_record(record)
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
            raise ValueError("箱单项目记录损坏；未覆盖原记录。") from exc

    def _write(self, record):
        from demo.projects import _write_atomic
        from packing_assistant.sandbox import assert_write
        record = validate_record(record)
        payload = json.dumps(dict(record, checksum=digest(record)), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(payload.encode()) > MAX_RECORD:
            raise ValueError("台账与历史超过 48 MiB，旧记录未覆盖。")
        _write_atomic(assert_write(self._path(record["id"]), profile=self.profile), payload, before_replace=check)

    @staticmethod
    def _public(record):
        from .ledger import audit_document, summarize
        result = {k: deepcopy(v) for k, v in record.items() if k not in {"history", "source_file", "confirmation", "undo_stack"}}
        result.update(confirmed=bool(record["confirmation"]), audit=audit_document(record["document"]), summary=summarize(record["document"]),
                      versions=[{k: item[k] for k in ("revision", "updated_at")} for item in record["history"]],
                      can_undo=bool(record["undo_stack"]), undo_target_revision=record["undo_stack"][-1] if record["undo_stack"] else None)
        return result

    @staticmethod
    def _retain_current(record):
        """History is an audit trail; its independent undo cursor never erases it."""
        snapshot = {k: deepcopy(record[k]) for k in ("name", "revision", "document", "updated_at")}
        record["history"] = (record["history"] + [snapshot])[-MAX_HISTORY:]
        retained = {item["revision"] for item in record["history"]}
        record["undo_stack"] = [revision for revision in record["undo_stack"] if revision in retained]

    def list_projects(self):
        rows = []
        for path in self._path().glob("*.json"):
            if not PROJECT_ID.fullmatch(path.stem):
                continue
            try:
                item = self._read(path.stem)
                rows.append({k: item[k] for k in ("id", "name", "revision", "updated_at")} | {"row_count": len(item["document"]["rows"]), "confirmed": bool(item["confirmation"])})
            except (ValueError, OSError, PermissionError) as exc:
                rows.append({"id": path.stem, "name": "无法读取的箱单", "revision": 0, "updated_at": "", "error": str(exc)})
        return sorted(rows, key=lambda r: r["updated_at"], reverse=True)

    def open(self, ident, version=None):
        record = self._read(ident)
        if version is not None and version != record["revision"]:
            item = next((h for h in record["history"] if h["revision"] == version), None)
            if not item:
                raise ScheduleNotFound("该历史版本已不存在。")
            record.update(deepcopy(item), confirmation=None)
            record["history"] = [h for h in record["history"] if h["revision"] < version]
            # Historical versions are read-only views, not a branch for undo.
            record["undo_stack"] = []
        return self._public(record)

    def source(self, ident):
        record = self._read(ident)
        return source_bytes(record), record["document"]["source"]["filename"]

    def create(self, name, document, data):
        from .ledger import validate_document
        doc = validate_document(document)
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SOURCE:
            raise ValueError("原件须为 1–8 MiB 内的有效文件。")
        if doc["source"]["sha256"] != hashlib.sha256(data).hexdigest() or doc["source"]["bytes"] != len(data):
            raise ValueError("原件与提取结果不匹配。")
        now = datetime.now(timezone.utc).isoformat()
        record = {"schema": SCHEMA, "id": uuid4().hex, "name": _name(name), "revision": 1, "document": doc,
                  "confirmation": None, "created_at": now, "updated_at": now, "history": [], "undo_stack": [],
                  "source_file": {"sha256": doc["source"]["sha256"], "bytes": len(data), "data": base64.b64encode(data).decode()}}
        return self.import_record(record, fresh=False)

    def import_record(self, record, fresh=True):
        from demo.projects import _mutation
        record = validate_record(record)
        self._writable()
        with _mutation(self._path()):
            if len(list(self.root.glob("*.json"))) >= 500:
                raise ValueError("箱单项目数量已达上限。")
            if fresh:
                record["id"] = uuid4().hex
                record["confirmation"] = None
                record["created_at"] = record["updated_at"] = datetime.now(timezone.utc).isoformat()
            public = self._public(record)
            self._write(record)
            return public

    def revise(self, ident, expected_revision, document, *, expected_digest=None):
        from .ledger import validate_document
        from demo.projects import _mutation
        doc = validate_document(document)
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            if expected_digest is not None and digest(record["document"]) != expected_digest:
                raise ScheduleConflict("修订建议属于旧台账，请重新检查。")
            record["undo_stack"].append(record["revision"])
            self._retain_current(record)
            record.update(document=doc, confirmation=None, revision=record["revision"] + 1, updated_at=datetime.now(timezone.utc).isoformat())
            public = self._public(record)
            self._write(record)
            return public

    def confirm(self, ident, expected_revision):
        from demo.projects import _mutation
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            # Confirmation acknowledges this exact ledger; completeness is checked separately at packing.
            record["confirmation"] = {"revision": record["revision"], "digest": digest(record["document"]), "at": datetime.now(timezone.utc).isoformat()}
            public = self._public(record)
            self._write(record)
            return public

    def undo(self, ident, expected_revision):
        from demo.projects import _mutation
        self._writable()
        with _mutation(self._path()):
            record = self._read(ident)
            self._expected(record, expected_revision)
            if not record["undo_stack"]:
                raise ValueError("没有可撤销的台账修订。")
            target = record["undo_stack"].pop()
            previous = next(item for item in record["history"] if item["revision"] == target)
            self._retain_current(record)
            record.update(name=previous["name"], document=deepcopy(previous["document"]), confirmation=None,
                          revision=record["revision"] + 1, updated_at=datetime.now(timezone.utc).isoformat())
            public = self._public(record)
            self._write(record)
            return public
