#!/usr/bin/env python3
"""P0：重心驱动自动闭环 — mid50 差应触发 replan，且 multi_start 优选中段方案。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.agents.replan_critic import agent_replan_critic
    from packing_assistant.agents.evaluator import agent_evaluator

    # 多件同重箱：有机会叠并应中段
    boxes = [
        {
            "box_id": f"C{i:02d}",
            "box_type": "木箱",
            "outer_size_mm": {"length": 2000, "width": 1100, "height": 700},
            "gross_weight_kg": 400 + (i % 3) * 50,
            "stackable": True,
            "prefer_bottom": False,
            "special_attributes": [],
            "structure_conclusion": "通过",
        }
        for i in range(16)
    ]

    plan0 = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "clearance_mm": 30,
        },
    )
    plan1 = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "clearance_mm": 20,
        },
    )

    def mid(p):
        b = p.get("cog_bundle") or {}
        if b.get("worst_mid50") is not None:
            return float(b["worst_mid50"])
        c = p.get("cog") or {}
        return float(c.get("mass_in_mid50_ratio") or 0)

    m0, m1 = mid(plan0), mid(plan1)
    print(f"mid50 default={m0:.2f} rebalance={m1:.2f} can_fit={plan1.get('can_fit')}")
    print(f"winner0={((plan0.get('stacking') or {}).get('multi_start_winner'))} "
          f"winner1={((plan1.get('stacking') or {}).get('multi_start_winner'))}")

    # critic 路由
    crit = agent_replan_critic(
        {
            "replan_round": 0,
            "ship_replan_round": 0,
            "evaluation": {"need_replan": False, "decision": "PASS"},
            "risk_report": {
                "decision": "REJECT",
                "reject_to": "planner",
                "auto_replanable": True,
                "blockers": ["中段50%质量占比 29%"],
            },
            "container_plan": {
                **plan0,
                "can_fit": True,
                "worst_mid50": 0.29,
                "cog": {"mass_in_mid50_ratio": 0.29, "balance": "block"},
            },
            "packing_options": {},
            "max_containers": 2,
        }
    )
    prop = crit.get("replan_proposal") or {}
    opts = crit.get("packing_options") or {}
    print("critic route", prop.get("route"), "cog_rebalance", opts.get("cog_rebalance"), prop.get("reasons")[:2])

    # evaluator need_replan on mid50
    st = {
        "boxes": boxes,
        "container_plan": plan0,
        "packing_options": {},
        "replan_round": 0,
        "ship_replan_round": 0,
        "plan": {"max_containers": 2},
        "max_containers": 2,
    }
    # inject bad mid50
    st["container_plan"] = {
        **plan0,
        "can_fit": True,
        "unpacked_box_ids": [],
        "cog": {"mass_in_mid50_ratio": 0.29, "balance": "block", "height_ratio": 0.3},
        "cog_bundle": {"worst_mid50": 0.29, "worst": {"mass_in_mid50_ratio": 0.29, "balance": "block"}},
        "weight_utilization": 0.5,
        "booking_volume_utilization": 0.4,
        "space_utilization": 0.3,
        "floor_utilization_avg": 0.4,
    }
    ev = agent_evaluator(st)
    evaluation = (ev or {}).get("evaluation") or {}
    print("eval need_replan", evaluation.get("need_replan"), evaluation.get("decision"))

    # R1 刚性平移
    from packing_assistant.tools.cog_shift import maybe_apply_r1_shift, shift_layout_to_mass_center

    raw = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={"prefer_stack": True, "multi_start": False, "cog_aware": True, "r1_shift": False},
    )
    # 强制关 r1 后再手动 R1
    plan_no = dict(raw)
    plan_no.pop("r1_shift", None)
    st_meta = dict(plan_no.get("stacking") or {})
    st_meta["r1_shift_applied"] = False
    plan_no["stacking"] = st_meta
    plan_r1 = maybe_apply_r1_shift(plan_no, boxes, force=True)
    m_raw = mid(plan_no)
    m_r1 = mid(plan_r1)
    r1_on = bool((plan_r1.get("stacking") or {}).get("r1_shift_applied")) or bool(
        plan_r1.get("r1_shift")
    )
    print(f"R1 mid50 before={m_raw:.2f} after={m_r1:.2f} applied_meta={r1_on}")

    ok = (
        plan1.get("can_fit")
        and prop.get("route") == "planner"
        and opts.get("cog_rebalance") is True
        and evaluation.get("need_replan") is True
        and m1 + 1e-9 >= m0 - 0.05  # 再平衡不应明显变差
        and m_r1 + 1e-9 >= m_raw - 0.02
    )
    # 再平衡目标：尽量更好；若已很高则保持
    if m0 < 0.55:
        ok = ok and (m1 >= m0 - 0.02)
    print("---", "PASS" if ok else "FAIL", f"(m0={m0:.2f} m1={m1:.2f} r1={m_r1:.2f})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
