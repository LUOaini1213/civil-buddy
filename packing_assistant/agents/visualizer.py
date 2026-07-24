"""Agent8 可视化智能体：三视角结构化数据 + 可选 PNG。"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

from packing_assistant.knowledge import color_for_box_type
from packing_assistant.state import PackingState
from packing_assistant.tools.consolidation import CONTAINER_SPECS

_FALLBACK_COLORS = [
    "#4C78A8",
    "#54A24B",
    "#F58518",
    "#B279A2",
    "#72B7B2",
    "#E45756",
    "#9D755D",
    "#BAB0AC",
]


def agent_visualizer(state: PackingState) -> Dict[str, Any]:
    plan = state.get("container_plan") or {}
    boxes = state.get("boxes") or []
    ctype = plan.get("container_type") or state.get("container_type") or "40HQ"
    spec = CONTAINER_SPECS.get(ctype, CONTAINER_SPECS["40HQ"])

    cont = {
        "length_mm": int(spec["长_m"] * 1000),
        "width_mm": int(spec["宽_m"] * 1000),
        "height_mm": int(spec["高_m"] * 1000),
    }

    color_map = {}
    legend = []
    for i, b in enumerate(boxes):
        bid = b.get("box_id") or f"B{i}"
        color_map[bid] = color_for_box_type(b.get("box_type") or "") or _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)]
        legend.append(
            {
                "box_id": bid,
                "color": color_map[bid],
                "box_type": b.get("box_type") or "",
            }
        )

    top_el, side_el, front_el = [], [], []
    for item in plan.get("layout") or []:
        bid = item.get("box_id") or ""
        pos = item.get("position") or {}
        size = item.get("size") or {}
        color = color_map.get(bid, "#4C78A8")
        x, y, z = int(pos.get("x") or 0), int(pos.get("y") or 0), int(pos.get("z") or 0)
        dx, dy, dz = int(size.get("dx") or 0), int(size.get("dy") or 0), int(size.get("dz") or 0)

        top_el.append(
            {
                "box_id": bid,
                "x": x,
                "y": y,
                "width": dx,
                "depth": dy,
                "color": color,
                "label": bid,
            }
        )
        side_el.append(
            {
                "box_id": bid,
                "x": x,
                "z": z,
                "width": dx,
                "height": dz,
                "color": color,
                "label": bid,
            }
        )
        front_el.append(
            {
                "box_id": bid,
                "y": y,
                "z": z,
                "depth": dy,
                "height": dz,
                "color": color,
                "label": bid,
            }
        )

    views = {
        "top": {
            "name": "俯视",
            "camera": "top",
            "container": cont,
            "elements": top_el,
        },
        "side": {
            "name": "侧视",
            "camera": "side",
            "container": cont,
            "elements": side_el,
        },
        "front": {
            "name": "正视",
            "camera": "front",
            "container": cont,
            "elements": front_el,
        },
    }

    # 后端侧视 PNG 兜底（复用旧 draw_layout 风格）
    image_data: Dict[str, Any] = {
        "top": {"path": None, "format": "png", "base64": None},
        "side": {"path": None, "format": "png", "base64": None},
        "front": {"path": None, "format": "png", "base64": None},
    }
    side_path = _draw_side_png(plan, boxes, ctype)
    if side_path:
        image_data["side"]["path"] = side_path

    return {
        "views": views,
        "image_data": image_data,
        "legend": legend,
        "messages": [
            {
                "role": "assistant",
                "content": f"三视角数据已生成（elements={len(top_el)}）",
            }
        ],
    }


def _draw_side_png(plan: Dict[str, Any], boxes: List[Dict[str, Any]], ctype: str) -> str | None:
    layout = plan.get("layout") or []
    if not layout:
        return None
    # 转为旧版 container_plan 供 matplotlib
    old = {
        "柜型": ctype,
        "结论": plan.get("message") or "",
        "空间利用率": f"{float(plan.get('space_utilization') or 0)*100:.0f}%",
        "重量利用率": f"{float(plan.get('weight_utilization') or 0)*100:.0f}%",
        "布局": [
            {
                "箱号": it.get("box_id"),
                "起始位置_m": (it.get("position") or {}).get("x", 0) / 1000.0,
                "长度_m": (it.get("size") or {}).get("dx", 0) / 1000.0,
                "层级": it.get("layer") or 1,
                "颜色": "blue",
            }
            for it in layout
        ],
    }
    try:
        from packing_assistant.tools.visualize import draw_layout

        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return draw_layout(old, output_dir="output", filename=f"side_{ts}.png")
    except Exception:
        return None
