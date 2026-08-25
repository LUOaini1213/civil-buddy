"""Codex-app threads: one session per thread, parallel across threads.

Same session stays serial (Scheduler lock). /new and /bg get a new session_id.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "demo" / "out" / "_threads"
_LOCK = Lock()
_POOL: Optional[ThreadPoolExecutor] = None
_FUTS: Dict[str, Future] = {}


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
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (thread_id or ""))[:40]
    return _DIR / f"{safe or 't'}.json"


def save_thread(th: CivilThread) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    th.updated_at = time.time()
    _path(th.thread_id).write_text(json.dumps(th.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_thread(thread_id: str) -> Optional[CivilThread]:
    p = _path(thread_id)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return CivilThread(
        thread_id=str(raw.get("thread_id") or thread_id),
        session_id=str(raw.get("session_id") or thread_id),
        title=str(raw.get("title") or ""),
        skill=str(raw.get("skill") or ""),
        state=str(raw.get("state") or "idle"),
        confirm=bool(raw.get("confirm")),
        last_text=str(raw.get("last_text") or ""),
        last_reply=str(raw.get("last_reply") or ""),
        hitl_pending=bool(raw.get("hitl_pending")),
        wrote=bool(raw.get("wrote")),
        artifacts=list(raw.get("artifacts") or []),
        error=str(raw.get("error") or ""),
        created_at=float(raw.get("created_at") or 0),
        updated_at=float(raw.get("updated_at") or 0),
    )


def list_threads() -> List[CivilThread]:
    if not _DIR.is_dir():
        return []
    out: List[CivilThread] = []
    for p in sorted(_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        th = load_thread(p.stem)
        if th:
            out.append(th)
    return out


def new_thread(title: str = "", *, confirm: bool = False) -> CivilThread:
    tid = f"t-{uuid4().hex[:8]}"
    th = CivilThread(
        thread_id=tid,
        session_id=tid,
        title=(title or "新对话").strip()[:80],
        confirm=confirm,
    )
    save_thread(th)
    return th


def _run_on_thread(thread_id: str, text: str, *, skill: str, confirm: bool) -> Dict[str, Any]:
    from packing_assistant.runtime.agent_loop import run_agent

    th = load_thread(thread_id) or new_thread()
    th.state = "running"
    th.last_text = text
    if not th.title or th.title == "新对话":
        th.title = (text or "").replace("\n", " ")[:40] or th.title
    save_thread(th)
    try:
        out = run_agent(
            text,
            session_id=th.session_id,
            expert_id=skill,
            p0_confirmed=confirm or th.confirm,
        )
    except Exception as exc:  # noqa: BLE001
        th.state = "failed"
        th.error = str(exc)
        th.last_reply = str(exc)
        save_thread(th)
        return {"ok": False, "error": str(exc), "thread_id": thread_id}
    th.skill = str(out.get("skill") or out.get("expert_id") or th.skill)
    th.last_reply = str(out.get("reply") or "")
    th.hitl_pending = bool(out.get("hitl_pending"))
    th.wrote = bool(out.get("wrote"))
    arts = out.get("artifacts") or out.get("files") or []
    th.artifacts = [str(a) for a in arts]
    th.state = "waiting_hitl" if th.hitl_pending else ("done" if out.get("ok") else "failed")
    th.error = str(out.get("error") or out.get("error_code") or "")
    save_thread(th)
    out = dict(out)
    out["thread_id"] = thread_id
    return out


def run_on_thread(
    thread_id: str,
    text: str,
    *,
    skill: str = "",
    confirm: bool = False,
    background: bool = False,
) -> Dict[str, Any]:
    if background:
        with _LOCK:
            fut = _pool().submit(_run_on_thread, thread_id, text, skill=skill, confirm=confirm)
            _FUTS[thread_id] = fut
        return {
            "ok": True,
            "background": True,
            "thread_id": thread_id,
            "state": "running",
        }
    return _run_on_thread(thread_id, text, skill=skill, confirm=confirm)


def spawn(text: str, *, skill: str = "", confirm: bool = False, title: str = "") -> Dict[str, Any]:
    th = new_thread(title or text, confirm=confirm)
    return run_on_thread(th.thread_id, text, skill=skill, confirm=confirm, background=True)


def thread_status(thread_id: str) -> Dict[str, Any]:
    th = load_thread(thread_id)
    if not th:
        return {"ok": False, "error": "unknown thread"}
    fut = _FUTS.get(thread_id)
    running = bool(fut and not fut.done())
    if running:
        th.state = "running"
    return {"ok": True, **th.to_dict(), "running": running}
