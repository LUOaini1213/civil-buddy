#!/usr/bin/env python3
"""T010: session.summary slots; compress note does not pretend unread details."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.runtime.memory import load_summary, save_summary

    path = save_summary(
        "mem-t010",
        jurisdiction="SG",
        project="滨河路",
        p0_confirmed=True,
        compressed=True,
    )
    assert path.is_file()
    got = load_summary("mem-t010")
    assert got and got["jurisdiction"] == "SG"
    assert got["project"] == "滨河路"
    assert got["p0_confirmed"] is True
    assert got["compressed"] is True
    assert "假装" in got["dropped_note"] or "不要假装" in got["dropped_note"]

    run = run_agent("什么是 GST", session_id="mem-t010-run", force_intent="chat")
    assert run.get("wrote") is False
    disk = load_summary("mem-t010-run")
    assert disk and disk.get("project")

    from packing_assistant.runtime.memory import assemble_context

    assemble_context("mem-sticky", text="滨河路人行道", project_name="滨河路", p0_confirmed=True)
    second = run_agent(
        "什么是 GST",
        session_id="mem-sticky",
        force_intent="chat",
        project_name="幕墙项目投标应答（草稿）",
    )
    assert second.get("wrote") is False
    assert (second.get("context") or {}).get("project") == "滨河路"
    assert (second.get("context") or {}).get("p0_confirmed") is True
    assert "9%" in (second.get("reply") or "")
    sticky = load_summary("mem-sticky")
    assert sticky and sticky["project"] == "滨河路"

    save_summary("mem-compressed-chat", jurisdiction="SG", project="滨河路", compressed=True)
    chat_c = run_agent("临边防护算不算危大？", session_id="mem-compressed-chat", force_intent="chat")
    assert chat_c.get("wrote") is False
    assert "假装" in (chat_c.get("reply") or "") or "不要假装" in (chat_c.get("reply") or "")
    assert (chat_c.get("context") or {}).get("compressed") is True

    from fastapi.testclient import TestClient
    from gateway.app import app

    client = TestClient(app)
    got = client.get("/api/context/mem-sticky")
    assert got.status_code == 200, got.text
    assert got.json()["context"]["project"] == "滨河路"
    print("PASS memory_slot compressed_note sticky_project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
