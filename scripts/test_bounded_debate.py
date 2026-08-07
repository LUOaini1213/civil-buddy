#!/usr/bin/env python3
"""有界辩论回归：critic↔planner 确定性对话 + tools 仍裁决。

1) 单元：planner_counter_proposal / run_bounded_debate 形状
2) 集成：真实 pipeline 在 need_replan 场景可出现 bounded_debate 或干净结束
"""

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

    # critic wants raise_bins but plan already fits with mid ok → planner modify
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
        "reasons": ["mid 刷分想加柜"],
        "packing_options_delta": {
            "strategy_request": "raise_bins_for_cog",
            "cog_rebalance": True,
        },
    }
    reply = planner_counter_proposal(state, prop)
    assert reply["stance"] == "modify", reply
    assert "densify" in str(reply.get("packing_options_delta", {}).get("strategy_request", "")), reply
    print("UNIT planner_counter modify_ok")

    # full debate with synthetic need (may stop if critic says no need)
    # force critic path: can_fit false
    state2 = {
        "container_plan": {
            "can_fit": False,
            "containers_used": 1,
            "unpacked_box_ids": ["x"],
            "worst_mid50": 0.4,
            "cog": {"mass_in_mid50_ratio": 0.4, "balance": "warn"},
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
    assert "replan_proposal" in out, out.keys()
    deb = out.get("bounded_debate") or {}
    assert deb.get("enabled") is True, deb
    assert deb.get("tools_adjudicate") is True, deb
    assert isinstance(deb.get("transcript"), list) and len(deb["transcript"]) >= 1, deb
    print(
        f"UNIT debate outcome={deb.get('outcome')} turns={deb.get('rounds')} "
        f"stop={out.get('replan_proposal', {}).get('stop')}"
    )

    # public summary
    pub = debate_public_summary({"bounded_debate": deb})
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
    # may or may not trigger replan on good high_util; field must exist
    assert "bounded_debate" in pub
    deb = pub.get("bounded_debate") or {}
    plan = st.get("container_plan") or {}
    print(
        f"PIPE phase={st.get('phase')} can_fit={plan.get('can_fit')} "
        f"debate={bool(deb)} outcome={deb.get('outcome')} "
        f"steps={[s.get('node') for s in (st.get('agent_steps') or []) if s.get('node') in ('bounded_debate', 'replan_critic')]}"
    )
    # tools still own packing
    assert plan.get("can_fit") is True or st.get("ship_ok") is not None


def main() -> int:
    test_unit()
    test_pipeline_smoke()
    print("ALL_PASS bounded_debate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
