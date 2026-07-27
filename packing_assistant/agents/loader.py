"""Agent5 装载执行：自 N0 递增柜数至 can_fit；skjolber → python-laff-3d → 1D。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.adapters import boxes_to_internal
from packing_assistant.skjolber_client import is_skjolber_configured, pack_via_skjolber
from packing_assistant.state import PackingState
from packing_assistant.tools.bin3d import pack_boxes_api
from packing_assistant.tools.consolidation import run_consolidation


def agent_loader(state: PackingState) -> Dict[str, Any]:
    boxes = list(state.get("boxes") or [])
    plan = state.get("plan") or {}
    ctype = plan.get("container_type") or state.get("container_type") or "40HQ"
    priority = plan.get("priority_order") or []
    booking = plan.get("booking") or state.get("booking") or {}
    n0 = int(
        plan.get("n0")
        or booking.get("n0")
        or booking.get("containers_needed")
        or 1
    )
    n0 = max(1, n0)
    # 搜索上限：plan 已带 headroom；state.max_containers 仅作用户封顶（非目标柜数）
    # 禁止把 n_max 压成 n0，否则几何失败无法自动加柜
    plan_cap = int(plan.get("max_containers") or 0)
    user_cap = int(state.get("max_containers") or 0)
    n_max = plan_cap if plan_cap > 0 else min(40, n0 + 8)
    if user_cap > 0:
        # 用户封顶不得低于 N0，也不得把搜索窗口缩成单点（至少 N0..N0 若 cap==N0 则只试 N0）
        n_max = max(n0, min(user_cap, 40)) if user_cap >= n0 else max(n0, n_max)
    n_max = max(n0, min(n_max, 40))
    # 若 cap 意外等于 n0 且无显式「只要一柜」意图，仍留 headroom（replan 前的安全垫）
    if n_max == n0 and user_cap <= 0:
        n_max = min(40, n0 + 8)

    if priority:
        order = {bid: i for i, bid in enumerate(priority)}
        boxes = sorted(boxes, key=lambda b: order.get(b.get("box_id"), 999))

    notes: List[str] = []
    container_plan: Dict[str, Any] | None = None

    # 1) 自主定柜：N0 起递增 3D（主路径）
    try:
        from packing_assistant.tools.booking import pack_with_auto_containers

        container_plan = pack_with_auto_containers(
            boxes,
            container_type=str(ctype),
            n0=n0,
            n_max=n_max,
            priority_order=priority or None,
            fill_ratio=0.82,
        )
        notes.append(
            f"auto_N0={n0}->used={container_plan.get('containers_used')} "
            f"booking_vol_util={container_plan.get('booking_volume_utilization')}"
        )
        notes.append(container_plan.get("engine") or "python-laff-3d")
    except Exception as e:
        notes.append(f"auto_booking失败: {e}")
        container_plan = None

    # 2) skjolber 可选覆盖（固定 max=最终 used 或 n0）
    if container_plan is None and is_skjolber_configured():
        try:
            mc = n0
            container_plan = pack_via_skjolber(
                boxes,
                {
                    **plan,
                    "container_type": ctype,
                    "max_containers": mc,
                },
                request_id=str(state.get("run_id") or state.get("packing_plan_id") or ""),
            )
            notes.append(container_plan.get("engine") or "skjolber")
        except Exception as e:
            notes.append(f"skjolber不可用: {e}")

    # 3) 兜底
    if container_plan is None:
        try:
            container_plan = pack_boxes_api(
                boxes,
                container_type=ctype,
                max_containers=n0,
                priority_order=priority or None,
            )
            notes.append(container_plan.get("engine") or "python-laff-3d")
        except Exception as e:
            notes.append(f"python3d失败: {e}")
            container_plan = _local_1d(boxes, ctype)
            notes.append("local-1d-fallback")

    # 指标拆分文案
    outer_u = float(container_plan.get("space_utilization") or 0)
    book_u = float(container_plan.get("booking_volume_utilization") or 0)
    n0_used = container_plan.get("n0") or n0
    return {
        "container_plan": container_plan,
        "booking": container_plan.get("booking") or booking,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"装载完成 engine={container_plan.get('engine')} "
                    f"can_fit={container_plan.get('can_fit')} "
                    f"用柜={container_plan.get('containers_used')}(自N0={n0_used}递增) "
                    f"外廓摆柜率{outer_u:.0%} "
                    f"订柜有效体积率{book_u:.0%} "
                    f"货外廓{float(container_plan.get('cargo_solid_volume_m3') or 0):.2f}m³/"
                    f"柜{float(container_plan.get('container_inner_volume_m3') or 0):.1f}m³ "
                    f"底面积{float(container_plan.get('floor_utilization_avg') or 0):.0%} "
                    f"重量{float(container_plan.get('weight_utilization') or 0):.0%} "
                    f"[{'; '.join(notes)}]"
                ),
            }
        ],
    }


def _local_1d(boxes: List[Dict[str, Any]], ctype: str) -> Dict[str, Any]:
    internal = boxes_to_internal(boxes)
    raw = run_consolidation(internal, container_type=ctype)
    layout_api: List[Dict[str, Any]] = []
    detail = raw.get("详情") or {}
    overflow = set(detail.get("溢出箱号") or [])
    unpacked: List[str] = []

    for item in raw.get("布局") or []:
        bid = item.get("箱号") or ""
        box = next((b for b in boxes if b.get("box_id") == bid), {})
        outer = box.get("outer_size_mm") or {}
        start_m = float(item.get("起始位置_m") or 0)
        length_m = float(item.get("长度_m") or 0)
        if bid in overflow:
            unpacked.append(bid)
        layout_api.append(
            {
                "box_id": bid,
                "container_no": 1,
                "position": {"x": int(round(start_m * 1000)), "y": 0, "z": 0},
                "size": {
                    "dx": int(outer.get("length") or length_m * 1000),
                    "dy": int(outer.get("width") or 0),
                    "dz": int(outer.get("height") or 0),
                },
                "rotation": "LWH",
                "layer": int(item.get("层级") or 1),
            }
        )

    def _pct(s: str) -> float:
        try:
            return float(str(s).replace("%", "")) / 100.0
        except ValueError:
            return 0.0

    return {
        "container_type": raw.get("柜型") or ctype,
        "containers_used": 1 if layout_api else 0,
        "space_utilization": round(_pct(raw.get("空间利用率") or "0%"), 4),
        "weight_utilization": round(_pct(raw.get("重量利用率") or "0%"), 4),
        "can_fit": len(unpacked) == 0 and len(layout_api) > 0,
        "layout": layout_api,
        "unpacked_box_ids": unpacked,
        "message": raw.get("结论") or "",
        "engine": "local-1d",
    }
