#!/usr/bin/env python3
"""Complete Civil Codex: skills, config/approvals, threads, CLI verbs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.civil import list_skills, main as civil_main, run_task
    from packing_assistant.civil_tui import handle_slash, TuiState
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.runtime.civil_config import decide_gate, load_config
    from packing_assistant.runtime.expert_skills import match_skill, parse_explicit
    from packing_assistant.runtime.threads import list_threads, new_thread, run_on_thread, spawn

    os.environ.pop("CIVIL_SANDBOX", None)
    os.environ.pop("CIVIL_APPROVAL", None)

    assert parse_explicit("$construction 写提纲") == "construction"
    assert match_skill("财务上施工发票备注栏怎么写？") is None
    assert match_skill("写临边防护方案讨论提纲") == "construction"
    assert match_skill("出一份税务日历") == "finance-tax"
    assert len(list_skills()) == 66

    cfg = load_config()
    assert cfg.sandbox == "workspace-write"
    assert cfg.approval == "on-request"
    assert decide_gate(intent="chat", risk="high", confirmed=False, cfg=cfg) == "go"
    assert decide_gate(intent="run", risk="high", confirmed=False, cfg=cfg) == "hitl"
    assert decide_gate(intent="run", risk="low", confirmed=False, cfg=cfg) == "go"

    os.environ["CIVIL_SANDBOX"] = "read-only"
    ro = run_agent("出一份税务日历", session_id="cx-ro")
    assert ro.get("wrote") is False
    assert ro.get("sandbox_mode") == "read-only"
    assert "read-only" in (ro.get("reply") or "")
    os.environ.pop("CIVIL_SANDBOX", None)

    os.environ["CIVIL_APPROVAL"] = "untrusted"
    ut = run_agent("出一份税务日历", session_id="cx-un", p0_confirmed=False)
    assert ut.get("hitl_pending") is True
    assert ut.get("wrote") is False
    os.environ.pop("CIVIL_APPROVAL", None)

    tax = run_task("出一份税务日历", session_id="cx-tax2")
    assert tax.get("skill") == "finance-tax"
    assert tax["wrote"] is True

    th = new_thread("测")
    got = run_on_thread(th.thread_id, "什么是 GST")
    assert got.get("thread_id") == th.thread_id
    assert got.get("wrote") is False
    assert "9%" in (got.get("reply") or "")
    bg = spawn("什么是 GST", title="bg-gst")
    assert bg.get("background") is True
    assert bg.get("thread_id")
    assert any(t.thread_id == th.thread_id for t in list_threads())

    st = TuiState()
    help_txt = handle_slash("/help", st)
    assert "/skills" in (help_txt or "")
    sk = handle_slash("/skills construction", st)
    assert "$construction" in (sk or "")
    assert "sandbox" in (handle_slash("/status", st) or "")
    msg = handle_slash("/sandbox read-only", st)
    assert "read-only" in (msg or "")
    os.environ.pop("CIVIL_SANDBOX", None)
    os.environ.pop("CIVIL_APPROVAL", None)

    assert civil_main(["skills"]) == 0
    assert civil_main(["help"]) == 0
    assert civil_main(["exec", "什么是 GST", "--json"]) == 0

    from fastapi.testclient import TestClient
    from gateway.app import app

    client = TestClient(app)
    assert client.get("/api/skills").json().get("n") == 66
    assert client.get("/api/config").json().get("sandbox") in {"read-only", "workspace-write"}
    assert client.get("/api/threads").status_code == 200
    ag = client.post("/api/agent", json={"text": "出一份税务日历", "session_id": "cx-http-tax2"})
    assert ag.status_code == 200
    assert ag.json().get("skill") == "finance-tax"

    print("PASS test_civil_codex complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
