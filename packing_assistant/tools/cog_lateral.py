"""横偏修理：左右半柜质量交换 + y 向条带重排。"""

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
    return float(it.get("gross_weight_kg") or 0) or 1.0


def _cy(it: Dict[str, Any]) -> float:
    pos, size = it.get("position") or {}, it.get("size") or {}
    return float(pos.get("y") or 0) + float(size.get("dy") or 0) / 2


def _overlap(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa, sa = a.get("position") or {}, a.get("size") or {}
    pb, sb = b.get("position") or {}, b.get("size") or {}
    ax, ay, az = float(pa.get("x") or 0), float(pa.get("y") or 0), float(pa.get("z") or 0)
    bx, by, bz = float(pb.get("x") or 0), float(pb.get("y") or 0), float(pb.get("z") or 0)
    adx, ady, adz = float(sa.get("dx") or 0), float(sa.get("dy") or 0), float(sa.get("dz") or 0)
    bdx, bdy, bdz = float(sb.get("dx") or 0), float(sb.get("dy") or 0), float(sb.get("dz") or 0)
    if az + adz <= bz or bz + bdz <= az:
        return False
    return not (
        ax + adx <= bx or bx + bdx <= ax or ay + ady <= by or by + bdy <= ay
    )


def _valid(items: List[Dict[str, Any]], L: float, W: float, H: float) -> bool:
    for it in items:
        pos, size = it.get("position") or {}, it.get("size") or {}
        x, y, z = float(pos.get("x") or 0), float(pos.get("y") or 0), float(pos.get("z") or 0)
        dx, dy, dz = float(size.get("dx") or 0), float(size.get("dy") or 0), float(size.get("dz") or 0)
        if x < -1 or y < -1 or z < -1 or x + dx > L + 1 or y + dy > W + 1 or z + dz > H + 1:
            return False
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _overlap(items[i], items[j]):
                return False
    return True


def _half_swap_y(
    items: List[Dict[str, Any]],
    W: float,
    L: float,
    H: float,
    wmap: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """左右半柜：质量较大的半边与另一边做 y 镜像交换（整半区平移对称）。"""
    mid_y = W / 2.0
    left = [it for it in items if _cy(it) < mid_y]
    right = [it for it in items if _cy(it) >= mid_y]
    ml = sum(_mass(it, wmap) for it in left)
    mr = sum(_mass(it, wmap) for it in right)
    if abs(ml - mr) / max(ml + mr, 1) < 0.08:
        return items, {"skipped": True, "reason": "already_balanced", "mass_L": ml, "mass_R": mr}

    # 整柜 y 镜像（等同 R1b，但只在半区质量差大时）
    out = []
    for it in items:
        nit = deepcopy(it)
        pos = dict(nit.get("position") or {})
        size = nit.get("size") or {}
        y = float(pos.get("y") or 0)
        dy = float(size.get("dy") or 0)
        pos["y"] = int(round(W - (y + dy)))
        if pos["y"] < 0:
            pos["y"] = 0
        nit["position"] = pos
        out.append(nit)
    if not _valid(out, L, W, H):
        return items, {"skipped": True, "reason": "invalid_after_swap"}
    return out, {
        "skipped": False,
        "method": "half_mirror_y",
        "mass_L_before": round(ml, 1),
        "mass_R_before": round(mr, 1),
    }


def _y_slab_reorder(
    items: List[Dict[str, Any]],
    W: float,
    L: float,
    H: float,
    wmap: Dict[str, float],
    n_slabs: int = 4,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """y 向条带：重条带靠中线。"""
    if len(items) < 3:
        return items, {"skipped": True}
    n_slabs = max(3, min(6, n_slabs))
    slab_h = W / n_slabs
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(n_slabs)]
    for it in items:
        si = int(_cy(it) / slab_h)
        si = max(0, min(n_slabs - 1, si))
        buckets[si].append(deepcopy(it))
    masses = [sum(_mass(it, wmap) for it in b) for b in buckets]
    src_order = sorted(range(n_slabs), key=lambda i: -masses[i])
    mid = (n_slabs - 1) / 2.0
    tgt = sorted(range(n_slabs), key=lambda i: abs(i - mid))
    new_b: List[List[Dict[str, Any]]] = [[] for _ in range(n_slabs)]
    for rank, s in enumerate(src_order):
        new_b[tgt[rank]] = buckets[s]

    placed: List[Dict[str, Any]] = []
    y_cursor = 0.0
    for si in range(n_slabs):
        slab = new_b[si]
        if not slab:
            continue
        min_y = min(float((it.get("position") or {}).get("y") or 0) for it in slab)
        max_y = max(
            float((it.get("position") or {}).get("y") or 0)
            + float((it.get("size") or {}).get("dy") or 0)
            for it in slab
        )
        width = max_y - min_y
        if y_cursor + width > W + 1:
            y_cursor = max(0.0, W - width)
        shift = y_cursor - min_y
        for it in slab:
            pos = dict(it.get("position") or {})
            pos["y"] = int(round(float(pos.get("y") or 0) + shift))
            it["position"] = pos
            placed.append(it)
        y_cursor += width

    if not _valid(placed, L, W, H):
        return items, {"skipped": True, "reason": "collision"}
    return placed, {"skipped": False, "method": "y_slab_reorder", "masses": masses}


def _pair_swap_lr(
    items: List[Dict[str, Any]],
    W: float,
    L: float,
    H: float,
    wmap: Dict[str, float],
    *,
    max_swaps: int = 8,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """左右半柜：最重左件与最轻右件（或反之）交换 y，最多 max_swaps 次。"""
    mid_y = W / 2.0
    work = [deepcopy(it) for it in items]
    n_swap = 0
    for _ in range(max_swaps):
        left = [it for it in work if _cy(it) < mid_y]
        right = [it for it in work if _cy(it) >= mid_y]
        if not left or not right:
            break
        ml = sum(_mass(it, wmap) for it in left)
        mr = sum(_mass(it, wmap) for it in right)
        if abs(ml - mr) / max(ml + mr, 1) < 0.06:
            break
        if ml > mr:
            heavy = max(left, key=lambda it: _mass(it, wmap))
            light = min(right, key=lambda it: _mass(it, wmap))
        else:
            heavy = max(right, key=lambda it: _mass(it, wmap))
            light = min(left, key=lambda it: _mass(it, wmap))
        # 交换 y（保持 x/z）
        ph, pl = dict(heavy.get("position") or {}), dict(light.get("position") or {})
        sh, sl = heavy.get("size") or {}, light.get("size") or {}
        yh, yl = float(ph.get("y") or 0), float(pl.get("y") or 0)
        dyh, dyl = float(sh.get("dy") or 0), float(sl.get("dy") or 0)
        # 镜像到对侧：用半宽对称
        ph2, pl2 = dict(ph), dict(pl)
        ph2["y"] = int(round(W - (yh + dyh)))
        pl2["y"] = int(round(W - (yl + dyl)))
        if ph2["y"] < 0:
            ph2["y"] = 0
        if pl2["y"] < 0:
            pl2["y"] = 0
        hid, lid = str(heavy.get("box_id")), str(light.get("box_id"))
        # 同 box_id 可能多件：用原 position 匹配
        hp = tuple((heavy.get("position") or {}).get(k) for k in ("x", "y", "z"))
        lp = tuple((light.get("position") or {}).get(k) for k in ("x", "y", "z"))
        trial = []
        for it in work:
            nit = deepcopy(it)
            ip = tuple((it.get("position") or {}).get(k) for k in ("x", "y", "z"))
            bid = str(it.get("box_id"))
            if bid == hid and ip == hp:
                nit["position"] = ph2
            elif bid == lid and ip == lp:
                nit["position"] = pl2
            trial.append(nit)
        if not _valid(trial, L, W, H):
            break
        work = trial
        n_swap += 1
    if n_swap == 0:
        return items, {"skipped": True, "reason": "no_pair_swap"}
    return work, {"skipped": False, "method": "pair_swap_lr", "n_swaps": n_swap}


def apply_lateral_repair(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    lat_threshold: float = 0.08,
    force: bool = False,
) -> Dict[str, Any]:
    """横偏 > 阈值时：半柜镜像 → 对换 y → y 条带重排，取 lat 最优。"""
    from packing_assistant.tools.cog import compute_cog_bundle, container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan

    ctype = str(plan.get("container_type") or "40HQ")
    dims = container_inner_mm(ctype)
    L, W, H = float(dims["L"]), float(dims["W"]), float(dims["H"])
    wmap = _wm(boxes)

    cog = plan.get("cog") or {}
    lat0 = float(cog.get("lateral_eccentricity") or 0)
    if not force and lat0 <= lat_threshold:
        return plan

    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    new_layout: List[Dict[str, Any]] = []
    stats: List[Dict[str, Any]] = []

    for cno in nos:
        items = [it for it in layout if int(it.get("container_no") or 1) == cno]
        from packing_assistant.tools.cog import cog_for_layout

        c = cog_for_layout(items, container_type=ctype, boxes=boxes, container_no=cno)
        lat_c = float((c or {}).get("lateral_eccentricity") or 0)
        if lat_c <= lat_threshold and not force:
            new_layout.extend(items)
            stats.append({"container_no": cno, "skipped": True, "lat": lat_c})
            continue

        candidates: List[Tuple[List[Dict[str, Any]], Dict[str, Any], float]] = []
        for fn, label in (
            (lambda its: _half_swap_y(its, W, L, H, wmap), "half_mirror"),
            (lambda its: _pair_swap_lr(its, W, L, H, wmap), "pair_swap"),
            (lambda its: _y_slab_reorder(its, W, L, H, wmap), "y_slab"),
        ):
            work, st = fn(items)
            cc = cog_for_layout(work, container_type=ctype, boxes=boxes, container_no=None)
            lat_x = float((cc or {}).get("lateral_eccentricity") or 9)
            candidates.append((work, {**st, "picked": label, "lat_after": lat_x}, lat_x))
            # 组合：pair 后再 y_slab
            if label == "pair_swap" and not st.get("skipped"):
                w2, st2 = _y_slab_reorder(work, W, L, H, wmap)
                c2 = cog_for_layout(w2, container_type=ctype, boxes=boxes, container_no=None)
                lat2 = float((c2 or {}).get("lateral_eccentricity") or 9)
                candidates.append(
                    (w2, {**st2, "picked": "pair+y_slab", "lat_after": lat2}, lat2)
                )

        best = min(candidates, key=lambda t: t[2])
        if best[2] <= lat_c + 1e-6:
            chosen, st = best[0], {
                **best[1],
                "lat_before": lat_c,
                "lat_after": best[2],
            }
        else:
            chosen, st = items, {"skipped": True, "reason": "no_improve", "lat": lat_c}
        for it in chosen:
            it["container_no"] = cno
        new_layout.extend(chosen)
        st["container_no"] = cno
        stats.append(st)

    out = dict(plan)
    out["layout"] = new_layout
    out["lateral_repair"] = {"method": "half_swap_and_y_slab", "per_container": stats}
    try:
        bundle = compute_cog_bundle(out, boxes=boxes)
        if not bundle:
            return plan
        new_lat = float((bundle.get("worst") or {}).get("lateral_eccentricity") or 9)
        # mid50 不能明显变差
        mid_b = plan.get("worst_mid50")
        mid_a = bundle.get("worst_mid50")
        if mid_b is not None and mid_a is not None and float(mid_a) + 1e-9 < float(mid_b) - 0.03:
            return plan
        if new_lat > lat0 + 0.02 and not force:
            return plan
        out["cog_bundle"] = bundle
        out["cog"] = bundle.get("worst") or bundle.get("primary")
        out["worst_mid50"] = bundle.get("worst_mid50")
        out["all_mid50_ok"] = bundle.get("all_mid50_ok")
        st = dict(out.get("stacking") or {})
        st["lateral_repair_applied"] = any(not s.get("skipped") for s in stats)
        st["lat_before"] = lat0
        st["lat_after"] = new_lat
        out["stacking"] = st
    except Exception:
        return plan
    return out
