"""绑扎/空隙工单 + 集中载荷垫梁清单（WARN 级，不拦 ship_ok）。

CTU 实践代理：
- 同层水平空隙 >150mm → 气囊/木方/填缝
- 单件毛重 >0.25×柜 payload → 垫梁/分散载荷
- 空隙 >800mm 分堆 → 加固带/防移位
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from packing_assistant.tools.consolidation import CONTAINER_SPECS


def _payload_kg(container_type: str) -> float:
    spec = CONTAINER_SPECS.get(str(container_type).upper()) or CONTAINER_SPECS.get("40HQ") or {}
    # consolidation 用中文键；bin3d 默认 COSCO PAYLOAD 28610
    return float(
        spec.get("max_load_kg")
        or spec.get("payload_kg")
        or spec.get("最大载重_kg")
        or 28610.0
    )


def build_secure_work_order(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    void_limit_mm: float = 150.0,
    payload_fraction: float = 0.25,
) -> Dict[str, Any]:
    """
    返回 secure_work_order 工件：
    - void_fills: 需气囊/木方的空隙
    - pad_beams: 集中载荷垫梁
    - strapping: 超长/分堆绑扎
    - items: 扁平工单行（给现场/HITL）
    - severity: low|medium|high（不阻断出运）
    """
    ctype = str(plan.get("container_type") or "40HQ")
    payload = _payload_kg(ctype)
    thr_w = payload * float(payload_fraction)

    lq = dict(plan.get("layout_quality") or {})
    if not lq:
        try:
            from packing_assistant.tools.layout_quality import analyze_layout_quality

            lq = analyze_layout_quality(plan, boxes, void_limit_mm=void_limit_mm)
        except Exception:
            lq = {}

    void_fills: List[Dict[str, Any]] = []
    for g in lq.get("gap_samples") or []:
        gap = float(g.get("gap_mm") or 0)
        if gap <= void_limit_mm:
            continue
        if gap > 800:
            action = "分堆空隙：钢带/绑带交叉固定 + 两端止挡，必要时加挡板"
            material = "钢带/止挡木"
        elif gap > 400:
            action = "大空隙：木方+气囊组合填充，防止横向窜动"
            material = "木方 + 充气气囊"
        else:
            action = "空隙填充：气囊或泡沫块楔紧（CTU 宜≤150mm）"
            material = "充气气囊/泡沫楔"
        void_fills.append(
            {
                "type": "void_fill",
                "container_no": g.get("container_no"),
                "axis": g.get("axis"),
                "z_mm": g.get("z"),
                "gap_mm": gap,
                "x_mm": g.get("x_mm"),
                "x_m": g.get("x_m"),
                "between": g.get("between"),
                "action": action,
                "material": material,
                "severity": "medium" if gap <= 800 else "high",
            }
        )

    # 无 sample 但有超限：总览一条
    max_gap = float(lq.get("max_horizontal_gap_mm") or 0)
    if max_gap > void_limit_mm and not void_fills:
        void_fills.append(
            {
                "type": "void_fill",
                "container_no": None,
                "gap_mm": max_gap,
                "action": "存在超 150mm 水平空隙，装柜时填缝/气囊（详见侧视图）",
                "material": "气囊/木方",
                "severity": "medium",
            }
        )

    wmap: Dict[str, float] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if bid:
            wmap[bid] = float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0)

    pad_beams: List[Dict[str, Any]] = []
    layout = list(plan.get("layout") or [])
    for it in layout:
        bid = str(it.get("box_id") or "")
        w = wmap.get(bid) or float(it.get("gross_weight_kg") or 0)
        if w < thr_w:
            continue
        pos, size = it.get("position") or {}, it.get("size") or {}
        dx = max(float(size.get("dx") or 1), 1)
        dy = max(float(size.get("dy") or 1), 1)
        area = (dx * dy) / 1e6
        pad_beams.append(
            {
                "type": "pad_beam",
                "box_id": bid,
                "container_no": it.get("container_no"),
                "weight_kg": round(w, 1),
                "payload_fraction": round(w / max(payload, 1), 3),
                "footprint_m2": round(area, 3),
                "position_z": int(pos.get("z") or 0),
                "action": (
                    f"单件 {w:.0f}kg > {payload_fraction:.0%}×PAYLOAD({payload:.0f}kg)："
                    f"垫梁/垫木将荷载传到柜底纵梁（CTU 集中载荷）"
                ),
                "material": "垫梁/槽钢垫木",
                "severity": "high" if w >= thr_w * 1.4 else "medium",
            }
        )

    # 也合并 layout_quality 已有 concentrated 提示
    for fl in lq.get("concentrated_load_flags") or []:
        bid = str(fl.get("box_id") or "")
        if any(p.get("box_id") == bid for p in pad_beams):
            continue
        pad_beams.append(
            {
                "type": "pad_beam",
                "box_id": bid,
                "weight_kg": fl.get("weight_kg"),
                "footprint_m2": fl.get("footprint_m2"),
                "action": fl.get("hint") or "集中载荷，建议垫梁",
                "material": "垫梁/垫木",
                "severity": "medium",
            }
        )

    strapping: List[Dict[str, Any]] = []
    for b in boxes or []:
        special = b.get("special_attributes") or []
        if "超长" in special or float((b.get("outer_size_mm") or {}).get("length") or 0) >= 6000:
            strapping.append(
                {
                    "type": "strapping",
                    "box_id": b.get("box_id"),
                    "action": "超长件沿柜长、禁止竖放；两端/中部绑扎不少于 3 道",
                    "material": "钢带/柔性绑带",
                    "severity": "medium",
                }
            )

    items: List[Dict[str, Any]] = []
    for i, row in enumerate(void_fills + pad_beams + strapping[:20], 1):
        items.append(
            {
                "seq": i,
                "type": row.get("type"),
                "severity": row.get("severity") or "medium",
                "container_no": row.get("container_no"),
                "box_id": row.get("box_id"),
                "action": row.get("action"),
                "material": row.get("material"),
                "detail": {
                    k: row.get(k)
                    for k in (
                        "gap_mm",
                        "weight_kg",
                        "payload_fraction",
                        "footprint_m2",
                        "between",
                        "axis",
                    )
                    if row.get(k) is not None
                },
            }
        )

    sev = "low"
    if any(x.get("severity") == "high" for x in items):
        sev = "high"
    elif items:
        sev = "medium"

    return {
        "schema": "secure.work_order.v1",
        "blocks_ship_ok": False,  # 明确：不拦出运
        "severity": sev,
        "payload_kg": payload,
        "payload_fraction_threshold": payload_fraction,
        "void_limit_mm": void_limit_mm,
        "void_fills": void_fills,
        "pad_beams": pad_beams,
        "strapping": strapping[:20],
        "items": items,
        "summary": (
            f"绑扎/空隙工单 {len(items)} 项（空隙{len(void_fills)}·垫梁{len(pad_beams)}·绑扎{min(len(strapping),20)}）；"
            f"WARN 级，不阻断 ship_ok"
        ),
        "layout_quality_ref": {
            "max_horizontal_gap_mm": lq.get("max_horizontal_gap_mm"),
            "gaps_over_limit": lq.get("gaps_over_limit"),
            "void_ok": lq.get("void_ok"),
        },
    }
