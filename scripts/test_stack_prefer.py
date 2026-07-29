#!/usr/bin/env python3
"""P0 叠高 + CTU 纵中 60/50 / multi_start CoG 回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.bin3d import pack_boxes_api
from packing_assistant.tools.cog import cog_for_layout


def _boxes(n: int = 12, h: int = 800, w_kg: float = 120.0, stackable: bool = True):
    out = []
    for i in range(n):
        out.append(
            {
                "box_id": f"S{i+1:02d}",
                "box_type": "木箱",
                "outer_size_mm": {"length": 2200, "width": 1100, "height": h},
                "gross_weight_kg": w_kg,
                "stackable": stackable,
                "prefer_bottom": False,
                "special_attributes": [],
            }
        )
    return out


def main() -> int:
    opts = {
        "prefer_stack": True,
        "clearance_mm": 30,
        "support_ratio_min": 0.55,
        "max_stack_layers": 3,
        "prefer_bottom_weight_kg": 2000,
        "multi_start": False,  # 固定叠高路径，便于断言
        "cog_aware": True,
    }
    boxes = _boxes(12, h=800, w_kg=150)
    plan = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=2,
        packing_options=opts,
    )
    layout = plan.get("layout") or []
    zs = [int((p.get("position") or {}).get("z") or 0) for p in layout]
    stacked = sum(1 for z in zs if z > 0)
    st = plan.get("stacking") or {}
    cog = plan.get("cog") or cog_for_layout(
        layout, container_type="40HQ", boxes=boxes
    ) or {}
    print("=== prefer_stack ON ===")
    print(
        f"can_fit={plan.get('can_fit')} used={plan.get('containers_used')} "
        f"boxes={len(layout)} stacked={stacked} max_z={max(zs) if zs else 0}"
    )
    print(f"space={plan.get('space_utilization')} stacking={st}")
    print(
        f"cog mid50={cog.get('mass_in_mid50_ratio')} mid50_ok={cog.get('mid50_ok')} "
        f"long={cog.get('longitudinal_position')} bal={cog.get('balance')} "
        f"h={cog.get('height_ratio')}"
    )
    for p in layout[:6]:
        pos = p.get("position") or {}
        print(
            f"  {p.get('box_id')} x={pos.get('x')} z={pos.get('z')} layer={p.get('layer')}"
        )

    plan_off = pack_boxes_api(
        _boxes(12, h=800, w_kg=150, stackable=False),
        container_type="40HQ",
        max_containers=4,
        packing_options={**opts, "prefer_stack": False},
    )
    zs_off = [int((p.get("position") or {}).get("z") or 0) for p in (plan_off.get("layout") or [])]
    stacked_off = sum(1 for z in zs_off if z > 0)
    print("=== stackable=False ===")
    print(
        f"can_fit={plan_off.get('can_fit')} used={plan_off.get('containers_used')} "
        f"stacked={stacked_off}"
    )

    plan_mid = pack_boxes_api(
        _boxes(8, h=900, w_kg=1200),
        container_type="40HQ",
        max_containers=3,
        packing_options=opts,
    )
    zs_mid = [int((p.get("position") or {}).get("z") or 0) for p in (plan_mid.get("layout") or [])]
    stacked_mid = sum(1 for z in zs_mid if z > 0)
    print("=== mid weight 1200kg ===")
    print(
        f"can_fit={plan_mid.get('can_fit')} used={plan_mid.get('containers_used')} "
        f"stacked={stacked_mid}"
    )

    # multi_start CoG：应挂 cog 且 winner 有记录
    plan_ms = pack_boxes_api(
        _boxes(10, h=800, w_kg=180),
        container_type="40HQ",
        max_containers=2,
        packing_options={**opts, "multi_start": True},
    )
    st_ms = plan_ms.get("stacking") or {}
    cog_ms = plan_ms.get("cog") or {}
    mid50 = float(cog_ms.get("mass_in_mid50_ratio") or cog.get("mass_in_mid50_ratio") or 0)
    long_pos = float(cog_ms.get("longitudinal_position") or cog.get("longitudinal_position") or 0)
    print("=== multi_start CoG ===")
    print(
        f"winner={st_ms.get('multi_start_winner')} multi_cog={st_ms.get('multi_start_cog')} "
        f"mid50={cog_ms.get('mass_in_mid50_ratio')} long={cog_ms.get('longitudinal_position')} "
        f"bal={cog_ms.get('balance')}"
    )

    # 断言：仍能叠高；禁叠不叠；纵中 mid50 明显改善（≥0.45 或 long∈[0.30,0.70]）
    cog_ok = mid50 >= 0.45 or (0.30 <= long_pos <= 0.70)
    ok = (
        stacked >= 4
        and stacked_off == 0
        and stacked_mid >= 1
        and cog_ok
        and st_ms.get("multi_start_cog") is True
    )
    print(
        "---",
        "PASS" if ok else "FAIL",
        f"(stacked={stacked}, mid={stacked_mid}, unstack={stacked_off==0}, "
        f"mid50={mid50:.2f}, long={long_pos:.2f})",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())