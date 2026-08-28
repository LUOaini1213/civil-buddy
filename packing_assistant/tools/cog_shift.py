"""R0 校验 + R1 修理（CTU CoG / EasyCargo）。

R0：校验 60/50、纵偏、横偏、竖向重心（每柜 + 最差柜）
R1a：整舱刚性平移至质量中心（long + lat）
R1b：横向镜像（整坨绕柜宽中线翻转）——修左右偏心

均不改相对叠层拓扑（R1b 只镜像 y）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


# CTU 阈值
MID50_OK = 0.60
MID50_BLOCK = 0.40
LONG_ECC_OK = 0.05  # |gx/L - 0.5|
LONG_ECC_SOFT = 0.10
LAT_ECC_OK = 0.05
LAT_ECC_BLOCK = 0.15
HEIGHT_OK = 0.55


def _score_cog(c: Dict[str, Any]) -> float:
    """越小越好：mid50 权重最高（不因 long 居中牺牲 60/50）。"""
    mid = float(c.get("mass_in_mid50_ratio") or 0)
    long_pos = float(c.get("longitudinal_position") or 0.5)
    lat = float(c.get("lateral_eccentricity") or 0)
    hr = float(c.get("height_ratio") or 0)
    pen = max(0.0, MID50_OK - mid) * 20.0  # mid50 主导
    if mid < MID50_BLOCK:
        pen += 15.0
    elif mid < 0.50:
        pen += 5.0
    pen += abs(long_pos - 0.5) * 4.0
    pen += max(0.0, lat - LAT_ECC_OK) * 8.0
    pen += max(0.0, hr - HEIGHT_OK) * 3.0
    return pen


def validate_cog_r0(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    R0：CTU 重心门禁检查（只读）。
    """
    from packing_assistant.tools.cog import compute_cog_bundle

    layout = plan.get("layout") or []
    if not layout:
        return {
            "ok": False,
            "pass": False,
            "reason": "empty_layout",
            "per_container": [],
            "worst_mid50": None,
        }

    bundle = plan.get("cog_bundle")
    if not bundle:
        bundle = compute_cog_bundle(plan, boxes=boxes) or {}

    per = list(bundle.get("per_container") or [])
    if not per and bundle.get("primary"):
        per = [bundle["primary"]]

    checks: List[Dict[str, Any]] = []
    all_ok = True
    for c in per:
        mid = float(c.get("mass_in_mid50_ratio") or 0)
        long_pos = float(c.get("longitudinal_position") or 0.5)
        long_ecc = abs(long_pos - 0.5)
        lat = float(c.get("lateral_eccentricity") or 0)
        hr = float(c.get("height_ratio") or 0)
        mid_ok = mid >= MID50_OK
        long_ok = long_ecc <= LONG_ECC_OK
        lat_ok = lat <= LAT_ECC_OK
        vert_ok = hr <= HEIGHT_OK
        block = mid < MID50_BLOCK or lat >= LAT_ECC_BLOCK or long_pos < 0.25 or long_pos > 0.75
        ok = mid_ok and long_ok and lat_ok and vert_ok
        if not ok:
            all_ok = False
        checks.append(
            {
                "container_no": c.get("container_no"),
                "mass_in_mid50_ratio": mid,
                "mid50_ok": mid_ok,
                "longitudinal_position": long_pos,
                "long_ecc": round(long_ecc, 4),
                "long_ok": long_ok,
                "lateral_eccentricity": lat,
                "lat_ok": lat_ok,
                "height_ratio": hr,
                "vertical_ok": vert_ok,
                "balance": c.get("balance"),
                "ok": ok,
                "block": block,
                "score": round(_score_cog(c), 4),
                "thresholds": {
                    "mid50_ok": MID50_OK,
                    "mid50_block": MID50_BLOCK,
                    "long_ecc_ok": LONG_ECC_OK,
                    "lat_ecc_ok": LAT_ECC_OK,
                    "height_ok": HEIGHT_OK,
                },
            }
        )

    worst = None
    if checks:
        worst = min(checks, key=lambda x: (float(x.get("mass_in_mid50_ratio") or 0), -float(x.get("score") or 0)))

    return {
        "ok": all_ok,
        "pass": all_ok,
        "method": "r0_ctu_validate",
        "worst_mid50": (worst or {}).get("mass_in_mid50_ratio"),
        "worst_container_no": (worst or {}).get("container_no"),
        "any_block": any(c.get("block") for c in checks),
        "per_container": checks,
        "caption": (
            f"R0 {'PASS' if all_ok else 'FAIL'} "
            f"worst_mid50={(worst or {}).get('mass_in_mid50_ratio')} "
            f"柜{(worst or {}).get('container_no')}"
        ),
    }


def _weight_map(boxes: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, float]:
    m: Dict[str, float] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if bid:
            m[bid] = float(b.get("gross_weight_kg") or 0)
    return m


def _aabb(items: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    min_x = min_y = 1e18
    max_x = max_y = -1e18
    for it in items:
        pos, size = it.get("position") or {}, it.get("size") or {}
        x, y = float(pos.get("x") or 0), float(pos.get("y") or 0)
        dx, dy = float(size.get("dx") or 0), float(size.get("dy") or 0)
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + dx)
        max_y = max(max_y, y + dy)
    return min_x, min_y, max_x, max_y


def _shift_items(
    items: List[Dict[str, Any]],
    sx: int,
    sy: int,
) -> List[Dict[str, Any]]:
    out = []
    for it in items:
        nit = dict(it)
        pos = dict(nit.get("position") or {})
        pos["x"] = int(float(pos.get("x") or 0) + sx)
        pos["y"] = int(float(pos.get("y") or 0) + sy)
        nit["position"] = pos
        out.append(nit)
    return out


def _mirror_y_items(items: List[Dict[str, Any]], W: float) -> List[Dict[str, Any]]:
    """横向镜像：y' = W - (y+dy)。"""
    out = []
    for it in items:
        nit = dict(it)
        pos = dict(nit.get("position") or {})
        size = nit.get("size") or {}
        y = float(pos.get("y") or 0)
        dy = float(size.get("dy") or 0)
        pos["y"] = int(round(W - (y + dy)))
        if pos["y"] < 0:
            pos["y"] = 0
        nit["position"] = pos
        out.append(nit)
    return out


def shift_layout_to_mass_center(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    container_type: Optional[str] = None,
    shift_longitudinal: bool = True,
    shift_lateral: bool = True,
    min_offset_mm: float = 1.0,
) -> Dict[str, Any]:
    """R1a：每柜刚性平移，使质量重心靠近柜几何中心。"""
    from packing_assistant.tools.cog import cog_for_layout, container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan

    ctype = str(container_type or plan.get("container_type") or "40HQ")
    dims = container_inner_mm(ctype)
    L, W = float(dims["L"]), float(dims["W"])
    wmap = _weight_map(boxes)

    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    new_layout: List[Dict[str, Any]] = []
    shifts: List[Dict[str, Any]] = []

    for cno in nos:
        items = [it for it in layout if int(it.get("container_no") or 1) == cno]
        if not items:
            continue
        cog = cog_for_layout(items, container_type=ctype, boxes=boxes, container_no=cno)
        if cog is None:
            gx = gy = m_tot = 0.0
            for it in items:
                pos, size = it.get("position") or {}, it.get("size") or {}
                dx = max(float(size.get("dx") or 1), 1)
                dy = max(float(size.get("dy") or 1), 1)
                w = wmap.get(str(it.get("box_id") or ""), dx * dy) or 1.0
                gx += w * (float(pos.get("x") or 0) + dx / 2)
                gy += w * (float(pos.get("y") or 0) + dy / 2)
                m_tot += w
            if m_tot <= 0:
                new_layout.extend(deepcopy_items(items))
                continue
            gx, gy = gx / m_tot, gy / m_tot
        else:
            gx = float(cog.get("gx_mm") or L / 2)
            gy = float(cog.get("gy_mm") or W / 2)

        min_x, min_y, max_x, max_y = _aabb(items)
        # 若 mid50 已达标且纵向已在舒适区，禁止纵向平移拉开端墙（贴端墙+双列是铁架主路径）
        mid_ok = False
        long_ok = abs((gx / L) - 0.5) <= LONG_ECC_SOFT if L > 0 else True
        if cog is not None:
            mid_ok = float(cog.get("mass_in_mid50_ratio") or 0) >= (MID50_OK - 1e-6)
            long_pos = float(cog.get("longitudinal_position") or (gx / L if L else 0.5))
            long_ok = abs(long_pos - 0.5) <= LONG_ECC_SOFT
        do_long = bool(shift_longitudinal) and not (mid_ok and long_ok)
        # 已贴一端墙且 mid50 OK：保持贴墙，只修横向
        wall_flush = min_x <= 1.0 or max_x >= L - 1.0
        if mid_ok and wall_flush:
            do_long = False
        # 分布式满舱货（跨度 ≥80% 柜长）贴端墙：平移最多 (L-span)/2，
        # mid50 提升只是离散伪影，代价是端墙留出无支撑滑移间隙 → 保持贴墙
        if wall_flush and (max_x - min_x) >= 0.80 * L:
            do_long = False
        sx = (L / 2.0 - gx) if do_long else 0.0
        sy = (W / 2.0 - gy) if shift_lateral else 0.0
        sx = max(-min_x, min(L - max_x, sx))
        sy = max(-min_y, min(W - max_y, sy))
        sx_i = int(round(sx))
        sy_i = int(round(sy))
        if abs(sx_i) < min_offset_mm:
            sx_i = 0
        if abs(sy_i) < min_offset_mm:
            sy_i = 0

        moved = _shift_items(items, sx_i, sy_i) if (sx_i or sy_i) else deepcopy_items(items)
        new_layout.extend(moved)
        shifts.append(
            {
                "container_no": cno,
                "dx_mm": sx_i,
                "dy_mm": sy_i,
                "gx_before_mm": round(gx, 1),
                "gy_before_mm": round(gy, 1),
                "applied": bool(sx_i or sy_i),
                "long_skipped_wall_flush": bool(mid_ok and wall_flush and shift_longitudinal),
            }
        )

    out = dict(plan)
    out["layout"] = new_layout
    out["r1_shift"] = {
        "method": "rigid_shift_to_mass_center",
        "per_container": shifts,
        "note": "R1a 整舱刚性平移",
    }
    _refresh_cog(out, boxes)
    return out


def mirror_layout_lateral(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    container_type: Optional[str] = None,
) -> Dict[str, Any]:
    """R1b：每柜横向镜像，修左右偏心。"""
    from packing_assistant.tools.cog import container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan
    ctype = str(container_type or plan.get("container_type") or "40HQ")
    W = float(container_inner_mm(ctype)["W"])
    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    new_layout: List[Dict[str, Any]] = []
    mirrors: List[Dict[str, Any]] = []
    for cno in nos:
        items = [it for it in layout if int(it.get("container_no") or 1) == cno]
        mirrored = _mirror_y_items(items, W)
        # 夹紧
        for it in mirrored:
            pos = it.get("position") or {}
            size = it.get("size") or {}
            y = float(pos.get("y") or 0)
            dy = float(size.get("dy") or 0)
            if y < 0:
                pos["y"] = 0
            if y + dy > W:
                pos["y"] = int(max(0, W - dy))
            it["position"] = pos
            it["container_no"] = cno
        new_layout.extend(mirrored)
        mirrors.append({"container_no": cno, "applied": True})

    out = dict(plan)
    out["layout"] = new_layout
    out["r1_mirror"] = {
        "method": "lateral_mirror_y",
        "per_container": mirrors,
        "note": "R1b 横向镜像",
    }
    _refresh_cog(out, boxes)
    return out


def deepcopy_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(it, position=dict(it.get("position") or {})) for it in items]


def _refresh_cog(plan: Dict[str, Any], boxes: Optional[Sequence[Dict[str, Any]]]) -> None:
    from packing_assistant.tools.cog import compute_cog_bundle

    try:
        bundle = compute_cog_bundle(plan, boxes=boxes)
        if bundle:
            plan["cog_bundle"] = bundle
            plan["cog"] = bundle.get("worst") or bundle.get("primary")
            plan["worst_mid50"] = bundle.get("worst_mid50")
            plan["all_mid50_ok"] = bundle.get("all_mid50_ok")
    except Exception:
        pass


def _plan_score(plan: Dict[str, Any], boxes: Optional[Sequence[Dict[str, Any]]]) -> float:
    from packing_assistant.tools.cog import compute_cog_bundle

    bundle = plan.get("cog_bundle") or compute_cog_bundle(plan, boxes=boxes) or {}
    worst = bundle.get("worst") or bundle.get("primary") or plan.get("cog") or {}
    return _score_cog(worst if isinstance(worst, dict) else {})


def apply_r0_r1(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    force: bool = False,
    enable_mirror: bool = True,
    enable_shift: bool = True,
) -> Dict[str, Any]:
    """
    R0 校验 → 不通过则 R1a 平移 → 仍横偏则 R1b 镜像 → 再 R0。
    每步仅当综合 score 不恶化时接受。
    """
    if not plan.get("layout"):
        return plan

    out = dict(plan)
    r0_before = validate_cog_r0(out, boxes)
    out["r0_validation"] = {"before": r0_before}
    score0 = _plan_score(out, boxes)

    need = force or (not r0_before.get("ok")) or r0_before.get("any_block")
    if not need:
        out["r0_validation"]["after"] = r0_before
        out["r0_validation"]["passed_without_repair"] = True
        st = dict(out.get("stacking") or {})
        st["r0_ok"] = True
        out["stacking"] = st
        return out

    best = out
    best_score = score0
    log: List[str] = []

    def _mid(p: Dict[str, Any]) -> float:
        v = p.get("worst_mid50")
        if v is not None:
            return float(v)
        return float((p.get("cog") or {}).get("mass_in_mid50_ratio") or 0)

    mid0 = _mid(out)

    # R1a shift
    if enable_shift:
        shifted = shift_layout_to_mass_center(out, boxes, min_offset_mm=1.0)
        sc = _plan_score(shifted, boxes)
        mid_s = _mid(shifted)
        any_move = any(
            s.get("applied")
            for s in (shifted.get("r1_shift") or {}).get("per_container") or []
        )
        # 禁止 mid50 明显下降
        mid_ok = mid_s + 1e-9 >= mid0 - 0.02
        if any_move and mid_ok and sc <= best_score + 1e-6:
            best = shifted
            best_score = sc
            log.append(f"r1a_shift score {score0:.3f}->{sc:.3f} mid {mid0:.2f}->{mid_s:.2f}")
        elif any_move and force and mid_ok and sc < score0 + 0.3:
            best = shifted
            best_score = sc
            log.append(f"r1a_shift_force score {score0:.3f}->{sc:.3f}")

    # R1b mirror if lateral still bad
    if enable_mirror:
        cog = best.get("cog") or {}
        lat = float(cog.get("lateral_eccentricity") or 0)
        mid_b = _mid(best)
        if lat > LAT_ECC_OK or (force and lat > 0.02):
            mirrored = mirror_layout_lateral(best, boxes)
            if best.get("r1_shift"):
                mirrored["r1_shift"] = best.get("r1_shift")
            sc = _plan_score(mirrored, boxes)
            mid_m = _mid(mirrored)
            if mid_m + 1e-9 >= mid_b - 0.02 and sc <= best_score + 1e-6:
                best = mirrored
                best_score = sc
                log.append(f"r1b_mirror score->{sc:.3f} mid {mid_b:.2f}->{mid_m:.2f}")

    r0_after = validate_cog_r0(best, boxes)
    best["r0_validation"] = {
        "before": r0_before,
        "after": r0_after,
        "log": log,
        "score_before": round(score0, 4),
        "score_after": round(best_score, 4),
        "improved": best_score <= score0 + 1e-9,
    }
    st = dict(best.get("stacking") or {})
    st["r0_ok"] = bool(r0_after.get("ok"))
    st["r1_applied"] = bool(log)
    st["r1_shift_applied"] = any("r1a" in x for x in log)
    st["r1_mirror_applied"] = any("r1b" in x for x in log)
    st["r0_worst_mid50_before"] = r0_before.get("worst_mid50")
    st["r0_worst_mid50_after"] = r0_after.get("worst_mid50")
    best["stacking"] = st
    return best


def maybe_apply_r1_shift(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """兼容旧接口：执行完整 R0→R1 管道。"""
    return apply_r0_r1(plan, boxes, force=force)
