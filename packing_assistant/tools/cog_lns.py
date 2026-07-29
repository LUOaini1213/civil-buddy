"""最差柜 LNS：卸两端轻货 → 重货中段重装 → 轻货回填。

比 R2 条带更狠：对 mid50 不足的柜整柜 EP 重装（可多柜迭代）。
顺序强制重货优先 + cog_rebalance 中段 EP。
"""

from __future__ import annotations

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


def _cx(it: Dict[str, Any]) -> float:
    pos, size = it.get("position") or {}, it.get("size") or {}
    return float(pos.get("x") or 0) + float(size.get("dx") or 0) / 2


def _repack_one_cabin(
    items_layout: List[Dict[str, Any]],
    *,
    ctype: str,
    cno: int,
    wmap: Dict[str, float],
    L: float,
) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    """单柜：重货先装中段，轻货/带外后回填。"""
    from packing_assistant.tools.bin3d import (
        Item3D,
        pack_items,
        policy_from_options,
        set_active_policy,
        get_active_policy,
    )

    if len(items_layout) < 3:
        return None, {"skipped": True, "reason": "too_few"}

    masses = [_mass(it, wmap) for it in items_layout]
    thr = sorted(masses, reverse=True)
    # 重货：质量前 40% 或 ≥ 中位数*1.5 或 当前在带外的重件
    cut = thr[max(0, int(len(thr) * 0.4) - 1)] if thr else 0
    mid_lo, mid_hi = 0.25 * L, 0.75 * L

    heavies: List[Dict[str, Any]] = []
    lights_end: List[Dict[str, Any]] = []
    lights_mid: List[Dict[str, Any]] = []
    for it in items_layout:
        m = _mass(it, wmap)
        cx = _cx(it)
        in_mid = mid_lo <= cx <= mid_hi
        is_heavy = m >= cut or m >= 400
        if is_heavy:
            heavies.append(it)
        elif not in_mid:
            lights_end.append(it)  # 两端轻货：后装
        else:
            lights_mid.append(it)

    heavies.sort(key=lambda it: -_mass(it, wmap))
    lights_mid.sort(key=lambda it: -_mass(it, wmap))
    lights_end.sort(key=lambda it: -_mass(it, wmap))
    # 真 LNS：重货中段 → 中段轻货回填 → 两端轻货最后
    pack_order = heavies + lights_mid + lights_end

    item3ds: List[Item3D] = []
    for it in pack_order:
        size = it.get("size") or {}
        bid = str(it.get("box_id") or "")
        m = _mass(it, wmap)
        item3ds.append(
            Item3D(
                box_id=bid,
                dx=max(int(size.get("dx") or 1), 1),
                dy=max(int(size.get("dy") or 1), 1),
                dz=max(int(size.get("dz") or 1), 1),
                weight_kg=m,
                allow_rotate=True,
                no_tip=max(int(size.get("dx") or 0), int(size.get("dy") or 0)) >= 2000,
                stackable=bool(it.get("stackable", True)),
                # 重货底层优先，利于中段 EP 站住
                prefer_bottom=bool(m >= cut or m >= 500),
            )
        )

    prev = get_active_policy()
    set_active_policy(
        policy_from_options(
            {
                "prefer_stack": True,
                "cog_aware": True,
                "cog_rebalance": True,
                "multi_start": False,
                "clearance_mm": 20,
                "max_stack_layers": 3,
            }
        )
    )
    try:
        sub = pack_items(
            item3ds,
            container_type=ctype,
            max_containers=1,
            packing_options={
                "prefer_stack": True,
                "cog_aware": True,
                "cog_rebalance": True,
                "multi_start": False,
                "r0_r1": False,
                "r2_slab": False,
                "r4_repair": False,
                "r3_repack": False,
                "lns_worst": False,
                "lateral_repair": False,
            },
        )
    finally:
        set_active_policy(prev)

    if sub.get("unpacked_box_ids"):
        return None, {
            "skipped": True,
            "reason": "unpacked",
            "unpacked": sub.get("unpacked_box_ids"),
        }

    new_c_layout = []
    for pl in sub.get("layout") or []:
        npl = dict(pl)
        npl["container_no"] = cno
        new_c_layout.append(npl)
    return new_c_layout, {
        "skipped": False,
        "n_heavy": len(heavies),
        "n_light_end": len(lights_end),
        "n_light_mid": len(lights_mid),
        "n_items": len(new_c_layout),
    }


def apply_lns_worst_container(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    target_mid50: float = 0.55,
    force: bool = False,
    max_cabins: int = 4,
) -> Dict[str, Any]:
    """
    对 mid50 < target 的柜做 LNS（最多 max_cabins 个），优先 worst。
    force=True 时至少修 worst 一柜。
    """
    from packing_assistant.tools.cog import compute_cog_bundle, container_inner_mm

    layout = list(plan.get("layout") or [])
    if not layout:
        return plan

    ctype = str(plan.get("container_type") or "40HQ")
    dims = container_inner_mm(ctype)
    L = float(dims["L"])
    wmap = _wm(boxes)

    bundle0 = plan.get("cog_bundle") or compute_cog_bundle(plan, boxes=boxes) or {}
    mid_before = plan.get("worst_mid50")
    if mid_before is None:
        mid_before = bundle0.get("worst_mid50", 1.0)

    # 收集需修的柜号
    per = list(bundle0.get("per_container") or [])
    bad: List[Tuple[float, int]] = []
    for c in per:
        mid = c.get("mass_in_mid50_ratio")
        cno = int(c.get("container_no") or 1)
        if mid is not None and float(mid) < target_mid50:
            bad.append((float(mid), cno))
    bad.sort()  # worst first

    if not bad:
        if force:
            worst = bundle0.get("worst") or bundle0.get("primary") or {}
            cno = int(worst.get("container_no") or 1)
            bad = [(float(mid_before or 0), cno)]
        else:
            return plan

    out = dict(plan)
    cur_layout = list(layout)
    applied: List[Dict[str, Any]] = []
    mid_cursor = float(mid_before or 0)

    for mid_c, cno in bad[: max(1, max_cabins)]:
        items_c = [it for it in cur_layout if int(it.get("container_no") or 1) == cno]
        if len(items_c) < 3:
            continue
        new_c, st = _repack_one_cabin(items_c, ctype=ctype, cno=cno, wmap=wmap, L=L)
        if not new_c:
            applied.append({"container_no": cno, **st})
            continue
        other = [it for it in cur_layout if int(it.get("container_no") or 1) != cno]
        trial_layout = other + new_c
        trial = {**out, "layout": trial_layout}
        try:
            bundle = compute_cog_bundle(trial, boxes=boxes)
            if not bundle:
                continue
            mid_after = float(bundle.get("worst_mid50") or 0)
            # 整票 worst 不得明显变差；该柜 mid 应改善
            cabin_after = None
            for pc in bundle.get("per_container") or []:
                if int(pc.get("container_no") or 1) == cno:
                    cabin_after = float(pc.get("mass_in_mid50_ratio") or 0)
                    break
            if mid_after + 1e-9 < mid_cursor - 0.02:
                applied.append(
                    {
                        "container_no": cno,
                        "skipped": True,
                        "reason": "global_mid50_worse",
                        "mid_before": mid_c,
                        "global_after": mid_after,
                    }
                )
                continue
            if cabin_after is not None and cabin_after + 1e-9 < mid_c - 0.005:
                applied.append(
                    {
                        "container_no": cno,
                        "skipped": True,
                        "reason": "cabin_mid50_worse",
                        "mid_before": mid_c,
                        "mid_after": cabin_after,
                    }
                )
                continue
            cur_layout = trial_layout
            out = trial
            out["cog_bundle"] = bundle
            out["cog"] = bundle.get("worst") or bundle.get("primary")
            out["worst_mid50"] = bundle.get("worst_mid50")
            out["all_mid50_ok"] = bundle.get("all_mid50_ok")
            mid_cursor = float(bundle.get("worst_mid50") or mid_cursor)
            applied.append(
                {
                    "container_no": cno,
                    "skipped": False,
                    "mid_before": mid_c,
                    "mid_after": cabin_after,
                    "global_worst_after": mid_cursor,
                    **{k: v for k, v in st.items() if k != "skipped"},
                }
            )
        except Exception as e:
            applied.append({"container_no": cno, "skipped": True, "reason": str(e)[:80]})

    any_ok = any(not a.get("skipped") for a in applied)
    if not any_ok:
        return plan

    out["layout"] = cur_layout
    out["lns_repair"] = {
        "method": "multi_cabin_destroy_repair",
        "target_mid50": target_mid50,
        "per_container": applied,
    }
    st = dict(out.get("stacking") or {})
    st["lns_applied"] = True
    st["lns_mid50_before"] = mid_before
    st["lns_mid50_after"] = out.get("worst_mid50")
    st["lns_cabins"] = [a.get("container_no") for a in applied if not a.get("skipped")]
    out["stacking"] = st
    return out
