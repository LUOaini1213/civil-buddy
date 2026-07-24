"""
截面库门面：委托 section_provider（方案 C：steel_table 优先）。

保留 list_i_table / box_default_i 等兼容 API。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from packing_assistant.tools.section_provider import (
    SectionNotFoundError,
    get_box_default_sections,
    get_section,
    load_steel_table,
)

# 长细比经验带
LAMBDA_GUIDE = {
    "comfortable_max": 100.0,
    "caution_max": 120.0,
    "steel_allow": 150.0,
    "wood_allow": 120.0,
}


def resolve_box_preset(box_type: str) -> Dict[str, Any]:
    """兼容旧接口：返回 frame/bottom_beam 字典（含 I/W/i/count）。"""
    d = get_box_default_sections(box_type)
    frame = dict(d["frame"])
    bottom = dict(d["bottom_beam"])
    return {
        "frame": frame,
        "bottom_beam": bottom,
        "gamma": d["gamma"],
        "lift_points_default": d["lift_points_default"],
        "calc_strategy": d["calc_strategy"],
        "material": "wood" if d.get("material") == "wood" else "steel",
    }


def list_i_table() -> List[Dict[str, Any]]:
    table = load_steel_table()
    rows = []
    for name, s in (table.get("sections") or {}).items():
        rows.append(
            {
                "name": name,
                "i_cm": s.get("i_cm"),
                "I_cm4": s.get("I_cm4"),
                "W_cm3": s.get("W_cm3"),
                "A_cm2": s.get("A_cm2"),
                "source": s.get("source") or "steel_table",
            }
        )
    return rows


def box_default_i(box_type: str) -> Dict[str, Any]:
    p = resolve_box_preset(box_type)
    fr, bb = p["frame"], p["bottom_beam"]
    return {
        "box_type": box_type,
        "frame_name": fr.get("name"),
        "frame_i_cm": fr.get("i_cm"),
        "bottom_beam_name": bb.get("name"),
        "bottom_beam_i_cm": bb.get("i_cm"),
        "gamma": p.get("gamma"),
    }


# 兼容旧 get_section 名
def get_section_compat(name: str) -> Optional[Dict[str, float]]:
    try:
        s = get_section(name)
        return {
            "I_cm4": s["I_cm4"],
            "W_cm3": s["W_cm3"],
            "i_cm": s["i_cm"],
            "A_cm2": s["A_cm2"],
        }
    except SectionNotFoundError:
        return None
