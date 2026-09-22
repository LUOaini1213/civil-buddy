#!/usr/bin/env python3
"""Wait-for cycle ≠ session_busy ≠ deny_cross."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.runtime.deadlock import (
        DeadlockWatch,
        demo_tax_pack_cycle,
        get_watch,
        reset_watch,
    )
    from packing_assistant.runtime.scheduler import Scheduler
    from packing_assistant.runtime.tool_engine import ERR_BUSY, ERR_DEADLOCK, ERR_DENIED, get_engine

    reset_watch()

    w = DeadlockWatch()
    a = w.begin("run-A", holds=["expert:finance-tax"], label="finance-tax")
    b = w.begin("run-B", holds=["expert:pack-ship"], label="pack-ship")
    assert a.allow and b.allow, (a, b)
    busy = w.wait_for("run-A", "expert:pack-ship")
    assert busy.allow is False
    assert busy.err == ERR_BUSY, busy
    assert "死锁" not in busy.reason
    dead = w.wait_for("run-B", "expert:finance-tax")
    assert dead.allow is False
    assert dead.err == ERR_DEADLOCK, dead
    assert dead.reason.startswith("死锁："), dead.reason
    assert "finance-tax" in dead.reason and "pack-ship" in dead.reason
    assert "run-A" in dead.cycle and "run-B" in dead.cycle
    w.end("run-A")
    w.end("run-B")
    snap = w.snapshot()
    assert snap["holds"] == {}
    assert snap["wait"] == {}

    demo = demo_tax_pack_cycle()
    assert demo.err == ERR_DEADLOCK
    assert "未阻塞等待" in demo.reason

    # no cycle: B waits for free resource
    w2 = DeadlockWatch()
    w2.begin("r1", holds=["expert:finance-tax"], label="finance-tax")
    own = w2.wait_for("r1", "expert:finance-tax")
    assert own.allow is True
    w2.end("r1")

    # A failed extension must never release resources this run already owned.
    rollback = DeadlockWatch()
    rollback.begin("owner", holds=["original"])
    rollback.begin("other", holds=["contended"])
    denied = rollback.begin("owner", holds=["original", "new", "contended"])
    assert denied.err == ERR_BUSY
    assert rollback.snapshot()["holds"] == {"original": "owner", "contended": "other"}

    # three-node cycle
    w3 = DeadlockWatch()
    w3.begin("A", holds=["expert:finance-tax"], label="finance-tax")
    w3.begin("B", holds=["expert:pack-ship"], label="pack-ship")
    w3.begin("C", holds=["expert:bid-parse"], label="bid-parse")
    assert w3.wait_for("A", "expert:pack-ship").err == ERR_BUSY
    assert w3.wait_for("B", "expert:bid-parse").err == ERR_BUSY
    cyc = w3.wait_for("C", "expert:finance-tax")
    assert cyc.err == ERR_DEADLOCK, cyc
    w3.end("A")
    w3.end("B")
    w3.end("C")

    # session_busy ≠ deadlock
    sch = Scheduler()
    r = sch.create_run("sess-dl", expert_id="finance-tax")
    r2 = sch.create_run("sess-dl", expert_id="pack-ship")
    assert r2.error_code == "session_busy"
    assert r2.error_code != ERR_DEADLOCK
    sch.release("sess-dl")

    # deny_cross ≠ deadlock
    sib = get_engine().execute(
        "pack-ship__plan",
        {"connected": False},
        expert_id="bid-parse",
        intent="run",
    )
    assert sib.get("error_code") == ERR_DENIED
    assert sib.get("error_code") != ERR_DEADLOCK

    # ToolEngine wait_resources hook (process watch)
    gw = reset_watch()
    gw.begin("run-A", holds=["expert:finance-tax"], label="finance-tax")
    gw.begin("run-B", holds=["expert:pack-ship"], label="pack-ship")
    gw.wait_for("run-A", "expert:pack-ship")
    hooked = get_engine().execute(
        "finance-tax__calendar",
        {"text": "税务日历"},
        expert_id="finance-tax",
        intent="run",
        run_id="run-B",
        wait_resources=["expert:finance-tax"],
    )
    assert hooked.get("error_code") == ERR_DEADLOCK, hooked
    assert "死锁" in (hooked.get("reason") or "")
    reset_watch()

    # Invalid/unauthorized tools cannot acquire resources before being denied.
    from packing_assistant.runtime.tool_engine import ToolEngine
    isolated_engine = ToolEngine()
    invalid = isolated_engine.execute("missing", run_id="invalid", wait_resources=["free"])
    assert invalid["ok"] is False
    assert get_watch().snapshot()["holds"] == {}

    # exclusive expert: second begin without end → expert_busy
    gw = get_watch()
    gw.begin("ghost-tax", holds=["expert:finance-tax"], label="finance-tax")
    out = run_agent(
        "出一份税务日历",
        expert_id="finance-tax",
        session_id="dl-busy",
        force_intent="run",
    )
    assert out.get("ok") is False
    assert out.get("error_code") == ERR_BUSY, out
    assert "死锁" not in (out.get("reason") or "")
    gw.end("ghost-tax")
    reset_watch()

    # sequential same expert still works
    first = run_agent(
        "出一份税务日历",
        expert_id="finance-tax",
        session_id="dl-seq-1",
        force_intent="run",
    )
    second = run_agent(
        "出一份税务日历",
        expert_id="finance-tax",
        session_id="dl-seq-2",
        force_intent="run",
    )
    assert first.get("error_code") in {"", "ok", None} or first.get("ok") is True, first
    assert second.get("ok") is True or second.get("wrote") is True, second
    assert second.get("error_code") != ERR_BUSY
    assert second.get("error_code") != ERR_DEADLOCK
    reset_watch()

    print("PASS deadlock", demo.err, "busy", ERR_BUSY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
