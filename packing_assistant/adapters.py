"""API snake_case ↔ 内部工具中文键 适配。"""

from __future__ import annotations

from typing import Any, Dict, List


def material_api_to_internal(m: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "名称": m.get("name") or m.get("名称") or "",
        "规格": m.get("spec") or m.get("规格") or "",
        "数量": int(m.get("quantity") or m.get("数量") or 1),
        "单重_kg": float(m.get("weight_kg") or m.get("单重_kg") or 0),
        "总重_kg": float(
            m.get("total_weight_kg")
            or m.get("总重_kg")
            or float(m.get("weight_kg") or 0) * int(m.get("quantity") or 1)
        ),
        "外尺寸_mm": {
            "长": float(m.get("length_mm") or (m.get("sizeMm") or {}).get("l") or (m.get("外尺寸_mm") or {}).get("长") or 0),
            "宽": float(m.get("width_mm") or (m.get("sizeMm") or {}).get("w") or (m.get("外尺寸_mm") or {}).get("宽") or 0),
            "高": float(m.get("height_mm") or (m.get("sizeMm") or {}).get("h") or (m.get("外尺寸_mm") or {}).get("高") or 0),
        },
        "备注": m.get("remark") or m.get("备注") or "",
        "加工件编号": m.get("part_no") or m.get("id") or m.get("加工件编号") or "",
        "id": m.get("id") or "",
        "category": m.get("category") or "",
    }


def material_internal_to_api(m: Dict[str, Any], idx: int = 1) -> Dict[str, Any]:
    dims = m.get("外尺寸_mm") or {}
    qty = int(m.get("数量") or 1)
    unit = float(m.get("单重_kg") or 0)
    total = float(m.get("总重_kg") or unit * qty)
    mid = m.get("id") or m.get("加工件编号") or f"M{idx:03d}"
    L = float(dims.get("长") or 0)
    cat = m.get("category") or classify_material(L, unit, total)
    return {
        "id": mid,
        "name": m.get("名称") or "",
        "spec": m.get("规格") or "",
        "length_mm": L,
        "width_mm": float(dims.get("宽") or 0),
        "height_mm": float(dims.get("高") or 0),
        "weight_kg": unit,
        "quantity": qty,
        "total_weight_kg": round(total, 3),
        "category": cat,
    }


def classify_material(length_mm: float, weight_kg: float, total_kg: float) -> str:
    try:
        from packing_assistant.knowledge import classify_by_kb

        return classify_by_kb(length_mm, weight_kg, total_kg)
    except Exception:
        if length_mm >= 4000:
            return "超长件"
        if weight_kg >= 200 or total_kg >= 1500:
            return "重件"
        return "普通件"


def box_internal_to_api(b: Dict[str, Any]) -> Dict[str, Any]:
    """packing 工具中文输出 → api-spec boxes。"""
    if "box_id" in b and "outer_size_mm" in b:
        return b
    dims = b.get("外尺寸_mm") or b.get("outer_size_mm") or {}
    content_in = b.get("装载内容") or b.get("content") or []
    content = []
    for c in content_in:
        content.append(
            {
                "material_id": c.get("material_id") or c.get("加工件编号") or "",
                "name": c.get("name") or c.get("名称") or "",
                "quantity": int(c.get("quantity") or c.get("数量") or 1),
            }
        )
    special = b.get("特殊属性") or b.get("special_attributes") or []
    struct = b.get("结构计算") or b.get("structure_calc") or {}
    detail = b.get("structure_detail") or {}
    if not detail and struct:
        detail = {
            "safety_factor_gamma": struct.get("safety_factor_gamma"),
            "design_load_kg": struct.get("design_load_kg"),
            "section_used": struct.get("section_used"),
            "bottom_bending": struct.get("bottom_bending"),
            "frame_stability": struct.get("frame_stability"),
            "local_bearing": struct.get("local_bearing"),
            "lifting_points": struct.get("lifting_points"),
            "summary": struct.get("summary"),
            "calc_report_md": struct.get("calc_report_md"),
        }
    return {
        "box_id": b.get("箱号") or b.get("box_id") or "",
        "box_type": b.get("箱型") or b.get("box_type") or "",
        "base_box_type": b.get("base_box_type") or "",
        "outer_size_mm": {
            "length": float(dims.get("长") or dims.get("length") or 0),
            "width": float(dims.get("宽") or dims.get("width") or 0),
            "height": float(dims.get("高") or dims.get("height") or 0),
        },
        "gross_weight_kg": float(b.get("毛重_kg") or b.get("gross_weight_kg") or 0),
        "net_weight_kg": float(b.get("净重_kg") or b.get("net_weight_kg") or 0),
        "content": content,
        "contents": content,  # 别名，避免漏读
        "special_attributes": list(special),
        "reinforcement": b.get("reinforcement")
        or (struct.get("底梁建议") or {}).get("截面建议_mm")
        or "",
        "structure_conclusion": b.get("结构结论") or b.get("structure_conclusion") or "",
        "structure_calc": struct,
        "structure_detail": detail,
        "crate_fill_ratio": b.get("crate_fill_ratio"),
        "customized_outer": b.get("customized_outer") or b.get("定制外廓"),
        "content_max_length_mm": b.get("content_max_length_mm"),
        "stackable": bool(b.get("stackable")),
        "prefer_bottom": bool(b.get("prefer_bottom")),
    }


def box_api_to_internal(b: Dict[str, Any]) -> Dict[str, Any]:
    """snake_case box → consolidation 等内部工具。"""
    if "外尺寸_mm" in b:
        return b
    outer = b.get("outer_size_mm") or {}
    return {
        "箱号": b.get("box_id") or "",
        "箱型": b.get("box_type") or "",
        "外尺寸_mm": {
            "长": float(outer.get("length") or 0),
            "宽": float(outer.get("width") or 0),
            "高": float(outer.get("height") or 0),
        },
        "毛重_kg": float(b.get("gross_weight_kg") or 0),
        "净重_kg": float(b.get("net_weight_kg") or 0),
        "特殊属性": list(b.get("special_attributes") or []),
        "结构结论": b.get("structure_conclusion") or "",
    }


def boxes_to_internal(boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [box_api_to_internal(b) for b in boxes]


def boxes_to_api(boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [box_internal_to_api(b) for b in boxes]
