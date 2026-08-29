"""结构化 trace 事件：output/runs/<run_id>/trace.jsonl（可回放）。

data(round2) 起改为 storage 薄壳：CB_STORAGE 三态分派（packing_assistant/storage.py）。
  json/dual：JSONL 文件照写（dual 另写 SQLite，失败仅告警）
  sqlite：只写 events 表；读优先 SQLite、无则回退 JSONL 文件（旧数据可读）
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from packing_assistant.config import HARNESS_VERSION, TRACE_DIR
from packing_assistant import storage as _storage

logger = logging.getLogger("civil.trace_events")

RUNS_DIR = Path(TRACE_DIR).resolve().parent / "runs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_trace_path(run_id: str) -> Path:
    d = RUNS_DIR / str(run_id)
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
            return ev
        except Exception:
            logger.warning("sqlite insert_event failed, fallback to JSONL", exc_info=True)

    line = json.dumps(ev, ensure_ascii=False, default=str) + "\n"
    path = run_trace_path(run_id)
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


def read_trace_jsonl(run_id: str, *, limit: int = 5000) -> list:
    if _storage.storage_mode() == "sqlite":
        try:
            rows = _storage.get_storage().read_trace_events(run_id, limit=limit)
            if rows:
                return rows
        except Exception:
            logger.warning("sqlite read_trace_events failed, fallback to JSONL", exc_info=True)
    path = run_trace_path(run_id)
    if not path.exists():
        return []
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
