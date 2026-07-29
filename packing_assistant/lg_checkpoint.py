"""LangGraph 持久化 checkpointer（Sqlite · 断进程可 resume）。

环境变量:
  PACKING_LG_CHECKPOINT=1     启用（默认 1）
  PACKING_LG_CHECKPOINT_PATH  sqlite 路径（默认 output/langgraph_checkpoints.db）

用法:
  app = create_team_a_app(checkpointer=get_checkpointer())
  app.invoke(state, config=thread_config(session_id))
  snap = get_thread_state(session_id)  # 重启后读取
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from packing_assistant.config import TRACE_DIR

_LOCK = threading.Lock()
_SAVER = None
_CONN = None


def checkpoint_enabled() -> bool:
    v = (os.getenv("PACKING_LG_CHECKPOINT") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def checkpoint_db_path() -> Path:
    raw = (os.getenv("PACKING_LG_CHECKPOINT_PATH") or "").strip()
    if raw:
        return Path(raw)
    return Path(TRACE_DIR).resolve().parent / "langgraph_checkpoints.db"


def get_checkpointer():
    """单例 SqliteSaver；不可用或关闭时返回 None。"""
    global _SAVER, _CONN
    if not checkpoint_enabled():
        return None
    with _LOCK:
        if _SAVER is not None:
            return _SAVER
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except Exception:
            try:
                from langgraph.checkpoint.memory import MemorySaver

                _SAVER = MemorySaver()
                return _SAVER
            except Exception:
                return None
        path = checkpoint_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # SqliteSaver 需要保持连接存活
        _CONN = sqlite3.connect(str(path), check_same_thread=False)
        _SAVER = SqliteSaver(_CONN)
        return _SAVER


def thread_config(thread_id: str, *, checkpoint_ns: str = "") -> Dict[str, Any]:
    tid = str(thread_id or "default")
    cfg: Dict[str, Any] = {"configurable": {"thread_id": tid}}
    if checkpoint_ns:
        cfg["configurable"]["checkpoint_ns"] = checkpoint_ns
    return cfg


def invoke_with_checkpoint(app: Any, state: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
    """invoke 并写入 LangGraph checkpoint。"""
    cp = get_checkpointer()
    config = thread_config(thread_id)
    if cp is None:
        return app.invoke(state)
    # app 应已 compile(checkpointer=cp)；若未带，退回无 checkpoint
    try:
        return app.invoke(state, config=config)
    except TypeError:
        return app.invoke(state)
    except Exception:
        # checkpoint 失败不阻断业务
        return app.invoke(state)


def get_thread_state(thread_id: str, app: Any = None) -> Optional[Dict[str, Any]]:
    """从 checkpointer 取最新 values（需传入已 compile 的 app）。"""
    cp = get_checkpointer()
    if cp is None or app is None:
        return None
    try:
        snap = app.get_state(thread_config(thread_id))
        if snap is None:
            return None
        values = getattr(snap, "values", None) or (snap.get("values") if isinstance(snap, dict) else None)
        if isinstance(values, dict) and values:
            return dict(values)
    except Exception:
        return None
    return None


def list_thread_ids(*, limit: int = 50) -> list:
    """尽力列出 sqlite 中的 thread（失败则空）。"""
    path = checkpoint_db_path()
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(str(path))
        cur = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY rowid DESC LIMIT ?",
            (int(limit),),
        )
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []
