"""Agent5 装载执行：skjolber HTTP → 纯 Python 3D → 1D 兜底。"""

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
    max_c = int(state.get("max_containers") or plan.get("max_containers") or 1)

    if priority:
        order = {bid: i for i, bid in enumerate(priority)}
        boxes = sorted(boxes, key=lambda b: order.get(b.get("box_id"), 999))

    notes: List[str] = []
    container_plan: Dict[str, Any] | None = None

    # 1) 真实 skjolber（若已配置且可达）
    if is_skjolber_configured():
        try:
            container_plan = pack_via_skjolber(
                boxes,
                {
                    **plan,
                    "container_type": ctype,
                    "max_containers": max_c,
                },
                request_id=str(state.get("run_id") or state.get("packing_plan_id") or ""),
            )
            notes.append(container_plan.get("engine") or "skjolber")
        except Exception as e:
            notes.append(f"skjolber不可用: {e}")

    # 2) 纯 Python 3D（无 Java 时的主路径）
    if container_plan is None:
        try:
            container_plan = pack_boxes_api(
                boxes,
                container_type=ctype,
                max_containers=max_c,
                priority_order=priority or None,
            )
            notes.append(container_plan.get("engine") or "python-laff-3d")
        except Exception as e:
            notes.append(f"python3d失败: {e}")
            container_plan = _local_1d(boxes, ctype)
            notes.append("local-1d-fallback")

    return {
        "container_plan": container_plan,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"装载完成 engine={container_plan.get('engine')} "
                    f"can_fit={container_plan.get('can_fit')} "
                    f"容积(实心外廓){float(container_plan.get('space_utilization') or 0):.0%} "
                    f"货{float(container_plan.get('cargo_solid_volume_m3') or 0):.2f}m³/"
                    f"柜{float(container_plan.get('container_inner_volume_m3') or 0):.1f}m³ "
                    f"最满柜{float(container_plan.get('space_utilization_best_container') or 0):.0%} "
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
        "can_fit": len(unpacked) == 0 and "放不下" not in str(raw.get("结论") or ""),
        "layout": layout_api,
        "unpacked_box_ids": unpacked,
        "message": raw.get("结论") or "",
        "engine": "local-linear-1d-placeholder",
    }
