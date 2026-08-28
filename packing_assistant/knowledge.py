"""加载并查询 packing_knowledge_base.json。"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "packing_knowledge_base.json"


@lru_cache(maxsize=2)
def load_kb(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path or os.getenv("PACKING_KB_PATH") or _DEFAULT_PATH)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def reload_kb() -> Dict[str, Any]:
    """改 JSON 后强制重载。"""
    load_kb.cache_clear()
    return load_kb()


def kb_version() -> str:
    return str(load_kb().get("version") or "")


def resolve_box_type_key(name: str) -> Optional[str]:
    """别名 → 知识库标准箱型键。"""
    kb = load_kb()
    boxes = kb.get("box_types") or {}
    if name in boxes:
        return name
    for key, spec in boxes.items():
        aliases = spec.get("aliases") or []
        if name == key or name in aliases:
            return key
    # 模糊
    for key, spec in boxes.items():
        if key in name or name in key:
            return key
        for a in spec.get("aliases") or []:
            if a in name or name in a:
                return key
    return None


def get_box_spec(name: str) -> Optional[Dict[str, Any]]:
    key = resolve_box_type_key(name)
    if not key:
        return None
    spec = dict((load_kb().get("box_types") or {}).get(key) or {})
    spec["_key"] = key
    return spec


def validate_boxes_against_kb(
    boxes: List[Dict[str, Any]],
    *,
    allow_passthrough: bool = True,
) -> Dict[str, Any]:
    """
    校验成箱结果是否落在标准箱库。
    返回 hit_rate、unknown 列表、by_type 计数。
    """
    total = 0
    hit = 0
    unknown: List[Dict[str, str]] = []
    by_type: Dict[str, int] = {}
    passthrough_n = 0
    for b in boxes or []:
        if not isinstance(b, dict):
            continue
        total += 1
        base = str(b.get("base_box_type") or "")
        btype = str(b.get("box_type") or "")
        if allow_passthrough and (
            base == "crate_passthrough" or "当量" in btype or "passthrough" in base
        ):
            passthrough_n += 1
            by_type["crate_passthrough"] = by_type.get("crate_passthrough", 0) + 1
            hit += 1  # 直通视为合法例外
            continue
        key = resolve_box_type_key(btype) or resolve_box_type_key(base)
        if key:
            hit += 1
            by_type[key] = by_type.get(key, 0) + 1
        else:
            unknown.append(
                {
                    "box_id": str(b.get("box_id") or b.get("id") or "?"),
                    "box_type": btype,
                    "base_box_type": base,
                }
            )
            label = btype or base or "unknown"
            by_type[label] = by_type.get(label, 0) + 1
    rate = (hit / total) if total else 1.0
    return {
        "n_boxes": total,
        "n_hit": hit,
        "n_unknown": len(unknown),
        "n_passthrough": passthrough_n,
        "hit_rate": round(rate, 4),
        "by_type": by_type,
        "unknown": unknown[:20],
        "ok": rate >= 0.90 or total == 0,
        "threshold": 0.90,
    }


def standard_box_types_for_packing() -> Dict[str, Dict[str, Any]]:
    """转为 packing.py 使用的 STANDARD_BOX_TYPES 形态。"""
    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in (load_kb().get("box_types") or {}).items():
        outer = spec.get("outer_mm") or {}
        # 主名 + 别名都注册，便于选型
        names = [key] + list(spec.get("aliases") or [])
        entry = {
            "外尺寸_mm": {
                "长": float(outer.get("length") or 0),
                "宽": float(outer.get("width") or 0),
                "高": float(outer.get("height") or 0),
            },
            "壁厚_mm": float(spec.get("wall_mm") or 40),
            "自重_kg": float(spec.get("tare_kg") or 0),
            "最大载荷_kg": float(spec.get("max_payload_kg") or 1500),
            "铁架": bool(spec.get("is_steel_frame")),
            "安全系数": float(spec.get("safety_factor") or 1.8),
            "calc_strategy": spec.get("calc_strategy") or "simple",
            "kb_key": key,
        }
        for n in names:
            out[n] = entry
    return out


def container_specs_for_tools() -> Dict[str, Dict[str, float]]:
    """consolidation / bin3d 用柜型表。"""
    out: Dict[str, Dict[str, float]] = {}
    for ctype, spec in (load_kb().get("containers") or {}).items():
        if ctype == "rules":
            continue
        inner = spec.get("inner_mm") or {}
        out[ctype] = {
            "长_m": float(inner.get("length") or 0) / 1000.0,
            "宽_m": float(inner.get("width") or 0) / 1000.0,
            "高_m": float(inner.get("height") or 0) / 1000.0,
            "最大载重_kg": float(spec.get("max_load_kg") or 20000),
        }
    return out


def container_inner_mm() -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for ctype, spec in (load_kb().get("containers") or {}).items():
        if ctype == "rules":
            continue
        inner = spec.get("inner_mm") or {}
        out[ctype] = {
            "L": float(inner.get("length") or 0),
            "W": float(inner.get("width") or 0),
            "H": float(inner.get("height") or 0),
            "max_load_kg": float(spec.get("max_load_kg") or 20000),
        }
    return out


def clearance_mm() -> float:
    rules = (load_kb().get("containers") or {}).get("rules") or {}
    cl = rules.get("clearance_mm") or [50, 100]
    if isinstance(cl, (list, tuple)) and cl:
        return float(cl[0])
    return 50.0


def safety_factor_for_box(box_type: str, gross_kg: float = 0) -> float:
    spec = get_box_spec(box_type) or {}
    gamma = float(spec.get("safety_factor") or 1.8)
    st = load_kb().get("structure") or {}
    lc = st.get("load_combination") or {}
    if gross_kg > 2000:
        gamma = max(gamma, float(lc.get("gamma_if_gross_over_2000kg") or 2.2))
    return gamma


def working_stress() -> Dict[str, float]:
    st = (load_kb().get("structure") or {}).get("working_stress_mpa") or {}
    return {
        "wood_fb": float(st.get("wood_fb") or 10),
        "steel_fb": float(st.get("steel_fb") or 150),
        "wood_floor_kg_per_m2": float(st.get("wood_floor_kg_per_m2") or 800),
        "steel_floor_kg_per_m2": float(st.get("steel_floor_kg_per_m2") or 2500),
    }


def deflection_limit_ratio() -> float:
    return float((load_kb().get("structure") or {}).get("deflection_limit_ratio") or 200)


def risk_thresholds() -> Dict[str, Any]:
    return dict(load_kb().get("risk_rules") or {})


def merge_rules() -> Dict[str, Any]:
    return dict(load_kb().get("merge_rules") or {})


def classify_by_kb(
    length_mm: float,
    unit_kg: float,
    total_kg: float,
    *,
    height_mm: float = 0.0,
    width_mm: float = 0.0,
    text: str = "",
) -> str:
    """扩展类：超长 > 薄板 > 重件 > 精密/工厂架关键词 > 普通。"""
    cats = (load_kb().get("materials") or {}).get("categories") or {}
    over = cats.get("超长件") or {}
    heavy = cats.get("重件") or {}
    thin = cats.get("薄板") or {}
    blob = (text or "").lower()
    if length_mm >= float(over.get("length_mm_gte") or 4000):
        return "超长件"
    h_lim = float(thin.get("height_mm_lte") or 80)
    l_lim = float(thin.get("length_mm_gte") or 1500)
    if 0 < height_mm <= h_lim and length_mm >= l_lim:
        return "薄板"
    if unit_kg >= float(heavy.get("unit_weight_kg_gte") or 200):
        return "重件"
    if total_kg >= float(heavy.get("or_total_weight_kg_gte") or 1500):
        return "重件"
    prec = cats.get("精密件") or {}
    for kw in prec.get("keywords") or []:
        if str(kw).lower() in blob:
            return "精密件"
    fac = cats.get("工厂架") or {}
    for kw in fac.get("keywords") or []:
        if str(kw).lower() in blob:
            return "工厂架"
    if "异形" in blob or "非标" in blob:
        return "异形件"
    return "普通件"


# 物料 category 白名单（parser / API）
MATERIAL_CATEGORIES = (
    "超长件",
    "重件",
    "薄板",
    "异形件",
    "精密件",
    "工厂架",
    "普通件",
)


def color_for_box_type(box_type: str) -> str:
    colors = (load_kb().get("visualization") or {}).get("colors_by_box_type") or {}
    if box_type in colors:
        return colors[box_type]
    key = resolve_box_type_key(box_type)
    if key and key in colors:
        return colors[key]
    return "#4C78A8"


def reinforcement_advice(length_mm: float, unit_kg: float, box_gross_kg: float) -> List[str]:
    actions: List[str] = []
    if length_mm > 5000:
        actions.append("专用超长架 + 多点支撑")
    elif length_mm > 3000:
        actions.append("纵向加强或铁架")
    if unit_kg > 500:
        actions.append("加强底座 + 限位")
    elif unit_kg > 200:
        actions.append("底部托盘/横梁")
    if box_gross_kg > 2000:
        actions.append("必须铁箱 + 全项校核")
    elif box_gross_kg > 1000:
        actions.append("优先铁箱/钢骨箱")
    return actions


def prefer_container() -> str:
    rules = (load_kb().get("containers") or {}).get("rules") or {}
    return str(rules.get("prefer_container") or "40HQ")
