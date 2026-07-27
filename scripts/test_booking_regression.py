#!/usr/bin/env python3
"""
订柜回归：不写死柜数，验收「~32t 铁件类」应自主得到约 2 柜。
虚大外廓输入应触发 volume_suspicious，且订柜有效体积不被 outer 绑架到 10+。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.booking import compute_booking, pack_with_auto_containers
from packing_assistant.tools.volume_estimate import estimate_containers


def test_steel_pieces_about_two() -> None:
    """真实件尺寸量级 ~32t 铁通 → 自主约 2 柜。"""
    mats = []
    for i in range(230):
        mats.append(
            {
                "name": f"steel-{i}",
                "spec": "13—铁件",
                "length_mm": 1400,
                "width_mm": 250,
                "height_mm": 250,
                "quantity": 1,
                "weight_kg": 140,
                "total_weight_kg": 140,
            }
        )
    r = estimate_containers(materials=mats, container_type="40HQ", fill_ratio=0.82)
    assert r["containers_by_weight"] == 2, r
    assert r["containers_needed"] == 2, r
    assert r["binding_constraint"] in ("weight", "both"), r
    print("OK steel pieces N=", r["containers_needed"], "bind=", r["binding_constraint"])


def test_hollow_outer_not_dominate() -> None:
    """低填充大外廓箱：订柜用 min(outer, content×k)，不应到 10+ 柜。"""
    boxes = []
    # 67 个空心 4m 架，每架内容很小、毛重约 480 → 总 ~32t
    for i in range(67):
        boxes.append(
            {
                "box_id": f"B{i}",
                "outer_size_mm": {"length": 4000, "width": 1100, "height": 1200},
                "outer_m3": 4.0 * 1.1 * 1.2,
                "content_m3": 0.35,  # 真实内容小
                "crate_fill_ratio": 0.07,
                "gross_weight_kg": 480,
                "net_weight_kg": 400,
                "content": [
                    {
                        "name": "steel",
                        "quantity": 8,
                        "outer_size_mm": {
                            "length": 1400,
                            "width": 250,
                            "height": 100,
                        },
                    }
                ],
            }
        )
    b = compute_booking(boxes=boxes, container_type="40HQ", fill_ratio=0.82)
    print(
        "hollow booking",
        "n0",
        b["n0"],
        "wt",
        b["containers_by_weight"],
        "vol",
        b["containers_by_volume"],
        "V_eff",
        b["volume_m3"],
        "outer",
        b.get("volume_detail", {}).get("crate_outer_m3"),
        "suspicious",
        b.get("volume_suspicious"),
    )
    assert b["containers_by_weight"] == 2, b
    # 有效体积应远小于 outer 353m3
    assert float(b["volume_m3"]) < 80, b
    assert b["containers_by_volume"] <= 3, b
    assert b["n0"] <= 3, b
    print("OK hollow outer discounted N0=", b["n0"])


def test_outer_only_suspicious() -> None:
    """无 content 仅虚大 outer：应打折且可能 volume_suspicious，绝不到 10+。"""
    boxes = [
        {
            "box_id": f"H{i}",
            "outer_size_mm": {"length": 6000, "width": 2200, "height": 2200},
            "outer_m3": 6.0 * 2.2 * 2.2,
            "gross_weight_kg": 2000,
            "net_weight_kg": 1800,
            # 故意不给 content_m3 / content → 按 outer×0.45
        }
        for i in range(16)  # 毛重 32t → 重量柜 2；outer 实心 ~464m³
    ]
    b = compute_booking(boxes=boxes, container_type="40HQ", fill_ratio=0.82)
    print(
        "outer-only",
        "n0",
        b["n0"],
        "wt",
        b["containers_by_weight"],
        "vol",
        b["containers_by_volume"],
        "V_eff",
        b["volume_m3"],
        "suspicious",
        b.get("volume_suspicious"),
    )
    assert b["containers_by_weight"] == 2, b
    # 0.45×outer 仍可能抬高体积柜，但应触发可疑且远小于按实心 outer 的 10+
    assert b["n0"] < 12, b
    assert float(b["volume_m3"]) < 250, b
    # 体积柜若仍 ≥2×重量柜则必须可疑
    if b["containers_by_volume"] >= 4:
        assert b.get("volume_suspicious") is True, b
    print("OK outer-only N0=", b["n0"], "suspicious=", b.get("volume_suspicious"))


def test_auto_pack_can_fit() -> None:
    boxes = []
    for i in range(12):
        boxes.append(
            {
                "box_id": f"C{i}",
                "outer_size_mm": {"length": 2000, "width": 1100, "height": 1000},
                "content_m3": 1.0,
                "outer_m3": 2.2,
                "crate_fill_ratio": 0.45,
                "gross_weight_kg": 800,
                "stackable": True,
                "prefer_bottom": False,
                "content": [
                    {
                        "name": "p",
                        "quantity": 1,
                        "outer_size_mm": {"length": 1800, "width": 900, "height": 600},
                    }
                ],
            }
        )
    plan = pack_with_auto_containers(boxes, container_type="40HQ", n0=1, n_max=8)
    assert plan.get("can_fit") is True, plan
    assert int(plan.get("containers_used") or 0) >= 1
    print("OK auto pack used=", plan.get("containers_used"), "n0=", plan.get("n0"))


if __name__ == "__main__":
    test_steel_pieces_about_two()
    test_hollow_outer_not_dominate()
    test_outer_only_suspicious()
    test_auto_pack_can_fit()
    print("ALL BOOKING REGRESSION OK")
