"""重心 / 偏心指标（质量加权优先，体积代理兜底）。

供 risk_compliance 与 visualizer 共用，前端可直接画 COG 标记。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from packing_assistant.tools.consolidation import CONTAINER_SPECS


def container_inner_mm(container_type: str = "40HQ") -> Dict[str, float]:
    spec = CONTAINER_SPECS.get(container_type) or CONTAINER_SPECS.get("40HQ") or {}
    return {
        "L": float(spec.get("长_m") or 12.032) * 1000,
        "W": float(spec.get("宽_m") or 2.352) * 1000,
        "H": float(spec.get("高_m") or 2.698) * 1000,
    }


def _item_volume_mm3(item: Dict[str, Any]) -> float:
    size = item.get("size") or {}
    dx = max(float(size.get("dx") or 1), 1)
    dy = max(float(size.get("dy") or 1), 1)
    dz = max(float(size.get("dz") or 1), 1)
    return dx * dy * dz


def _item_known_weight(
    item: Dict[str, Any],
    weight_map: Dict[str, float],
) -> Optional[float]:
    """已知毛重（kg）；无重量信息返回 None。"""
    bid = str(item.get("box_id") or "")
    w = weight_map.get(bid)
    if w is not None and w > 0:
        return float(w)
    # layout 上可能带 gross_weight_kg
    gw = item.get("gross_weight_kg")
    if gw is not None and float(gw) > 0:
        return float(gw)
    return None


def cog_for_layout(
    layout: Sequence[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    container_no: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """计算单个柜（或过滤 container_no）的重心。

    返回 mm 坐标 + 偏心率；质量优先用 boxes 毛重。
    """
    items = list(layout or [])
    if container_no is not None:
        items = [
            it
            for it in items
            if int(it.get("container_no") or 1) == int(container_no)
        ]
    if not items:
        return None

    weight_map: Dict[str, float] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if not bid:
            continue
        gw = float(b.get("gross_weight_kg") or 0)
        if gw > 0:
            weight_map[bid] = gw

    dims = container_inner_mm(container_type)
    L, W, H = dims["L"], dims["W"], dims["H"]

    # 质量口径：已知毛重用 kg；缺重箱按「已知箱平均密度 × 体积」估算，
    # 避免 mm³ 体积代理（数量级 1e9）与 kg 混算把重心拉向缺重箱。
    known_w = 0.0
    known_vol = 0.0
    any_missing = False
    masses: List[float] = []
    for p in items:
        w = _item_known_weight(p, weight_map)
        if w is None:
            any_missing = True
            masses.append(-1.0)  # 占位，稍后按密度补
        else:
            known_w += w
            known_vol += _item_volume_mm3(p)
            masses.append(w)
    used_weight = known_w > 0
    if any_missing:
        if known_w > 0 and known_vol > 0:
            density = known_w / known_vol  # kg/mm³
            masses = [
                m if m >= 0 else _item_volume_mm3(p) * density
                for m, p in zip(masses, items)
            ]
        else:
            # 全部缺重：纯体积代理（仅相对比例有意义）
            masses = [_item_volume_mm3(p) for p in items]

    mx = my = mz = 0.0
    m_tot = 0.0
    m_mid50 = 0.0  # 质心 x 落在 [0.25L, 0.75L] 的质量（CTU 60/50 规则）
    for p, m in zip(items, masses):
        pos, size = p.get("position") or {}, p.get("size") or {}
        dx = max(float(size.get("dx") or 1), 1)
        dy = max(float(size.get("dy") or 1), 1)
        dz = max(float(size.get("dz") or 1), 1)
        cx = float(pos.get("x") or 0) + dx / 2
        cy = float(pos.get("y") or 0) + dy / 2
        cz = float(pos.get("z") or 0) + dz / 2
        mx += m * cx
        my += m * cy
        mz += m * cz
        m_tot += m
        # CTU 60/50：质量中心落在柜长中段 50% 带内的质量占比
        if L > 0 and (0.25 * L) <= cx <= (0.75 * L):
            m_mid50 += m
    if m_tot <= 0:
        return None

    gx, gy, gz = mx / m_tot, my / m_tot, mz / m_tot
    lat_ecc = abs(gy - W / 2) / (W / 2) if W > 0 else 0.0
    long_pos = gx / L if L > 0 else 0.5
    height_ratio = gz / H if H > 0 else 0.0
    mass_in_mid50_ratio = m_mid50 / m_tot if m_tot > 0 else 0.0
    # CTU 60/50 规则：≥60% 质量在中段 50% 柜长
    mid50_ok = mass_in_mid50_ratio >= 0.60
    # 软目标：重心高度不超过约半舱高（装载货物高度方向）
    vertical_ok = height_ratio <= 0.55

    # 状态：左右 ≤5% 且前后 40–60% 为 balanced；并考虑 mid50 / 高度
    lat_ok = lat_ecc < 0.05
    long_ok = 0.40 <= long_pos <= 0.60
    if (
        lat_ecc >= 0.15
        or long_pos < 0.25
        or long_pos > 0.75
        or mass_in_mid50_ratio < 0.40
    ):
        balance = "block"
    elif (
        lat_ecc >= 0.10
        or long_pos < 0.35
        or long_pos > 0.65
        or not mid50_ok
        or not vertical_ok
    ):
        balance = "warn_high" if (lat_ecc >= 0.10 or mass_in_mid50_ratio < 0.50) else "warn"
    elif not lat_ok or not long_ok:
        balance = "warn"
    else:
        balance = "ok"

    return {
        "container_type": container_type,
        "container_no": int(container_no) if container_no is not None else None,
        "gx_mm": round(gx, 1),
        "gy_mm": round(gy, 1),
        "gz_mm": round(gz, 1),
        "lateral_eccentricity": round(lat_ecc, 4),
        "longitudinal_position": round(long_pos, 4),
        "height_ratio": round(height_ratio, 4),
        "mass_in_mid50_ratio": round(mass_in_mid50_ratio, 4),
        "mid50_ok": bool(mid50_ok),
        "vertical_ok": bool(vertical_ok),
        "mass_basis": "gross_weight_kg" if used_weight else "volume_proxy",
        "item_count": len(items),
        "balance": balance,
        "thresholds": {
            "lateral_warn": 0.05,
            "lateral_block": 0.15,
            "longitudinal_ideal": [0.40, 0.60],
            "mid50_mass_min": 0.60,  # CTU 60/50
            "mid50_mass_block": 0.40,
            "height_ratio_soft_max": 0.55,
            "mid50_band": [0.25, 0.75],
        },
        "labels": {
            "lateral": f"左右偏心 {lat_ecc:.1%}（宜≤5%）",
            "longitudinal": f"前后位置 {long_pos:.0%}（宜40%–60%）",
            "height": f"重心高度比 {height_ratio:.0%}（宜≤55%）",
            "mid50": (
                f"中段50%质量占比 {mass_in_mid50_ratio:.0%}"
                f"（CTU 60/50，宜≥60%）"
            ),
        },
    }


def compute_cog_bundle(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """整单 COG：主柜 + 分柜列表。"""
    layout = plan.get("layout") or []
    if not layout:
        return None
    ctype = str(plan.get("container_type") or "40HQ")
    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    per: List[Dict[str, Any]] = []
    for n in nos:
        c = cog_for_layout(layout, container_type=ctype, boxes=boxes, container_no=n)
        if c:
            per.append(c)
    # 出运决策用「最差柜」：mid50 最低优先，其次 balance=block，再 lat_ecc
    def _worst_key(c: Dict[str, Any]) -> Tuple:
        mid = float(c.get("mass_in_mid50_ratio") or 1.0)
        bal = str(c.get("balance") or "")
        bal_r = {"block": 0, "warn_high": 1, "warn": 2, "ok": 3}.get(bal, 2)
        lat = float(c.get("lateral_eccentricity") or 0)
        return (mid, bal_r, -lat)

    if per:
        primary = min(per, key=_worst_key)
        best = max(per, key=lambda c: float(c.get("mass_in_mid50_ratio") or 0))
    else:
        primary = cog_for_layout(layout, container_type=ctype, boxes=boxes)
        best = primary
    if not primary:
        return None
    # 若只有一柜且未标 container_no，统一 container_no=1
    if primary.get("container_no") is None:
        primary = dict(primary)
        primary["container_no"] = 1
    labels = primary.get("labels") or {}
    mid50_lbl = labels.get("mid50") or ""
    worst_mid = float(primary.get("mass_in_mid50_ratio") or 0)
    return {
        "primary": primary,
        "worst": primary,  # 出运/ replan 用最差柜
        "best": best,
        "per_container": per,
        "containers": len(per) or 1,
        "worst_mid50": round(worst_mid, 4),
        "all_mid50_ok": all(bool(c.get("mid50_ok")) for c in per) if per else bool(primary.get("mid50_ok")),
        "caption": (
            f"最差柜{primary.get('container_no') or 1} "
            f"{labels.get('lateral', '')}｜"
            f"{labels.get('longitudinal', '')}｜"
            f"{mid50_lbl + '｜' if mid50_lbl else ''}"
            f"basis={primary.get('mass_basis')}"
        ),
    }
