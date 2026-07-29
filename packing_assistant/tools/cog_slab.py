"""R2：纵向条带（slab）按质量重排靠中 — Davies/Bischoff 墙交换简化版。

将每柜按柜长切成 n 条带，按条带总质量把最重的条带挪到中部，轻条带去两端。
条带内部相对几何保持不变，只做整体 x 平移。
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
    return max(
        float(size.get("dx") or 1)
        * float(size.get("dy") or 1)
        * float(size.get("dz") or 1)
        / 1e8,
        1.0,
    )


def _cx(it: Dict[str, Any]) -> float:
    pos, size = it.get("position") or {}, it.get("size") or {}
    return float(pos.get("x") or 0) + float(size.get("dx") or 0) / 2


def _mid50(items: List[Dict[str, Any]], L: float, wmap: Dict[str, float]) -> float:
    tot = mid = 0.0
    for it in items:
        m = _mass(it, wmap)
        tot += m
        cx = _cx(it)
        if 0.25 * L <= cx <= 0.75 * L:
            mid += m
    return mid / tot if tot > 0 else 0.0


def _overlap_xy(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa, sa = a.get("position") or {}, a.get("size") or {}
    pb, sb = b.get("position") or {}, b.get("size") or {}
    ax, ay = float(pa.get("x") or 0), float(pa.get("y") or 0)
    bx, by = float(pb.get("x") or 0), float(pb.get("y") or 0)
    adx, ady = float(sa.get("dx") or 0), float(sa.get("dy") or 0)
    bdx, bdy = float(sb.get("dx") or 0), float(sb.get("dy") or 0)
    za, zb = float(pa.get("z") or 0), float(pb.get("z") or 0)
    adz, bdz = float(sa.get("dz") or 0), float(sb.get("dz") or 0)
    if za + adz <= zb or zb + bdz <= za:
        return False
    return not (
        ax + adx <= bx or bx + bdx <= ax or ay + ady <= by or by + bdy <= ay
    )


def _valid_layout(items: List[Dict[str, Any]], L: float, W: float, H: float) -> bool:
    for it in items:
        pos, size = it.get("position") or {}, it.get("size") or {}
        x, y, z = float(pos.get("x") or 0), float(pos.get("y") or 0), float(pos.get("z") or 0)
        dx, dy, dz = float(size.get("dx") or 0), float(size.get("dy") or 0), float(size.get("dz") or 0)
        if x < -1e-3 or y < -1e-3 or z < -1e-3:
            return False
        if x + dx > L + 1 or y + dy > W + 1 or z + dz > H + 1:
            return False
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            if _overlap_xy(items[i], items[j]):
                return False
    return True


def reorder_slabs_container(
    items: List[Dict[str, Any]],
    *,
    L: float,
    W: float,
    H: float,
    wmap: Dict[str, float],
    n_slabs: int = 6,
    gap_mm: int = 0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """单柜条带重排。"""
    if len(items) < 3:
        return items, {"skipped": True, "reason": "too_few"}

    mid0 = _mid50(items, L, wmap)
    if mid0 >= 0.60:
        return items, {"skipped": True, "mid50_before": mid0, "mid50_after": mid0}

    n_slabs = max(4, min(10, int(n_slabs)))
    slab_w = L / n_slabs
    buckets: List[List[Dict[str, Any]]] = [[] for _ in range(n_slabs)]
    for it in items:
        si = int(_cx(it) / slab_w)
        si = max(0, min(n_slabs - 1, si))
        buckets[si].append(deepcopy(it))

    masses = [sum(_mass(it, wmap) for it in b) for b in buckets]
    # 源条带按质量从重到轻
    src_order = sorted(range(n_slabs), key=lambda i: -masses[i])
    # 目标槽位：由中心向外
    mid = (n_slabs - 1) / 2.0
    tgt_slots = sorted(range(n_slabs), key=lambda i: abs(i - mid))

    new_buckets: List[List[Dict[str, Any]]] = [[] for _ in range(n_slabs)]
    for rank, src_i in enumerate(src_order):
        new_buckets[tgt_slots[rank]] = buckets[src_i]

    # 从左到右紧凑放置各条带（保持条带内相对 x）
    placed: List[Dict[str, Any]] = []
    x_cursor = 0.0
    for si in range(n_slabs):
        slab = new_buckets[si]
        if not slab:
            continue
        min_x = min(float((it.get("position") or {}).get("x") or 0) for it in slab)
        max_x = max(
            float((it.get("position") or {}).get("x") or 0)
            + float((it.get("size") or {}).get("dx") or 0)
            for it in slab
        )
        width = max_x - min_x
        if x_cursor + width > L + 1e-3:
            # 放不下则尝试压缩到剩余
            shift = -min_x  # 先归零
            # 若 width > L，放弃本柜
            if width > L + 1:
                return items, {"skipped": True, "reason": "slab_too_wide", "mid50_before": mid0}
            x_cursor = max(0.0, L - width)
        shift = x_cursor - min_x
        for it in slab:
            pos = dict(it.get("position") or {})
            pos["x"] = int(round(float(pos.get("x") or 0) + shift))
            it["position"] = pos
            placed.append(it)
        x_cursor += width + gap_mm

    if not _valid_layout(placed, L, W, H):
        return items, {"skipped": True, "reason": "collision_or_oob", "mid50_before": mid0}

    mid1 = _mid50(placed, L, wmap)
    if mid1 + 1e-9 < mid0 - 0.005:
        return items, {
            "skipped": True,
            "reason": "mid50_worse",
            "mid50_before": mid0,
            "mid50_after": mid1,
        }

    return placed, {
        "skipped": False,
        "mid50_before": round(mid0, 4),
        "mid50_after": round(mid1, 4),
        "n_slabs": n_slabs,
        "masses_old": [round(m, 1) for m in masses],
        "src_order": src_order,
        "tgt_slots": tgt_slots,
    }


def apply_r2_slab_reorder(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    n_slabs: int = 6,
    target_mid50: float = 0.55,
    force: bool = False,
) -> Dict[str, Any]:
    """对 worst mid50 不足的柜做 R2 条带重排。"""
    from packing_assistant.tools.cog import compute_cog_bundle, container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan

    ctype = str(plan.get("container_type") or "40HQ")
    dims = container_inner_mm(ctype)
    L, W, H = float(dims["L"]), float(dims["W"]), float(dims["H"])
    wmap = _wm(boxes)

    mid_before = plan.get("worst_mid50")
    if mid_before is None:
        b0 = compute_cog_bundle(plan, boxes=boxes) or {}
        mid_before = b0.get("worst_mid50", 1.0)
    if not force and mid_before is not None and float(mid_before) >= target_mid50:
        return plan

    nos = sorted({int(it.get("container_no") or 1) for it in layout})
    new_layout: List[Dict[str, Any]] = []
    stats: List[Dict[str, Any]] = []

    for cno in nos:
        items = [it for it in layout if int(it.get("container_no") or 1) == cno]
        m_c = _mid50(items, L, wmap)
        if m_c >= target_mid50 and not force:
            new_layout.extend(items)
            stats.append({"container_no": cno, "skipped": True, "mid50": round(m_c, 4)})
            continue
        repaired, st = reorder_slabs_container(
            items, L=L, W=W, H=H, wmap=wmap, n_slabs=n_slabs
        )
        for it in repaired:
            it["container_no"] = cno
        new_layout.extend(repaired)
        st["container_no"] = cno
        stats.append(st)

    out = dict(plan)
    out["layout"] = new_layout
    out["r2_slab"] = {"method": "longitudinal_slab_mass_reorder", "per_container": stats}

    try:
        bundle = compute_cog_bundle(out, boxes=boxes)
        if not bundle:
            return plan
        mid_after = bundle.get("worst_mid50")
        if mid_after is not None and float(mid_after) + 1e-9 < float(mid_before or 0) - 0.01:
            return plan
        out["cog_bundle"] = bundle
        out["cog"] = bundle.get("worst") or bundle.get("primary")
        out["worst_mid50"] = mid_after
        out["all_mid50_ok"] = bundle.get("all_mid50_ok")
        st = dict(out.get("stacking") or {})
        st["r2_slab_applied"] = any(not s.get("skipped") for s in stats)
        st["r2_mid50_before"] = mid_before
        st["r2_mid50_after"] = mid_after
        out["stacking"] = st
    except Exception:
        return plan
    return out


def apply_r3_partial_repack(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    target_mid50: float = 0.55,
) -> Dict[str, Any]:
    """
    R3 轻量：最差柜上，把带外重货尽量 x 滑入中段（调用 R4 slide 逻辑加强）。
    不做完整 EP 重装，避免耗时。
    """
    from packing_assistant.tools.cog_repair import apply_r4_repair

    mid = plan.get("worst_mid50")
    if mid is not None and float(mid) >= target_mid50:
        return plan
    # 强制 R4 再跑一轮（更激进目标）
    return apply_r4_repair(plan, boxes, target_mid50=target_mid50, force=True)
