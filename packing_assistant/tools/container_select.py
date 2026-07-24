"""
柜型选型（主控开头/结尾共用）。

行业经验（实务装货，非理论满容）:
- 20GP：重货优先，实务约 25–28 CBM / 载重高
- 40GP：常规轻泡与中等体积，实务约 55–58 CBM
- 40HQ：超高/轻泡，实务约 60–68 CBM；同体积货用 HQ 会拉低容积率

规则（可解释）:
1. 最长件 > 5900 → 至少 40 尺
2. 单箱/单件过高 > 2400 → 优先 40HQ
3. 估算货体外廓体积 V、毛重 W
4. 若 V 较小且 W/V 大（重货）→ 20GP
5. 若 V 中等 → 40GP
6. 若 V 大或有超高 → 40HQ
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# 实务可用容积（m³）— 选型阈值用略保守值
PRACTICAL_CBM = {
    "20GP": 27.0,
    "40GP": 56.0,
    "40HQ": 65.0,
}
INNER_MM = {
    "20GP": {"L": 5898, "W": 2352, "H": 2385, "max_kg": 21000},
    "40GP": {"L": 12032, "W": 2352, "H": 2385, "max_kg": 26680},
    "40HQ": {"L": 12032, "W": 2352, "H": 2698, "max_kg": 26480},
}


def _est_from_materials(materials: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    max_L = 0.0
    max_H = 0.0
    net = 0.0
    # 粗估：件体积×1.35 作箱体外廓放大（合箱/壁厚）
    piece_vol = 0.0
    for m in materials:
        L = float(m.get("length_mm") or m.get("L") or 0)
        W = float(m.get("width_mm") or m.get("W") or 0)
        H = float(m.get("height_mm") or m.get("H") or 0)
        q = max(int(m.get("quantity") or m.get("q") or 1), 1)
        wt = float(m.get("total_weight_kg") or 0) or float(m.get("weight_kg") or 0) * q
        max_L = max(max_L, L)
        max_H = max(max_H, H)
        net += wt
        piece_vol += (L * W * H * q) / 1e9
    # 箱体外廓实心粗估（钢结构合箱/模块化外廓放大约 2.2~2.8 倍）
    cargo_m3 = max(piece_vol * 2.6, piece_vol + 1.0)
    # 有长件时再放大，避免误选 20GP 导致双柜
    if max_L >= 3500:
        cargo_m3 = max(cargo_m3, 16.0)
    gross = net * 1.35  # 箱自重粗估
    return {
        "max_length_mm": max_L,
        "max_height_mm": max_H,
        "net_kg": net,
        "gross_kg_est": gross,
        "cargo_m3_est": cargo_m3,
    }


def _est_from_boxes(boxes: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    max_L = 0.0
    max_H = 0.0
    gross = 0.0
    cargo_m3 = 0.0
    for b in boxes:
        o = b.get("outer_size_mm") or {}
        L = float(o.get("length") or 0)
        W = float(o.get("width") or 0)
        H = float(o.get("height") or 0)
        max_L = max(max_L, L)
        max_H = max(max_H, H)
        gross += float(b.get("gross_weight_kg") or 0)
        cargo_m3 += L * W * H / 1e9
    return {
        "max_length_mm": max_L,
        "max_height_mm": max_H,
        "net_kg": gross * 0.85,
        "gross_kg_est": gross,
        "cargo_m3_est": cargo_m3,
    }


def recommend_container(
    *,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    user_hint: Optional[str] = None,
    phase: str = "start",
) -> Dict[str, Any]:
    """
    返回推荐柜型与理由。
    phase: start | end
    """
    if boxes:
        est = _est_from_boxes(boxes)
        source = "boxes"
    else:
        est = _est_from_materials(materials or [])
        source = "materials"

    max_L = est["max_length_mm"]
    max_H = est["max_height_mm"]
    V = est["cargo_m3_est"]
    W = est["gross_kg_est"]
    density = (W / V) if V > 0.1 else 0.0  # kg/m3

    reasons: List[str] = []
    candidates = ["20GP", "40GP", "40HQ"]

    # 长度约束
    if max_L > 5900:
        candidates = [c for c in candidates if c != "20GP"]
        reasons.append(f"最长件/箱 {max_L:.0f}mm > 5900，排除 20GP")
    # 高度约束
    if max_H > 2350:
        candidates = ["40HQ"] if "40HQ" in candidates else candidates
        reasons.append(f"高度 {max_H:.0f}mm 偏高，倾向 40HQ")

    def fits_weight(ct: str) -> bool:
        return W <= INNER_MM[ct]["max_kg"] * 0.95

    def score(ct: str) -> Tuple[float, List[str]]:
        notes: List[str] = []
        prac = PRACTICAL_CBM[ct]
        # 体积占用（相对实务可用容）
        fill = V / prac if prac else 1
        # 理想填充 0.45–0.85
        if fill < 0.25:
            vol_s = 20 + fill * 80  # 太空
            notes.append(f"{ct} 预估填充 {fill:.0%} 偏空")
        elif fill > 1.05:
            vol_s = 10
            notes.append(f"{ct} 预估体积可能超实务可用容")
        else:
            vol_s = 100 - abs(fill - 0.65) * 80
        # 重量
        wfill = W / INNER_MM[ct]["max_kg"]
        if wfill > 1.0:
            wt_s = 0
            notes.append(f"{ct} 可能超重")
        elif density > 400 and ct == "20GP":
            wt_s = 95  # 重货小柜
            notes.append("重货密度高，20GP 吃重更划算")
        elif density < 150 and ct == "40HQ":
            wt_s = 90
            notes.append("轻泡货，高柜吃体积")
        else:
            wt_s = 70 + min(wfill, 0.8) * 30
        # 能 1 柜装下加分
        one_bin = 30 if fill <= 0.95 and wfill <= 0.95 else 0
        # HQ 惩罚：同体积用 HQ 容积率虚低
        hq_pen = 8 if ct == "40HQ" and max_H <= 2200 and fill < 0.7 else 0
        total = vol_s * 0.45 + wt_s * 0.4 + one_bin - hq_pen
        return total, notes

    scored = []
    for ct in candidates:
        if not fits_weight(ct) and V > PRACTICAL_CBM[ct] * 0.3:
            s, n = score(ct)
            s -= 25
            n.append("单柜重量紧张，可能需多柜")
            scored.append((s, ct, n))
        else:
            s, n = score(ct)
            # 体积超过单柜实务容太多 → 20GP 多柜惩罚（优先 1×40）
            if ct == "20GP" and V > PRACTICAL_CBM["20GP"] * 0.85:
                s -= 35
                n.append("货体积接近/超过 1×20GP 实务容，易被迫双柜，降权")
            if ct == "40GP" and V <= PRACTICAL_CBM["40GP"] * 0.9 and max_L <= 5800:
                s += 12
                n.append("体积适合 1×40GP 装下")
            scored.append((s, ct, n))

    scored.sort(key=lambda x: -x[0])
    best_s, best, best_notes = scored[0]
    reasons.extend(best_notes)

    user = (user_hint or "").upper().replace(" ", "")
    if user in INNER_MM and user != best:
        reasons.append(f"对照：原先倾向 {user}，综合体积/重量后推荐 {best}")

    # 预估利用率
    prac = PRACTICAL_CBM[best]
    max_kg = INNER_MM[best]["max_kg"]
    pred = {
        "space_est": min(V / (INNER_MM[best]["L"] * INNER_MM[best]["W"] * INNER_MM[best]["H"] / 1e9), 1.0),
        "weight_est": min(W / max_kg, 1.0),
        "practical_fill_est": min(V / prac, 1.5),
    }

    alt = [c for _, c, _ in scored[1:3]]

    return {
        "phase": phase,
        "source": source,
        "recommended": best,
        "alternatives": alt,
        "score": round(best_s, 1),
        "reasons": reasons[:8],
        "estimates": {
            "max_length_mm": round(max_L, 1),
            "max_height_mm": round(max_H, 1),
            "cargo_m3_est": round(V, 3),
            "gross_kg_est": round(W, 1),
            "density_kg_per_m3": round(density, 1),
        },
        "predicted_util": {k: round(v, 4) for k, v in pred.items()},
        "stacking": {
            "recommend_two_layer": max_H <= 1300 or (boxes is not None and _many_stackable(boxes)),
            "note": "单箱高≤1300mm 且非超长顶层时，建议二层堆码提高层高利用率",
        },
    }


def _many_stackable(boxes: Sequence[Dict[str, Any]]) -> bool:
    n = 0
    for b in boxes:
        o = b.get("outer_size_mm") or {}
        H = float(o.get("height") or 0)
        sp = b.get("special_attributes") or []
        if H <= 1300 and "超长" not in sp and "内容物超长" not in sp:
            n += 1
    return n >= 2


def compare_after_load(
    boxes: Sequence[Dict[str, Any]],
    current_type: str,
    plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """装载后复核：若换柜型 theoretically 更好则建议。"""
    rec = recommend_container(boxes=boxes, user_hint=current_type, phase="end")
    cur = (current_type or "40HQ").upper()
    plan = plan or {}
    actual = {
        "space": plan.get("space_utilization"),
        "weight": plan.get("weight_utilization"),
        "floor": plan.get("floor_utilization_avg"),
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
    }
    switch = rec["recommended"] != cur
    msg = (
        f"主控复核：当前 {cur}，推荐 {rec['recommended']}"
        + ("（建议换柜）" if switch else "（维持）")
    )
    return {
        **rec,
        "current": cur,
        "suggest_switch": switch,
        "actual_util": actual,
        "review_message": msg,
    }
