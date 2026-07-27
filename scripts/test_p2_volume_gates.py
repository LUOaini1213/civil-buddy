#!/usr/bin/env python3
"""P2 门禁/schema/双率：crate_outer 不得静默污染订柜；BoxModel 体积字段；visualizer 文案。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_crate_outer_redirected_by_default() -> None:
    from packing_assistant.tools.volume_estimate import estimate_containers

    boxes = [
        {
            "box_id": f"B{i}",
            "outer_size_mm": {"length": 4000, "width": 1100, "height": 1200},
            "outer_m3": 5.28,
            "content_m3": 0.4,
            "crate_fill_ratio": 0.08,
            "gross_weight_kg": 500,
        }
        for i in range(20)
    ]
    # 误开 crate_outer：必须改回 pack_effective，不能静默用全 outer 抬柜
    bad = estimate_containers(
        boxes=boxes,
        container_type="40HQ",
        fill_ratio=0.82,
        volume_mode="crate_outer",
        allow_crate_outer_debug=False,
    )
    good = estimate_containers(
        boxes=boxes,
        container_type="40HQ",
        fill_ratio=0.82,
        volume_mode="pack_effective",
    )
    assert bad.get("crate_outer_redirected") is True, bad
    assert bad.get("volume_source") != "crate_outer_DEBUG", bad
    assert "crate_outer" in (bad.get("warning") or "").lower() or bad.get("warnings"), bad
    # 有效体积柜数应与 pack_effective 一致量级，远小于全 outer
    assert bad["containers_by_volume"] == good["containers_by_volume"], (bad, good)
    assert bad["volume_m3"] == good["volume_m3"], (bad, good)
    # 若真用 outer：20*5.28 / (76.4*0.82) ≈ 1.7 → 至少 2；更多箱会更大
    outer_only = estimate_containers(
        boxes=boxes,
        container_type="40HQ",
        fill_ratio=0.82,
        volume_mode="crate_outer",
        allow_crate_outer_debug=True,
    )
    assert outer_only.get("volume_source") == "crate_outer_DEBUG", outer_only
    assert outer_only["volume_m3"] > bad["volume_m3"], (outer_only, bad)
    assert outer_only["containers_by_volume"] >= bad["containers_by_volume"], (
        outer_only,
        bad,
    )
    print(
        "OK crate_outer gate: redirected V=",
        bad["volume_m3"],
        "debug V=",
        outer_only["volume_m3"],
        "n_vol",
        bad["containers_by_volume"],
        "vs",
        outer_only["containers_by_volume"],
    )


def test_boxmodel_volume_fields() -> None:
    from packing_assistant.schemas import BoxModel, validate_packing_result

    # API 风格 + 体积字段
    raw = {
        "箱子列表": [
            {
                "box_id": "BOX-01",
                "box_type": "4米铁架",
                "outer_size_mm": {"length": 4000, "width": 1100, "height": 1750},
                "gross_weight_kg": 800,
                "content_m3": 1.2,
                "crate_fill_ratio": 0.16,
                "outer_m3": 7.7,
                "booking_volume_m3": 1.8,
            }
        ]
    }
    data, warns = validate_packing_result(raw)
    boxes = data.get("箱子列表") or []
    assert boxes, data
    b0 = boxes[0]
    assert b0.get("content_m3") == 1.2 or float(b0.get("content_m3") or 0) == 1.2
    assert float(b0.get("crate_fill_ratio") or 0) == 0.16
    # 缺字段应 WARN
    raw2 = {
        "箱子列表": [
            {
                "箱号": "X1",
                "箱型": "木箱",
                "外尺寸_mm": {"长": 1000, "宽": 800, "高": 600},
                "毛重_kg": 10,
            }
        ]
    }
    _, warns2 = validate_packing_result(raw2)
    assert any("体积字段" in w for w in warns2), warns2
    # model 可声明字段
    m = BoxModel.model_validate(
        {
            "箱号": "A",
            "箱型": "t",
            "外尺寸_mm": {"长": 1, "宽": 1, "高": 1},
            "content_m3": 0.5,
            "crate_fill_ratio": 0.2,
            "booking_volume_m3": 0.6,
        }
    )
    assert m.content_m3 == 0.5
    print("OK BoxModel volume fields, missing WARN=", [w for w in warns2 if "体积" in w][:1])


def test_visualizer_dual_metrics_caption() -> None:
    from packing_assistant.agents.visualizer import agent_visualizer

    state = {
        "container_plan": {
            "container_type": "40HQ",
            "layout": [
                {
                    "box_id": "B1",
                    "container_no": 1,
                    "position": {"x": 0, "y": 0, "z": 0},
                    "size": {"dx": 2000, "dy": 1100, "dz": 1000},
                    "layer": 1,
                }
            ],
            "space_utilization": 0.45,
            "outer_space_utilization": 0.45,
            "booking_volume_utilization": 0.22,
            "weight_utilization": 0.60,
            "can_fit": True,
        },
        "boxes": [{"box_id": "B1", "box_type": "铁架"}],
        "container_type": "40HQ",
    }
    out = agent_visualizer(state)
    dm = out.get("display_metrics") or {}
    assert "booking_volume_utilization" in dm, dm
    assert "outer_space_utilization" in dm, dm
    cap = dm.get("caption") or ""
    assert "订柜有效体积" in cap and "外廓摆柜" in cap, cap
    assert "外廓率≠订柜" in cap or "外廓≠" in cap or "非订柜" in cap, cap
    # 消息里不得单独把 outer 说成订柜
    msg = (out.get("messages") or [{}])[0].get("content") or ""
    assert "订柜有效体积" in msg, msg
    print("OK visualizer dual metrics:", cap[:80])


def test_adapter_preserves_volume() -> None:
    from packing_assistant.adapters import box_api_to_internal, box_internal_to_api

    api = {
        "box_id": "C1",
        "box_type": "架",
        "outer_size_mm": {"length": 1100, "width": 1100, "height": 1750},
        "content_m3": 0.9,
        "crate_fill_ratio": 0.25,
        "outer_m3": 2.1,
        "booking_volume_m3": 1.2,
        "gross_weight_kg": 100,
        "content": [
            {
                "name": "steel",
                "quantity": 2,
                "outer_size_mm": {"length": 1000, "width": 200, "height": 200},
            }
        ],
    }
    internal = box_api_to_internal(api)
    assert internal.get("content_m3") == 0.9
    assert internal.get("crate_fill_ratio") == 0.25
    assert internal.get("booking_volume_m3") == 1.2
    back = box_internal_to_api(internal)
    # 从中文内部再转出应仍带体积（若仍是内部形态会走完整映射）
    if "content_m3" in back:
        assert float(back["content_m3"]) == 0.9
    print("OK adapter volume passthrough")


if __name__ == "__main__":
    test_crate_outer_redirected_by_default()
    test_boxmodel_volume_fields()
    test_visualizer_dual_metrics_caption()
    test_adapter_preserves_volume()
    print("ALL P2 GATES OK")
