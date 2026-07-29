#!/usr/bin/env python3
"""R0 校验 + R1 平移/镜像 回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.bin3d import pack_boxes_api
    from packing_assistant.tools.cog_shift import apply_r0_r1, validate_cog_r0

    boxes = []
    for i in range(10):
        boxes.append(
            {
                "box_id": f"B{i}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 2000, "width": 1000, "height": 700},
                "gross_weight_kg": 300 + i * 20,
                "stackable": True,
                "prefer_bottom": False,
                "special_attributes": [],
            }
        )

    # 关 R0R1 的原始装
    raw = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=1,
        packing_options={
            "prefer_stack": True,
            "multi_start": False,
            "cog_aware": True,
            "r0_r1": False,
            "r1_shift": False,
            "r4_repair": False,
        },
    )
    r0_raw = validate_cog_r0(raw, boxes)
    fixed = apply_r0_r1(raw, boxes, force=True)
    r0_fix = validate_cog_r0(fixed, boxes)

    print("raw", r0_raw.get("caption"), "worst", r0_raw.get("worst_mid50"))
    print("fix", r0_fix.get("caption"), "worst", r0_fix.get("worst_mid50"))
    print("meta", (fixed.get("r0_validation") or {}).get("log"))
    print(
        "stacking",
        {
            k: (fixed.get("stacking") or {}).get(k)
            for k in (
                "r0_ok",
                "r1_applied",
                "r1_shift_applied",
                "r1_mirror_applied",
                "r0_worst_mid50_before",
                "r0_worst_mid50_after",
            )
        },
    )

    # 全开路径
    full = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=1,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "r0_r1": True,
            "r4_repair": True,
        },
    )
    print(
        "full can_fit",
        full.get("can_fit"),
        "worst_mid50",
        full.get("worst_mid50"),
        "r0",
        (full.get("r0_validation") or {}).get("after", {}).get("ok"),
    )

    ok = full.get("can_fit") and fixed.get("layout")
    # R0 结构完整
    ok = ok and "per_container" in r0_fix and r0_fix.get("method") == "r0_ctu_validate"
    # score 不恶化
    sc0 = (fixed.get("r0_validation") or {}).get("score_before")
    sc1 = (fixed.get("r0_validation") or {}).get("score_after")
    if sc0 is not None and sc1 is not None:
        ok = ok and float(sc1) <= float(sc0) + 0.5

    print("---", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
