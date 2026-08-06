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
    """低填充大外廓箱：订柜有效体积用 min(outer, content×k)，体积柜不被 outer 绑架。

    N0* = max(wt, vol, geom_floor, geom_slot)：4m 不可叠架的几何下界可以 >3 柜，
    那是底面/槽位真实约束，不是虚大 outer 体积绑架（本用例外廓合计 ~354m³）。
    """
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
        "geom_f",
        b.get("containers_by_geom_floor"),
        "geom_s",
        b.get("containers_by_geom_slot"),
        "bind",
        b.get("binding_constraint"),
        "suspicious",
        b.get("volume_suspicious"),
    )
    assert b["containers_by_weight"] == 2, b
    # 有效体积应远小于 outer 353m3；体积柜不能被 outer 抬到 10+
    assert float(b["volume_m3"]) < 80, b
    assert b["containers_by_volume"] <= 3, b
    outer_m3 = float((b.get("volume_detail") or {}).get("crate_outer_m3") or 0)
    assert outer_m3 > 200, "fixture should have large hollow outer sum"
    # 体积路径未把 outer 当订舱分子 → 体积柜 << 按实心 outer 估算
    assert b["containers_by_volume"] < max(8, int(outer_m3 / 60)), b
    # N0* 可由几何抬起，但不得由「虚大体积」单独抬起
    comps = b.get("n0_components") or {}
    assert int(comps.get("volume") or 0) <= 3, comps
    assert int(b["n0"] or 0) == max(
        int(comps.get("weight") or 0),
        int(comps.get("volume") or 0),
        int(comps.get("geom_floor") or 0),
        int(comps.get("geom_slot") or 0),
        1,
    ), b
    if int(b["n0"] or 0) > 3:
        assert b.get("binding_constraint") in ("geom_floor", "geom_slot", "multi"), b
    print(
        "OK hollow outer discounted vol=",
        b["containers_by_volume"],
        "N0*=",
        b["n0"],
        "bind=",
        b.get("binding_constraint"),
    )


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


def test_four_long_frames_one_40hq() -> None:
    """4 个 ~4m 铁架应 1×40HQ 装下：条带双列全进，CoG 后 mid50 达标。

    条带初解贴端墙；R1 可能为 CTU mid50 做刚性平移（flush 时前两架质心会掉出 mid 带）。
    回归防的是旧 bug：只装 2 箱 / 多柜碎片，而不是禁止一切 x>0。
    """
    from packing_assistant.tools.bin3d import pack_boxes_api, pack_items
    from packing_assistant.tools import bin3d as B

    boxes = [
        {
            "box_id": f"F{i}",
            "outer_size_mm": {
                "length": 4350 if i < 2 else 4000,
                "width": 1100,
                "height": 1750,
            },
            "gross_weight_kg": 750,
            "stackable": False,
            "prefer_bottom": True,
            "content_m3": 1.5,
            "outer_m3": 8.0,
            "crate_fill_ratio": 0.2,
        }
        for i in range(4)
    ]
    # 条带阶段必须贴端墙双列（pack_items 无 CoG 后处理）
    items = []
    for b in boxes:
        o = b["outer_size_mm"]
        items.append(
            B.Item3D(
                box_id=str(b["box_id"]),
                dx=int(o["length"]),
                dy=int(o["width"]),
                dz=int(o["height"]),
                weight_kg=750.0,
                allow_rotate=True,
                no_tip=True,
                stackable=False,
                prefer_bottom=True,
            )
        )
    raw = pack_items(items, container_type="40HQ", max_containers=1)
    assert raw.get("can_fit") is True, raw
    assert int(raw.get("containers_used") or 0) == 1, raw
    assert len(raw.get("layout") or []) == 4, raw
    raw_xs = sorted(L["position"]["x"] for L in raw["layout"])
    assert raw_xs[0] == 0, f"条带初解应贴端墙 x=0，实际 {raw_xs}"
    assert len(set(raw_xs)) == 2, f"双列两条 x 前沿，实际 {raw_xs}"

    p = pack_boxes_api(boxes, container_type="40HQ", max_containers=1)
    assert p.get("can_fit") is True, p
    assert int(p.get("containers_used") or 0) == 1, p
    nos = {L.get("container_no") for L in (p.get("layout") or [])}
    assert nos == {1}, p.get("layout")
    assert len(p.get("layout") or []) == 4, p.get("layout")
    cog = (p.get("cog_bundle") or {}).get("primary") or p.get("cog") or {}
    mid = float(cog.get("mass_in_mid50_ratio") or 0)
    assert mid >= 0.60, f"出运 mid50 应≥0.60，实际 {mid} cog={cog}"
    print(
        "OK 4 long frames in 1×40HQ raw_xs=",
        raw_xs,
        "final_xs=",
        sorted(L["position"]["x"] for L in p["layout"]),
        "mid50=",
        mid,
    )


if __name__ == "__main__":
    test_steel_pieces_about_two()
    test_hollow_outer_not_dominate()
    test_outer_only_suspicious()
    test_auto_pack_can_fit()
    test_four_long_frames_one_40hq()
    print("ALL BOOKING REGRESSION OK")
