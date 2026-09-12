"""User-requested repair of derived task context, without model or tool runs."""
from __future__ import annotations

import json
from pathlib import Path

import context
import local_retrieval
import projects
import task_memory
import uploads
from packing_assistant.sandbox import assert_write
from packing_assistant.runtime.civil_config import load_config

_CACHE_NAMES = ("context.summary.json", "context.last.json", "semantic.summary.json",
                "semantic.attempt.json", "local-retrieval.sqlite3",
                "local-retrieval.sqlite3-wal", "local-retrieval.sqlite3-shm", "local-retrieval.sqlite3-journal")


def rebuild(root: Path, sid: str) -> dict:
    """Caller holds the same per-task lease used for chat and export.

    Validate all fixed cache paths and complete source input before changing
    derived files. No original transcript, attachment, slot, or run is written.
    A failed cache write can leave other derived caches refreshed; all can be
    rebuilt again, and errors never report a successful repair.
    """
    projects.safe_session_id(sid)
    if not load_config().allow_write():
        raise PermissionError("当前沙箱为只读模式")
    folder = projects._bounded_path(root, sid)
    if not folder.is_dir():
        raise FileNotFoundError("该任务尚无已保存的记录")
    paths = {}
    for name in _CACHE_NAMES:
        path = assert_write(projects._bounded_path(root, sid, name))
        if path.exists() and not path.is_file():
            raise ValueError(f"缓存位置 {name} 不是普通文件，无法自动重建；原始资料未改动")
        paths[name] = path
    history = projects.read_full_history(root, sid, strict=True)
    documents = uploads.strict_documents(sid)
    summary = task_memory.build(history)
    summary["session_id"] = sid
    raw = json.dumps(summary, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(raw.encode("utf-8")) > task_memory.MAX_FILE_BYTES:
        raise ValueError("任务记忆超过存储上限；完整原文未改动")
    indexed = local_retrieval.sync_session(root, sid, history, documents, rebuild=True)
    projects._write_atomic(paths["context.summary.json"], raw)
    # A running model turn cannot race this operation: the HTTP boundary holds
    # SessionLease. Late detached model responses have no persistence path.
    for name in ("semantic.summary.json", "semantic.attempt.json"):
        assert_write(projects._bounded_path(root, sid, name)).unlink(missing_ok=True)
    report = {**context.policy(), "used": 0, "pct": 0, "mode": "local", "compressed": False,
              "note": "任务记忆和本地搜索已重建；尚无新的模型请求。",
              "history_count": len(history), "indexed_history": len(history),
              "attachments_indexed": len(documents), "retrieved": 0, "memory_saved": True,
              "semantic": {"status": "reset", "model_calls": 0, "input_tokens": 0,
                  "output_reserve": 0, "output_tokens": 0, "covered_messages": 0,
                  "included": False, "note": "旧模型摘要已清除；本次整理没有调用模型。"}}
    projects._write_atomic(paths["context.last.json"], json.dumps(report, ensure_ascii=False))
    from session_context import detail
    return {"ok": True, **detail(root, sid),
            "note": "已重新整理任务记忆；原始对话、附件和交付物已保留，本次没有调用模型。",
            "rebuild": {"history_messages": len(history), "attachments": len(documents),
                "sources": indexed["sources"], "chunks": indexed["chunks"],
                "semantic_cleared": True, "model_calls": 0}}
