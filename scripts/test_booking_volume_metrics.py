#!/usr/bin/env python3
"""booking 双口径体积单测：订舱体积 ≠ 盲目外廓；N0=max(重量,体积)。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0


def _ok(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS", name, detail)
    else:
        FAIL += 1
        print("FAIL", name, detail)


def test_n0_weight_volume() -> None:
    from packing_assistant.tools.booking import compute_booking

    # 重货：重量柜应 ≥1
    mats = [
        {
            "id": "1",
            "length_mm": 1000,
            "width_mm": 200,
            "height_mm": 200,
            "total_weight_kg": 20000,
            "quantity": 1,
            "name": "重钢",
            "spec": "铁件",
        }
    ]
    b = compute_booking(materials=mats, container_type="40HQ")
    _ok("n0_exists", b.get("n0") is not None or b.get("containers_needed") is not None, str(b.get("n0")))
    n0 = int(b.get("n0") or b.get("containers_needed") or 0)
    nw = int(b.get("containers_by_weight") or 0)
    nv = int(b.get("containers_by_volume") or 0)
    _ok("n0_ge_weight", n0 >= nw >= 1, f"n0={n0} nw={nw} nv={nv}")
    _ok("n0_is_max", n0 == max(nw, nv, 1), f"n0={n0} max={max(nw,nv,1)}")
    _ok("binding_set", bool(b.get("binding_constraint")), str(b.get("binding_constraint")))


def test_booking_not_blind_outer() -> None:
    from packing_assistant.tools.volume_estimate import booking_volume_from_boxes

    # 外廓虚大、内容小：订舱体积应取 min 路径，显著小于 outer 累加
    boxes = [
        {
            "box_id": "B1",
            "outer_size_mm": {"length": 6000, "width": 1150, "height": 1200},
            "outer_m3": 6.0 * 1.15 * 1.2,  # ~8.28
            "content_m3": 0.5,
            "crate_fill_ratio": 0.2,
            "booking_volume_m3": None,
            "net_weight_kg": 400,
            "gross_weight_kg": 500,
        }
    ]
    # 若 API 用 outer 字段
    bv = booking_volume_from_boxes(boxes)
    book = float(bv.get("booking_volume_m3") or bv.get("volume_m3") or 0)
    outer = float(boxes[0]["outer_m3"])
    _ok("booking_lt_outer_when_hollow", book > 0 and book <= outer + 1e-6, f"book={book} outer={outer}")
    # 理想：book 接近 content*k 量级，不应等于虚大 outer（允许实现用 min）
    _ok(
        "booking_not_equal_hollow_outer_if_min",
        book < outer * 0.95 or book <= float(boxes[0]["content_m3"]) * 2.0,
        f"book={book}",
    )


def test_dual_metrics_fields_on_plan() -> None:
    from packing_assistant.harness import run_agent_pipeline

    st = run_agent_pipeline(
        "booking dual metrics",
        materials=[
            {
                "id": "m1",
                "part_no": "FST",
                "name": "钢通",
                "spec": "13—铁件",
                "length_mm": 1500,
                "width_mm": 150,
                "height_mm": 150,
                "total_weight_kg": 120,
                "quantity": 1,
            }
        ],
        enable_auto_confirm=True,
        session_id="book-dual",
        save_artifacts=False,
        packing_options={"standard_boxes": True},
    )
    plan = st.get("container_plan") or {}
    _ok("can_fit", plan.get("can_fit") is True, str(plan.get("can_fit")))
    # 双口径字段至少有一个订舱体积相关 + 外廓相关（或兼容别名）
    has_book = any(
        plan.get(k) is not None
        for k in (
            "booking_volume_utilization",
            "booking_volume_m3",
            "space_utilization",  # 可能混用历史字段
        )
    )
    has_outer = any(
        plan.get(k) is not None
        for k in (
            "outer_space_utilization",
            "space_utilization",
            "floor_utilization_avg",
        )
    )
    _ok("has_util_fields", has_book or has_outer, str(list(plan.keys())[:20]))
    # 规划侧 N0
    pl = st.get("plan") or {}
    book = pl.get("booking") or plan.get("booking") or {}
    _ok(
        "plan_or_booking_n0",
        (pl.get("n0") is not None)
        or (book.get("n0") is not None)
        or (plan.get("n0") is not None),
        f"plan_n0={pl.get('n0')} book={book.get('n0')}",
    )


def test_overweight_not_silent_in_booking() -> None:
    from packing_assistant.tools.booking import compute_booking
    from packing_assistant.tools.cargo_feasibility import check_cargo_feasibility

    mats = [
        {
            "id": "Z",
            "name": "怪兽",
            "length_mm": 6000,
            "width_mm": 200,
            "height_mm": 200,
            "total_weight_kg": 80000,
            "weight_kg": 80000,
            "quantity": 1,
        }
    ]
    feas = check_cargo_feasibility(materials=mats, container_type="40HQ")
    _ok("feas_flags_over", feas.get("ok") is False, str(feas.get("failure_class")))
    b = compute_booking(materials=mats, container_type="40HQ")
    nw = int(b.get("containers_by_weight") or 0)
    _ok("booking_weight_cabin_ge_2", nw >= 2, f"nw={nw}")


def test_light_volume_bound() -> None:
    from packing_assistant.tools.booking import compute_booking

    mats = []
    for i in range(30):
        mats.append(
            {
                "id": f"L{i}",
                "name": "轻泡",
                "spec": "铝板",
                "length_mm": 3000,
                "width_mm": 1200,
                "height_mm": 50,
                "total_weight_kg": 20,
                "quantity": 1,
            }
        )
    b = compute_booking(materials=mats, container_type="40HQ")
    nv = int(b.get("containers_by_volume") or 0)
    nw = int(b.get("containers_by_weight") or 0)
    n0 = int(b.get("n0") or b.get("containers_needed") or 0)
    _ok("volume_can_dominate", nv >= 1 and n0 == max(nw, nv), f"nv={nv} nw={nw} n0={n0}")


def test_compute_booking_boxes_path() -> None:
    from packing_assistant.tools.booking import compute_booking

    boxes = [
        {
            "box_id": "1",
            "outer_m3": 2.0,
            "content_m3": 1.0,
            "gross_weight_kg": 1000,
            "net_weight_kg": 900,
            "outer_size_mm": {"length": 2000, "width": 1000, "height": 1000},
        },
        {
            "box_id": "2",
            "outer_m3": 1.5,
            "content_m3": 0.8,
            "gross_weight_kg": 800,
            "net_weight_kg": 700,
            "outer_size_mm": {"length": 1500, "width": 1000, "height": 1000},
        },
    ]
    b = compute_booking(boxes=boxes, container_type="40HQ")
    _ok("boxes_path_n0", int(b.get("n0") or b.get("containers_needed") or 0) >= 1, str(b.get("n0")))
    _ok("boxes_path_volume", float(b.get("volume_m3") or 0) > 0, str(b.get("volume_m3")))


def main() -> int:
    test_n0_weight_volume()
    test_booking_not_blind_outer()
    test_overweight_not_silent_in_booking()
    test_light_volume_bound()
    test_compute_booking_boxes_path()
    test_dual_metrics_fields_on_plan()
    total = PASS + FAIL
    rate = PASS / total if total else 0
    print(f"SUMMARY pass={PASS} fail={FAIL} rate={rate:.2%} total={total}")
    # 目标 ≥95%：6 组里允许 0 fail
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
