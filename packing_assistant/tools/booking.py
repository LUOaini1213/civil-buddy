"""
自主定柜引擎（无业务目标柜数）。

N0 = max(N_weight, N_volume)
N 从 N0 起 3D 试装直至 can_fit 或达上限。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from packing_assistant.tools.volume_estimate import (
    booking_volume_from_boxes,
    estimate_containers,
)


def compute_booking(
    *,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
    fill_ratio: float = 0.82,
) -> Dict[str, Any]:
    """
    订柜初值 N0 与明细。
    有 boxes 时优先用 min(outer, content×k)；否则用材料 pack_effective。
    """
    if boxes:
        est = estimate_containers(
            boxes=list(boxes),
            container_type=container_type,
            fill_ratio=fill_ratio,
            volume_mode="pack_effective",
        )
        bv = booking_volume_from_boxes(boxes)
        est["volume_detail"] = {**(est.get("volume_detail") or {}), **bv}
        est["volume_m3"] = bv.get("booking_volume_m3", est.get("volume_m3"))
        # 用 booking_volume 重算体积柜数
        usable = float(est.get("usable_m3_per_container") or 1)
        v = float(est["volume_m3"] or 0)
        import math

        n_vol = max(1, int(math.ceil(v / usable - 1e-9))) if v > 0 else 0
        n_wt = int(est.get("containers_by_weight") or 0)
        n0 = max(n_wt, n_vol, 1)
        est["containers_by_volume"] = n_vol
        est["containers_needed"] = n0
        est["n0"] = n0
        if n_wt >= n_vol:
            est["binding_constraint"] = "weight" if n_wt > n_vol else "both"
        else:
            est["binding_constraint"] = "volume"
        # 体积可疑
        if n_vol >= max(2, 2 * max(n_wt, 1)):
            est["volume_suspicious"] = True
            est["warning"] = (
                f"体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，有效体积分子可能仍偏虚，"
                f"请核对箱填充率/尺寸来源"
            )
        else:
            est["volume_suspicious"] = False
        return est

    est = estimate_containers(
        materials=list(materials or []),
        container_type=container_type,
        fill_ratio=fill_ratio,
        volume_mode="pack_effective",
    )
    est["n0"] = int(est.get("containers_needed") or 1)
    n_vol = int(est.get("containers_by_volume") or 0)
    n_wt = int(est.get("containers_by_weight") or 0)
    est["volume_suspicious"] = n_vol >= max(2, 2 * max(n_wt, 1))
    if est["volume_suspicious"]:
        est["warning"] = (
            f"体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，请核对材料尺寸/包装膨胀"
        )
    return est


def pack_with_auto_containers(
    boxes: List[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    n0: Optional[int] = None,
    n_max: int = 40,
    priority_order: Optional[List[str]] = None,
    fill_ratio: float = 0.82,
) -> Dict[str, Any]:
    """
    从 N0 起递增 max_containers 直到 can_fit 或达 n_max。
    返回 container_plan + booking 元数据。
    """
    from packing_assistant.tools.bin3d import pack_boxes_api

    booking = compute_booking(
        boxes=boxes, container_type=container_type, fill_ratio=fill_ratio
    )
    start = int(n0 or booking.get("n0") or booking.get("containers_needed") or 1)
    start = max(1, min(start, n_max))
    last = None
    tried = []
    for n in range(start, n_max + 1):
        plan = pack_boxes_api(
            boxes,
            container_type=container_type,
            max_containers=n,
            priority_order=priority_order,
        )
        tried.append(
            {
                "n": n,
                "can_fit": plan.get("can_fit"),
                "used": plan.get("containers_used"),
                "unpacked": len(plan.get("unpacked_box_ids") or []),
            }
        )
        last = plan
        if plan.get("can_fit"):
            break

    if last is None:
        last = {
            "can_fit": False,
            "containers_used": 0,
            "engine": "none",
            "unpacked_box_ids": [b.get("box_id") for b in boxes],
        }

    last["booking"] = booking
    last["n0"] = start
    last["n_tried"] = tried
    last["auto_containers"] = True
    # 订柜体积利用率（有效体积 / (用柜×可用容积)）
    used = int(last.get("containers_used") or 0) or start
    usable = float(booking.get("usable_m3_per_container") or 1) * used
    v_eff = float(booking.get("volume_m3") or 0)
    last["booking_volume_utilization"] = (
        round(min(v_eff / usable, 9.99), 4) if usable > 0 else 0.0
    )
    last["outer_space_utilization"] = last.get("space_utilization")
    return last
