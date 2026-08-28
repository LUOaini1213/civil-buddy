"""装柜布局质量：水平空隙、集中载荷、可叠未叠等（CTU 实践代理指标）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def analyze_layout_quality(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    void_limit_mm: float = 150.0,
) -> Dict[str, Any]:
    """
    返回：
    - max_horizontal_gap_mm：同层相邻箱在 x/y 方向的最大空隙（粗扫）
    - gaps_over_limit：超过 void_limit 的空隙条数
    - concentrated_load_flags：底面积小且重的底层件
    - stackable_floor_only：可叠却全部 z=0
    """
    layout = list(plan.get("layout") or [])
    if not layout:
        return {
            "max_horizontal_gap_mm": 0.0,
            "gaps_over_limit": 0,
            "void_limit_mm": void_limit_mm,
            "void_ok": True,
            "concentrated_load_flags": [],
            "stackable_floor_only": False,
            "stackable_count": 0,
            "stacked_count": 0,
        }

    weight_map: Dict[str, float] = {}
    stackable_map: Dict[str, bool] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if not bid:
            continue
        weight_map[bid] = float(b.get("gross_weight_kg") or 0)
        stackable_map[bid] = bool(b.get("stackable", True)) and not bool(
            b.get("prefer_bottom")
        )

    # 分柜分层
    by_c: Dict[int, List[Dict[str, Any]]] = {}
    for it in layout:
        n = int(it.get("container_no") or 1)
        by_c.setdefault(n, []).append(it)

    max_gap = 0.0
    over = 0
    gap_samples: List[Dict[str, Any]] = []

    for cno, items in by_c.items():
        # 按大致 z 层聚类
        layers: Dict[int, List[Dict[str, Any]]] = {}
        for it in items:
            z = int((it.get("position") or {}).get("z") or 0)
            layers.setdefault(z, []).append(it)
        for z, layer_items in layers.items():
            # x 方向：按 x 排序，看相邻间隙
            rows = []
            for it in layer_items:
                pos, size = it.get("position") or {}, it.get("size") or {}
                rows.append(
                    {
                        "x": float(pos.get("x") or 0),
                        "y": float(pos.get("y") or 0),
                        "dx": float(size.get("dx") or 0),
                        "dy": float(size.get("dy") or 0),
                        "id": it.get("box_id"),
                    }
                )
            # 同 y 带内 x 间隙
            rows_x = sorted(rows, key=lambda r: (round(r["y"] / 200), r["x"]))
            for i in range(len(rows_x) - 1):
                a, b = rows_x[i], rows_x[i + 1]
                if abs(a["y"] - b["y"]) > max(a["dy"], b["dy"]) * 0.6:
                    continue  # 不同列带
                gap = b["x"] - (a["x"] + a["dx"])
                if gap > max_gap:
                    max_gap = gap
                if gap > void_limit_mm:
                    over += 1
                    if len(gap_samples) < 12:
                        gap_samples.append(
                            {
                                "container_no": cno,
                                "axis": "x",
                                "z": z,
                                "gap_mm": round(gap, 1),
                                "x_mm": round(a["x"] + a["dx"], 1),
                                "x_m": round((a["x"] + a["dx"]) / 1000.0, 3),
                                "between": [a["id"], b["id"]],
                            }
                        )
            rows_y = sorted(rows, key=lambda r: (round(r["x"] / 200), r["y"]))
            for i in range(len(rows_y) - 1):
                a, b = rows_y[i], rows_y[i + 1]
                if abs(a["x"] - b["x"]) > max(a["dx"], b["dx"]) * 0.6:
                    continue
                gap = b["y"] - (a["y"] + a["dy"])
                if gap > max_gap:
                    max_gap = gap
                if gap > void_limit_mm:
                    over += 1
                    if len(gap_samples) < 8:
                        gap_samples.append(
                            {
                                "container_no": cno,
                                "axis": "y",
                                "z": z,
                                "gap_mm": round(gap, 1),
                                "between": [a["id"], b["id"]],
                            }
                        )

    # 集中载荷：底层、质量大、底面积小；或单件 >0.25×PAYLOAD（CTU）
    concentrated: List[Dict[str, Any]] = []
    try:
        from packing_assistant.tools.consolidation import CONTAINER_SPECS

        ctype = str(plan.get("container_type") or "40HQ").upper()
        sp = CONTAINER_SPECS.get(ctype) or CONTAINER_SPECS.get("40HQ") or {}
        payload = float(
            sp.get("max_load_kg") or sp.get("最大载重_kg") or 28610.0
        )
    except Exception:
        payload = 28610.0
    thr_025 = 0.25 * payload
    seen_conc: set = set()

    for it in layout:
        pos, size = it.get("position") or {}, it.get("size") or {}
        bid = str(it.get("box_id") or "")
        w = weight_map.get(bid) or float(it.get("gross_weight_kg") or 0)
        dx = max(float(size.get("dx") or 1), 1)
        dy = max(float(size.get("dy") or 1), 1)
        area_m2 = (dx * dy) / 1e6
        z0 = int(pos.get("z") or 0) == 0
        if w >= thr_025 and bid not in seen_conc:
            seen_conc.add(bid)
            concentrated.append(
                {
                    "box_id": bid,
                    "weight_kg": round(w, 1),
                    "footprint_m2": round(area_m2, 3),
                    "payload_fraction": round(w / payload, 3),
                    "hint": (
                        f"单件 {w:.0f}kg >25% PAYLOAD({payload:.0f}kg)："
                        f"垫梁/垫木分散至柜底纵梁（CTU）"
                    ),
                    "code": "PAD_BEAM_025P",
                }
            )
        elif z0 and w >= 800 and area_m2 < 1.2 and bid not in seen_conc:
            seen_conc.add(bid)
            concentrated.append(
                {
                    "box_id": bid,
                    "weight_kg": round(w, 1),
                    "footprint_m2": round(area_m2, 3),
                    "hint": "建议垫梁/垫木将荷载传到柜底纵梁",
                    "code": "PAD_BEAM_FOOTPRINT",
                }
            )
        elif z0 and w >= 1500 and area_m2 < 2.5 and bid not in seen_conc:
            seen_conc.add(bid)
            concentrated.append(
                {
                    "box_id": bid,
                    "weight_kg": round(w, 1),
                    "footprint_m2": round(area_m2, 3),
                    "hint": "重件小底面积，检查地板集中载荷",
                    "code": "PAD_BEAM_HEAVY",
                }
            )

    stacked = sum(
        1 for it in layout if int((it.get("position") or {}).get("z") or 0) > 0
    )
    stackable_n = 0
    for it in layout:
        bid = str(it.get("box_id") or "")
        if stackable_map.get(bid, True):
            stackable_n += 1
    stackable_floor_only = stackable_n >= 4 and stacked == 0

    return {
        "max_horizontal_gap_mm": round(max_gap, 1),
        "gaps_over_limit": over,
        "void_limit_mm": void_limit_mm,
        "void_ok": over == 0 and max_gap <= void_limit_mm + 1e-6,
        "gap_samples": gap_samples,
        "concentrated_load_flags": concentrated[:12],
        "stackable_floor_only": stackable_floor_only,
        "stackable_count": stackable_n,
        "stacked_count": stacked,
    }
