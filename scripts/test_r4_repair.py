#!/usr/bin/env python3
"""R4：重货↔轻货 swap / 中段滑动，mid50 应提升或不恶化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.tools.cog_repair import apply_r4_repair
    from packing_assistant.tools.cog_shift import maybe_apply_r1_shift

    # 构造：部分重货容易落在端头
    boxes = []
    for i in range(8):
        boxes.append(
            {
                "box_id": f"H{i}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 1800, "width": 1000, "height": 600},
                "gross_weight_kg": 800,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
            }
        )
    for i in range(12):
        boxes.append(
            {
                "box_id": f"L{i}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 1200, "width": 800, "height": 500},
                "gross_weight_kg": 80,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
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
            "r1_shift": True,
            "r4_repair": False,  # 先不要 R4
            "clearance_mm": 20,
        },
    )
    m0 = float(base.get("worst_mid50") or (base.get("cog") or {}).get("mass_in_mid50_ratio") or 0)

    # 手动 R1 再 R4
    p1 = maybe_apply_r1_shift(base, boxes, force=True)
    m1 = float(p1.get("worst_mid50") or m0)
    p2 = apply_r4_repair(p1, boxes, target_mid50=0.55, force=True)
    m2 = float(p2.get("worst_mid50") or m1)
    r4 = p2.get("r4_repair") or {}
    st = p2.get("stacking") or {}

    # 全开 R4 的 multi 路径
    full = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r1_shift": True,
            "r4_repair": True,
            "r4_target_mid50": 0.55,
            "clearance_mm": 20,
        },
    )
    mf = float(full.get("worst_mid50") or (full.get("cog") or {}).get("mass_in_mid50_ratio") or 0)

    print(f"mid50 base={m0:.3f} after_R1={m1:.3f} after_R4={m2:.3f} full_pipeline={mf:.3f}")
    print(f"r4 stats={r4.get('per_container')}")
    print(f"stacking r4={st.get('r4_repair_applied')} r4_after={st.get('r4_mid50_after')}")
    print(f"can_fit full={full.get('can_fit')} winner={(full.get('stacking') or {}).get('multi_start_winner')}")

    ok = (
        full.get("can_fit")
        and m2 + 1e-9 >= m1 - 0.01
        and mf + 1e-9 >= m0 - 0.02
    )
    # 若 base 已经很高，R4 持平即可；若 base 偏低，期望 R4 或 full 有提升
    if m0 < 0.55:
        ok = ok and (m2 >= m0 - 0.01 or mf >= m0 + 0.02 or mf >= 0.50)
    print("---", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
