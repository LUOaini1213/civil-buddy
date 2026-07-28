"""
结构计算（升一档 · 半严格三件套）。

步骤：
1. 读取箱型/尺寸/货重/自重/吊点
2. 荷载组合 Fd = G × γ
3. 匹配截面库（槽钢/方管 W、I、i）
4. 底板抗弯（跨距、M、σ、挠度）
5. 框架立柱轴压稳定（N、λ=L0/i）
6. 局部承压
7. 吊点分载
8. 综合判定 + 加固建议

非正式签章计算书；有图纸时用真实截面覆盖预置表。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from packing_assistant.tools.section_provider import get_box_default_sections

G = 9.80665  # m/s²


def _stress_defaults():
    try:
        from packing_assistant.knowledge import clearance_mm, deflection_limit_ratio, working_stress

        ws = working_stress()
        return (
            float(ws["wood_fb"]),
            float(ws["steel_fb"]),
            float(ws["wood_floor_kg_per_m2"]),
            float(ws["steel_floor_kg_per_m2"]),
            float(clearance_mm()),
            float(deflection_limit_ratio()),
        )
    except Exception:
        return 10.0, 150.0, 800.0, 2500.0, 50.0, 200.0


WOOD_FB_MPA, STEEL_FB_MPA, WOOD_FLOOR_KG_PER_M2, STEEL_FLOOR_KG_PER_M2, CLEARANCE_MM, _DEFL_RATIO = (
    _stress_defaults()
)
DEFAULT_SAFETY_FACTOR = 1.8

# 允许长细比（受压构件经验）
LAMBDA_ALLOW_STEEL = 150.0
LAMBDA_ALLOW_WOOD = 120.0


def orient_dims(L: float, W: float, H: float) -> Tuple[float, float, float]:
    vals = sorted([float(L or 0), float(W or 0), float(H or 0)], reverse=True)
    return vals[0], vals[1], vals[2]


# ---------------------------------------------------------------------------
# 几何堆码（沿用，供装载空间粗检）
# ---------------------------------------------------------------------------

def _pack_cross_section(
    pieces: List[Tuple[float, float]],
    max_width: float,
) -> Tuple[float, float, bool]:
    if not pieces:
        return 0.0, 0.0, True
    ordered = sorted(pieces, key=lambda p: max(p[0], p[1]), reverse=True)
    shelves: List[List[float]] = []
    all_fit = True
    for w0, h0 in ordered:
        orients = [(w0, h0), (h0, w0)]
        placed = False
        for ow, oh in orients:
            if max_width > 0 and ow > max_width + 1e-6:
                continue
            for shelf in shelves:
                sh, sw = shelf[0], shelf[1]
                if max_width > 0 and sw + ow > max_width + 1e-6:
                    continue
                if oh <= sh + 1e-6:
                    shelf[1] = sw + ow
                    placed = True
                    break
                if max_width > 0 and sw + ow <= max_width + 1e-6:
                    shelf[0] = max(sh, oh)
                    shelf[1] = sw + ow
                    placed = True
                    break
            if placed:
                break
            if max_width <= 0 or ow <= max_width + 1e-6:
                shelves.append([oh, ow])
                placed = True
                break
        if not placed:
            all_fit = False
            shelves.append([max(h0, w0), max(h0, w0)])
    used_w = max((s[1] for s in shelves), default=0.0)
    used_h = sum(s[0] for s in shelves)
    return used_w, used_h, all_fit


def cargo_envelope(
    items: List[Dict[str, Any]],
    inner_length_mm: Optional[float] = None,
    inner_width_mm: Optional[float] = None,
    inner_height_mm: Optional[float] = None,
) -> Dict[str, float]:
    if not items:
        return {
            "长": 0.0,
            "宽": 0.0,
            "高": 0.0,
            "体积_mm3": 0.0,
            "件数": 0,
            "截面可装入": True,
            "纵向工位截面件数": 0,
        }
    max_len = 0.0
    used_len = 0.0
    total_vol = 0.0
    total_pcs = 0
    pieces: List[Tuple[float, float]] = []
    gap = CLEARANCE_MM / 2.0
    for it in items:
        dims = it.get("外尺寸_mm") or {}
        L, W, H = orient_dims(dims.get("长"), dims.get("宽"), dims.get("高"))
        qty = max(int(it.get("数量") or 1), 1)
        max_len = max(max_len, L)
        total_pcs += qty
        total_vol += L * W * H * qty
        if inner_length_mm and L > 0:
            n_along = max(1, int(float(inner_length_mm) // (L + gap)))
        else:
            n_along = max(1, int(3000 // max(L + gap, 1)))
        n_cross = int(math.ceil(qty / n_along))
        rows_along = int(math.ceil(qty / max(n_cross, 1)))
        used_len = max(used_len, rows_along * L + max(rows_along - 1, 0) * gap)
        for _ in range(n_cross):
            pieces.append((W, H))
    bin_w = float(inner_width_mm) if inner_width_mm else 1000.0
    env_w, env_h, fit = _pack_cross_section(pieces, bin_w)
    if inner_height_mm is not None and env_h > float(inner_height_mm) + 1e-6:
        fit = False
    env_len = max(max_len, used_len)
    if inner_length_mm is not None and env_len > float(inner_length_mm) + 1e-6:
        fit = False
    return {
        "长": round(env_len, 1),
        "宽": round(env_w, 1),
        "高": round(env_h, 1),
        "体积_mm3": total_vol,
        "件数": total_pcs,
        "截面可装入": fit,
        "纵向工位截面件数": len(pieces),
    }


def calc_weights(items: List[Dict[str, Any]], box_tare_kg: float) -> Dict[str, float]:
    net = 0.0
    for it in items:
        qty = max(int(it.get("数量") or 1), 1)
        unit = float(it.get("单重_kg") or 0)
        if it.get("总重_kg") is not None:
            net += float(it["总重_kg"])
        else:
            net += qty * unit
    tare = float(box_tare_kg or 0)
    return {
        "净重_kg": round(net, 2),
        "箱自重_kg": round(tare, 2),
        "毛重_kg": round(net + tare, 2),
    }


def geometry_fit(
    envelope: Dict[str, float],
    inner: Dict[str, float],
    clearance_mm: float = CLEARANCE_MM,
) -> Dict[str, Any]:
    need_L = envelope.get("长", 0) + clearance_mm
    need_W = envelope.get("宽", 0) + clearance_mm
    need_H = envelope.get("高", 0) + clearance_mm
    inn_L = float(inner.get("长") or 0)
    inn_W = float(inner.get("宽") or 0)
    inn_H = float(inner.get("高") or 0)
    fit_default = need_L <= inn_L and need_W <= inn_W and need_H <= inn_H
    fit_rot = need_L <= inn_L and need_W <= inn_H and need_H <= inn_W
    ok = fit_default or fit_rot
    cargo_vol = float(envelope.get("体积_mm3") or 0)
    box_vol = inn_L * inn_W * inn_H
    vol_util = (cargo_vol / box_vol * 100) if box_vol > 0 else 0.0
    return {
        "尺寸适配": ok,
        "需求尺寸_mm": {"长": need_L, "宽": need_W, "高": need_H},
        "内净空_mm": {"长": inn_L, "宽": inn_W, "高": inn_H},
        "间隙_mm": clearance_mm,
        "体积利用率": f"{min(vol_util, 999):.1f}%",
        "体积利用率_数值": round(vol_util, 2),
    }


# ---------------------------------------------------------------------------
# 半严格：荷载 / 底板 / 框架 / 局部 / 吊点
# ---------------------------------------------------------------------------

def design_load_kg(gross_kg: float, gamma: float) -> float:
    return float(gross_kg) * float(gamma)


def check_bottom_bending(
    *,
    design_load_kg: float,
    box_length_mm: float,
    beam: Dict[str, Any],
    is_steel: bool,
    gamma: float,
    defl_ratio: float = 200.0,
) -> Dict[str, Any]:
    """
    底板纵梁抗弯。
    跨距取梁间距近似：L_span ≈ box_length / (count) 不合理；
    实际纵梁沿箱长，跨距取底板横向支撑间距，默认 min(1200, 箱宽相关) 或 箱长/3。
    这里：跨距 span = min(1500, max(600, box_length_mm / (count+1)))
    弯矩按简支均布：每根梁分担 Fd/count，q = N_beam/span, M = q L^2 / 8
    """
    count = max(int(beam.get("count") or 1), 1)
    # 有效根数偏安全：最多按 2 根计满载（规范说明）
    n_eff = min(count, 2) if count > 1 else 1
    # 对 3 根及以上仍给 2.5 有效
    if count >= 3:
        n_eff = 2.5

    span = min(1500.0, max(600.0, float(box_length_mm) / (count + 1)))
    # 也可用纵梁沿长时跨距=箱长、多根并联：M 更小；取跨中最不利
    span_long = float(box_length_mm)
    # 两种模型取较不利应力
    W_cm3 = float(beam.get("W_cm3") or 25.3)
    I_cm4 = float(beam.get("I_cm4") or 101.0)
    W_mm3 = W_cm3 * 1e3  # cm³ → mm³
    I_mm4 = I_cm4 * 1e4  # cm⁴ → mm⁴

    total_N = design_load_kg * G  # N
    # 模型A：沿箱长简支，荷载 n_eff 根分摊
    q_a = total_N / n_eff / max(span_long, 1)  # N/mm
    M_a = q_a * span_long * span_long / 8.0  # N·mm
    # 模型B：横向跨距 span
    q_b = total_N / n_eff / max(span, 1)
    M_b = q_b * span * span / 8.0
    if M_a >= M_b:
        M, span_use, q = M_a, span_long, q_a
        model = "纵梁沿箱长简支均布"
    else:
        M, span_use, q = M_b, span, q_b
        model = "底板横向跨距简支"

    sigma = M / W_mm3 if W_mm3 > 0 else float("inf")  # MPa
    fb = STEEL_FB_MPA if is_steel else WOOD_FB_MPA
    # 许用取材料强度/γ 已在 design_load 中含 γ，此处再保留材料设计值
    allow = fb / max(gamma * 0.5, 1.0)  # 避免双重过严；主 γ 在 Fd
    # 更清晰：Fd 已放大，应力与材料设计值直接比（Q235 取 145~160）
    allow = STEEL_FB_MPA if is_steel else WOOD_FB_MPA
    ok_stress = sigma <= allow + 1e-6

    E = 2.06e5 if is_steel else 1.0e4
    delta = (5 * q * span_use**4) / (384 * E * I_mm4) if I_mm4 > 0 else float("inf")
    delta_limit = span_use / defl_ratio
    ok_defl = delta <= delta_limit + 1e-6

    status = "通过" if (ok_stress and ok_defl) else "不通过"
    suggestion = None
    if not ok_stress:
        suggestion = "加大底板纵梁截面或增加纵梁根数"
    elif not ok_defl:
        suggestion = f"挠度超限，减小跨距或加大 I（当前 δ={delta:.1f}mm > L/{defl_ratio:.0f}）"

    return {
        "span_mm": round(span_use, 1),
        "moment_Nm": round(M / 1000.0, 2),
        "section_modulus_Wx_cm3": W_cm3,
        "I_cm4": I_cm4,
        "beam_count": count,
        "effective_beam_count": n_eff,
        "stress_MPa": round(sigma, 2),
        "allowable_MPa": round(allow, 2),
        "deflection_mm": round(delta, 2),
        "deflection_limit_mm": round(delta_limit, 2),
        "model": model,
        "status": status,
        "suggestion": suggestion,
    }


def check_frame_stability(
    *,
    design_load_kg: float,
    box_height_mm: float,
    frame: Dict[str, Any],
    is_steel: bool,
    n_columns: int = 4,
    k_factor: float = 1.0,
) -> Dict[str, Any]:
    """
    立柱轴压 + 长细比 λ = L0 / i。

    L0 = k × H（不确定时 k=1.0 偏安全，两端铰接）
    i 单位 cm，L0 换算为 cm 后计算 λ（与预置表一致）
    """
    from packing_assistant.tools.section_library import LAMBDA_GUIDE

    n_col = max(int(n_columns), 4)
    N = design_load_kg * G / n_col  # N 每柱
    i_cm = float(frame.get("i_cm") or 2.0)
    # 计算长度：箱高，k 默认 1.0（偏安全）；可传 0.7 表示两端约束更好
    H_mm = float(box_height_mm or 1000)
    L0_cm = (k_factor * H_mm) / 10.0  # mm → cm
    lam = L0_cm / i_cm if i_cm > 0 else 999.0

    lam_allow = (
        float(LAMBDA_GUIDE["steel_allow"])
        if is_steel
        else float(LAMBDA_GUIDE["wood_allow"])
    )
    comfort = float(LAMBDA_GUIDE["comfortable_max"])
    caution = float(LAMBDA_GUIDE["caution_max"])

    A_cm2 = float(frame.get("A_cm2") or 10.0)
    A_mm2 = A_cm2 * 100.0
    sigma = N / A_mm2 if A_mm2 > 0 else float("inf")  # MPa
    fb = (STEEL_FB_MPA if is_steel else WOOD_FB_MPA) * 0.7  # 稳定折减粗算
    ok_stress = sigma <= fb
    ok_lam = lam <= lam_allow

    if not ok_lam or not ok_stress:
        status = "不通过"
    elif lam > caution:
        status = "需加强"  # 未超允许但偏大
    else:
        status = "通过"

    suggestion = None
    if not ok_lam:
        suggestion = (
            f"长细比 λ={lam:.0f} 超允许 {lam_allow:.0f}，"
            "加斜撑或加大截面/缩短计算长度 L0"
        )
    elif not ok_stress:
        suggestion = "立柱轴压应力偏高，加大框架截面或增加立柱"
    elif lam > caution:
        suggestion = f"λ={lam:.0f} 已偏大（>{caution:.0f}），建议加斜撑提高稳定性"

    band = "稳妥"
    if lam >= lam_allow:
        band = "超限"
    elif lam > caution:
        band = "警惕"
    elif lam > comfort:
        band = "可接受偏大"

    return {
        "member": "立柱",
        "axial_force_N": round(N, 1),
        "L0_cm": round(L0_cm, 2),
        "L0_mm": round(k_factor * H_mm, 1),
        "k_factor": k_factor,
        "section_i_cm": i_cm,
        "slenderness_lambda": round(lam, 1),
        "lambda_formula": "λ = L0_cm / i_cm",
        "lambda_allow": lam_allow,
        "lambda_band": band,
        "lambda_guide": {
            "comfortable_max": comfort,
            "caution_max": caution,
            "note": "λ<80～100 相对稳妥；>120～150 需警惕失稳",
        },
        "stress_MPa": round(sigma, 2),
        "allowable_MPa": round(fb, 2),
        "column_count": n_col,
        "status": status,
        "suggestion": suggestion,
    }


def check_local_bearing(
    *,
    design_load_kg: float,
    concentrated_piece_kg: float = 0,
    bearing_area_mm2: float = 0,
    is_steel: bool = True,
) -> Dict[str, Any]:
    """局部承压：集中力 / 承压面积。"""
    # 集中力取最重单件设计力，否则取总重的 1/4
    if concentrated_piece_kg > 0:
        F = concentrated_piece_kg * G * 1.2  # 略放大
    else:
        F = design_load_kg * G / 4.0
    Ac = bearing_area_mm2 if bearing_area_mm2 > 0 else 80.0 * 80.0  # 默认垫板 80×80
    sigma_c = F / Ac if Ac > 0 else float("inf")
    # 木材抗压 / 钢局部
    allow = 120.0 if is_steel else 8.0  # MPa 粗值
    ok = sigma_c <= allow
    suggestion = None if ok else "局部承压超限，加大垫板面积或分散支点"
    return {
        "force_N": round(F, 1),
        "area_mm2": round(Ac, 1),
        "stress_MPa": round(sigma_c, 2),
        "allowable_MPa": allow,
        "status": "通过" if ok else "不通过",
        "suggestion": suggestion,
    }


def check_lifting_points(
    *,
    design_load_kg: float,
    lift_count: int = 4,
    symmetric: bool = True,
    eccentricity_factor: float = 1.0,
) -> Dict[str, Any]:
    n = max(int(lift_count or 4), 1)
    if not symmetric:
        eccentricity_factor = max(eccentricity_factor, 1.25)
    # 单点力
    F1 = design_load_kg * G / n * eccentricity_factor
    # 经验：单点不宜超过 设计总载 / 2.5（过少吊点）
    ok_count = n >= 4 or design_load_kg < 800
    ok_ecc = eccentricity_factor <= 1.35
    status = "通过" if (ok_count and ok_ecc) else "不通过"
    suggestion = None
    if not ok_count:
        suggestion = "吊点数量不足，建议四角对称布置"
    elif not ok_ecc:
        suggestion = "吊点偏心过大，调整至对称近重心"
    elif n < 4 and design_load_kg >= 1500:
        suggestion = "重箱建议不少于 4 点吊装"
        status = "需加强"
    return {
        "count": n,
        "force_per_point_N": round(F1, 1),
        "eccentricity_factor": eccentricity_factor,
        "symmetric": symmetric,
        "status": status if status != "需加强" else "需加强",
        "suggestion": suggestion,
    }


def run_structure_calc(
    *,
    box_type: str,
    outer_mm: Dict[str, float],
    inner_mm: Dict[str, float],
    tare_kg: float,
    max_payload_kg: float,
    is_steel_frame: bool,
    items: List[Dict[str, Any]],
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    lift_point_count: Optional[int] = None,
    concentrated_max_piece_kg: Optional[float] = None,
    box_id: str = "",
    design_facts: Optional[Dict[str, Any]] = None,
    require_detailed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    单箱完整结构计算（半严格三件套 + 几何重量）。

    design_facts：详设结构事实（截面/γ/吊点/图纸号）。
    有详设 → fidelity=detailed_design；无详设 → default_preset，且默认不可作正式出运依据。
    """
    from packing_assistant.tools.design_facts import (
        apply_section_overrides,
        has_detailed_facts,
        resolve_box_design,
    )

    weights = calc_weights(items, tare_kg)
    envelope = cargo_envelope(
        items,
        inner_length_mm=float(inner_mm.get("长") or 0) or None,
        inner_width_mm=float(inner_mm.get("宽") or 0) or None,
        inner_height_mm=float(inner_mm.get("高") or 0) or None,
    )
    geo = geometry_fit(envelope, inner_mm)
    if envelope.get("截面可装入") is False:
        geo = {**geo, "尺寸适配": False}

    # 预置截面 + 详设覆盖
    design = resolve_box_design(
        box_type=box_type, box_id=box_id or "", facts=design_facts or {}
    )
    if design.get("tare_kg") is not None:
        tare_kg = float(design["tare_kg"])
        weights = calc_weights(items, tare_kg)
    if design.get("max_payload_kg") is not None:
        max_payload_kg = float(design["max_payload_kg"])

    preset = get_box_default_sections(box_type)
    preset = apply_section_overrides(preset, design)
    design_errors = list(preset.get("design_errors") or [])
    fidelity = str(design.get("fidelity") or "default_preset")
    if design.get("frame_section") or design.get("bottom_beam_section"):
        fidelity = "detailed_design"
    detailed_ok = fidelity == "detailed_design" and not design_errors
    if require_detailed is None:
        require_detailed = bool((design_facts or {}).get("require_for_ship", True))

    gamma = float(preset.get("gamma") or 1.8)
    if design.get("gamma"):
        gamma = float(design["gamma"])
    if safety_factor and float(safety_factor) > gamma:
        gamma = float(safety_factor)
    if weights["毛重_kg"] > 2000:
        gamma = max(gamma, 2.2)
    strategy = preset.get("calc_strategy") or "semi_strict"
    if detailed_ok:
        strategy = "detailed_design_semi_strict"

    G_kg = weights["毛重_kg"]
    Fd = design_load_kg(G_kg, gamma)

    frame = preset.get("frame") or {}
    bottom = preset.get("bottom_beam") or {}
    n_lift = int(
        lift_point_count
        or design.get("lift_points")
        or preset.get("lift_points_default")
        or 4
    )
    n_columns = int(design.get("column_count") or 4)
    k_col = float(design.get("k_factor_column") or 1.0)
    defl_ratio = float(design.get("defl_ratio") or _DEFL_RATIO or 200)
    is_wood = (preset.get("material") or "") == "wood"

    # 最重单件
    max_piece = concentrated_max_piece_kg
    if max_piece is None:
        max_piece = 0.0
        for it in items:
            max_piece = max(max_piece, float(it.get("单重_kg") or 0))

    is_steel = is_steel_frame and not is_wood
    if is_wood:
        is_steel = False

    bearing_area = 0.0
    pad = design.get("bearing_pad_mm")
    if isinstance(pad, (list, tuple)) and len(pad) >= 2:
        bearing_area = float(pad[0]) * float(pad[1])

    bottom_bending = check_bottom_bending(
        design_load_kg=Fd,
        box_length_mm=float(outer_mm.get("长") or 0),
        beam=bottom,
        is_steel=is_steel,
        gamma=gamma,
        defl_ratio=defl_ratio,
    )
    frame_stability = check_frame_stability(
        design_load_kg=Fd,
        box_height_mm=float(outer_mm.get("高") or 0),
        frame=frame,
        is_steel=is_steel,
        n_columns=n_columns,
        k_factor=k_col,
    )
    local_bearing = check_local_bearing(
        design_load_kg=Fd,
        concentrated_piece_kg=float(max_piece or 0),
        bearing_area_mm2=bearing_area,
        is_steel=is_steel,
    )
    lifting_points = check_lifting_points(
        design_load_kg=Fd,
        lift_count=n_lift,
        symmetric=True,
        eccentricity_factor=1.0,
    )

    # 载荷利用率
    payload_ok = weights["净重_kg"] <= float(max_payload_kg) + 1e-6

    checks = {
        "geometry": "通过" if geo.get("尺寸适配") else "不通过",
        "payload": "通过" if payload_ok else "不通过",
        "bottom_bending": bottom_bending["status"],
        "frame_stability": frame_stability["status"],
        "local_bearing": local_bearing["status"],
        "lifting_points": lifting_points["status"],
    }

    fails = [k for k, v in checks.items() if v == "不通过"]
    soft_fails = [k for k, v in checks.items() if v == "需加强"]

    reinforcement_plan: List[str] = []
    for block in (bottom_bending, frame_stability, local_bearing, lifting_points):
        if block.get("suggestion"):
            reinforcement_plan.append(block["suggestion"])
    if not payload_ok:
        reinforcement_plan.append(f"净重超设计载荷 {max_payload_kg}kg，拆箱或升级箱型")
    if not geo.get("尺寸适配"):
        reinforcement_plan.append("件体尺寸超出内净空，调整箱型或拆件")

    if fails:
        conclusion = "不通过"
        risk_level = "高"
        passed = False
        need_reinf = True
    elif soft_fails or reinforcement_plan:
        conclusion = "需加强"
        risk_level = "中"
        passed = True  # 加强后可接受
        need_reinf = True
    else:
        conclusion = "通过"
        risk_level = "低"
        passed = True
        need_reinf = False

    # 无详设：不可当作正式结构通过（业务要求详设事实）
    if require_detailed and not detailed_ok and conclusion == "通过":
        conclusion = "待详设"
        risk_level = "中"
        passed = False
        need_reinf = True
        reinforcement_plan = [
            "未提供详设结构事实（截面/图纸号/γ）。请上传 structure_design_facts 或用自然语言指定框架/底板截面后重算。"
        ] + reinforcement_plan
    if design_errors:
        conclusion = "不通过"
        risk_level = "高"
        passed = False
        need_reinf = True
        reinforcement_plan = [f"详设截面解析失败：{e}" for e in design_errors] + reinforcement_plan

    # 强制半严格：4/6 米任一软项升为需加强已处理
    if strategy == "forced_semi_strict" and conclusion == "通过":
        # 仍输出全项，保持通过
        pass

    # 截面来源：框架/底梁各自 source，汇总优先 steel_table
    src_f = frame.get("source") or "unknown"
    src_b = bottom.get("source") or "unknown"
    if src_f == src_b:
        src_all = src_f
    else:
        src_all = f"{src_f}+{src_b}"

    section_used = {
        "frame": frame.get("name"),
        "bottom_beam": f"{bottom.get('name')}×{bottom.get('count', 1)}",
        "source": src_all,
        "frame_detail": {
            "name": frame.get("name"),
            "A_cm2": frame.get("A_cm2"),
            "I_cm4": frame.get("I_cm4"),
            "W_cm3": frame.get("W_cm3"),
            "i_cm": frame.get("i_cm"),
            "source": src_f,
        },
        "bottom_beam_detail": {
            "name": bottom.get("name"),
            "A_cm2": bottom.get("A_cm2"),
            "I_cm4": bottom.get("I_cm4"),
            "W_cm3": bottom.get("W_cm3"),
            "i_cm": bottom.get("i_cm"),
            "count": bottom.get("count"),
            "source": src_b,
        },
    }

    summary = {
        "passed": passed and conclusion not in ("不通过", "待详设"),
        "risk_level": risk_level,
        "reinforcement_required": need_reinf,
        "reinforcement_plan": reinforcement_plan,
        "fidelity": fidelity,
        "detailed_design": detailed_ok,
        "drawing_no": design.get("drawing_no") or preset.get("drawing_no"),
        "final_conclusion": (
            (
                f"按详设截面与γ={gamma}校核{conclusion}"
                if detailed_ok
                else f"按默认截面筛查γ={gamma}→{conclusion}（非正式详设）"
            )
            + (f"；建议：{'；'.join(reinforcement_plan[:3])}" if reinforcement_plan else "")
        ),
        "calc_strategy": strategy,
        "checks": checks,
        "design_errors": design_errors,
    }

    # 兼容旧字段
    risks: List[str] = list(reinforcement_plan)
    if not payload_ok:
        risks.append(f"净重 {weights['净重_kg']}kg 超过箱型设计载荷 {max_payload_kg}kg")
    if not geo.get("尺寸适配"):
        risks.append(f"件体需求超出内净空 {geo.get('内净空_mm')}")

    util_stress = bottom_bending.get("stress_MPa", 0) / max(
        bottom_bending.get("allowable_MPa") or 1, 1
    )

    result = {
        # —— 新版 API 字段 ——
        "box_id": box_id,
        "box_type": box_type,
        "total_weight_kg": weights["毛重_kg"],
        "safety_factor_gamma": gamma,
        "design_load_kg": round(Fd, 1),
        "section_used": section_used,
        "bottom_bending": bottom_bending,
        "frame_stability": frame_stability,
        "local_bearing": local_bearing,
        "lifting_points": lifting_points,
        "summary": summary,
        # —— 中文兼容（旧链路）——
        "结论": conclusion,
        "fidelity": fidelity,
        "detailed_design": detailed_ok,
        "drawing_no": design.get("drawing_no") or preset.get("drawing_no"),
        "安全系数": gamma,
        "箱型": box_type,
        "是否铁架": is_steel_frame,
        "重量": weights,
        "设计载荷_kg": max_payload_kg,
        "载荷利用率": (
            f"{min(weights['净重_kg'] / max_payload_kg * 100, 999):.1f}%"
            if max_payload_kg
            else "N/A"
        ),
        "件体包围盒_mm": {
            "长": envelope["长"],
            "宽": envelope["宽"],
            "高": envelope["高"],
        },
        "几何": geo,
        "底面荷载": {
            "底面积_m2": round(
                float(inner_mm.get("长") or 1)
                * float(inner_mm.get("宽") or 1)
                / 1e6,
                4,
            ),
            "均布荷载_kg_m2": round(
                weights["净重_kg"]
                / max(
                    float(inner_mm.get("长") or 1)
                    * float(inner_mm.get("宽") or 1)
                    / 1e6,
                    1e-6,
                ),
                1,
            ),
            "通过": payload_ok and geo.get("尺寸适配"),
        },
        "底梁建议": {
            "截面建议_mm": bottom.get("name"),
            "主梁间距_mm": int(
                float(outer_mm.get("长") or 1000) / max(int(bottom.get("count") or 2), 1)
            ),
            "纵向主梁数": int(bottom.get("count") or 2),
            "材质建议": "钢材" if is_steel else "木材",
            "说明": f"截面来源 {src_all}（方案C：steel_table优先）",
        },
        "底梁抗弯": {
            "模型": bottom_bending.get("model"),
            "计算应力_MPa": bottom_bending.get("stress_MPa"),
            "许用应力_MPa": bottom_bending.get("allowable_MPa"),
            "应力利用率": f"{util_stress * 100:.1f}%",
            "应力通过": bottom_bending.get("status") == "通过",
            "挠度_mm": bottom_bending.get("deflection_mm"),
            "挠度限值_mm": bottom_bending.get("deflection_limit_mm"),
            "挠度通过": (bottom_bending.get("deflection_mm") or 0)
            <= (bottom_bending.get("deflection_limit_mm") or 1e9),
            "安全系数": gamma,
        },
        "重心稳定性": {
            "合成重心高_mm": round(float(envelope.get("高") or 0) / 2, 1),
            "稳定性": "合格" if float(envelope.get("高") or 0) < float(inner_mm.get("宽") or 1) * 0.8 else "关注",
            "通过": True,
        },
        "结构利用率": f"{min(util_stress * 100, 999):.1f}%",
        "风险点": risks,
        "计算假定": [
            "荷载组合 Fd=G×γ，γ 按箱型 1.8～2.2",
            "截面：steel_table.json 优先，未命中走 sectionproperties/解析式",
            "底板抗弯：简支均布，多梁有效根数偏安全",
            "立柱轴压+长细比 λ=L0_cm/i_cm",
            "局部承压与吊点分载为经验公式",
            "正式出运前需包装工程师按图纸复核",
        ],
    }

    # 始终附带 Markdown 计算书
    try:
        from packing_assistant.tools.calc_report import render_structure_report_md

        result["calc_report_md"] = render_structure_report_md(
            result, outer_mm=outer_mm
        )
    except Exception:
        result["calc_report_md"] = ""

    return result


def attach_calc_report_md(
    struct: Dict[str, Any], outer_mm: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """给结构结果附加/刷新 Markdown 计算书。"""
    from packing_assistant.tools.calc_report import render_structure_report_md

    md = render_structure_report_md(struct, outer_mm=outer_mm)
    struct = dict(struct)
    struct["calc_report_md"] = md
    return struct


def structure_pass(result: Dict[str, Any]) -> bool:
    if result.get("summary"):
        return bool(result["summary"].get("passed"))
    return (result or {}).get("结论") == "通过"
