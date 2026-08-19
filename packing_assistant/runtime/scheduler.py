"""Run scheduler: legal edges, max_steps, cancel. Same session stays serial in-process."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional  # Run.messages/tools keep mixed payloads
from uuid import uuid4

STATES = (
    "pending",
    "planning",
    "acting",
    "waiting_tool",
    "waiting_hitl",
    "reflecting",
    "done",
    "failed",
    "cancelled",
)
TERMINAL = frozenset({"done", "failed", "cancelled"})
LEGAL = {
    ("pending", "planning"),
    ("planning", "acting"),
    ("planning", "waiting_hitl"),
    ("planning", "done"),  # chat: explain only
    ("waiting_hitl", "acting"),
    ("acting", "waiting_tool"),
    ("waiting_tool", "acting"),
    ("waiting_tool", "reflecting"),
    ("acting", "reflecting"),
    ("reflecting", "acting"),
    ("reflecting", "done"),
    ("acting", "done"),
}
FORBIDDEN = {("done", "acting")}
for _s in STATES:
    if _s not in TERMINAL:
        LEGAL.add((_s, "cancelled"))
        LEGAL.add((_s, "failed"))


@dataclass
class Run:
    run_id: str
    session_id: str
    expert_id: str = ""
    intent: str = "chat"
    state: str = "pending"
    steps: int = 0
    max_steps: int = 8
    cancelled: bool = False
    history: List[Dict[str, str]] = field(default_factory=list)
    error_code: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    duration_ms: int = 0

    def stamp_end(self) -> None:
        self.ended_at = time.time()
        self.duration_ms = max(0, int((self.ended_at - self.started_at) * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "expert_id": self.expert_id,
            "intent": self.intent,
            "state": self.state,
            "steps": self.steps,
            "max_steps": self.max_steps,
            "cancelled": self.cancelled,
            "error_code": self.error_code,
            "history": list(self.history),
            "messages": list(self.messages),
            "tools_used": list(self.tools_used),
            "artifacts": list(self.artifacts),
            "duration_ms": self.duration_ms,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


class Scheduler:
    def __init__(self) -> None:
        self._runs: Dict[str, Run] = {}
        self._locks: Dict[str, bool] = {}

    def create_run(
        self,
        session_id: str,
        *,
        expert_id: str = "",
        intent: str = "chat",
        max_steps: int = 8,
    ) -> Run:
        sid = session_id or "default"
        if self._locks.get(sid):
            run = Run(
                run_id=f"run-{uuid4().hex[:8]}",
                session_id=sid,
                expert_id=expert_id,
                intent=intent,
                max_steps=max_steps,
                state="failed",
                error_code="session_busy",
            )
            self._runs[run.run_id] = run
            return run
        self._locks[sid] = True
        run = Run(
            run_id=f"run-{uuid4().hex[:8]}",
            session_id=sid,
            expert_id=expert_id,
            intent=intent,
            max_steps=max_steps,
        )
        self._runs[run.run_id] = run
        return run

    def release(self, session_id: str) -> None:
        self._locks.pop(session_id or "default", None)

    def get(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def transition(self, run: Run, dest: str) -> bool:
        edge = (run.state, dest)
        if edge in FORBIDDEN or edge not in LEGAL:
            run.history.append({"from": run.state, "to": dest, "ok": "false", "error": "illegal_edge"})
            return False
        if dest not in TERMINAL:
            # Count tool rounds, not every legal edge (chat planning→done is not a tool step).
            if dest == "waiting_tool":
                run.steps += 1
                if run.steps > run.max_steps:
                    run.state = "failed"
                    run.error_code = "max_steps"
                    run.history.append({"from": edge[0], "to": "failed", "ok": "true", "error": "max_steps"})
                    return False
        run.history.append({"from": run.state, "to": dest, "ok": "true"})
        run.state = dest
        if dest == "cancelled":
            run.cancelled = True
        return True

    def cancel(self, run_id: str) -> bool:
        run = self.get(run_id)
        if not run or run.state in TERMINAL:
            return False
        ok = self.transition(run, "cancelled")
        self.release(run.session_id)
        return ok


_SCHED: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _SCHED
    if _SCHED is None:
        _SCHED = Scheduler()
    return _SCHED
