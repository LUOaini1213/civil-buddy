#!/usr/bin/env python3
"""全量优化回归：叠高 + CoG/mid50 + multi_start + 空隙 + risk 钩子。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.bin3d import pack_boxes_api
from packing_assistant.tools.layout_quality import analyze_layout_quality
from packing_assistant.agents.risk_compliance import agent_risk_compliance
from packing_assistant.agents.evaluator import agent_evaluator


def _boxes(n=10, h=800, w=150.0, stackable=True):
    return [
        {
            "box_id": f"B{i+1:02d}",
            "box_type": "木箱",
            "outer_size_mm": {"length": 2200, "width": 1100, "height": h},
            "gross_weight_kg": w,
            "stackable": stackable,
            "prefer_bottom": False,
            "special_attributes": [],
            "structure_conclusion": "通过",
        }
        for i in range(n)
    ]


def main() -> int:
    opts = {
        "prefer_stack": True,
        "clearance_mm": 30,
        "support_ratio_min": 0.55,
        "max_stack_layers": 3,
        "multi_start": True,
        "cog_aware": True,
        "corner_support": True,
        "export_strict": False,
    }
    boxes = _boxes(10, h=800, w=180)
    plan = pack_boxes_api(boxes, container_type="40HQ", max_containers=2, packing_options=opts)
    st = plan.get("stacking") or {}
    cog = plan.get("cog") or {}
    lq = plan.get("layout_quality") or analyze_layout_quality(plan, boxes)
    stacked = int(st.get("stacked_placements") or 0)
    mid50 = float(cog.get("mass_in_mid50_ratio") or 0)
    print("=== pack ===")
    print(
        f"fit={plan.get('can_fit')} used={plan.get('containers_used')} "
        f"stacked={stacked} winner={st.get('multi_start_winner')} n={st.get('multi_start_n')}"
    )
    print(
        f"mid50={mid50:.2f} long={cog.get('longitudinal_position')} bal={cog.get('balance')} "
        f"gap={lq.get('max_horizontal_gap_mm')} over={lq.get('gaps_over_limit')}"
    )

    state = {
        "boxes": boxes,
        "container_plan": plan,
        "packing_options": opts,
        "evaluation": {},
        "structure_constraints": [],
        "replan_round": 0,
        "plan": {"container_type": "40HQ", "max_containers": 2},
    }
    # risk / eval 可能返回 partial state update
    try:
        rr = agent_risk_compliance(state)  # type: ignore
        if isinstance(rr, dict) and rr.get("risk_report"):
            state.update({k: v for k, v in rr.items() if k in ("risk_report", "messages")})
        print("risk decision=", (state.get("risk_report") or rr.get("risk_report") or {}).get("decision"))
    except Exception as e:
        print("risk err", e)

    try:
        ev = agent_evaluator(state)  # type: ignore
        evaluation = (ev or {}).get("evaluation") or state.get("evaluation") or {}
        print(
            f"eval score={evaluation.get('score')} decision={evaluation.get('decision')} "
            f"replan={evaluation.get('need_replan')}"
        )
    except Exception as e:
        print("eval err", e)
        evaluation = {}

    # 叠高冒烟
    from scripts.test_stack_prefer import main as stack_main

    stack_rc = stack_main()

    ok = (
        plan.get("can_fit")
        and stacked >= 2
        and mid50 >= 0.45
        and st.get("multi_start_cog") is True
        and stack_rc == 0
    )
    print("---", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
