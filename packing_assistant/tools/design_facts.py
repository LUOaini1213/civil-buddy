"""
详设结构事实（design facts）

正式结构校核必须能追溯到：截面型号、γ、吊点、立柱计算长度系数、图纸号等。
无详设时：仅允许 default_preset 筛查，并在结论中标明「非正式/待详设」。
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / "knowledge" / "structure_design_facts.json"
_EXAMPLE_PATH = _ROOT / "knowledge" / "structure_design_facts.example.json"


def design_facts_path() -> Path:
    return Path(os.getenv("STRUCTURE_DESIGN_FACTS_PATH") or _DEFAULT_PATH)


def load_design_facts(
    path: Optional[str] = None,
    *,
    inline: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """加载详设 JSON；inline 优先合并覆盖文件。"""
    base: Dict[str, Any] = {}
    p = Path(path) if path else design_facts_path()
    if p.exists():
        base = json.loads(p.read_text(encoding="utf-8"))
    elif _EXAMPLE_PATH.exists() and os.getenv("STRUCTURE_USE_EXAMPLE_FACTS", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        base = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
        base["_loaded_example"] = True
    if inline:
        base = merge_design_facts(base, inline)
    if not base.get("fidelity"):
        base["fidelity"] = "detailed_design" if base.get("box_types") or base.get("boxes") else "none"
    return base


def merge_design_facts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base or {})
    ov = overlay or {}
    for k, v in ov.items():
        if k in ("box_types", "boxes") and isinstance(v, dict):
            out.setdefault(k, {})
            out[k] = {**out.get(k, {}), **v}
        elif k == "defaults" and isinstance(v, dict):
            out.setdefault("defaults", {})
            out["defaults"] = {**out.get("defaults", {}), **v}
        else:
            out[k] = v
    if out.get("box_types") or out.get("boxes"):
        out["fidelity"] = out.get("fidelity") or "detailed_design"
    return out


def has_detailed_facts(facts: Optional[Dict[str, Any]]) -> bool:
    if not facts:
        return False
    if facts.get("fidelity") in ("detailed_design", "drawing", "project"):
        return bool(facts.get("box_types") or facts.get("boxes") or facts.get("defaults"))
    return bool(facts.get("box_types") or facts.get("boxes"))


def resolve_box_design(
    *,
    box_type: str,
    box_id: str = "",
    facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    解析单箱详设覆盖。
    返回 {fidelity, frame_section, bottom_beam_section, gamma, ...}
    """
    facts = facts or {}
    defaults = dict(facts.get("defaults") or {})
    by_type = (facts.get("box_types") or {}).get(box_type) or {}
    # 别名模糊
    if not by_type:
        for k, v in (facts.get("box_types") or {}).items():
            if k in box_type or box_type in k:
                by_type = v
                break
    by_id = (facts.get("boxes") or {}).get(box_id) or {}
    merged = {**defaults, **by_type, **by_id}
    fidelity = "detailed_design" if merged and has_detailed_facts(facts) else "default_preset"
    if by_id or by_type:
        fidelity = "detailed_design"
    return {
        "fidelity": fidelity,
        "box_type": box_type,
        "box_id": box_id,
        "frame_section": merged.get("frame_section") or merged.get("frame"),
        "bottom_beam_section": merged.get("bottom_beam_section") or merged.get("bottom_beam"),
        "bottom_beam_count": int(merged.get("bottom_beam_count") or merged.get("beam_count") or 0)
        or None,
        "gamma": merged.get("gamma") or merged.get("safety_factor"),
        "lift_points": merged.get("lift_points") or merged.get("lift_point_count"),
        "column_count": merged.get("column_count") or merged.get("n_columns"),
        "k_factor_column": merged.get("k_factor_column") or merged.get("k_factor"),
        "max_payload_kg": merged.get("max_payload_kg"),
        "tare_kg": merged.get("tare_kg"),
        "bearing_pad_mm": merged.get("bearing_pad_mm"),
        "defl_ratio": merged.get("defl_ratio"),
        "drawing_no": merged.get("drawing_no") or facts.get("drawing_no"),
        "source": facts.get("source") or merged.get("source") or "",
        "note": merged.get("note") or "",
        "raw": merged,
    }


def apply_section_overrides(
    preset: Dict[str, Any],
    design: Dict[str, Any],
) -> Dict[str, Any]:
    """把详设截面名解析为参数，覆盖 get_box_default_sections 结果。"""
    out = deepcopy(preset or {})
    from packing_assistant.tools.section_provider import get_section

    if design.get("gamma"):
        out["gamma"] = float(design["gamma"])
    if design.get("lift_points"):
        out["lift_points_default"] = int(design["lift_points"])
    if design.get("frame_section"):
        try:
            sec = get_section(str(design["frame_section"]))
            out["frame"] = {
                "name": sec.get("name") or design["frame_section"],
                "A_cm2": sec["A_cm2"],
                "I_cm4": sec["I_cm4"],
                "W_cm3": sec["W_cm3"],
                "i_cm": sec["i_cm"],
                "source": f"design_facts:{sec.get('source')}",
            }
        except Exception as e:
            out.setdefault("design_errors", []).append(f"框架截面: {e}")
    if design.get("bottom_beam_section"):
        try:
            sec = get_section(str(design["bottom_beam_section"]))
            cnt = int(design.get("bottom_beam_count") or (out.get("bottom_beam") or {}).get("count") or 2)
            out["bottom_beam"] = {
                "name": sec.get("name") or design["bottom_beam_section"],
                "A_cm2": sec["A_cm2"],
                "I_cm4": sec["I_cm4"],
                "W_cm3": sec["W_cm3"],
                "i_cm": sec["i_cm"],
                "count": cnt,
                "source": f"design_facts:{sec.get('source')}",
            }
        except Exception as e:
            out.setdefault("design_errors", []).append(f"底梁截面: {e}")
    out["design_fidelity"] = design.get("fidelity") or "default_preset"
    out["drawing_no"] = design.get("drawing_no")
    out["design_source"] = design.get("source")
    return out


def facts_status_summary(facts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ok = has_detailed_facts(facts)
    return {
        "has_detailed_facts": ok,
        "fidelity": (facts or {}).get("fidelity") or ("detailed_design" if ok else "none"),
        "box_types_count": len((facts or {}).get("box_types") or {}),
        "boxes_count": len((facts or {}).get("boxes") or {}),
        "source": (facts or {}).get("source") or "",
        "require_for_ship": bool((facts or {}).get("require_for_ship", True)),
        "message": (
            "已加载详设结构事实，校核按图纸截面"
            if ok
            else "未提供详设事实：仅默认截面筛查，不可作正式出运结构依据"
        ),
    }
