"""In-process event bus. No message middleware in this slice."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

EVENT_TYPES = (
    "run_started",
    "tool_call",
    "tool_result",
    "hitl",
    "run_ended",
    "cancelled",
    # model-driven turns (runtime/model_loop.py)
    "plan",
    "skill_loaded",
    "message",
    "guard",
    "deadlock",
)


@dataclass
class Event:
    run_id: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "type": self.type,
            "payload": self.payload,
            "ts": self.ts,
        }


class Bus:
    def __init__(self) -> None:
        self._events: List[Event] = []
        self._listeners: List[Callable[[Event], None]] = []

    def emit(self, run_id: str, type: str, payload: Optional[Dict[str, Any]] = None) -> Event:
        ev = Event(run_id=run_id, type=type, payload=payload or {})
        self._events.append(ev)
        for listener in list(self._listeners):
            try:
                listener(ev)
            except Exception:  # noqa: BLE001 - a broken printer must not fail the run
                pass
        return ev

    def subscribe(self, listener: Callable[[Event], None]) -> Callable[[], None]:
        """Call ``listener`` for every event as it happens. Returns the unsubscribe function."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def for_run(self, run_id: str) -> List[Event]:
        return [e for e in self._events if e.run_id == run_id]


_BUS: Optional[Bus] = None


def get_bus() -> Bus:
    global _BUS
    if _BUS is None:
        _BUS = Bus()
    return _BUS
