#!/usr/bin/env python3
"""LNS 最差柜 + 重量配额 + 横偏修理 回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.tools.cog_lns import apply_lns_worst_container
    from packing_assistant.tools.cog_lateral import apply_lateral_repair

    boxes = []
    for i in range(10):
        boxes.append(
            {
                "box_id": f"H{i}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 1600, "width": 1000, "height": 600},
                "gross_weight_kg": 700 + i * 10,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
            }
        )
    for i in range(20):
        boxes.append(
            {
                "box_id": f"L{i}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 1000, "width": 700, "height": 500},
                "gross_weight_kg": 50 + i,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
            }
        )

    # 关后处理的 baseline
    base = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=3,
        packing_options={
            "prefer_stack": True,
            "multi_start": False,
            "cog_aware": True,
            "r0_r1": False,
            "r2_slab": False,
            "r4_repair": False,
            "r3_repack": False,
            "lns_worst": False,
            "lateral_repair": False,
        },
    )
    m0 = float(base.get("worst_mid50") or 0)
    lat0 = float((base.get("cog") or {}).get("lateral_eccentricity") or 0)
    print(f"base mid50={m0:.3f} lat={lat0:.3f} used={base.get('containers_used')} can_fit={base.get('can_fit')}")

    lns = apply_lns_worst_container(base, boxes, target_mid50=0.55, force=True)
    m_lns = float(lns.get("worst_mid50") or m0)
    print(f"LNS mid50={m_lns:.3f} applied={(lns.get('stacking') or {}).get('lns_applied')}")

    lat_p = apply_lateral_repair(lns, boxes, lat_threshold=0.05, force=True)
    lat1 = float((lat_p.get("cog") or {}).get("lateral_eccentricity") or lat0)
    print(f"lateral lat={lat1:.3f} applied={(lat_p.get('stacking') or {}).get('lateral_repair_applied')}")

    full = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=3,
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
            "r4_target_mid50": 0.55,
        },
    )
    mf = float(full.get("worst_mid50") or 0)
    latf = float((full.get("cog") or {}).get("lateral_eccentricity") or 0)
    print(
        f"full mid50={mf:.3f} lat={latf:.3f} used={full.get('containers_used')} "
        f"can_fit={full.get('can_fit')} stack={((full.get('stacking') or {}))}"
    )

    ok = full.get("can_fit") is True
    ok = ok and (mf + 1e-9 >= m0 - 0.05 or mf >= 0.50)
    ok = ok and (latf <= lat0 + 0.05 or latf < 0.15)
    print("---", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
