#!/usr/bin/env python3
"""Hollow outer must not dominate booking volume; geom may raise N0*."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main() -> int:
    from packing_assistant.tools.booking import compute_booking
    boxes = []
    for i in range(20):
        boxes.append({
            "box_id": f"H{i}",
            "outer_size_mm": {"length": 4000, "width": 1100, "height": 1200},
            "outer_m3": 5.28,
            "content_m3": 0.35,
            "crate_fill_ratio": 0.07,
            "gross_weight_kg": 480,
        })
    b = compute_booking(boxes=boxes, container_type="40HQ", fill_ratio=0.82)
    assert float(b["volume_m3"]) < float(b.get("volume_detail",{}).get("crate_outer_m3") or 999)
    assert int(b["containers_by_volume"]) <= 2
    comps = b.get("n0_components") or {}
    assert int(comps.get("volume") or 0) <= 2
    assert int(b["n0"]) == max(int(comps.get(k) or 0) for k in ("weight","volume","geom_floor","geom_slot"))
    print("PASS hollow_volume_not_dominate n0=", b["n0"], "vol=", b["containers_by_volume"], "bind=", b.get("binding_constraint"))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
