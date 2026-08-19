"""In-process event bus. No message middleware in this slice."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

EVENT_TYPES = (
    "run_started",
    "tool_call",
    "tool_result",
    "hitl",
    "run_ended",
    "cancelled",
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

    def emit(self, run_id: str, type: str, payload: Optional[Dict[str, Any]] = None) -> Event:
        ev = Event(run_id=run_id, type=type, payload=payload or {})
        self._events.append(ev)
        return ev

    def for_run(self, run_id: str) -> List[Event]:
        return [e for e in self._events if e.run_id == run_id]


_BUS: Optional[Bus] = None


def get_bus() -> Bus:
    global _BUS
    if _BUS is None:
        _BUS = Bus()
    return _BUS
