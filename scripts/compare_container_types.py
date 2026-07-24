#!/usr/bin/env python3
"""同一票货对比 20GP / 40GP / 40HQ 利用率。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.harness import run_pipeline
from packing_assistant.tools.bin3d import CONTAINER_INNER


def main() -> int:
    mats = [
        {
            "id": "M001",
            "name": "镀锌钢通",
            "quantity": 20,
            "weight_kg": 45,
            "total_weight_kg": 900,
            "length_mm": 2500,
            "width_mm": 250,
            "height_mm": 250,
        },
        {
            "id": "M002",
            "name": "镀锌钢通长件",
            "quantity": 8,
            "weight_kg": 85,
            "total_weight_kg": 680,
            "length_mm": 4200,
            "width_mm": 250,
            "height_mm": 250,
        },
        {
            "id": "M003",
            "name": "幕墙支撑",
            "quantity": 6,
            "weight_kg": 70,
            "total_weight_kg": 420,
            "length_mm": 3800,
            "width_mm": 300,
            "height_mm": 200,
        },
        {
            "id": "M004",
            "name": "铁垫片",
            "quantity": 200,
            "weight_kg": 0.2,
            "total_weight_kg": 40,
            "length_mm": 150,
            "width_mm": 100,
            "height_mm": 10,
        },
        {
            "id": "M005",
            "name": "短支撑",
            "quantity": 15,
            "weight_kg": 18,
            "total_weight_kg": 270,
            "length_mm": 800,
            "width_mm": 150,
            "height_mm": 150,
        },
    ]

    print("同一票：净重约 2310 kg，最长件 4200 mm")
    print()
    rows = []
    for ct in ("20GP", "40GP", "40HQ"):
        st = run_pipeline(
            raw_input=ct,
            materials=mats,
            container_type=ct,
            enable_auto_confirm=True,
            max_containers=3,
        )
        p = st.get("container_plan") or {}
        boxes = st.get("boxes") or []
        gross = sum(float(b.get("gross_weight_kg") or 0) for b in boxes)
        spec = CONTAINER_INNER[ct]
        vol = spec["L"] * spec["W"] * spec["H"] / 1e9
        rows.append(
            {
                "type": ct,
                "vol_m3": vol,
                "max_kg": spec["max_load_kg"],
                "boxes": len(boxes),
                "fit": p.get("can_fit"),
                "used": p.get("containers_used"),
                "space": p.get("space_utilization"),
                "floor": p.get("floor_utilization_avg"),
                "wt": p.get("weight_utilization"),
                "cargo_m3": p.get("cargo_solid_volume_m3"),
                "gross": gross,
                "unpacked": p.get("unpacked_box_ids") or [],
            }
        )
        print(f"=== {ct}  内尺寸 {spec['L']:.0f}×{spec['W']:.0f}×{spec['H']:.0f} mm")
        print(f"    柜容 {vol:.1f} m³  载重上限 {spec['max_load_kg']:.0f} kg")
        print(
            f"    boxes={len(boxes)} can_fit={p.get('can_fit')} used={p.get('containers_used')} "
            f"gross≈{gross:.0f}kg"
        )
        print(
            f"    容积={p.get('space_utilization')} 底面积={p.get('floor_utilization_avg')} "
            f"重量={p.get('weight_utilization')} 货实心={p.get('cargo_solid_volume_m3')}m³"
        )
        if p.get("unpacked_box_ids"):
            print(f"    未装入: {p.get('unpacked_box_ids')}")
        print()

    # 建议
    ok = [r for r in rows if r["fit"] and (r["used"] or 1) == 1]
    if ok:
        best = max(ok, key=lambda r: (r["space"] or 0) + (r["wt"] or 0))
        print(
            f"建议：在能 1 柜装下的前提下，优先 {best['type']} "
            f"（容积 {best['space']:.0%} + 重量 {best['wt']:.0%} 更均衡）"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
