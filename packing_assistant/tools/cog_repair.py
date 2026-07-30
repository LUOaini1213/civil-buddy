"""R4：局部重货↔轻货 swap + 中段再插入（改相对位置抬 mid50）。

在 R1 刚性平移之后调用。不发明新坐标搜索全柜，只在已有布局上：
1) 带外重货 ↔ 带内轻货 位置交换（AABB 可互换）
2) 带外重货沿 x 滑入中段 [0.25L,0.75L]（同 y/z，无碰撞）
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _wm(boxes: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, float]:
    m: Dict[str, float] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if bid:
            m[bid] = float(b.get("gross_weight_kg") or 0)
    return m


def _mass(it: Dict[str, Any], wmap: Dict[str, float]) -> float:
    bid = str(it.get("box_id") or "")
    if bid in wmap and wmap[bid] > 0:
        return wmap[bid]
    gw = float(it.get("gross_weight_kg") or 0)
    if gw > 0:
        return gw
    size = it.get("size") or {}
    return max(float(size.get("dx") or 1) * float(size.get("dy") or 1) * float(size.get("dz") or 1) / 1e8, 1.0)


def _rect(it: Dict[str, Any]) -> Tuple[float, float, float, float, float, float]:
    pos, size = it.get("position") or {}, it.get("size") or {}
    x, y, z = float(pos.get("x") or 0), float(pos.get("y") or 0), float(pos.get("z") or 0)
    dx, dy, dz = float(size.get("dx") or 1), float(size.get("dy") or 1), float(size.get("dz") or 1)
    return x, y, z, dx, dy, dz


def _cx(it: Dict[str, Any]) -> float:
    x, _, _, dx, _, _ = _rect(it)
    return x + dx / 2


def _in_mid(cx: float, L: float) -> bool:
    return (0.25 * L) <= cx <= (0.75 * L)


def _overlap_xy(
    x1: float, y1: float, dx1: float, dy1: float,
    x2: float, y2: float, dx2: float, dy2: float,
    gap: float = 0.0,
) -> bool:
    return not (
        x1 + dx1 + gap <= x2
        or x2 + dx2 + gap <= x1
        or y1 + dy1 + gap <= y2
        or y2 + dy2 + gap <= y1
    )


def _overlap_3d(a: Dict[str, Any], b: Dict[str, Any], gap: float = 0.0) -> bool:
    ax, ay, az, adx, ady, adz = _rect(a)
    bx, by, bz, bdx, bdy, bdz = _rect(b)
    # 垂直分离（堆叠贴顶允许）
    if az + adz <= bz or bz + bdz <= az:
        return False
    return _overlap_xy(ax, ay, adx, ady, bx, by, bdx, bdy, gap)


def _fits_container(it: Dict[str, Any], L: float, W: float, H: float) -> bool:
    x, y, z, dx, dy, dz = _rect(it)
    return x >= 0 and y >= 0 and z >= 0 and x + dx <= L + 1e-6 and y + dy <= W + 1e-6 and z + dz <= H + 1e-6


def _no_collision(it: Dict[str, Any], others: List[Dict[str, Any]], skip_ids: set) -> bool:
    for o in others:
        oid = str(o.get("box_id") or "")
        if oid in skip_ids or oid == str(it.get("box_id") or ""):
            continue
        if _overlap_3d(it, o):
            return False
    return True


def _mid50_of(items: List[Dict[str, Any]], L: float, wmap: Dict[str, float]) -> float:
    tot = mid = 0.0
    for it in items:
        m = _mass(it, wmap)
        tot += m
        if _in_mid(_cx(it), L):
            mid += m
    return mid / tot if tot > 0 else 0.0


def _try_swap(
    heavy: Dict[str, Any],
    light: Dict[str, Any],
    items: List[Dict[str, Any]],
    L: float,
    W: float,
    H: float,
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """尝试交换两箱的 (x,y,z)；要求对方足迹装得下本箱尺寸。"""
    hx, hy, hz, hdx, hdy, hdz = _rect(heavy)
    lx, ly, lz, ldx, ldy, ldz = _rect(light)
    # 足迹：重货放轻货位置需 hdx<=空间——用轻货位置角点，尺寸用重货自身
    # 简化：仅当平面尺寸相容（重货不比轻货足迹大太多）或双方尺寸相同
    if hdx > ldx + 50 or hdy > ldy + 50:
        # 重货更大：不能塞进轻货脚印，除非轻货更大
        if hdx > L or hdy > W:
            return None
    if ldx > hdx + 50 or ldy > hdy + 50:
        pass  # 轻货放重货位通常 OK

    h2 = deepcopy(heavy)
    l2 = deepcopy(light)
    h2["position"] = {"x": int(lx), "y": int(ly), "z": int(lz)}
    # 若高度不同，尽量保持各自 z（同层交换）
    if abs(hdz - ldz) > 1:
        h2["position"]["z"] = int(hz)
        l2["position"] = {"x": int(hx), "y": int(hy), "z": int(lz)}
    else:
        l2["position"] = {"x": int(hx), "y": int(hy), "z": int(hz)}

    if not _fits_container(h2, L, W, H) or not _fits_container(l2, L, W, H):
        return None
    # 互不重叠且不与其它碰撞
    if _overlap_3d(h2, l2):
        return None
    skip = {str(heavy.get("box_id")), str(light.get("box_id"))}
    if not _no_collision(h2, items, skip) or not _no_collision(l2, items, skip):
        return None
    return h2, l2


def _try_slide_to_mid(
    heavy: Dict[str, Any],
    items: List[Dict[str, Any]],
    L: float,
    W: float,
    H: float,
) -> Optional[Dict[str, Any]]:
    """沿 x 把重货中心滑向 L/2，夹在中段带内，保持 y/z。"""
    x, y, z, dx, dy, dz = _rect(heavy)
    target_cx = L / 2.0
    # 理想 x 使中心在 mid 内且靠近 L/2
    ideal_x = target_cx - dx / 2
    lo = 0.25 * L - dx / 2
    hi = 0.75 * L - dx / 2
    ideal_x = max(0.0, min(L - dx, ideal_x))
    ideal_x = max(lo, min(hi, ideal_x)) if hi >= lo else ideal_x

    # 在当前 x 与 ideal 之间采样
    samples = []
    for t in (1.0, 0.75, 0.5, 0.35, 0.25):
        sx = x + (ideal_x - x) * t
        samples.append(int(round(sx)))
    # 中段网格
    for frac in (0.35, 0.45, 0.5, 0.55, 0.65):
        samples.append(int(round(L * frac - dx / 2)))
    samples = sorted(set(max(0, min(int(L - dx), s)) for s in samples))

    skip = {str(heavy.get("box_id"))}
    best = None
    best_d = abs(_cx(heavy) - target_cx)
    for sx in samples:
        cand = deepcopy(heavy)
        cand["position"] = {"x": sx, "y": int(y), "z": int(z)}
        if not _fits_container(cand, L, W, H):
            continue
        if not _no_collision(cand, items, skip):
            continue
        d = abs(_cx(cand) - target_cx)
        if d + 1e-6 < best_d and _in_mid(_cx(cand), L):
            best_d = d
            best = cand
    return best


def _rigid_shift_to_max_mid50(
    items: List[Dict[str, Any]],
    L: float,
    W: float,
    H: float,
    wmap: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], float]:
    """整坨货沿柜长刚性平移，最大化 mid50（门端堆满导致两端质量出带时很有效）。"""
    if not items:
        return items, 0.0
    work0 = [deepcopy(it) for it in items]
    mid0 = _mid50_of(work0, L, wmap)
    xs = []
    rights = []
    for it in work0:
        x, y, z, dx, dy, dz = _rect(it)
        xs.append(x)
        rights.append(x + dx)
    min_x = min(xs)
    max_r = max(rights)
    span = max_r - min_x
    if span <= 1 or span > L + 1e-3:
        return work0, 0.0

    best = work0
    best_mid = mid0
    max_left = max(0.0, L - span)
    # 采样：居中优先 + 均匀网格
    samples = [max_left * 0.5]
    step = max(25.0, max_left / 48.0) if max_left > 0 else 25.0
    t = 0.0
    while t <= max_left + 1e-6:
        samples.append(t)
        t += step
    samples = sorted(set(int(round(s)) for s in samples))

    for left in samples:
        delta = float(left) - min_x
        if abs(delta) < 1e-6:
            continue
        trial: List[Dict[str, Any]] = []
        ok = True
        for it in work0:
            x, y, z, dx, dy, dz = _rect(it)
            cand = deepcopy(it)
            cand["position"] = {"x": int(round(x + delta)), "y": int(y), "z": int(z)}
            if not _fits_container(cand, L, W, H):
                ok = False
                break
            trial.append(cand)
        if not ok:
            continue
        m = _mid50_of(trial, L, wmap)
        if m > best_mid + 1e-5:
            best_mid = m
            best = trial
    return best, float(best_mid - mid0)


def repair_container_r4(
    items: List[Dict[str, Any]],
    *,
    L: float,
    W: float,
    H: float,
    wmap: Dict[str, float],
    max_swaps: int = 40,
    max_slides: int = 40,
    target_mid50: float = 0.60,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """单柜 R4 修理；返回新 items + 统计。目标 mid50 默认 0.60（CTU 60/50）。"""
    work = [deepcopy(it) for it in items]
    mid0 = _mid50_of(work, L, wmap)
    tgt = float(target_mid50 or 0.60)
    if mid0 >= tgt:
        return work, {
            "swaps": 0,
            "slides": 0,
            "rigid_shift": 0,
            "mid50_before": mid0,
            "mid50_after": mid0,
            "skipped": True,
        }

    swaps = 0
    slides = 0
    rigid = 0
    meta_swaps: List[Dict[str, Any]] = []

    def refresh_lists():
        heavies_out = []
        lights_in = []
        for it in work:
            m = _mass(it, wmap)
            cx = _cx(it)
            if not _in_mid(cx, L) and m > 0:
                heavies_out.append((m, it))
            elif _in_mid(cx, L):
                lights_in.append((m, it))
        heavies_out.sort(key=lambda t: -t[0])
        lights_in.sort(key=lambda t: t[0])  # 最轻的在中段
        return heavies_out, lights_in

    # —— Phase 0: 整坨沿柜长平移，先抬 mid50 ——
    shifted, d_mid = _rigid_shift_to_max_mid50(work, L, W, H, wmap)
    if d_mid > 1e-5:
        work = shifted
        rigid = 1

    # —— Phase A: swaps ——
    for _ in range(max_swaps):
        mid_now = _mid50_of(work, L, wmap)
        if mid_now >= tgt:
            break
        heavies_out, lights_in = refresh_lists()
        if not heavies_out or not lights_in:
            break
        improved = False
        for hm, h in heavies_out[:12]:
            for lm, l in lights_in[:16]:
                if hm <= lm * 1.05:
                    continue  # 交换无质量收益
                # 交换后：重货中心应更靠中段
                if _in_mid(_cx(h), L):
                    continue
                pair = _try_swap(h, l, work, L, W, H)
                if not pair:
                    continue
                h2, l2 = pair
                # 试验
                trial = []
                hid, lid = str(h.get("box_id")), str(l.get("box_id"))
                for it in work:
                    bid = str(it.get("box_id"))
                    if bid == hid:
                        trial.append(h2)
                    elif bid == lid:
                        trial.append(l2)
                    else:
                        trial.append(it)
                m_new = _mid50_of(trial, L, wmap)
                if m_new > mid_now + 1e-4:
                    work = trial
                    swaps += 1
                    meta_swaps.append(
                        {
                            "heavy": hid,
                            "light": lid,
                            "mid50": round(m_new, 4),
                        }
                    )
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break

    # —— Phase B: slides ——
    for _ in range(max_slides):
        mid_now = _mid50_of(work, L, wmap)
        if mid_now >= tgt:
            break
        heavies_out, _ = refresh_lists()
        if not heavies_out:
            break
        improved = False
        for hm, h in heavies_out[:15]:
            slid = _try_slide_to_mid(h, work, L, W, H)
            if not slid:
                continue
            trial = []
            hid = str(h.get("box_id"))
            for it in work:
                if str(it.get("box_id")) == hid:
                    trial.append(slid)
                else:
                    trial.append(it)
            m_new = _mid50_of(trial, L, wmap)
            if m_new > mid_now + 1e-4:
                work = trial
                slides += 1
                improved = True
                break
        if not improved:
            break

    # —— Phase C: 再刚性平移一次（swap/slide 后跨度可能变化）——
    if _mid50_of(work, L, wmap) < tgt:
        shifted2, d2 = _rigid_shift_to_max_mid50(work, L, W, H, wmap)
        if d2 > 1e-5:
            work = shifted2
            rigid += 1

    mid1 = _mid50_of(work, L, wmap)
    return work, {
        "swaps": swaps,
        "slides": slides,
        "rigid_shift": rigid,
        "mid50_before": round(mid0, 4),
        "mid50_after": round(mid1, 4),
        "target_mid50": tgt,
        "swap_log": meta_swaps[:8],
        "skipped": False,
    }


def apply_r4_repair(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    target_mid50: float = 0.60,
    force: bool = False,
) -> Dict[str, Any]:
    """
    对 mid50 < target 的柜做 R4（刚性平移 + 重轻交换 + 滑入中段）。
    默认目标 0.60（CTU 60/50）；整体 mid50 不恶化才接受。
    """
    from packing_assistant.tools.cog import compute_cog_bundle, container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan

    ctype = str(plan.get("container_type") or "40HQ")
    dims = container_inner_mm(ctype)
    L, W, H = float(dims["L"]), float(dims["W"]), float(dims["H"])
    wmap = _wm(boxes)
    tgt = float(target_mid50 or 0.60)

    mid_before = plan.get("worst_mid50")
    if mid_before is None:
        b0 = compute_cog_bundle(plan, boxes=boxes)
        mid_before = (b0 or {}).get("worst_mid50", 1.0)
    # force 时仍跑（可再抬）；否则已达标跳过
    if not force and mid_before is not None and float(mid_before) >= tgt:
        return plan

    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    new_layout: List[Dict[str, Any]] = []
    per_stats: List[Dict[str, Any]] = []

    for cno in nos:
        items = [it for it in layout if int(it.get("container_no") or 1) == cno]
        m_c = _mid50_of(items, L, wmap)
        if m_c >= tgt and not force:
            new_layout.extend(items)
            per_stats.append({"container_no": cno, "skipped": True, "mid50": m_c})
            continue
        repaired, st = repair_container_r4(
            items, L=L, W=W, H=H, wmap=wmap, target_mid50=tgt
        )
        # 保持 container_no
        for it in repaired:
            it["container_no"] = cno
        new_layout.extend(repaired)
        st["container_no"] = cno
        per_stats.append(st)

    out = dict(plan)
    out["layout"] = new_layout
    out["r4_repair"] = {
        "method": "rigid_shift_swap_slide_mid",
        "target_mid50": tgt,
        "per_container": per_stats,
    }
    try:
        bundle = compute_cog_bundle(out, boxes=boxes)
        if bundle:
            mid_after = bundle.get("worst_mid50")
            # 变差则回退
            if mid_after is not None and float(mid_after) + 1e-9 < float(mid_before or 0) - 0.01:
                return plan
            out["cog_bundle"] = bundle
            out["cog"] = bundle.get("worst") or bundle.get("primary")
            out["worst_mid50"] = mid_after
            out["all_mid50_ok"] = bundle.get("all_mid50_ok")
            st = dict(out.get("stacking") or {})
            st["r4_repair_applied"] = True
            st["r4_mid50_before"] = mid_before
            st["r4_mid50_after"] = mid_after
            out["stacking"] = st
    except Exception:
        pass
    return out
