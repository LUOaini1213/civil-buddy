#!/usr/bin/env python3
"""R2 条带重排 + 出运停损回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.tools.cog_slab import apply_r2_slab_reorder
    from packing_assistant.agents.evaluator import agent_evaluator

    boxes = []
    for i in range(6):
        boxes.append(
            {
                "box_id": f"H{i}",
                "outer_size_mm": {"length": 1500, "width": 1000, "height": 600},
                "gross_weight_kg": 900,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
                "box_type": "木箱",
            }
        )
    for i in range(14):
        boxes.append(
            {
                "box_id": f"L{i}",
                "outer_size_mm": {"length": 1000, "width": 800, "height": 500},
                "gross_weight_kg": 60,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
                "box_type": "木箱",
            }
        )

    base = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "r0_r1": True,
            "r2_slab": False,
            "r4_repair": False,
            "r3_repack": False,
        },
    )
    m0 = float(base.get("worst_mid50") or 0)
    r2 = apply_r2_slab_reorder(base, boxes, target_mid50=0.55, force=True)
    m2 = float(r2.get("worst_mid50") or m0)
    print(f"mid50 base={m0:.3f} after_R2={m2:.3f} r2_meta={(r2.get('stacking') or {}).get('r2_slab_applied')}")

    full = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r0_r1": True,
            "r2_slab": True,
            "r4_repair": True,
            "r3_repack": True,
            "r4_target_mid50": 0.55,
        },
    )
    mf = float(full.get("worst_mid50") or 0)
    print(f"full pipeline mid50={mf:.3f} can_fit={full.get('can_fit')} winner={(full.get('stacking') or {}).get('multi_start_winner')}")

    # 停损：mid50=0.45 can_fit 已 replan 过 → need_replan False for mid50
    st = {
        "boxes": boxes,
        "container_plan": {
            **full,
            "can_fit": True,
            "unpacked_box_ids": [],
            "worst_mid50": 0.45,
            "cog": {"mass_in_mid50_ratio": 0.45, "balance": "warn_high", "height_ratio": 0.3},
            "cog_bundle": {"worst_mid50": 0.45},
            "weight_utilization": 0.7,
            "booking_volume_utilization": 0.3,
            "space_utilization": 0.3,
            "floor_utilization_avg": 0.4,
        },
        "packing_options": {},
        "replan_round": 1,
        "ship_replan_round": 1,
        "max_containers": 2,
        "plan": {"max_containers": 2},
    }
    ev = agent_evaluator(st)
    evaluation = (ev or {}).get("evaluation") or {}
    # mid50 soft stop: round>=1 and ship_r>=1 → should NOT need_replan solely for 0.45
    print("eval@0.45 after replan", evaluation.get("need_replan"), evaluation.get("decision"), evaluation.get("score"))

    st0 = dict(st)
    st0["replan_round"] = 0
    st0["ship_replan_round"] = 0
    ev0 = agent_evaluator(st0)
    e0 = (ev0 or {}).get("evaluation") or {}
    print("eval@0.45 first", e0.get("need_replan"), e0.get("suggestions", [])[:3])

    ok = full.get("can_fit") and mf + 1e-9 >= m0 - 0.05
    # 停损：已 replan 后 0.45 不再强制 need_replan
    ok = ok and (evaluation.get("need_replan") is not True or evaluation.get("decision") == "PASS")
    # 首轮 0.45 应触发一次
    ok = ok and e0.get("need_replan") is True
    print("---", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
