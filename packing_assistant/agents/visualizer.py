"""Agent8 可视化智能体：三视角 + COG 标记 + 可选 PNG。"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

from packing_assistant.knowledge import color_for_box_type
from packing_assistant.state import PackingState
from packing_assistant.tools.cog import compute_cog_bundle
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
    container_nos = set()
    for item in plan.get("layout") or []:
        bid = item.get("box_id") or ""
        pos = item.get("position") or {}
        size = item.get("size") or {}
        color = color_map.get(bid, "#4C78A8")
        cno = int(item.get("container_no") or 1)
        container_nos.add(cno)
        x, y, z = int(pos.get("x") or 0), int(pos.get("y") or 0), int(pos.get("z") or 0)
        dx, dy, dz = int(size.get("dx") or 0), int(size.get("dy") or 0), int(size.get("dz") or 0)

        top_el.append(
            {
                "box_id": bid,
                "container_no": cno,
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
                "container_no": cno,
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
                "container_no": cno,
                "y": y,
                "z": z,
                "depth": dy,
                "height": dz,
                "color": color,
                "label": bid,
            }
        )

    nos_sorted = sorted(container_nos) or [1]
    # 默认只画第 1 柜，避免多柜叠在同一轮廓里「挤成一团」
    default_cno = nos_sorted[0]

    def _filter(els: List[Dict[str, Any]], cno: int) -> List[Dict[str, Any]]:
        return [e for e in els if int(e.get("container_no") or 1) == int(cno)]

    views = {
        "top": {
            "name": "俯视",
            "camera": "top",
            "container": cont,
            "container_no": default_cno,
            "elements": _filter(top_el, default_cno),
            "elements_all": top_el,
        },
        "side": {
            "name": "侧视",
            "camera": "side",
            "container": cont,
            "container_no": default_cno,
            "elements": _filter(side_el, default_cno),
            "elements_all": side_el,
            # 提示前端：长/高悬殊，应用更高画布、勿压扁高度
            "aspect_hint": "long_horizontal",
        },
        "front": {
            "name": "正视",
            "camera": "front",
            "container": cont,
            "container_no": default_cno,
            "elements": _filter(front_el, default_cno),
            "elements_all": front_el,
            "aspect_hint": "portraitish",
        },
        "_meta": {
            "containers": nos_sorted,
            "default_container_no": default_cno,
            "note": "默认单柜绘制；前端可切换 container_no 过滤 elements_all",
        },
    }

    # 重心：优先 risk_report.cog，否则现场算（主柜）
    risk = state.get("risk_report") or {}
    cog_bundle = None
    try:
        cog_bundle = compute_cog_bundle(plan, boxes)
    except Exception:
        cog_bundle = None
    cog_primary = None
    if cog_bundle and cog_bundle.get("primary"):
        cog_primary = dict(cog_bundle["primary"])
    elif isinstance(risk.get("cog"), dict) and risk["cog"].get("gx_mm") is not None:
        cog_primary = dict(risk["cog"])
    if cog_primary:
        marker = {
            "gx_mm": cog_primary.get("gx_mm"),
            "gy_mm": cog_primary.get("gy_mm"),
            "gz_mm": cog_primary.get("gz_mm"),
            "color": "#ef4444",
            "label": "COG",
        }
        views["top"]["cog"] = marker
        views["side"]["cog"] = {
            "gx_mm": marker["gx_mm"],
            "gz_mm": marker["gz_mm"],
            "color": marker["color"],
            "label": "COG",
        }
        views["front"]["cog"] = {
            "gy_mm": marker["gy_mm"],
            "gz_mm": marker["gz_mm"],
            "color": marker["color"],
            "label": "COG",
        }
        # 中心参考线（俯视/正视画柜中线）
        views["top"]["center_lines"] = {
            "longitudinal_mid_mm": cont["length_mm"] / 2,
            "lateral_mid_mm": cont["width_mm"] / 2,
        }
        views["front"]["center_lines"] = {"lateral_mid_mm": cont["width_mm"] / 2}
        views["side"]["center_lines"] = {
            "longitudinal_mid_mm": cont["length_mm"] / 2,
            "height_mid_mm": cont["height_mm"] / 2,
        }

    # 3D 等轴测：默认第 1 柜（与 views 一致）；全量在 boxes_all
    filter_cno = int((cog_primary or {}).get("container_no") or default_cno or 1)
    if filter_cno not in nos_sorted:
        filter_cno = default_cno
    # 垫梁/集中载荷箱：3D 用醒目红色
    pad_ids = set()
    try:
        from packing_assistant.tools.secure_work_order import build_secure_work_order

        _swo = state.get("secure_work_order") or build_secure_work_order(plan, boxes)
        for pb in (_swo.get("pad_beams") or []):
            if pb.get("box_id"):
                pad_ids.add(str(pb["box_id"]))
        for itx in _swo.get("items") or []:
            if itx.get("type") == "pad_beam" and itx.get("box_id"):
                pad_ids.add(str(itx["box_id"]))
    except Exception:
        pass
    all_3d = [
        {
            "box_id": it.get("box_id"),
            "position": it.get("position") or {},
            "size": it.get("size") or {},
            "color": (
                "#e74c3c"
                if str(it.get("box_id") or "") in pad_ids
                else color_map.get(it.get("box_id") or "", "#4C78A8")
            ),
            "pad_beam": str(it.get("box_id") or "") in pad_ids,
            "container_no": int(it.get("container_no") or 1),
        }
        for it in (plan.get("layout") or [])
    ]
    scene3d = {
        "container": cont,
        "container_type": ctype,
        "boxes": [b for b in all_3d if b["container_no"] == filter_cno],
        "boxes_all": all_3d,
        "cog": (
            {
                "gx_mm": cog_primary.get("gx_mm"),
                "gy_mm": cog_primary.get("gy_mm"),
                "gz_mm": cog_primary.get("gz_mm"),
                "color": "#ef4444",
            }
            if cog_primary
            else None
        ),
        "filter_container_no": filter_cno,
        "containers": nos_sorted,
    }

    # 后端侧视 PNG：多柜时每柜一张 + 总览
    image_data: Dict[str, Any] = {
        "top": {"path": None, "format": "png", "base64": None},
        "side": {"path": None, "format": "png", "base64": None},
        "front": {"path": None, "format": "png", "base64": None},
        "side_per_container": [],
        "side_overview": None,
    }
    plan_for_draw = dict(plan)
    # 侧视图工单标注：空隙/垫梁
    swo = state.get("secure_work_order")
    if not swo:
        try:
            from packing_assistant.tools.secure_work_order import build_secure_work_order

            swo = build_secure_work_order(plan, boxes)
        except Exception:
            swo = {}
    if swo:
        plan_for_draw["secure_work_order"] = swo
    side_path = _draw_side_png(plan_for_draw, boxes, ctype)
    if side_path:
        image_data["side"]["path"] = side_path
    side_images = plan_for_draw.get("side_images") or {}
    if side_images:
        image_data["side_overview"] = side_images.get("overview_path")
        image_data["side_per_container"] = side_images.get("per_container") or []
        if side_images.get("primary_path"):
            image_data["side"]["path"] = side_images["primary_path"]

    layout_for_count = plan.get("layout") or []
    n_c = len({int(it.get("container_no") or 1) for it in layout_for_count}) or 1

    # 双率展示：订柜有效体积 vs 外廓摆柜（禁止把 outer 写成订柜/唯一装满度）
    outer_u = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    book_u = float(plan.get("booking_volume_utilization") or 0)
    weight_u = float(plan.get("weight_utilization") or 0)
    metrics_display = {
        "outer_space_utilization": outer_u,
        "booking_volume_utilization": book_u,
        "weight_utilization": weight_u,
        "labels": {
            "outer_space_utilization": "外廓摆柜率（仅布局松紧，非订柜）",
            "booking_volume_utilization": "订柜有效体积率（V_eff，非空心架实心）",
            "weight_utilization": "重量利用率",
        },
        "caption": (
            f"订柜有效体积率 {book_u:.0%}｜外廓摆柜率 {outer_u:.0%}｜重量 {weight_u:.0%}；"
            f"外廓率≠订柜装满度，铁架常见偏低"
        ),
    }
    # 挂到 views 元数据，便于前端/导出
    for v in views.values():
        v["metrics"] = metrics_display
        if cog_primary:
            v["cog_metrics"] = {
                "lateral_eccentricity": cog_primary.get("lateral_eccentricity"),
                "longitudinal_position": cog_primary.get("longitudinal_position"),
                "height_ratio": cog_primary.get("height_ratio"),
                "balance": cog_primary.get("balance"),
                "mass_basis": cog_primary.get("mass_basis"),
            }

    tools_used = ["visualize.draw_layout", "views.build_tri_view", "views.build_scene3d"]
    if cog_primary:
        tools_used.append("cog.compute")
    if side_images.get("per_container"):
        tools_used.append("visualize.draw_layout_multi")
    cog_cap = ""
    if cog_bundle and cog_bundle.get("caption"):
        cog_cap = f"｜{cog_bundle['caption']}"
    elif cog_primary and cog_primary.get("labels"):
        lab = cog_primary["labels"]
        cog_cap = f"｜COG {lab.get('lateral','')} {lab.get('longitudinal','')}"
    msg = (
        f"三视角+3D 场景已生成（elements={len(top_el)}，柜数={n_c}"
        f"{'，侧视图'+str(len(side_images['per_container']))+'张+总览' if side_images.get('per_container') else ''}"
        f"）｜{metrics_display['caption']}{cog_cap}"
        f"｜tools={','.join(tools_used)}"
    )

    cog_out = {
        "primary": cog_primary,
        "per_container": (cog_bundle or {}).get("per_container") or [],
        "caption": (cog_bundle or {}).get("caption")
        or (risk.get("cog") or {}).get("caption"),
    }

    return {
        "views": views,
        "scene3d": scene3d,
        "cog": cog_out,
        "image_data": image_data,
        "legend": legend,
        "display_metrics": metrics_display,
        "agent_meta": {
            "node": "visualizer",
            "capability": ["使用工具", "采取行动"],
            "tools_used": tools_used,
            "artifacts": {
                "elements": len(top_el),
                "containers": n_c,
                "booking_volume_utilization": book_u,
                "outer_space_utilization": outer_u,
                "cog_balance": (cog_primary or {}).get("balance"),
            },
        },
        "messages": [
            {
                "role": "assistant",
                "content": msg,
            }
        ],
    }


def _draw_side_png(plan: Dict[str, Any], boxes: List[Dict[str, Any]], ctype: str) -> str | None:
    layout = plan.get("layout") or []
    if not layout:
        return None
    try:
        from packing_assistant.tools.visualize import draw_layout, draw_layout_multi

        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 多柜：每柜一张 + 总览；返回总览路径作为主图
        nos = {
            int(it.get("container_no") or 1)
            for it in layout
        }
        if len(nos) > 1:
            multi = draw_layout_multi(
                plan,
                container_type=ctype,
                output_dir="output",
                prefix=f"side_{ts}",
            )
            # 把分柜路径挂到 plan 便于 finalize/xlsx
            plan["side_images"] = multi
            return multi.get("primary_path") or multi.get("overview_path")
        # 单柜：侧视图图注区分外廓 vs 订柜有效体积（勿写「订柜=外廓」）
        outer_u = float(
            plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
        )
        book_u = float(plan.get("booking_volume_utilization") or 0)
        weight_u = float(plan.get("weight_utilization") or 0)
        caption = (
            f"外廓摆柜{outer_u*100:.0f}%｜订柜有效体积{book_u*100:.0f}%｜重量{weight_u*100:.0f}%"
            f"（外廓≠订柜）"
        )
        old = {
            "柜型": ctype,
            "结论": (plan.get("message") or "") + " | " + caption,
            # 兼容旧字段：空间利用率=外廓摆柜率
            "空间利用率": f"{outer_u*100:.0f}%",
            "订柜有效体积率": f"{book_u*100:.0f}%",
            "外廓摆柜率": f"{outer_u*100:.0f}%",
            "重量利用率": f"{weight_u*100:.0f}%",
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
        return draw_layout(old, output_dir="output", filename=f"side_{ts}.png")
    except Exception:
        return None
