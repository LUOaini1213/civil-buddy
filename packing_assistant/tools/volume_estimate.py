"""
体积 / 柜数估算（重量与体积双约束，避免体积算虚）。

分层体积（由紧到松）：
1. piece_solid_m3   件体外接长方体 Σ(L×W×H×qty) —— 零件实体占位下界
2. pack_effective_m3  件体积 × 货种包装膨胀 —— **估柜用的体积分子**
3. crate_outer_m3    已成箱外廓实心 —— 仅 3D 摆柜几何用，**禁止**拿虚大当量外廓当估柜分子

柜数：
  n = max(
    ceil(gross_kg / payload_kg),
    ceil(pack_effective_m3 / (container_m3 × fill_ratio)),
  )

COSCO 40HQ 默认：payload=28610 kg，container_m3=76.4
fill_ratio / η 实务约 0.80–0.85（行业可用容积），不是 1.0。
成箱后订柜体积：min(outer_m3, content_m3 × k)，k≤1.5–1.8。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 货种 → 包装/堆码膨胀系数（相对件体外接 AABB）
# 钢结构应小；玻璃/板材略大。切忌 2.5× 以上当默认。
CATEGORY_PACK_FACTOR: Dict[str, float] = {
    "steel": 1.30,  # 铁件/钢通：合箱+间隙
    "aluminum_profile": 1.35,
    "aluminum_panel": 1.50,
    "glass": 1.80,
    "hardware": 1.40,  # 五金箱
    "timber_panel": 1.45,
    "general": 1.40,
}

# 物料组关键词 → 货种
_GROUP_HINTS: List[Tuple[str, str]] = [
    ("玻璃", "glass"),
    ("Glass", "glass"),
    ("铝板", "aluminum_panel"),
    ("铝材", "aluminum_profile"),
    ("铁件", "steel"),
    ("不锈钢", "steel"),
    ("紧固", "hardware"),
    ("螺丝", "hardware"),
    ("螺栓", "hardware"),
    ("胶条", "hardware"),
    ("垫块", "hardware"),
    ("木板", "timber_panel"),
    ("瓦楞", "timber_panel"),
]


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def infer_category(material: Dict[str, Any]) -> str:
    text = " ".join(
        str(material.get(k) or "")
        for k in ("spec", "name", "note", "group", "物料组描述", "category")
    )
    for key, cat in _GROUP_HINTS:
        if key in text:
            return cat
    # 长细比粗判
    L = _f(material.get("length_mm") or material.get("L"))
    W = _f(material.get("width_mm") or material.get("W"))
    H = _f(material.get("height_mm") or material.get("H"))
    if L >= 2000 and max(W, H) <= 300:
        return "steel"
    if min(W, H) <= 50 and max(W, H) >= 800:
        return "aluminum_panel"
    return "general"


def piece_solid_m3(materials: Sequence[Dict[str, Any]]) -> float:
    """件体外接长方体体积合计 (m³)。"""
    total = 0.0
    for m in materials:
        L = _f(m.get("length_mm") or m.get("L"))
        W = _f(m.get("width_mm") or m.get("W"))
        H = _f(m.get("height_mm") or m.get("H"))
        q = max(_f(m.get("quantity") or m.get("q") or 1), 1)
        total += L * W * H * q / 1e9
    return total


def pack_effective_m3(
    materials: Sequence[Dict[str, Any]],
    *,
    default_factor: Optional[float] = None,
) -> Dict[str, Any]:
    """
    估柜用有效体积 = Σ(件体积 × 货种膨胀)。
    返回明细便于审计「体积是否虚大」。
    """
    rows = []
    solid = 0.0
    effective = 0.0
    for m in materials:
        L = _f(m.get("length_mm") or m.get("L"))
        W = _f(m.get("width_mm") or m.get("W"))
        H = _f(m.get("height_mm") or m.get("H"))
        q = max(_f(m.get("quantity") or m.get("q") or 1), 1)
        v = L * W * H * q / 1e9
        cat = str(m.get("volume_category") or infer_category(m))
        fac = float(
            m.get("pack_factor")
            or default_factor
            or CATEGORY_PACK_FACTOR.get(cat, CATEGORY_PACK_FACTOR["general"])
        )
        # 硬上限：估柜膨胀不超过 1.8，防止再出现 2.6× 虚高
        fac = min(max(fac, 1.05), 1.80)
        solid += v
        effective += v * fac
        rows.append(
            {
                "id": m.get("id") or m.get("name"),
                "category": cat,
                "solid_m3": round(v, 4),
                "pack_factor": fac,
                "effective_m3": round(v * fac, 4),
            }
        )
    return {
        "piece_solid_m3": round(solid, 4),
        "pack_effective_m3": round(effective, 4),
        "inflation_ratio": round(effective / solid, 3) if solid > 1e-9 else 1.0,
        "by_line": rows,
    }


def crate_outer_m3(boxes: Sequence[Dict[str, Any]]) -> float:
    """已成箱外廓实心体积（3D 几何用，不作材料估柜分子）。"""
    total = 0.0
    for b in boxes:
        o = b.get("outer_size_mm") or b.get("外尺寸_mm") or {}
        L = _f(o.get("length") or o.get("长"))
        W = _f(o.get("width") or o.get("宽"))
        H = _f(o.get("height") or o.get("高"))
        total += L * W * H / 1e9
    return round(total, 4)


def box_content_m3(box: Dict[str, Any]) -> float:
    """单箱内容件体积 m³。"""
    if box.get("content_m3") is not None:
        return _f(box.get("content_m3"))
    if box.get("content_volume_m3") is not None:
        return _f(box.get("content_volume_m3"))
    total = 0.0
    for c in box.get("content") or box.get("装载内容") or []:
        dims = c.get("outer_size_mm") or c.get("外尺寸_mm") or {}
        L = _f(dims.get("length") or dims.get("长"))
        W = _f(dims.get("width") or dims.get("宽"))
        H = _f(dims.get("height") or dims.get("高"))
        q = max(_f(c.get("quantity") or c.get("数量") or 1), 1)
        total += L * W * H * q / 1e9
    return total


def box_outer_m3(box: Dict[str, Any]) -> float:
    if box.get("outer_m3") is not None:
        return _f(box.get("outer_m3"))
    o = box.get("outer_size_mm") or box.get("外尺寸_mm") or {}
    L = _f(o.get("length") or o.get("长"))
    W = _f(o.get("width") or o.get("宽"))
    H = _f(o.get("height") or o.get("高"))
    return L * W * H / 1e9


def box_pack_effective_m3(box: Dict[str, Any], *, k_max: float = 1.60) -> float:
    """
    单箱订柜贡献体积 = min(outer_m3, content_m3 × k)
    空心铁架 fill 低时不会把 outer 全算进订柜。
    """
    outer = box_outer_m3(box)
    content = box_content_m3(box)
    fill = _f(box.get("crate_fill_ratio"))
    if fill <= 0 and outer > 1e-12:
        fill = content / outer
    # 低填充时 k 取小一些
    if fill > 0 and fill < 0.20:
        k = min(k_max, 1.35)
    elif fill < 0.35:
        k = min(k_max, 1.50)
    else:
        k = k_max
    if content <= 1e-12:
        # 无内容尺寸：对外廓打折，避免实心方块
        return outer * 0.45
    return min(outer, content * k) if outer > 0 else content * k


def booking_volume_from_boxes(
    boxes: Sequence[Dict[str, Any]],
    *,
    k_max: float = 1.60,
) -> Dict[str, Any]:
    """成箱后订柜有效体积 Σ min(outer, content×k)。"""
    rows = []
    v_eff = 0.0
    v_outer = 0.0
    v_content = 0.0
    for b in boxes:
        o = box_outer_m3(b)
        c = box_content_m3(b)
        e = box_pack_effective_m3(b, k_max=k_max)
        v_outer += o
        v_content += c
        v_eff += e
        rows.append(
            {
                "box_id": b.get("box_id") or b.get("箱号"),
                "outer_m3": round(o, 4),
                "content_m3": round(c, 4),
                "booking_m3": round(e, 4),
                "fill": round(c / o, 4) if o > 1e-12 else 0.0,
            }
        )
    return {
        "mode": "pack_effective_min_outer_content",
        "booking_volume_m3": round(v_eff, 4),
        "crate_outer_m3": round(v_outer, 4),
        "content_solid_m3": round(v_content, 4),
        "volume_m3": round(v_eff, 4),
        "by_box": rows,
        "note": "订柜体积=Σ min(outer, content×k)；3D 仍用 outer",
    }


def container_spec(container_type: str = "40HQ") -> Dict[str, float]:
    """从知识库读柜；失败则 COSCO 40HQ 铭牌默认。"""
    try:
        from packing_assistant.knowledge import load_kb

        c = (load_kb().get("containers") or {}).get(container_type) or {}
        inner = c.get("inner_mm") or {}
        L = float(inner.get("length") or 12032)
        W = float(inner.get("width") or 2352)
        H = float(inner.get("height") or 2698)
        return {
            "payload_kg": float(c.get("max_load_kg") or 28610),
            "tare_kg": float(c.get("tare_kg") or c.get("tare_ton_approx", 3.89) * 1000),
            "max_gross_kg": float(c.get("max_gross_kg") or 32500),
            "inner_m3": L * W * H / 1e9,
            "theory_m3": float(c.get("volume_m3_theory") or 76.4),
        }
    except Exception:
        return {
            "payload_kg": 28610.0,
            "tare_kg": 3890.0,
            "max_gross_kg": 32500.0,
            "inner_m3": 76.4,
            "theory_m3": 76.4,
        }


def estimate_containers(
    *,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    net_kg: Optional[float] = None,
    gross_kg: Optional[float] = None,
    container_type: str = "40HQ",
    fill_ratio: float = 0.82,
    volume_mode: str = "pack_effective",
) -> Dict[str, Any]:
    """
    双约束估柜。

    volume_mode:
      - pack_effective: 材料=件×膨胀；成箱=min(outer, content×k)（推荐订柜）
      - piece_solid: 仅件体积（下界）
      - crate_outer: 已成箱外廓（仅调试；勿作订柜）
    fill_ratio / η: 柜容积可用比例，默认 0.82（行业 80–85%）
    """
    spec = container_spec(container_type)
    payload = spec["payload_kg"]
    cont_m3 = spec["theory_m3"] or spec["inner_m3"]
    fill = min(max(float(fill_ratio), 0.50), 0.90)
    usable_m3 = cont_m3 * fill

    # 重量
    if gross_kg is None:
        if net_kg is not None:
            gross_kg = float(net_kg) * 1.12  # 箱皮粗加
        elif materials:
            net = sum(
                _f(m.get("total_weight_kg"))
                or _f(m.get("weight_kg")) * max(_f(m.get("quantity") or 1), 1)
                for m in materials
            )
            gross_kg = net * 1.12
        elif boxes:
            gross_kg = sum(
                _f(b.get("gross_weight_kg") or b.get("毛重_kg") or b.get("net_weight_kg"))
                for b in boxes
            )
        else:
            gross_kg = 0.0
    gross_kg = float(gross_kg or 0)
    n_weight = max(1, int(math.ceil(gross_kg / payload - 1e-9))) if gross_kg > 0 else 0

    # 体积
    vol_detail: Dict[str, Any] = {}
    if volume_mode == "crate_outer" and boxes:
        v = crate_outer_m3(boxes)
        vol_detail = {"mode": "crate_outer", "volume_m3": v}
    elif boxes and volume_mode in ("pack_effective", "boxes_booking", ""):
        bv = booking_volume_from_boxes(boxes)
        v = float(bv["booking_volume_m3"])
        vol_detail = bv
    elif materials:
        pe = pack_effective_m3(materials)
        if volume_mode == "piece_solid":
            v = pe["piece_solid_m3"]
        else:
            v = pe["pack_effective_m3"]
        vol_detail = {"mode": volume_mode, **pe}
    elif boxes:
        bv = booking_volume_from_boxes(boxes)
        v = float(bv["booking_volume_m3"])
        vol_detail = bv
    else:
        v = 0.0
        vol_detail = {"mode": volume_mode, "volume_m3": 0.0}

    n_volume = max(1, int(math.ceil(v / usable_m3 - 1e-9))) if v > 0 else 0
    n_final = max(n_weight, n_volume, 1 if (gross_kg > 0 or v > 0) else 0)

    binding = "weight" if n_weight >= n_volume else "volume"
    if n_weight == n_volume:
        binding = "both"

    return {
        "container_type": container_type,
        "payload_kg": payload,
        "container_m3": cont_m3,
        "fill_ratio": fill,
        "usable_m3_per_container": round(usable_m3, 3),
        "gross_kg": round(gross_kg, 1),
        "volume_m3": round(v, 4),
        "volume_detail": vol_detail,
        "containers_by_weight": n_weight,
        "containers_by_volume": n_volume,
        "containers_needed": n_final,
        "binding_constraint": binding,
        "formula": "max(ceil(G/payload), ceil(V_eff/(V_cont*fill)))",
        "warning": (
            None
            if vol_detail.get("mode") != "crate_outer"
            else "crate_outer 模式仅用于真实成箱；虚当量外廓会导致体积约束过紧"
        ),
    }
