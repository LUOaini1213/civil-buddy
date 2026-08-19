#!/usr/bin/env python3
"""Complete agent loop + sandbox: chat no write, run via engine, deny, max_steps."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.runtime.scheduler import Scheduler
    from packing_assistant.runtime.tool_engine import ERR_DENIED, get_engine
    from packing_assistant.understand import understand

    eng = get_engine()

    # Engine sandbox: outside root, .env, generic spawn
    outside = ROOT / "docs" / "agent-should-not-write.txt"
    if outside.exists():
        outside.unlink()
    denied_out = eng.execute(
        "write_deliverable",
        {"path": str(outside), "text": "nope"},
        intent="run",
    )
    assert denied_out["error_code"] == ERR_DENIED, denied_out
    assert not outside.exists()

    envp = ROOT / "demo" / "out" / "agent-loop" / ".env"
    denied_env = eng.execute(
        "write_deliverable",
        {"path": str(envp), "text": "SECRET=1"},
        intent="run",
    )
    assert denied_env["error_code"] == ERR_DENIED, denied_env
    assert not envp.exists()

    spawn = eng.execute(
        "spawn_helper",
        {"command": ["cmd", "/c", "dir"], "kind": "generic"},
        intent="run",
    )
    assert spawn["error_code"] == ERR_DENIED, spawn

    chat_write = eng.execute(
        "write_deliverable",
        {"path": str(ROOT / "demo" / "out" / "agent-loop" / "chat.md"), "text": "x"},
        intent="chat",
    )
    assert chat_write["error_code"] == ERR_DENIED, chat_write

    high = run_agent(
        "写一份专项方案讨论提纲",
        expert_id="method-hazard",
        session_id="ag-hitl",
        force_intent="run",
        p0_confirmed=False,
    )
    assert high.get("hitl_pending") is True, high
    assert high.get("wrote") is False

    # Chat: explain only
    assert understand("什么是 GST") == "chat"
    chat = run_agent("什么是 GST", session_id="ag-chat")
    assert chat["schema"] == "civil.agent.v1"
    assert chat["intent"] == "chat"
    assert chat["wrote"] is False
    assert chat["artifacts"] == []
    assert chat.get("matrix") is None
    assert "9%" in (chat.get("reply") or "")
    assert "可以投标" not in (chat.get("reply") or "")
    assert chat.get("submit_blocked") is True
    assert chat.get("run_id")
    assert chat.get("state") == "done"
    assert not chat.get("tools_used")

    # Run via engine + sandbox write inside demo/out
    tax = run_agent(
        "出一份税务日历",
        expert_id="finance-tax",
        session_id="ag-tax",
        force_intent="run",
    )
    assert tax["intent"] == "run"
    assert tax["wrote"] is True
    assert tax["artifacts"], tax
    art = Path(tax["artifacts"][0])
    assert art.is_file(), art
    assert "demo" in str(art).replace("\\", "/") and "out" in str(art).replace("\\", "/")
    body = art.read_text(encoding="utf-8")
    assert "可以开工" not in body or "不判定可以开工" in body
    assert "write_deliverable" in tax["tools_used"]

    # Pack-ship disconnected: UNSPECIFIED, still through engine
    pack = run_agent(
        "出一份装箱作业单 铁架",
        expert_id="pack-ship",
        session_id="ag-pack-off",
        force_intent="run",
    )
    plan = (pack.get("pack_ship") or {}).get("plan") or {}
    for k in ("utilization", "can_fit", "mid50", "系固待办"):
        assert plan.get(k) == "UNSPECIFIED", (k, plan)
    assert "pack-ship__health" in (pack.get("tools_used") or [])

    # max_steps: pack-ship plans 4 tools, cap at 1
    capped = run_agent(
        "出一份装箱作业单",
        expert_id="pack-ship",
        session_id="ag-max",
        force_intent="run",
        max_steps=1,
        scheduler=Scheduler(),
    )
    assert capped.get("error_code") == "max_steps", capped
    assert capped.get("state") == "failed"
    assert len(capped.get("tools_used") or []) <= 1

    # cancel → execute denied
    sch = Scheduler()
    run = sch.create_run("ag-cancel")
    sch.transition(run, "planning")
    assert sch.cancel(run.run_id)
    deny_c = eng.execute(
        "write_deliverable",
        {"path": str(ROOT / "demo" / "out" / "agent-loop" / "x.md"), "text": "x"},
        intent="run",
        cancelled=True,
    )
    assert deny_c["error_code"] == ERR_DENIED

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    http_chat = client.post("/api/agent", json={"text": "什么是 GST", "session_id": "ag-http-chat"})
    assert http_chat.status_code == 200, http_chat.text
    jc = http_chat.json()
    assert jc.get("intent") == "chat" and jc.get("wrote") is False
    assert "9%" in (jc.get("reply") or "")
    assert jc.get("run_id")
    got = client.get(f"/api/runs/{jc['run_id']}")
    assert got.status_code == 200
    assert got.json().get("state") in {"done", "acting", "planning"}
    ev = client.get(f"/api/runs/{jc['run_id']}/events")
    assert ev.status_code == 200
    assert ev.json().get("events")

    live = client.get("/api/eval/live")
    assert live.status_code == 200, live.text
    lj = live.json()
    assert lj.get("schema") == "civil.eval.live.v1"
    assert lj.get("live_web") is False
    assert lj.get("ok") is True, lj.get("gates")
    ids = {n["id"] for n in lj.get("needles") or []}
    assert {"gst-9", "fire-code", "ctu-2014", "gebiz-not-scoring"} <= ids
    assert all(n.get("found") for n in lj["needles"]), lj["needles"]

    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/api/agent" in index
    assert "/api/turn" in index
    print(
        "PASS agent_loop",
        f"chat={chat['run_id']}",
        f"tax={art.name}",
        f"max_steps={capped.get('error_code')}",
        f"eval={lj.get('verdict')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
