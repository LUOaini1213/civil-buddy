"""Agent runtime kernel (Scheduler · ToolEngine · Run · Bus · loop). Domain plugins stay outside."""

from packing_assistant.runtime.agent_loop import run_agent
from packing_assistant.runtime.bus import Bus, get_bus
from packing_assistant.runtime.scheduler import (
    FORBIDDEN,
    LEGAL,
    Scheduler,
    get_scheduler,
)
from packing_assistant.runtime.session_packing import load_packing_snapshot, save_packing_snapshot
from packing_assistant.runtime.deadlock import (
    DeadlockWatch,
    demo_tax_pack_cycle,
    get_watch,
    reset_watch,
)
from packing_assistant.runtime.tool_engine import (
    ERR_BUSY,
    ERR_CIRCUIT,
    ERR_DEADLOCK,
    ERR_DENIED,
    ERR_INVALID,
    ERR_MAX_STEPS,
    ERR_OK,
    ERR_TIMEOUT,
    ERR_UNSPECIFIED,
    ToolEngine,
    get_engine,
)

__all__ = [
    "FORBIDDEN",
    "LEGAL",
    "Bus",
    "DeadlockWatch",
    "Scheduler",
    "demo_tax_pack_cycle",
    "get_bus",
    "get_scheduler",
    "get_watch",
    "reset_watch",
    "load_packing_snapshot",
    "save_packing_snapshot",
    "ERR_BUSY",
    "ERR_CIRCUIT",
    "ERR_DEADLOCK",
    "ERR_DENIED",
    "ERR_INVALID",
    "ERR_MAX_STEPS",
    "ERR_OK",
    "ERR_TIMEOUT",
    "ERR_UNSPECIFIED",
    "ToolEngine",
    "get_engine",
    "run_agent",
]
