#!/usr/bin/env python3
"""R1a：mid50 已达标且贴端墙时不纵向拉开；横向仍可修偏心。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.cog_shift import shift_layout_to_mass_center

    # 贴 x=0 且整坨跨过 mid 带 → mid50 已达标：纵向应保持 0
    layout = [
        {
            "box_id": "A",
            "container_no": 1,
            "position": {"x": 0, "y": 100, "z": 0},
            "size": {"dx": 7000, "dy": 1100, "dz": 1000},
            "gross_weight_kg": 1000,
        },
        {
            "box_id": "B",
            "container_no": 1,
            "position": {"x": 0, "y": 1200, "z": 0},
            "size": {"dx": 7000, "dy": 1100, "dz": 1000},
            "gross_weight_kg": 1000,
        },
        {
            "box_id": "C",
            "container_no": 1,
            "position": {"x": 7000, "y": 100, "z": 0},
            "size": {"dx": 3000, "dy": 1100, "dz": 1000},
            "gross_weight_kg": 1000,
        },
        {
            "box_id": "D",
            "container_no": 1,
            "position": {"x": 7000, "y": 1200, "z": 0},
            "size": {"dx": 3000, "dy": 1100, "dz": 1000},
            "gross_weight_kg": 1000,
        },
    ]
    boxes = [
        {"box_id": bid, "gross_weight_kg": 1000}
        for bid in ("A", "B", "C", "D")
    ]
    plan = {"layout": layout, "container_type": "40HQ", "containers_used": 1}
    out = shift_layout_to_mass_center(plan, boxes, shift_longitudinal=True, shift_lateral=True)
    xs = [int(it["position"]["x"]) for it in out["layout"]]
    assert min(xs) == 0, f"mid50 OK + wall flush must keep x=0, got {xs}"
    meta = (out.get("r1_shift") or {}).get("per_container") or []
    assert meta and meta[0].get("dx_mm", 1) == 0, meta
    print("PASS cog_shift mid_ok wall_flush xs=", sorted(set(xs)), "dy=", meta[0].get("dy_mm"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
