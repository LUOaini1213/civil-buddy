"""Codex-app threads: one session per thread, parallel across threads.

Admission is serial per thread, including queued background turns. /new and /bg
get a new session_id. Thread snapshots are replaced atomically on disk.
"""

from __future__ import annotations

import json
import math
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path, PureWindowsPath
from threading import Lock
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "demo" / "out" / "_threads"
_LOCK = Lock()
_POOL: Optional[ThreadPoolExecutor] = None
_ACTIVE: Set[str] = set()


@dataclass
class CivilThread:
    thread_id: str
    session_id: str
    title: str = ""
    skill: str = ""
    state: str = "idle"
    confirm: bool = False
    last_text: str = ""
    last_reply: str = ""
    hitl_pending: bool = False
    wrote: bool = False
    artifacts: List[str] = field(default_factory=list)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        from packing_assistant.runtime.civil_config import load_config

        n = load_config().max_parallel
        _POOL = ThreadPoolExecutor(max_workers=n, thread_name_prefix="civil-th")
    return _POOL


def _path(thread_id: str) -> Path:
    if not isinstance(thread_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", thread_id):
        raise ValueError("invalid thread id")
    if PureWindowsPath(f"{thread_id}.json").is_reserved():
        raise ValueError("invalid thread id")
    return _DIR / f"{thread_id}.json"


def save_thread(th: CivilThread) -> None:
    path = _path(th.thread_id)
    _DIR.mkdir(parents=True, exist_ok=True)
    th.updated_at = time.time()
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=_DIR, prefix=f".{th.thread_id}-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(th.to_dict(), stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_thread(thread_id: str) -> Optional[CivilThread]:
    try:
        p = _path(thread_id)
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(raw, dict) or raw.get("thread_id") != thread_id:
        return None
    if any(key in raw and not isinstance(raw[key], bool) for key in ("confirm", "hitl_pending", "wrote")):
        return None
    artifacts = raw.get("artifacts") or []
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        return None
    try:
        created_at = float(raw.get("created_at") or 0)
        updated_at = float(raw.get("updated_at") or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(created_at) or not math.isfinite(updated_at):
        return None
    return CivilThread(
        thread_id=thread_id,
        session_id=str(raw.get("session_id") or thread_id),
        title=str(raw.get("title") or ""),
        skill=str(raw.get("skill") or ""),
        state=str(raw.get("state") or "idle"),
        confirm=bool(raw.get("confirm")),
        last_text=str(raw.get("last_text") or ""),
        last_reply=str(raw.get("last_reply") or ""),
        hitl_pending=bool(raw.get("hitl_pending")),
        wrote=bool(raw.get("wrote")),
        artifacts=artifacts,
        error=str(raw.get("error") or ""),
        created_at=created_at,
        updated_at=updated_at,
    )


def list_threads() -> List[CivilThread]:
    if not _DIR.is_dir():
        return []
    out: List[CivilThread] = []
    for p in _DIR.glob("*.json"):
        th = load_thread(p.stem)
        if th:
            out.append(th)
    out.sort(key=lambda th: th.updated_at, reverse=True)
    return out


def new_thread(title: str = "", *, confirm: bool = False) -> CivilThread:
    tid = f"t-{uuid4().hex[:8]}"
    th = CivilThread(
        thread_id=tid,
        session_id=tid,
        title=(title or "新对话").strip()[:80],
        confirm=confirm is True,
    )
    save_thread(th)
    return th


def _failed(th: CivilThread, exc: Exception, *, code: str) -> Dict[str, Any]:
    th.state = "failed"
    th.error = str(exc)
    th.last_reply = str(exc)
    result = {"ok": False, "error": str(exc), "reply": str(exc), "error_code": code, "thread_id": th.thread_id}
    try:
        save_thread(th)
    except OSError as storage_error:
        result["storage_error"] = str(storage_error)
    return result


def _run_on_thread(th: CivilThread, text: str, *, skill: str, confirm: bool) -> Dict[str, Any]:
    try:
        from packing_assistant.runtime.agent_loop import run_agent

        out = run_agent(
            text,
            session_id=th.session_id,
            expert_id=skill,
            p0_confirmed=confirm is True or th.confirm is True,
        )
        th.skill = str(out.get("skill") or out.get("expert_id") or th.skill)
        th.last_reply = str(out.get("reply") or "")
        th.hitl_pending = bool(out.get("hitl_pending"))
        th.wrote = bool(out.get("wrote"))
        arts = out.get("artifacts") or out.get("files") or []
        th.artifacts = [str(a) for a in arts]
        th.state = "waiting_hitl" if th.hitl_pending else ("done" if out.get("ok") else "failed")
        th.error = str(out.get("error") or out.get("error_code") or "")
        save_thread(th)
        return {**out, "thread_id": th.thread_id}
    except Exception as exc:  # noqa: BLE001
        return _failed(th, exc, code="thread_execution_failed")
    finally:
        with _LOCK:
            _ACTIVE.discard(th.thread_id)


def run_on_thread(
    thread_id: str,
    text: str,
    *,
    skill: str = "",
    confirm: bool = False,
    background: bool = False,
) -> Dict[str, Any]:
    with _LOCK:
        th = load_thread(thread_id)
        if th is None:
            return {"ok": False, "error": "unknown thread", "error_code": "unknown_thread", "thread_id": thread_id}
        if thread_id in _ACTIVE:
            return {"ok": False, "error": "thread is busy", "error_code": "thread_busy", "thread_id": thread_id}
        _ACTIVE.add(thread_id)
        th.state = "running"
        th.last_text = text
        th.last_reply = ""
        th.hitl_pending = False
        th.wrote = False
        th.artifacts = []
        th.error = ""
        if not th.title or th.title == "新对话":
            th.title = (text or "").replace("\n", " ")[:40] or th.title
        try:
            save_thread(th)
            if background:
                _pool().submit(_run_on_thread, th, text, skill=skill, confirm=confirm)
        except Exception as exc:  # noqa: BLE001
            _ACTIVE.discard(thread_id)
            return _failed(th, exc, code="thread_start_failed")
        if background:
            return {"ok": True, "background": True, "thread_id": thread_id, "state": "running"}
    return _run_on_thread(th, text, skill=skill, confirm=confirm)


def spawn(text: str, *, skill: str = "", confirm: bool = False, title: str = "") -> Dict[str, Any]:
    th = new_thread(title or text, confirm=confirm)
    return run_on_thread(th.thread_id, text, skill=skill, confirm=confirm, background=True)


def thread_status(thread_id: str) -> Dict[str, Any]:
    with _LOCK:
        th = load_thread(thread_id)
        if not th:
            return {"ok": False, "error": "unknown thread", "error_code": "unknown_thread", "thread_id": thread_id}
        running = thread_id in _ACTIVE
    if running:
        th.state = "running"
    return {"ok": True, **th.to_dict(), "running": running}
