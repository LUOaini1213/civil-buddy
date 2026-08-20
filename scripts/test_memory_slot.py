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
    print("PASS memory_slot compressed_note")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
