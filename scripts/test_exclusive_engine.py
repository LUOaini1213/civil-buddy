#!/usr/bin/env python3
"""Exclusive writers are ToolEngine tools: chat denied, sibling denied, run writes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.expert_roster import exclusive_owner, list_experts
    from packing_assistant.runtime.tool_engine import ERR_DENIED, get_engine

    eng = get_engine()
    names = set(eng.list())
    assert "finance-tax__calendar" in names
    assert "survey__record" in names
    assert "plan-master__network" in names
    assert "variation__form" in names
    assert "claim__notice" in names
    assert "subcontract__sheet" in names
    assert "interim__measure" in names
    assert "pack-ship__plan" in names
    n_ex = sum(len(e.exclusive) for e in list_experts())
    assert n_ex >= 66
    assert exclusive_owner("finance-tax__calendar") == "finance-tax"

    chat = eng.execute(
        "finance-tax__calendar",
        {"text": "出一份税务日历", "session_id": "eng-tax-chat"},
        expert_id="finance-tax",
        intent="chat",
    )
    assert chat.get("error_code") == ERR_DENIED, chat

    sib = eng.execute(
        "finance-tax__calendar",
        {"text": "出一份税务日历", "session_id": "eng-tax-sib"},
        expert_id="cost",
        intent="run",
    )
    assert sib.get("error_code") == ERR_DENIED, sib

    run = eng.execute(
        "finance-tax__calendar",
        {"text": "出一份税务日历", "session_id": "eng-tax-run", "confirm_ok": True},
        expert_id="finance-tax",
        intent="run",
    )
    assert run.get("ok") is True, run
    data = run.get("data") if isinstance(run.get("data"), dict) else run
    assert data.get("wrote") is True
    path = Path(data["files"][0]["path"])
    text = path.read_text(encoding="utf-8")
    assert "9%" in text
    assert "可以开工" not in text

    hz = eng.execute(
        "method-hazard__judge_hazard",
        {"text": "写一份危大判定书 临边", "session_id": "eng-hz"},
        expert_id="method-hazard",
        intent="run",
    )
    data_h = hz.get("data") if isinstance(hz.get("data"), dict) else hz
    assert data_h.get("wrote") is False
    assert data_h.get("hitl_pending") is True

    print("PASS exclusive_engine registered chat_denied sibling_denied run_writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
