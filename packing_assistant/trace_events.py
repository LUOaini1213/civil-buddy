"""结构化 trace 事件：output/runs/<run_id>/trace.jsonl（可回放）。

data(round2) 起改为 storage 薄壳：CB_STORAGE 三态分派（packing_assistant/storage.py）。
  json/dual：JSONL 文件照写（dual 另写 SQLite，失败仅告警）
  sqlite：优先写 events 表，失败落 JSONL；读取/导出合并两者，保留失败期间的事件
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Dict, Optional

from packing_assistant.config import HARNESS_VERSION, TRACE_DIR
from packing_assistant import storage as _storage

logger = logging.getLogger("civil.trace_events")

RUNS_DIR = Path(TRACE_DIR).resolve().parent / "runs"
# Serialize snapshot replacement with fallback appends in this process.
_TRACE_LOCK = RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# A run whose events were never recorded gets a labelled summary of its agent
# steps instead. Real events supersede it (see _merge_events).
STEP_SUMMARY_SOURCE = "agent_steps_snapshot"
_SUMMARY_SOURCES = frozenset({STEP_SUMMARY_SOURCE, "step_summary"})


def run_trace_path(run_id: str, *, create: bool = False) -> Path:
    """Where a run's JSONL trace lives. Only writers create the directory:
    looking up a run that never existed must not leave an empty folder behind."""
    d = RUNS_DIR / str(run_id)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d / "trace.jsonl"


def normalize_event(run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """AG-UI / agents-observe 风格轻量信封（兼容旧字段）。

    标准字段: type, run_id, node, parent_node, status, duration_ms, ts, t_ms, seq, harness_version
    """
    ev = dict(event)
    ev.setdefault("ts", _now_iso())
    ev.setdefault("t_ms", int(time.time() * 1000))
    ev.setdefault("run_id", str(run_id))
    ev.setdefault("harness_version", HARNESS_VERSION)
    # 别名：agent_id ↔ node
    if ev.get("node") and not ev.get("agent_id"):
        ev["agent_id"] = ev["node"]
    if ev.get("agent_id") and not ev.get("node"):
        ev["node"] = ev["agent_id"]
    # parent 链（orchestrator 为根时可无）
    ev.setdefault("parent_node", ev.get("parent") or None)
    # status 默认
    t = ev.get("type")
    if t in ("agent_start", "tool_start", "run_start"):
        ev.setdefault("status", "running")
    elif t in ("agent_end", "tool_end", "done"):
        ev.setdefault("status", "ok")
    elif t == "hitl":
        ev.setdefault("status", "wait")
    elif t == "replan":
        ev.setdefault("status", "replan")
    # duration_ms 键始终存在（可为 None）便于消费方
    if "duration_ms" not in ev:
        ev["duration_ms"] = None
    # 协议版本（便于前端/回放器演进）
    ev.setdefault("schema", "packing.stream.v1")
    return ev


def append_trace_event(
    run_id: str,
    event: Dict[str, Any],
    *,
    also_global: bool = True,
) -> Dict[str, Any]:
    """追加一行 JSONL（json/dual）或写 events 表（sqlite），返回规范化事件。"""
    with _TRACE_LOCK:
        return _append_trace_event(run_id, event, also_global=also_global)


def _append_trace_event(run_id: str, event: Dict[str, Any], *, also_global: bool) -> Dict[str, Any]:
    ev = normalize_event(run_id, event)
    mode = _storage.storage_mode()

    if mode == "sqlite":
        try:
            st = _storage.get_storage()
            if ev.get("type") == "run_start":
                st.ensure_run(
                    {
                        "run_id": str(run_id),
                        "session_id": ev.get("session_id"),
                        "started_at": ev.get("ts"),
                        "phase": ev.get("phase"),
                        "container_type": ev.get("container_type"),
                        "run_dir": str(RUNS_DIR / str(run_id)),
                    }
                )
            st.insert_event(ev)
        except Exception:
            logger.warning("sqlite insert_event failed, fallback to JSONL", exc_info=True)
        else:
            # A downloadable trace is a snapshot of the authoritative event
            # store. Finalization can precede the terminal event, so refresh an
            # existing export once that event has also been committed.
            try:
                if ev.get("type") == "done" and run_trace_path(run_id).exists():
                    export_trace_jsonl(run_id)
            except Exception:
                # The event is already committed. An export failure must not be
                # misreported as an insert failure or append a second done.
                logger.warning("trace snapshot refresh failed; SQLite event is committed", exc_info=True)
            return ev

    line = json.dumps(ev, ensure_ascii=False, default=str) + "\n"
    path = run_trace_path(run_id, create=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    if also_global:
        g = Path(TRACE_DIR)
        g.mkdir(parents=True, exist_ok=True)
        with (g / "stream.jsonl").open("a", encoding="utf-8") as f:
            f.write(line)

    if mode == "dual":
        try:
            st = _storage.get_storage()
            if ev.get("type") == "run_start":
                st.ensure_run(
                    {
                        "run_id": str(run_id),
                        "session_id": ev.get("session_id"),
                        "started_at": ev.get("ts"),
                        "phase": ev.get("phase"),
                        "container_type": ev.get("container_type"),
                        "run_dir": str(RUNS_DIR / str(run_id)),
                    }
                )
            st.insert_event(ev)
        except Exception:
            logger.warning("dual write of trace event to sqlite failed (non-blocking)", exc_info=True)
    return ev


def _step_summary(run_id: str, steps: Optional[list]) -> list:
    """One labelled agent_end event per pipeline step, for a run with no recorded events."""
    events = []
    for i, step in enumerate(steps or []):
        if not isinstance(step, dict):
            continue
        events.append(normalize_event(run_id, {
            "type": "agent_end",
            "seq": i + 1,
            "run_id": str(run_id),
            "node": step.get("node"),
            "step": step,
            "source": STEP_SUMMARY_SOURCE,
        }))
    return events


def export_trace_jsonl(run_id: str, *, steps: Optional[list] = None) -> Optional[Path]:
    """Atomically export SQLite plus real JSONL fallback events.

    ``steps`` (the pipeline's agent_steps) is written as a labelled summary only
    when the run recorded no events at all, so a summary never stands in for
    real events. An unavailable DB must not replace a complete snapshot with a
    partial file: the failure is logged and raised, the old file is preserved,
    and the caller can retry.
    """
    with _TRACE_LOCK:
        rows = _read_trace(run_id, limit=10**9, strict_sqlite=True)
        if not rows:
            rows = _step_summary(run_id, steps)
        if not rows:
            return None
        target = run_trace_path(run_id, create=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                    prefix=".trace-", suffix=".jsonl.tmp", delete=False) as f:
                temporary = Path(f.name)
                for ev in rows:
                    f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target


def _event_time(event: dict) -> Optional[float]:
    value = event.get("t_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        stamp = datetime.fromisoformat(str(event.get("ts", "")).replace("Z", "+00:00"))
        return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).timestamp() * 1000
    except (ValueError, OverflowError):
        return None


def _merge_events(primary: list, fallback: list) -> list:
    """SQLite wins duplicate (run_id, integer seq) identities.

    Legacy events without seq keep their full payload and occurrence count:
    identical events in a snapshot are copies, but repeated events inside one
    source may be real repetitions. Use the larger per-source occurrence count.
    Timestamped legacy events are placed among numbered events where possible;
    events with neither seq nor time retain source order at the end.
    """
    primary = [ev for ev in primary if isinstance(ev, dict)]
    fallback = [ev for ev in fallback if isinstance(ev, dict)]
    if any(ev.get("source") not in _SUMMARY_SOURCES for ev in primary + fallback):
        primary = [ev for ev in primary if ev.get("source") not in _SUMMARY_SOURCES]
        fallback = [ev for ev in fallback if ev.get("source") not in _SUMMARY_SOURCES]
    numbered, legacy = {}, []
    primary_counts, fallback_counts = Counter(), Counter()
    for source, rows in enumerate((primary, fallback)):
        for ev in rows:
            seq = ev.get("seq")
            if isinstance(seq, int) and not isinstance(seq, bool):
                numbered.setdefault((ev.get("run_id"), seq), ev)
                continue
            identity = json.dumps(ev, ensure_ascii=False, sort_keys=True, default=str)
            if source == 0:
                primary_counts[identity] += 1
            else:
                fallback_counts[identity] += 1
                if fallback_counts[identity] <= primary_counts[identity]:
                    continue
            legacy.append(ev)
    result = sorted(numbered.values(), key=lambda ev: ev["seq"])
    # Preserve normal sequence order even if wall-clock timestamps moved back.
    for ev in sorted(legacy, key=lambda ev: (_event_time(ev) is None, _event_time(ev) or 0)):
        stamp = _event_time(ev)
        before = next((i for i, current in enumerate(result)
                       if stamp is not None and _event_time(current) is not None
                       and _event_time(current) > stamp), len(result))
        result.insert(before, ev)
    return result


def read_trace_jsonl(run_id: str, *, limit: int = 5000) -> list:
    with _TRACE_LOCK:
        return _read_trace(run_id, limit=limit)


def _read_trace(run_id: str, *, limit: int, strict_sqlite: bool = False) -> list:
    limit = max(1, int(limit))
    primary = []
    if _storage.storage_mode() == "sqlite":
        try:
            primary = _storage.get_storage().read_trace_events(run_id, limit=limit)
        except Exception:
            if strict_sqlite:
                logger.warning("sqlite read_trace_events failed; the existing export is kept", exc_info=True)
                raise
            logger.warning("sqlite read_trace_events failed, fallback to JSONL", exc_info=True)
    path = run_trace_path(run_id)
    if not path.exists():
        return _merge_events(primary, [])[:limit]
    out = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    if _storage.storage_mode() == "sqlite":
        return _merge_events(primary, out)[:limit]
    return out


def list_runs(*, limit: int = 50) -> list:
    """最近 run 列表（sqlite 模式 SQL 直查；json/dual 扫 output/runs）。"""
    if _storage.storage_mode() == "sqlite":
        try:
            items = _storage.get_storage().list_runs(limit=limit)
            if items:
                return items
        except Exception:
            logger.warning("sqlite list_runs failed, fallback to scan", exc_info=True)
    if not RUNS_DIR.exists():
        return []
    items = []
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        idx = d / "index.json"
        meta: Dict[str, Any] = {"run_id": d.name, "run_dir": str(d)}
        if idx.exists():
            try:
                meta.update(json.loads(idx.read_text(encoding="utf-8")))
            except Exception:
                pass
        meta["has_trace_jsonl"] = (d / "trace.jsonl").exists()
        meta["mtime"] = datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="seconds")
        items.append(meta)
        if len(items) >= limit:
            break
    return items
