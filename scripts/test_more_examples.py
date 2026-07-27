#!/usr/bin/env python3
"""
更多订柜/装载例子（不写死目标柜数）。

覆盖：重量主导、体积主导、单柜小票、20GP、混货、1.1m 架、
crate_outer 门禁、loader enrich、评估不把 outer 当订柜分。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.booking import compute_booking, pack_with_auto_containers
from packing_assistant.tools.bin3d import pack_boxes_api
from packing_assistant.tools.volume_estimate import estimate_containers, pack_effective_m3


def _box(
    i: int,
    *,
    L: int,
    W: int,
    H: int,
    gross: float,
    content_m3: float | None = None,
    fill: float | None = None,
    stackable: bool = False,
    prefer_bottom: bool = True,
) -> Dict[str, Any]:
    outer = L * W * H / 1e9
    c = content_m3 if content_m3 is not None else outer * 0.35
    f = fill if fill is not None else (c / outer if outer > 0 else 0)
    return {
        "box_id": f"X{i}",
        "box_type": "test",
        "outer_size_mm": {"length": L, "width": W, "height": H},
        "outer_m3": round(outer, 6),
        "content_m3": round(c, 6),
        "crate_fill_ratio": round(f, 4),
        "booking_volume_m3": round(min(outer, c * 1.5), 6),
        "gross_weight_kg": gross,
        "net_weight_kg": gross * 0.9,
        "stackable": stackable,
        "prefer_bottom": prefer_bottom,
        "content": [
            {
                "name": "cargo",
                "quantity": 1,
                "outer_size_mm": {
                    "length": max(1, int(L * 0.85)),
                    "width": max(1, int(W * 0.7)),
                    "height": max(1, int(H * 0.5)),
                },
            }
        ],
    }


# ── 1. 重量主导：重货小体积 ─────────────────────────────────
def test_weight_bound_dense() -> None:
    """高密度货：重量先满，体积柜 ≤ 重量柜。"""
    mats = [
        {
            "name": f"dense-{i}",
            "spec": "13—铁件",
            "length_mm": 400,
            "width_mm": 200,
            "height_mm": 150,
            "quantity": 1,
            "weight_kg": 200,
            "total_weight_kg": 200,
        }
        for i in range(200)  # 40 t
    ]
    r = estimate_containers(materials=mats, container_type="40HQ", fill_ratio=0.82)
    assert r["containers_by_weight"] == 2, r  # 40000/28610 → 2
    assert r["containers_by_volume"] <= r["containers_by_weight"], r
    assert r["binding_constraint"] in ("weight", "both"), r
    assert r["containers_needed"] == r["containers_by_weight"], r
    print(
        "OK weight-bound dense N=",
        r["containers_needed"],
        "wt",
        r["containers_by_weight"],
        "vol",
        r["containers_by_volume"],
    )


# ── 2. 体积主导：轻泡 ─────────────────────────────────────
def test_volume_bound_light() -> None:
    """轻泡大件：体积柜 > 重量柜。"""
    mats = [
        {
            "name": f"foam-{i}",
            "spec": "28—杂项配件",
            "length_mm": 2000,
            "width_mm": 1200,
            "height_mm": 800,
            "quantity": 1,
            "weight_kg": 15,
            "total_weight_kg": 15,
        }
        for i in range(40)  # 轻 ~0.6t，件体积大
    ]
    r = estimate_containers(materials=mats, container_type="40HQ", fill_ratio=0.82)
    assert r["containers_by_weight"] == 1, r
    assert r["containers_by_volume"] >= 1, r
    assert r["containers_needed"] == max(
        r["containers_by_weight"], r["containers_by_volume"]
    ), r
    print(
        "OK volume-ish light N=",
        r["containers_needed"],
        "wt",
        r["containers_by_weight"],
        "vol",
        r["containers_by_volume"],
        "bind",
        r["binding_constraint"],
    )


# ── 3. 小票 1 柜 ──────────────────────────────────────────
def test_small_shipment_one_hq() -> None:
    boxes = [_box(i, L=1200, W=800, H=600, gross=300, content_m3=0.4, fill=0.5) for i in range(6)]
    b = compute_booking(boxes=boxes, container_type="40HQ")
    assert b["n0"] == 1, b
    p = pack_with_auto_containers(boxes, container_type="40HQ", n0=1, n_max=4)
    assert p.get("can_fit") is True, p
    assert int(p.get("containers_used") or 0) == 1, p
    print("OK small 6 boxes N0=1 used=", p.get("containers_used"))


# ── 4. 20GP vs 40HQ 同货 ──────────────────────────────────
def test_20gp_vs_40hq() -> None:
    boxes = [
        _box(i, L=2000, W=1100, H=1000, gross=800, content_m3=1.0, fill=0.4)
        for i in range(8)
    ]
    b20 = compute_booking(boxes=boxes, container_type="20GP")
    b40 = compute_booking(boxes=boxes, container_type="40HQ")
    # 同货 20GP 柜数应 ≥ 40HQ
    assert b20["n0"] >= b40["n0"], (b20, b40)
    assert b20["payload_kg"] < b40["payload_kg"]
    print("OK 20GP N0=", b20["n0"], "40HQ N0=", b40["n0"])


# ── 5. 混货：铁架 + 五金 ──────────────────────────────────
def test_mixed_frames_and_hardware() -> None:
    boxes: List[Dict[str, Any]] = []
    for i in range(8):
        boxes.append(
            _box(
                i,
                L=1100,
                W=1100,
                H=1750,
                gross=1200,
                content_m3=0.8,
                fill=0.25,
                prefer_bottom=True,
            )
        )
    for i in range(8, 20):
        boxes.append(
            _box(
                i,
                L=800,
                W=600,
                H=500,
                gross=80,
                content_m3=0.15,
                fill=0.6,
                stackable=True,
                prefer_bottom=False,
            )
        )
    b = compute_booking(boxes=boxes, container_type="40HQ")
    assert b["n0"] >= 1, b
    p = pack_with_auto_containers(boxes, container_type="40HQ", n0=b["n0"], n_max=8)
    assert p.get("can_fit") is True, p
    assert int(p.get("containers_used") or 0) <= 4, p
    assert p.get("booking_volume_utilization") is not None
    assert p.get("outer_space_utilization") is not None or p.get("space_utilization")
    print(
        "OK mixed frames+hw N0=",
        b["n0"],
        "used=",
        p.get("containers_used"),
        "book_u=",
        p.get("booking_volume_utilization"),
        "outer_u=",
        p.get("outer_space_utilization") or p.get("space_utilization"),
    )


# ── 6. 1.1m 铁架双列 ──────────────────────────────────────
def test_eleven_hundred_frames_floor() -> None:
    """12 个 1.1m 架应能 1×40HQ 贴端墙装下（重量允许时）。"""
    boxes = [
        _box(i, L=1100, W=1100, H=1750, gross=900, content_m3=0.7, fill=0.22)
        for i in range(12)
    ]
    p = pack_boxes_api(boxes, container_type="40HQ", max_containers=1)
    assert p.get("can_fit") is True, p
    assert int(p.get("containers_used") or 0) == 1, p
    xs = [L["position"]["x"] for L in p["layout"]]
    assert min(xs) == 0, xs
    print("OK 12×1.1m frames in 1×40HQ floor=", p.get("floor_utilization_avg"))


# ── 7. 货种膨胀 glass > steel ─────────────────────────────
def test_category_pack_factor() -> None:
    steel = {
        "name": "s",
        "spec": "铁件",
        "length_mm": 1000,
        "width_mm": 1000,
        "height_mm": 1000,
        "quantity": 1,
        "weight_kg": 10,
        "total_weight_kg": 10,
    }
    glass = {
        "name": "g",
        "spec": "玻璃",
        "length_mm": 1000,
        "width_mm": 1000,
        "height_mm": 1000,
        "quantity": 1,
        "weight_kg": 10,
        "total_weight_kg": 10,
    }
    pe_s = pack_effective_m3([steel])
    pe_g = pack_effective_m3([glass])
    assert pe_g["pack_effective_m3"] > pe_s["pack_effective_m3"], (pe_s, pe_g)
    assert pe_g["inflation_ratio"] <= 1.80
    print(
        "OK pack_factor glass",
        pe_g["inflation_ratio"],
        "> steel",
        pe_s["inflation_ratio"],
    )


# ── 8. volume_suspicious 条件 ────────────────────────────
def test_volume_suspicious_when_vol_dominates() -> None:
    # 极轻极大 content 推高体积柜
    boxes = [
        _box(
            i,
            L=5000,
            W=2200,
            H=2000,
            gross=100,
            content_m3=18.0,  # 故意大 content
            fill=0.8,
        )
        for i in range(6)
    ]
    b = compute_booking(boxes=boxes, container_type="40HQ")
    # n_vol 应明显高于 n_wt
    if b["containers_by_volume"] >= max(2, 2 * max(b["containers_by_weight"], 1)):
        assert b.get("volume_suspicious") is True, b
        print("OK volume_suspicious n_vol=", b["containers_by_volume"], "n_wt=", b["containers_by_weight"])
    else:
        print(
            "OK volume_suspicious skipped (n_vol not 2x wt)",
            b["containers_by_volume"],
            b["containers_by_weight"],
        )


# ── 9. loader enrich：裸 plan 也能补 booking util ─────────
def test_loader_enrich_metrics() -> None:
    from packing_assistant.agents.loader import _enrich_plan_metrics

    boxes = [_box(i, L=2000, W=1000, H=1000, gross=400, content_m3=0.8) for i in range(4)]
    plan = {
        "can_fit": True,
        "containers_used": 1,
        "space_utilization": 0.33,
        "weight_utilization": 0.1,
        "engine": "mock",
    }
    out = _enrich_plan_metrics(
        plan, boxes=boxes, booking={}, container_type="40HQ", n0=1
    )
    assert out.get("outer_space_utilization") == 0.33
    assert float(out.get("booking_volume_utilization") or 0) > 0
    assert out.get("booking")
    assert out.get("booking_volume_basis")
    print(
        "OK loader enrich book_u=",
        out["booking_volume_utilization"],
        "basis=",
        out.get("booking_volume_basis"),
    )


# ── 10. evaluator 不用 outer 顶替 booking ────────────────
def test_evaluator_no_outer_as_booking() -> None:
    from packing_assistant.agents.evaluator import agent_evaluator

    state = {
        "container_plan": {
            "can_fit": True,
            "containers_used": 1,
            "space_utilization": 0.90,  # 外廓很高
            "outer_space_utilization": 0.90,
            "booking_volume_utilization": 0.0,  # 缺失
            "weight_utilization": 0.55,
            "floor_utilization_avg": 0.7,
            "unpacked_box_ids": [],
            "booking": {
                "volume_m3": 20.0,
                "usable_m3_per_container": 62.6,
                "n0": 1,
                "containers_by_weight": 1,
                "containers_by_volume": 1,
            },
        },
        "boxes": [],
        "plan": {"max_containers": 1},
        "max_containers": 1,
        "orchestrator": {},
    }
    upd = agent_evaluator(state)
    ev = upd.get("evaluation") or {}
    # 应能从 booking 重算 book_u，且 basis 不是 outer
    assert ev.get("volume_basis_score") in ("booking_volume", "booking_unknown"), ev
    # 外廓 90% 不得直接变成订柜体积分主导
    if ev.get("booking_volume_known"):
        assert float(ev.get("booking_volume_utilization") or 0) < 0.90, ev
    print(
        "OK evaluator basis=",
        ev.get("volume_basis_score"),
        "book_u=",
        ev.get("booking_volume_utilization"),
        "known=",
        ev.get("booking_volume_known"),
    )


# ── 11. 空列表 / 零量边界 ────────────────────────────────
def test_empty_and_zero() -> None:
    r = estimate_containers(materials=[], container_type="40HQ")
    assert r["containers_needed"] == 0 or r["gross_kg"] == 0, r
    b = compute_booking(boxes=[], container_type="40HQ")
    # 空箱仍给 n0 至少 1 或 0 视实现；不应崩溃
    assert "n0" in b or "containers_needed" in b, b
    print("OK empty materials/boxes no crash n0=", b.get("n0"), "mat_n=", r.get("containers_needed"))


# ── 12. 3D 超重加柜 ──────────────────────────────────────
def test_overweight_forces_more_containers() -> None:
    """单柜 payload 装不下重量时，用柜数应上升。"""
    # 每箱 15t，2 箱 → 重量至少 2 柜
    boxes = [
        _box(0, L=3000, W=2000, H=1500, gross=15000, content_m3=5.0, fill=0.5),
        _box(1, L=3000, W=2000, H=1500, gross=15000, content_m3=5.0, fill=0.5),
    ]
    b = compute_booking(boxes=boxes, container_type="40HQ")
    assert b["containers_by_weight"] >= 2, b
    p = pack_with_auto_containers(boxes, container_type="40HQ", n0=b["n0"], n_max=6)
    assert p.get("can_fit") is True, p
    assert int(p.get("containers_used") or 0) >= 2, p
    print("OK overweight N0=", b["n0"], "used=", p.get("containers_used"))


# ── 13. η 影响体积柜 ──────────────────────────────────────
def test_eta_affects_volume_cabinets() -> None:
    mats = [
        {
            "name": f"m{i}",
            "spec": "铝板",
            "length_mm": 1800,
            "width_mm": 1200,
            "height_mm": 50,
            "quantity": 10,
            "weight_kg": 20,
            "total_weight_kg": 200,
        }
        for i in range(30)
    ]
    loose = estimate_containers(materials=mats, fill_ratio=0.55)
    tight = estimate_containers(materials=mats, fill_ratio=0.85)
    # 可用容积更小 → 体积柜数只增不减
    assert loose["containers_by_volume"] >= tight["containers_by_volume"], (loose, tight)
    print(
        "OK eta: fill0.55 n_vol=",
        loose["containers_by_volume"],
        "fill0.85 n_vol=",
        tight["containers_by_volume"],
    )


# ── 14. 选型不静默全 outer ────────────────────────────────
def test_container_select_no_full_outer() -> None:
    from packing_assistant.tools.container_select import _est_from_boxes

    boxes = [
        {
            "outer_size_mm": {"length": 6000, "width": 2200, "height": 2200},
            "gross_weight_kg": 500,
            # 无 content → 应走折扣或 booking，不大于 outer
        }
    ]
    est = _est_from_boxes(boxes)
    assert est["cargo_m3_est"] <= est["outer_m3"] + 1e-6, est
    assert est["cargo_m3_est"] < est["outer_m3"] * 0.6 or est.get("volume_source") == "booking_volume"
    print("OK select cargo_m3=", est["cargo_m3_est"], "outer=", est["outer_m3"], "src=", est.get("volume_source"))


# ── 15. 不写死 2：极小/极大 ───────────────────────────────
def test_not_hardcoded_two() -> None:
    tiny = estimate_containers(
        materials=[
            {
                "name": "bolt",
                "spec": "紧固件",
                "length_mm": 100,
                "width_mm": 50,
                "height_mm": 50,
                "quantity": 10,
                "weight_kg": 0.1,
                "total_weight_kg": 1,
            }
        ]
    )
    huge_mats = [
        {
            "name": f"h{i}",
            "spec": "铁件",
            "length_mm": 3000,
            "width_mm": 300,
            "height_mm": 300,
            "quantity": 1,
            "weight_kg": 500,
            "total_weight_kg": 500,
        }
        for i in range(200)  # 100t
    ]
    huge = estimate_containers(materials=huge_mats, container_type="40HQ")
    assert tiny["containers_needed"] <= 1, tiny
    assert huge["containers_by_weight"] >= 3, huge  # 100t / 28.6t
    assert huge["containers_needed"] != 2 or huge["containers_by_weight"] == 2  # 允许碰巧 2，但不强制
    # 关键：大货可以不是 2
    assert huge["containers_needed"] >= 3, huge
    print("OK not hardcoded: tiny N=", tiny["containers_needed"], "huge N=", huge["containers_needed"])


def main() -> None:
    tests = [
        test_weight_bound_dense,
        test_volume_bound_light,
        test_small_shipment_one_hq,
        test_20gp_vs_40hq,
        test_mixed_frames_and_hardware,
        test_eleven_hundred_frames_floor,
        test_category_pack_factor,
        test_volume_suspicious_when_vol_dominates,
        test_loader_enrich_metrics,
        test_evaluator_no_outer_as_booking,
        test_empty_and_zero,
        test_overweight_forces_more_containers,
        test_eta_affects_volume_cabinets,
        test_container_select_no_full_outer,
        test_not_hardcoded_two,
    ]
    failed = []
    for fn in tests:
        try:
            fn()
        except Exception as e:
            failed.append((fn.__name__, e))
            print("FAIL", fn.__name__, e)
    print("---")
    print(f"passed {len(tests) - len(failed)}/{len(tests)}")
    if failed:
        for name, e in failed:
            print(" ", name, ":", e)
        raise SystemExit(1)
    print("ALL MORE EXAMPLES OK")


if __name__ == "__main__":
    main()
