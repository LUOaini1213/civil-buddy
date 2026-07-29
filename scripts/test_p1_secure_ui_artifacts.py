#!/usr/bin/env python3
"""P1：secure_work_order + packing_plan per_cabin / r_pipeline 冒烟。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.tools.secure_work_order import build_secure_work_order
    from packing_assistant.packing_plan import build_packing_plan

    boxes = []
    # 重件触发 0.25P（40HQ payload≈28610 → 0.25≈7152）
    boxes.append(
        {
            "box_id": "HEAVY1",
            "outer_size_mm": {"length": 3000, "width": 1100, "height": 1200},
            "gross_weight_kg": 8000,
            "net_weight_kg": 7800,
            "stackable": False,
            "prefer_bottom": True,
            "structure_conclusion": "通过",
            "special_attributes": ["超长"],
        }
    )
    for i in range(12):
        boxes.append(
            {
                "box_id": f"L{i}",
                "outer_size_mm": {"length": 1200, "width": 800, "height": 600},
                "gross_weight_kg": 120 + i * 5,
                "stackable": True,
                "structure_conclusion": "通过",
                "special_attributes": [],
            }
        )

    plan = pack_boxes_api(
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
            "lns_worst": True,
            "lateral_repair": True,
        },
    )
    assert plan.get("can_fit") is True, plan.get("unpacked_box_ids")

    swo = build_secure_work_order(plan, boxes)
    assert swo.get("blocks_ship_ok") is False
    assert swo.get("schema") == "secure.work_order.v1"
    assert any(p.get("type") == "pad_beam" for p in (swo.get("pad_beams") or [])), swo
    print("PASS secure pad_beam", swo.get("summary"))

    pp = build_packing_plan(
        {
            "container_plan": plan,
            "boxes": boxes,
            "packing_options": {"cog_aware": True},
            "evaluation": {"score": 80, "decision": "PASS"},
            "risk_report": {"decision": "WARN", "ship_ok": True},
            "secure_work_order": swo,
        }
    )
    assert "per_cabin_cog" in pp
    assert "r_pipeline" in pp
    assert pp.get("secure_work_order", {}).get("items")
    steps = [r.get("step") for r in pp.get("r_pipeline") or []]
    assert "R0" in steps and "LNS" in steps and "LAT" in steps, steps
    print(
        "PASS packing_plan",
        "cabins",
        len(pp.get("per_cabin_cog") or []),
        "r",
        steps,
        "sec_items",
        len(pp["secure_work_order"]["items"]),
    )
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
