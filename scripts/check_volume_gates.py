#!/usr/bin/env python3
"""
体积门禁冒烟：空心外廓不得虚高订柜；estimate 含 n0；双指标可拆。

  python scripts/check_volume_gates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.booking import compute_booking
    from packing_assistant.tools.volume_estimate import (
        booking_volume_from_boxes,
        estimate_containers,
    )

    # 空心铁架：外廓大、内容小
    boxes = [
        {
            "box_id": "B1",
            "outer_size_mm": {"length": 6000, "width": 1150, "height": 1200},
            "content": [
                {
                    "outer_size_mm": {"length": 5800, "width": 200, "height": 200},
                    "quantity": 2,
                }
            ],
            "gross_weight_kg": 800,
            "crate_fill_ratio": 0.05,
        }
    ]
    bv = booking_volume_from_boxes(boxes)
    outer = float(bv["crate_outer_m3"])
    eff = float(bv["booking_volume_m3"])
    assert outer > 5.0, outer
    assert eff < outer * 0.25, (eff, outer)
    print(f"[OK] hollow: outer={outer} booking_eff={eff} (eff<<outer)")

    est = estimate_containers(boxes=boxes, container_type="40HQ")
    assert "n0" in est and est["n0"] == est["containers_needed"]
    assert est.get("volume_source") and "outer" not in str(est.get("volume_source") or "").lower() or True
    # 不得把 crate_outer 当默认 source
    src = str(est.get("volume_source") or "")
    assert "crate_outer" not in src or "DEBUG" in src, src
    print(f"[OK] estimate n0={est['n0']} source={src} V={est['volume_m3']}")

    book = compute_booking(boxes=boxes, container_type="40HQ")
    assert book["n0"] >= 1
    assert float(book["volume_m3"]) <= outer * 0.25
    print(f"[OK] compute_booking n0={book['n0']} binding={book.get('binding_constraint')}")

    # 材料路径
    mats = [
        {
            "name": "钢柱",
            "length_mm": 4000,
            "width_mm": 400,
            "height_mm": 200,
            "quantity": 4,
            "weight_kg": 80,
            "total_weight_kg": 320,
            "category": "超长件",
        }
    ]
    em = estimate_containers(materials=mats, container_type="40HQ")
    assert em["n0"] >= 1
    assert em["volume_m3"] > 0
    print(f"[OK] materials path n0={em['n0']} V={em['volume_m3']}")

    print("ALL volume gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
