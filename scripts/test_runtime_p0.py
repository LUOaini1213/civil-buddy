#!/usr/bin/env python3
"""P0: pack-ship snapshot copy, ToolEngine deny/timeout, Scheduler edges."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.expert_turn import run_expert_turn
    from packing_assistant.runtime.scheduler import FORBIDDEN, Scheduler
    from packing_assistant.runtime.session_packing import save_packing_snapshot
    from packing_assistant.runtime.tool_engine import (
        ERR_CIRCUIT,
        ERR_DENIED,
        ERR_INVALID,
        ERR_TIMEOUT,
        ToolEngine,
        get_engine,
    )

    # P0-1 disconnected
    off = run_expert_turn("出一份装箱作业单 铁架", "pack-ship", session_id="p0-off")
    plan = (off.get("pack_ship") or {}).get("plan") or {}
    for k in ("utilization", "can_fit", "mid50", "系固待办"):
        assert plan.get(k) == "UNSPECIFIED", (k, plan)
    assert plan.get("xyz") == "UNSPECIFIED"

    # P0-1 connected copy, not recomputed
    snap = {"utilization": 0.55, "can_fit": True, "mid50": 0.7, "系固待办": ["绑扎未确认"]}
    save_packing_snapshot("p0-on", snap)
    on = run_expert_turn("出一份装箱作业单 铁架", "pack-ship", session_id="p0-on", packing_summary=snap)
    plan2 = (on.get("pack_ship") or {}).get("plan") or {}
    assert plan2.get("utilization") == 0.55
    assert plan2.get("can_fit") is True
    assert plan2.get("mid50") == 0.7
    assert plan2.get("系固待办") == ["绑扎未确认"]
    assert plan2.get("xyz") == "UNSPECIFIED"
    assert "pack-ship__health" in (on.get("tools_run") or [])

    # P0-2 engine
    eng = get_engine()
    deny = eng.execute("pack-ship__plan", {"connected": False}, expert_id="bid-parse", intent="run")
    assert deny["error_code"] == ERR_DENIED
    chat = eng.execute("pack-ship__export", {"connected": False}, expert_id="pack-ship", intent="chat")
    assert chat["error_code"] == ERR_DENIED
    slow = ToolEngine()
    slow.register("slow", lambda a: time.sleep(2), timeout_s=0.05, writes=False)
    to = slow.execute("slow", {})
    assert to["error_code"] == ERR_TIMEOUT
    slow.execute("slow", {})
    circ = slow.execute("slow", {})
    assert circ["error_code"] in {ERR_TIMEOUT, ERR_CIRCUIT}
    miss = eng.execute("no-such", {}, expert_id="pack-ship")
    assert miss["error_code"] == ERR_INVALID

    # P0-3 scheduler
    sch = Scheduler()
    run = sch.create_run("sched-1", intent="run")
    assert sch.transition(run, "planning")
    assert sch.transition(run, "acting")
    assert sch.transition(run, "done")
    assert not sch.transition(run, "acting")
    assert ("done", "acting") in FORBIDDEN
    run2 = sch.create_run("sched-2")
    sch.transition(run2, "planning")
    assert sch.cancel(run2.run_id)
    assert run2.cancelled and run2.state == "cancelled"
    deny_c = eng.execute(
        "pack-ship__plan", {"connected": False}, expert_id="pack-ship", intent="run", cancelled=True
    )
    assert deny_c["error_code"] == ERR_DENIED

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    r = client.post(
        "/api/turn",
        json={
            "text": "出一份装箱作业单",
            "expert_id": "pack-ship",
            "session_id": "p0-http",
            "packing_summary": snap,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("run_id")
    got = client.get(f"/api/runs/{body['run_id']}")
    assert got.status_code == 200
    assert got.json().get("state") in {"done", "acting", "planning"}
    print("PASS runtime_p0", body.get("run_id"), plan2.get("can_fit"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
