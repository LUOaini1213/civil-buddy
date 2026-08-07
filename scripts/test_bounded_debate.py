#!/usr/bin/env python3
"""有界辩论回归（优化版）：冲突消解 + transcript + public。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")


def test_unit() -> None:
    from packing_assistant.bounded_debate import (
        planner_counter_proposal,
        run_bounded_debate,
        debate_public_summary,
    )

    # raise_bins + mid ok → densify modify
    state = {
        "container_plan": {
            "can_fit": True,
            "containers_used": 3,
            "worst_mid50": 0.62,
            "reference_light_used": 2,
            "cog": {"mass_in_mid50_ratio": 0.62, "balance": "ok"},
        },
        "ship_ok": True,
        "packing_options": {},
        "evaluation": {"need_replan": True},
        "replan_round": 0,
        "ship_replan_round": 0,
        "boxes": [],
        "materials": [],
        "container_type": "40HQ",
    }
    prop = {
        "stop": False,
        "route": "planner",
        "reasons": ["想加柜刷 mid"],
        "packing_options_delta": {
            "strategy_request": "raise_bins_for_cog",
            "container_budget_soft": 6,
            "cog_rebalance": True,
        },
    }
    reply = planner_counter_proposal(state, prop)
    assert reply["stance"] == "modify", reply
    assert "densify" in str(
        reply.get("packing_options_delta", {}).get("strategy_request", "")
    ), reply
    print("UNIT planner_counter anti_raise_bins ok")

    # thin mid 55-60
    state_thin = {
        **state,
        "container_plan": {
            **state["container_plan"],
            "worst_mid50": 0.57,
            "cog": {"mass_in_mid50_ratio": 0.57},
        },
    }
    prop2 = {
        "stop": False,
        "route": "planner",
        "reasons": ["mid soft"],
        "packing_options_delta": {"cog_rebalance": True},
    }
    r2 = planner_counter_proposal(state_thin, prop2)
    assert r2["stance"] == "modify", r2
    assert float(r2["packing_options_delta"].get("r4_target_mid50") or 0) >= 0.60
    print("UNIT thin_mid densify ok")

    # full debate can_fit false
    state2 = {
        "container_plan": {
            "can_fit": False,
            "containers_used": 1,
            "unpacked_box_ids": ["x"],
            "worst_mid50": 0.4,
            "cog": {"mass_in_mid50_ratio": 0.4},
        },
        "evaluation": {"need_replan": True, "decision": "REPLAN"},
        "risk_report": {},
        "packing_options": {"bounded_debate": True},
        "replan_round": 0,
        "ship_replan_round": 0,
        "boxes": [
            {
                "box_id": "B1",
                "gross_weight_kg": 500,
                "outer_size_mm": {"length": 1000, "width": 800, "height": 800},
            }
        ],
        "materials": [],
        "container_type": "40HQ",
        "max_containers": 2,
    }
    out = run_bounded_debate(state2)
    deb = out.get("bounded_debate") or {}
    assert deb.get("enabled") and deb.get("tools_adjudicate")
    assert len(deb.get("transcript") or []) >= 2
    print(f"UNIT debate outcome={deb.get('outcome')} turns={deb.get('rounds')}")

    # debate that should improve (raise vs densify)
    state3 = {
        "container_plan": {
            "can_fit": True,
            "containers_used": 4,
            "worst_mid50": 0.58,
            "reference_light_used": 3,
            "cog": {"mass_in_mid50_ratio": 0.58, "balance": "ok"},
            "n0": 3,
        },
        "evaluation": {"need_replan": True, "decision": "REPLAN"},
        "risk_report": {"decision": "ACCEPT"},
        "packing_options": {"bounded_debate": True},
        "replan_round": 0,
        "ship_replan_round": 0,
        "boxes": [
            {
                "box_id": f"B{i}",
                "gross_weight_kg": 800,
                "outer_size_mm": {"length": 1100, "width": 1000, "height": 1100},
            }
            for i in range(8)
        ],
        "materials": [],
        "container_type": "40HQ",
        "max_containers": 8,
    }
    out3 = run_bounded_debate(state3)
    deb3 = out3.get("bounded_debate") or {}
    prop3 = out3.get("replan_proposal") or {}
    strat = str(
        (prop3.get("packing_options_delta") or {}).get("strategy_request")
        or deb3.get("final_strategy")
        or ""
    )
    print(
        f"UNIT improve_path outcome={deb3.get('outcome')} improved={deb3.get('improved')} "
        f"strategy={strat}"
    )
    # thin mid should densify not raise
    assert "raise_bins" not in strat or deb3.get("improved") is True or "densify" in strat or prop3.get("stop")

    pub = debate_public_summary({"bounded_debate": deb3})
    assert pub.get("tools_adjudicate") is True
    print("UNIT public_summary ok")


def test_pipeline_smoke() -> None:
    from packing_assistant.demo_presets import (
        materials_high_util,
        packing_options_high_util,
    )
    from packing_assistant.harness import run_agent_pipeline, public_response

    opts = packing_options_high_util()
    opts["bounded_debate"] = True
    st = run_agent_pipeline(
        "bounded debate smoke high_util",
        materials=materials_high_util(),
        packing_options=opts,
        enable_auto_confirm=True,
        session_id="debate-smoke",
        save_artifacts=False,
    )
    pub = public_response(st)
    assert "bounded_debate" in pub
    plan = st.get("container_plan") or {}
    print(
        f"PIPE phase={st.get('phase')} can_fit={plan.get('can_fit')} "
        f"mid50={plan.get('worst_mid50')} debate={bool(pub.get('bounded_debate'))}"
    )


def test_frontend_marker() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "boundedDebate" in html and "有界辩论" in html
    print("UI marker boundedDebate ok")


def main() -> int:
    test_unit()
    test_pipeline_smoke()
    test_frontend_marker()
    print("ALL_PASS bounded_debate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
