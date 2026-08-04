"""
自主定柜引擎（无业务目标柜数）。

N0* = max(N_weight, N_volume, N_geom_floor, N_geom_slot)
N 从 N0* 起 3D 试装直至 can_fit 或达上限；末柜偏空可尝试并回 N-1。

柜级策略说明（与柜内 multi_start 不同）：
- 柜内 multi_start：固定 N 柜时多种放置/排序候选（bin3d）。
- 柜级：下界 N0* + 递增试装（非经典跨柜 FFD 全局最优）；Agent 负责意图/锁柜/解释。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from packing_assistant.tools.volume_estimate import (
    booking_volume_from_boxes,
    estimate_containers,
)


def _box_outer_lwh(b: Dict[str, Any]) -> tuple:
    o = b.get("outer_size_mm") or b.get("外尺寸_mm") or {}
    L = float(o.get("length") or o.get("长") or 0)
    W = float(o.get("width") or o.get("宽") or 0)
    H = float(o.get("height") or o.get("高") or 0)
    return L, W, H


def geom_n0_components(
    boxes: Sequence[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    eta_floor: float = 0.88,
) -> Dict[str, Any]:
    """
    几何下界（业界 multi-container lower bound 的轻量版）：
    - floor：Σ 底面积 / (柜底面积 × η)
    - slot：不可叠箱按两排槽位估算（raw 常偏紧，供审计）
    - n_geom_slot_capped：软封顶后的槽位柜数（进 N0* 搜索，防 446t 类 slot 虚高）
    """
    try:
        from packing_assistant.knowledge import container_inner_mm

        cab = container_inner_mm().get((container_type or "40HQ").upper()) or {}
        cab_L = float(cab.get("L") or 12032)
        cab_W = float(cab.get("W") or 2352)
    except Exception:
        cab_L, cab_W = 12032.0, 2352.0

    eta = min(max(float(eta_floor), 0.70), 0.95)
    foot = 0.0
    floor_items = 0.0
    lengths = []
    widths = []
    for b in boxes:
        L, W, H = _box_outer_lwh(b)
        if L <= 0 or W <= 0:
            continue
        foot += L * W
        lengths.append(L)
        widths.append(W)
        special = b.get("special_attributes") or []
        stackable = b.get("stackable")
        if stackable is None:
            stackable = H <= 1300 and "超长" not in special and L < 4000
        prefer_bottom = bool(b.get("prefer_bottom")) or L >= 4000 or float(
            b.get("gross_weight_kg") or 0
        ) >= 2000
        if not stackable or prefer_bottom or H > 1500:
            floor_items += 1.0
        else:
            floor_items += 0.45  # 可叠/轻货：略松于 0.55，避免 slot 虚高

    floor_area = max(cab_L * cab_W * eta, 1.0)
    n_geom_floor = max(1, int(math.ceil(foot / floor_area - 1e-9))) if foot > 0 else 0

    # 沿长向：用中位长（抗极端超长拉高 avg）
    lengths_sorted = sorted(lengths) if lengths else [2000.0]
    mid_L = lengths_sorted[len(lengths_sorted) // 2]
    n_along = max(1, int(cab_L // max(mid_L, 500.0)))
    # 两排：多数箱宽 ≤ 半柜+80 才按 2 排；否则按 1 排
    half_ok = sum(1 for w in widths if w <= cab_W * 0.5 + 80) if widths else 0
    n_across = 2 if (not widths or half_ok >= max(1, int(0.55 * len(widths)))) else 1
    cap_floor = max(1, n_along * n_across)
    n_geom_slot_raw = (
        max(1, int(math.ceil(floor_items / cap_floor - 1e-9))) if floor_items > 0 else 0
    )
    # 软封顶：slot 不高于 max(floor, 1)×1.35+2，且不高于 floor+wt 量级的松弛上界
    # （raw 仍写入 geom_detail 供审计）
    n_geom_slot = n_geom_slot_raw

    return {
        "n_geom_floor": n_geom_floor,
        "n_geom_slot": n_geom_slot,
        "n_geom_slot_raw": n_geom_slot_raw,
        "eta_floor": eta,
        "footprint_mm2": round(foot, 1),
        "floor_items_eq": round(floor_items, 2),
        "slots_per_container": cap_floor,
        "n_along": n_along,
        "n_across": n_across,
        "median_L_mm": round(mid_L, 1),
    }


def compute_booking(
    *,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
    fill_ratio: float = 0.82,
) -> Dict[str, Any]:
    """
    订柜初值 N0 与明细。
    有 boxes 时优先用 min(outer, content×k)；否则用材料 pack_effective。
    """
    if boxes:
        est = estimate_containers(
            boxes=list(boxes),
            container_type=container_type,
            fill_ratio=fill_ratio,
            volume_mode="pack_effective",
        )
        bv = booking_volume_from_boxes(boxes)
        est["volume_detail"] = {**(est.get("volume_detail") or {}), **bv}
        est["volume_m3"] = bv.get("booking_volume_m3", est.get("volume_m3"))
        # 用 booking_volume 重算体积柜数
        usable = float(est.get("usable_m3_per_container") or 1)
        v = float(est["volume_m3"] or 0)

        n_vol = max(1, int(math.ceil(v / usable - 1e-9))) if v > 0 else 0
        n_wt = int(est.get("containers_by_weight") or 0)
        geom = geom_n0_components(boxes, container_type=container_type)
        n_gf = int(geom.get("n_geom_floor") or 0)
        n_gs_raw = int(geom.get("n_geom_slot_raw") or geom.get("n_geom_slot") or 0)
        # 槽位软封顶：避免长料/混料把 N0* 抬到远超 wt/floor（搜索从虚高 N 起 → 实装 gap 假象 + 并回弱）
        base_geo = max(n_wt, n_vol, n_gf, 1)
        n_gs_cap = max(base_geo, int(math.ceil(base_geo * 1.30 + 2)))
        n_gs = min(n_gs_raw, n_gs_cap) if n_gs_raw > 0 else 0
        n0 = max(n_wt, n_vol, n_gf, n_gs, 1)
        # 搜索起点可略紧于 n0（先试 base 量级，再递增），大票省试装且逼近真最小柜
        # 搜索起点：重量/体积/底面，不把 slot 软顶抬进起点（slot 仅进 n0 报告）
        n0_search = max(n_wt, n_vol, n_gf, 1)
        n0_search = min(n0_search, n0)
        est["containers_by_volume"] = n_vol
        est["containers_by_geom_floor"] = n_gf
        est["containers_by_geom_slot"] = n_gs
        est["containers_by_geom_slot_raw"] = n_gs_raw
        est["n0_components"] = {
            "weight": n_wt,
            "volume": n_vol,
            "geom_floor": n_gf,
            "geom_slot": n_gs,
            "geom_slot_raw": n_gs_raw,
        }
        est["geom_detail"] = {**geom, "n_geom_slot_capped": n_gs, "n_gs_cap": n_gs_cap}
        est["containers_needed"] = n0
        est["n0"] = n0
        est["n0_search"] = n0_search
        # binding：谁抬起了 N0*
        comps = [
            ("weight", n_wt),
            ("volume", n_vol),
            ("geom_floor", n_gf),
            ("geom_slot", n_gs),
        ]
        top = max(comps, key=lambda x: x[1])
        if sum(1 for _, v in comps if v == top[1]) > 1:
            est["binding_constraint"] = "multi"
        else:
            est["binding_constraint"] = top[0]
        cap_note = f",slot_raw={n_gs_raw}" if n_gs_raw != n_gs else ""
        est["n0_note"] = (
            f"N0*=max(wt={n_wt},vol={n_vol},floor={n_gf},slot={n_gs}{cap_note})={n0}"
            + (f"; search≥{n0_search}" if n0_search != n0 else "")
        )
        # 体积可疑
        if n_vol >= max(2, 2 * max(n_wt, 1)):
            est["volume_suspicious"] = True
            est["warning"] = (
                f"体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，有效体积分子可能仍偏虚，"
                f"请核对箱填充率/尺寸来源"
            )
        else:
            est["volume_suspicious"] = False
        return est

    est = estimate_containers(
        materials=list(materials or []),
        container_type=container_type,
        fill_ratio=fill_ratio,
        volume_mode="pack_effective",
    )
    n_vol = int(est.get("containers_by_volume") or 0)
    n_wt = int(est.get("containers_by_weight") or 0)
    n0 = max(int(est.get("containers_needed") or 1), n_wt, n_vol, 1)
    est["n0"] = n0
    est["containers_needed"] = n0
    est["n0_components"] = {"weight": n_wt, "volume": n_vol, "geom_floor": 0, "geom_slot": 0}
    est["n0_note"] = f"N0*=max(wt={n_wt},vol={n_vol})={n0}（无成箱几何）"
    est["volume_suspicious"] = n_vol >= max(2, 2 * max(n_wt, 1))
    if est["volume_suspicious"]:
        est["warning"] = (
            f"体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，请核对材料尺寸/包装膨胀"
        )
    return est


def _last_container_stats(plan: Dict[str, Any]) -> Dict[str, Any]:
    used = int(plan.get("containers_used") or 0)
    per = plan.get("per_container") or []
    if not per or used <= 0:
        # fallback from layout
        layout = plan.get("layout") or []
        by: Dict[int, int] = {}
        for p in layout:
            cn = int(p.get("container_no") or 1)
            by[cn] = by.get(cn, 0) + 1
        if not by:
            return {"container_no": used, "n_boxes": 0, "floor_utilization": 0.0}
        last_no = max(by.keys())
        return {
            "container_no": last_no,
            "n_boxes": by[last_no],
            "floor_utilization": None,
            "load_kg": None,
        }
    last = max(per, key=lambda x: int(x.get("container_no") or 0))
    return {
        "container_no": int(last.get("container_no") or used),
        "n_boxes": int(last.get("boxes") or 0),
        "floor_utilization": last.get("floor_utilization"),
        "load_kg": last.get("load_kg"),
        "volume_utilization": last.get("volume_utilization"),
    }


def _is_residual_last(last_stats: Dict[str, Any], used: int) -> bool:
    """末柜是否偏空（并回候选）。"""
    if used < 2:
        return False
    n_boxes = int(last_stats.get("n_boxes") or 0)
    floor_u = last_stats.get("floor_utilization")
    load = last_stats.get("load_kg")
    if n_boxes <= 3:
        return True
    if floor_u is not None and float(floor_u or 0) < 0.35:
        return True
    if load is not None and float(load or 0) < 4000:
        return True
    return False


def _plan_worst_mid50(plan: Optional[Dict[str, Any]]) -> Optional[float]:
    """从 plan 取最差柜 mid50（0~1）。"""
    if not plan:
        return None
    try:
        if plan.get("worst_mid50") is not None:
            return float(plan.get("worst_mid50"))
        bundle = plan.get("cog_bundle") or {}
        if bundle.get("worst_mid50") is not None:
            return float(bundle.get("worst_mid50"))
        cog = plan.get("cog") or bundle.get("worst") or bundle.get("primary") or {}
        if cog.get("mass_in_mid50_ratio") is not None:
            return float(cog.get("mass_in_mid50_ratio"))
    except (TypeError, ValueError):
        return None
    return None


def _candidate_row(
    strategy_id: str,
    plan: Dict[str, Any],
    *,
    reference_only: bool = False,
    note: str = "",
) -> Dict[str, Any]:
    used = int(plan.get("containers_used") or 0)
    mid = _plan_worst_mid50(plan)
    try:
        wt = float(plan.get("weight_utilization") or 0)
    except (TypeError, ValueError):
        wt = 0.0
    can_fit = bool(plan.get("can_fit"))
    ship_ok_hint = bool(
        can_fit
        and not reference_only
        and (mid is None or mid >= 0.55)
    )
    return {
        "strategy_id": strategy_id,
        "used": used,
        "weight_utilization": round(wt, 4),
        "mid50": None if mid is None else round(mid, 4),
        "can_fit": can_fit,
        "reference_only": reference_only,
        "ship_ok_hint": ship_ok_hint,
        "density_mode": plan.get("density_mode") or strategy_id,
        "note": note,
    }


def select_packing_strategy(
    candidates: List[Dict[str, Any]],
    *,
    mid50_hard: float = 0.55,
    mid50_target: float = 0.60,
) -> Dict[str, Any]:
    """
    Agent 择优规则（确定性，可审计）：
    1) 可出运（can_fit 且非 reference 且 mid50≥hard）中取 used 最少
    2) 否则 mid50≥target 放宽 reference 外
    3) 否则取非 reference 的 can_fit 最少 used，并标记 need_cog_warn
    4) 否则取任意 can_fit
    """
    if not candidates:
        return {
            "chosen": None,
            "reason": "无候选",
            "candidates": [],
        }
    shipable = [
        c
        for c in candidates
        if c.get("can_fit")
        and not c.get("reference_only")
        and (
            c.get("mid50") is None
            or float(c.get("mid50") or 0) >= mid50_hard
        )
    ]
    if shipable:
        shipable.sort(key=lambda c: (int(c.get("used") or 99), -float(c.get("mid50") or 0)))
        ch = shipable[0]
        return {
            "chosen": ch.get("strategy_id"),
            "reason": (
                f"Agent 选 {ch.get('strategy_id')}：可出运候选中最少柜 "
                f"(used={ch.get('used')}, mid50={ch.get('mid50')}, wt={ch.get('weight_utilization')})"
            ),
            "candidates": candidates,
            "chosen_row": ch,
            "need_cog_warn": False,
            "ship_ok_hint": True,
        }
    soft = [
        c
        for c in candidates
        if c.get("can_fit")
        and not c.get("reference_only")
        and c.get("mid50") is not None
        and float(c.get("mid50") or 0) >= mid50_target - 0.05
    ]
    if soft:
        soft.sort(key=lambda c: (int(c.get("used") or 99), -float(c.get("mid50") or 0)))
        ch = soft[0]
        return {
            "chosen": ch.get("strategy_id"),
            "reason": (
                f"Agent 选 {ch.get('strategy_id')}：mid50 接近目标，建议 HITL warn "
                f"(used={ch.get('used')}, mid50={ch.get('mid50')})"
            ),
            "candidates": candidates,
            "chosen_row": ch,
            "need_cog_warn": True,
            "ship_ok_hint": False,
        }
    full = [c for c in candidates if c.get("can_fit") and not c.get("reference_only")]
    if full:
        full.sort(key=lambda c: (int(c.get("used") or 99), -float(c.get("mid50") or 0)))
        ch = full[0]
        return {
            "chosen": ch.get("strategy_id"),
            "reason": (
                f"Agent 选 {ch.get('strategy_id')}：无 mid50≥{mid50_hard:.0%} 方案，"
                f"取 full 最少柜并需 CoG replan (used={ch.get('used')}, mid50={ch.get('mid50')})"
            ),
            "candidates": candidates,
            "chosen_row": ch,
            "need_cog_warn": True,
            "ship_ok_hint": False,
        }
    any_fit = [c for c in candidates if c.get("can_fit")]
    if any_fit:
        ch = min(any_fit, key=lambda c: int(c.get("used") or 99))
        return {
            "chosen": ch.get("strategy_id"),
            "reason": f"仅参考/降级候选 {ch.get('strategy_id')}（reference_only 勿直接出运）",
            "candidates": candidates,
            "chosen_row": ch,
            "need_cog_warn": True,
            "ship_ok_hint": False,
        }
    return {
        "chosen": candidates[0].get("strategy_id"),
        "reason": "无 can_fit 候选",
        "candidates": candidates,
        "chosen_row": candidates[0],
        "need_cog_warn": True,
        "ship_ok_hint": False,
    }


def pack_with_auto_containers(
    boxes: List[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    n0: Optional[int] = None,
    n_max: int = 40,
    priority_order: Optional[List[str]] = None,
    fill_ratio: float = 0.82,
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    从 N0*（或更紧的 n0_search）起递增 max_containers 直到 can_fit 或达 n_max。
    末柜偏空时多轮并回 used-1, used-2…（残料 rebalance）。

    柜级 ≠ 柜内 multi_start：
    - 柜内：固定 N 时多种放置策略（bin3d multi_start）
    - 柜级：N0* 下界 + 递增试装 + 多轮末柜并回
    """
    from packing_assistant.tools.bin3d import pack_boxes_api

    booking = compute_booking(
        boxes=boxes, container_type=container_type, fill_ratio=fill_ratio
    )
    n0_star = int(booking.get("n0") or booking.get("containers_needed") or 1)
    n0_search = int(booking.get("n0_search") or n0_star)
    comps0 = booking.get("n0_components") or {}
    hard_lb0 = max(1, int(comps0.get("weight") or 0), int(comps0.get("volume") or 0))
    # 搜索起点：优先略紧的 n0_search；外部 n0 更大时不抬高起点（防 slot 虚高），更小时尊重（锁柜/预算）
    if n0 is not None:
        n_ext = int(n0)
        start = min(n_ext, n0_search) if n_ext > n0_search else n_ext
    else:
        start = n0_search
    # 大票：搜索从 hard_lb 起递增（避免宽松 max_c 贪婪多开柜）
    if len(boxes) >= 40 or start >= 8:
        start = min(start, max(hard_lb0, int(comps0.get("geom_floor") or hard_lb0)))
        # 若 geom_floor 明显高于重量，仍从 max(wt, 0.85*floor) 起，给几何留一点余量
        gf = int(comps0.get("geom_floor") or 0)
        if gf > hard_lb0 + 2:
            start = min(start, max(hard_lb0, int(math.ceil(gf * 0.88))))
    start = max(1, min(start, n_max))

    last = None
    tried = []
    for n in range(start, n_max + 1):
        plan = pack_boxes_api(
            boxes,
            container_type=container_type,
            max_containers=n,
            priority_order=priority_order,
            packing_options=packing_options,
        )
        tried.append(
            {
                "n": n,
                "can_fit": plan.get("can_fit"),
                "used": plan.get("containers_used"),
                "unpacked": len(plan.get("unpacked_box_ids") or []),
            }
        )
        last = plan
        if plan.get("can_fit"):
            break

    if last is None:
        last = {
            "can_fit": False,
            "containers_used": 0,
            "engine": "none",
            "unpacked_box_ids": [b.get("box_id") for b in boxes],
        }

    # —— 大票密度下界：轻量策略（关 multi/重 CoG）常更少柜；找到后用该柜数重跑完整策略 ——
    used0 = int(last.get("containers_used") or 0)
    if (
        last.get("can_fit")
        and used0 >= 6
        and len(boxes) >= 40
        and packing_options
    ):
        light_opts = {
            **dict(packing_options),
            "multi_start": False,
            "cog_aware": False,
            "cog_rebalance": False,
            "lns_worst": False,
            "lateral_repair": False,
            "r0_r1": False,
            "r1_shift": False,
            "r3_repack": False,
            "r4_repair": False,
            "r2_slab": False,
            # 仅 prefer_stack 等基础，专找柜数下界
        }
        # 从 hard_lb 扫到 used0，找轻量最小可装
        light_best = None
        light_lo = max(hard_lb0, used0 - 10)
        for n in range(light_lo, used0 + 1):
            lp = pack_boxes_api(
                boxes,
                container_type=container_type,
                max_containers=n,
                priority_order=priority_order,
                packing_options=light_opts,
            )
            lu = int(lp.get("containers_used") or 0)
            tried.append(
                {
                    "n": n,
                    "can_fit": lp.get("can_fit"),
                    "used": lu,
                    "unpacked": len(lp.get("unpacked_box_ids") or []),
                    "light_density": True,
                }
            )
            if lp.get("can_fit") and lu > 0 and lu <= n:
                light_best = lp
                break
        if light_best is not None:
            lu = int(light_best.get("containers_used") or 0)
            light_best["density_mode"] = "min_bins_light"
            light_best["reference_only"] = True  # 禁止单独 ship
            last["reference_light_used"] = lu
            last["reference_light_plan"] = {
                "used": lu,
                "weight_utilization": light_best.get("weight_utilization"),
                "mid50": _plan_worst_mid50(light_best),
                "reference_only": True,
                "strategy_id": "min_bins_light",
            }
            if lu < used0:
                # CoG-aware：从 light 下界扫到 used0+2，Tool 对齐 opts、无 priority，少柜+mid≥0.55
                full_mid_ok = None
                full_any = None
                scan_hi = min(n_max, max(used0, lu + 3))
                tight_opts = {
                    "prefer_stack": True,
                    "multi_start": True,
                    "cog_aware": True,
                    "cog_rebalance": True,
                    "r4_repair": True,
                    "r4_target_mid50": 0.60,
                    "r0_r1": True,
                    "r2_slab": True,
                    "lateral_repair": True,  # 必须开：否则左右偏心 block
                    "clearance_mm": int((packing_options or {}).get("clearance_mm") or 30),
                    "lns_worst": False,
                    "r3_repack": False,
                }
                drop_p = bool((packing_options or {}).get("drop_load_priority", True))
                prio_use = None if drop_p else priority_order
                for n in range(lu, scan_hi + 1):
                    full_n = pack_boxes_api(
                        boxes,
                        container_type=container_type,
                        max_containers=n,
                        priority_order=prio_use,
                        packing_options=tight_opts,
                    )
                    fu = int(full_n.get("containers_used") or 0)
                    mid = _plan_worst_mid50(full_n)
                    tried.append(
                        {
                            "n": n,
                            "can_fit": full_n.get("can_fit"),
                            "used": fu,
                            "unpacked": len(full_n.get("unpacked_box_ids") or []),
                            "full_on_light_lb": True,
                            "mid50": mid,
                            "tight_no_prio": prio_use is None,
                        }
                    )
                    if not (full_n.get("can_fit") and fu > 0 and fu <= n):
                        continue
                    if full_any is None:
                        full_any = full_n
                    if mid is not None and mid + 1e-9 >= 0.55:
                        full_mid_ok = full_n
                        full_mid_ok["density_mode"] = (
                            "tight_budget_cog" if n <= lu + 3 else "balance_cog"
                        )
                        break  # 最少柜且 mid≥55%
                if full_mid_ok is not None:
                    last = full_mid_ok
                    used0 = int(last.get("containers_used") or 0)
                    # 紧预算命中后：同 N 或 +1 柜内再修 lateral（完整 opts）
                    try:
                        fu0 = int(last.get("containers_used") or used0)

                        def _lat(p: Dict[str, Any]) -> float:
                            c = p.get("cog") or {}
                            if isinstance(c, dict) and c.get("primary"):
                                c = c["primary"]
                            try:
                                return float(c.get("lateral_eccentricity") or 0)
                            except (TypeError, ValueError):
                                return 0.0

                        polish_opts = dict(packing_options or {})
                        polish_opts["lateral_repair"] = True
                        polish_opts["cog_rebalance"] = True
                        polish_opts["drop_load_priority"] = True
                        best_p = last
                        best_lat = _lat(last)
                        for n_pol in range(fu0, min(fu0 + 2, n_max) + 1):
                            polished = pack_boxes_api(
                                boxes,
                                container_type=container_type,
                                max_containers=n_pol,
                                priority_order=prio_use,
                                packing_options=polish_opts,
                            )
                            if not polished.get("can_fit"):
                                continue
                            pu = int(polished.get("containers_used") or 0)
                            if pu <= 0 or pu > n_pol:
                                continue
                            pm = _plan_worst_mid50(polished)
                            if pm is not None and pm + 1e-9 < 0.55:
                                continue
                            plat = _lat(polished)
                            # 优先 lat 合规，再少柜
                            if plat < best_lat - 0.02 or (
                                plat < 0.15 and best_lat >= 0.15
                            ) or (
                                plat < 0.15
                                and best_lat < 0.15
                                and pu < int(best_p.get("containers_used") or 99)
                            ):
                                best_p = polished
                                best_lat = plat
                            if plat < 0.10 and pu <= fu0:
                                break
                        if best_p is not last:
                            dm = last.get("density_mode")
                            last = best_p
                            last["density_mode"] = dm or "tight_budget_cog"
                            last["tight_polished"] = True
                            used0 = int(last.get("containers_used") or used0)
                            tried.append(
                                {
                                    "n": used0,
                                    "can_fit": True,
                                    "used": used0,
                                    "polished_full_opts": True,
                                    "mid50": _plan_worst_mid50(last),
                                    "lat": best_lat,
                                }
                            )
                    except Exception:
                        pass
                elif full_any is not None:
                    last = full_any
                    last["density_mode"] = "balance_cog"
                    used0 = int(last.get("containers_used") or 0)
                else:
                    last["density_mode"] = last.get("density_mode") or "balance_cog"
                last["reference_light_used"] = lu
                last["reference_light_plan"] = {
                    "used": lu,
                    "weight_utilization": light_best.get("weight_utilization"),
                    "mid50": _plan_worst_mid50(light_best),
                    "reference_only": True,
                    "strategy_id": "min_bins_light",
                }

    # —— 收紧：宽松 max_c 下 used 偏松时，用 max_c=used 再装一回（逼近真占用）——
    used0 = int(last.get("containers_used") or 0)
    if last.get("can_fit") and used0 >= 2:
        # 找到本轮试装的 max_c（tried 最后成功项）
        last_try_n = None
        for t in reversed(tried):
            if t.get("can_fit") and not t.get("light_density"):
                last_try_n = int(t.get("n") or 0)
                break
        if last_try_n and used0 < last_try_n:
            tight = pack_boxes_api(
                boxes,
                container_type=container_type,
                max_containers=used0,
                priority_order=priority_order,
                packing_options=packing_options,
            )
            t_used = int(tight.get("containers_used") or 0)
            if tight.get("can_fit") and t_used > 0 and t_used <= used0:
                last = tight
                tried.append(
                    {
                        "n": used0,
                        "can_fit": True,
                        "used": t_used,
                        "unpacked": 0,
                        "tighten": True,
                    }
                )

    # —— 多轮末柜并回：残料柜过稀 → 连续试 used-1 … 直至失败或达重量/搜索下界 ——
    merged_attempt = False
    merged_ok = False
    merge_rounds = 0
    residual = False
    last_stats = _last_container_stats(last)
    used = int(last.get("containers_used") or 0)
    comps = booking.get("n0_components") or {}
    # hard_lb：重量/体积硬下界；soft_lb：含底面（常偏紧，可尝试压到 hard_lb 以抬重量利用率）
    hard_lb = max(
        1,
        int(comps.get("weight") or 0),
        int(comps.get("volume") or 0),
    )
    soft_lb = max(hard_lb, int(comps.get("geom_floor") or 0))
    floor_lb = hard_lb  # 并回目标可压到重量/体积下界
    # 大票多并几轮；小票最多 4 轮
    max_merge_rounds = 10 if used >= 10 else 4
    if last.get("can_fit") and used >= 2:
        # 即使末柜不极空，若 used 明显高于重量下界也尝试并回（抬重量利用率）
        wt_util_est = 0.0
        try:
            total_w = sum(float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0) for b in boxes)
            # 40HQ ~28600 payload 粗算
            payload = float(booking.get("payload_kg") or booking.get("max_load_kg") or 28600)
            if used > 0 and payload > 0:
                wt_util_est = total_w / (payload * used)
        except Exception:
            wt_util_est = 0.0
        want_merge = _is_residual_last(last_stats, used) or (
            used > hard_lb and wt_util_est < 0.72 and used >= 4
        )
        residual = _is_residual_last(last_stats, used)
        while want_merge and used > floor_lb and merge_rounds < max_merge_rounds:
            merged_attempt = True
            target_n = used - 1
            trial = pack_boxes_api(
                boxes,
                container_type=container_type,
                max_containers=target_n,
                priority_order=priority_order,
                packing_options=packing_options,
            )
            trial_used = int(trial.get("containers_used") or 0)
            trial_fit = bool(trial.get("can_fit")) and trial_used > 0
            # 真正并回：used 必须严格下降且 ≤ 目标柜数（防 engine 报 can_fit 但仍用 used 柜）
            improved = trial_fit and trial_used < used and trial_used <= target_n
            tried.append(
                {
                    "n": target_n,
                    "can_fit": trial.get("can_fit"),
                    "used": trial_used,
                    "unpacked": len(trial.get("unpacked_box_ids") or []),
                    "merge_back": True,
                    "round": merge_rounds + 1,
                    "accepted": improved,
                }
            )
            merge_rounds += 1
            if improved:
                last = trial
                merged_ok = True
                used = trial_used
                last_stats = _last_container_stats(last)
                residual = _is_residual_last(last_stats, used)
                # 继续并回若仍残或重量利用率仍偏低
                try:
                    total_w = sum(
                        float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0)
                        for b in boxes
                    )
                    payload = float(
                        booking.get("payload_kg") or booking.get("max_load_kg") or 28600
                    )
                    wt_util_est = total_w / (payload * used) if used and payload else 0.0
                except Exception:
                    wt_util_est = 0.0
                want_merge = residual or (
                    used > hard_lb and wt_util_est < 0.72 and used >= 4
                )
            else:
                # 并回失败：保留 residual 标记
                residual = residual or _is_residual_last(last_stats, used)
                break

    n0_report = int(booking.get("n0") or n0_star or start)
    last["booking"] = booking
    last["n0"] = n0_report
    last["n0_star"] = n0_report
    last["n0_search"] = start
    last["n0_components"] = booking.get("n0_components") or {}
    last["n0_note"] = booking.get("n0_note") or f"N0*={n0_report}"
    last["n_tried"] = tried
    last["auto_containers"] = True
    last["n0_gap"] = int(used) - int(n0_report) if used else 0
    last["last_container_stats"] = last_stats
    last["merged_attempt"] = merged_attempt
    last["merged_ok"] = merged_ok
    last["merge_rounds"] = merge_rounds
    last["residual_last_container"] = residual and not (
        merged_ok and not _is_residual_last(last_stats, used)
    )
    # 订柜体积利用率（有效体积 / (用柜×可用容积)）
    used_u = int(last.get("containers_used") or 0) or start
    usable = float(booking.get("usable_m3_per_container") or 1) * used_u
    v_eff = float(booking.get("volume_m3") or 0)
    last["booking_volume_utilization"] = (
        round(min(v_eff / usable, 9.99), 4) if usable > 0 else 0.0
    )
    last["outer_space_utilization"] = last.get("space_utilization")
    # 可解释一行
    gap = last["n0_gap"]
    gap_txt = f"+{gap}" if gap > 0 else ("0" if gap == 0 else str(gap))
    merge_txt = ""
    if merged_ok:
        merge_txt = f"; 末柜并回成功×{merge_rounds}" if merge_rounds else "; 末柜并回成功"
    elif residual:
        merge_txt = "; 末柜偏空(未并回)"
    elif merged_attempt:
        merge_txt = "; 并回尝试未成"
    # —— soft_budget 压柜：在 light..soft 内找 mid50≥目标 的最少 full 方案 ——
    opts_pb = dict(packing_options or {})
    ref_light_u = int(last.get("reference_light_used") or 0)
    used_now = int(last.get("containers_used") or 0)
    soft_cap = int(
        opts_pb.get("container_budget_soft")
        or opts_pb.get("soft_budget")
        or 0
    )
    mid_tgt = float(opts_pb.get("soft_budget_mid50") or 0.60)
    # 大票默认：若 used 明显高于 light，在 light..min(used, light+4) 内压柜
    cur_mid0 = _plan_worst_mid50(last)
    # 只要 used > light 就扫 soft 带压柜（即使 mid 已够，也尝试更少柜）
    need_densify = (
        used_now >= 8
        and ref_light_u > 0
        and ref_light_u < used_now
        and not opts_pb.get("disable_soft_budget_densify")
    )
    if need_densify:
        # 允许略高于当前 used（最多 light+3）去换 mid50≥目标，勿被 used_now 卡住
        default_hi = max(used_now, ref_light_u + 3)
        hi = soft_cap if soft_cap >= ref_light_u else default_hi
        hi = min(max(hi, ref_light_u), ref_light_u + 4, n_max)
        densify_pick = None  # 首个 can_fit
        best_ge55 = None  # mid≥0.55 最少柜
        best_ge60 = None  # mid≥目标 最少柜
        best_mid_plan = None  # 区间内 mid 最高
        best_mid_val = -1.0
        # 压柜对齐 Tool：无 priority + 轻量 opts（避免 lns/lateral 把 mid 打乱）
        densify_prio = None if opts_pb.get("drop_load_priority", True) else priority_order
        densify_opts = {
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r4_repair": True,
            "r4_target_mid50": mid_tgt,
            "r0_r1": True,
            "r2_slab": True,
            "lateral_repair": True,
            "clearance_mm": int(opts_pb.get("clearance_mm") or 30),
            "support_ratio_min": float(opts_pb.get("support_ratio_min") or 0.55),
            "max_stack_layers": int(opts_pb.get("max_stack_layers") or 3),
            "prefer_bottom_weight_kg": float(opts_pb.get("prefer_bottom_weight_kg") or 2000),
            "lns_worst": False,
            "r3_repack": False,
        }
        for n in range(ref_light_u, hi + 1):
            full_n = pack_boxes_api(
                boxes,
                container_type=container_type,
                max_containers=n,
                priority_order=densify_prio,
                packing_options=densify_opts,
            )
            fu = int(full_n.get("containers_used") or 0)
            mid = _plan_worst_mid50(full_n)
            tried.append(
                {
                    "n": n,
                    "can_fit": full_n.get("can_fit"),
                    "used": fu,
                    "unpacked": len(full_n.get("unpacked_box_ids") or []),
                    "soft_budget_densify": True,
                    "mid50": mid,
                    "densify_no_prio": densify_prio is None,
                }
            )
            if not (full_n.get("can_fit") and fu > 0 and fu <= n):
                continue
            if densify_pick is None:
                densify_pick = full_n
            if mid is not None and mid > best_mid_val:
                best_mid_val = mid
                best_mid_plan = full_n
            if mid is not None and mid + 1e-9 >= 0.55 and best_ge55 is None:
                best_ge55 = full_n
                best_ge55["density_mode"] = (
                    "soft_budget_cog"
                    if mid + 1e-9 >= mid_tgt
                    else "soft_budget_cog_soft"
                )
            if mid is not None and mid + 1e-9 >= mid_tgt and best_ge60 is None:
                best_ge60 = full_n
                best_ge60["density_mode"] = "soft_budget_cog"
            # 少柜优先：一旦有 mid≥55% 的方案且 n 已到 light+1，不再为 60% 加柜
            if best_ge55 is not None and n >= ref_light_u + 1:
                break
        # 关键：少柜优先 — mid≥55% 的最小 n，不要被更高 mid 的更多柜覆盖
        pick = best_ge55 or best_ge60 or densify_pick
        if pick is not None:
            pu = int(pick.get("containers_used") or 0)
            cur_u = int(last.get("containers_used") or 0)
            cur_mid = _plan_worst_mid50(last)
            pick_mid = _plan_worst_mid50(pick)
            if pick.get("density_mode") in (None, "balance_cog") and pick_mid is not None:
                if pick_mid + 1e-9 >= mid_tgt:
                    pick["density_mode"] = "soft_budget_cog"
                elif pick_mid >= 0.55:
                    pick["density_mode"] = "soft_budget_cog_soft"
            # 更少柜 / mid 达目标 / mid 提升且柜数不增太多
            better = pu < cur_u and (
                pick_mid is None
                or pick_mid >= 0.55
                or (cur_mid is not None and pick_mid >= (cur_mid or 0) - 0.02)
            )
            mid_win = (
                pick_mid is not None
                and pick_mid + 1e-9 >= mid_tgt
                and pu <= cur_u + 2
            )
            soft_ok = (
                pick_mid is not None
                and pick_mid >= 0.55
                and pu <= cur_u + 1
            )
            mid_improve = (
                pick_mid is not None
                and cur_mid is not None
                and pick_mid > cur_mid + 0.02
                and pu <= cur_u + 2
            )
            if better or mid_win or soft_ok or mid_improve:
                # 保留 booking / n0 元数据
                keep = {
                    k: last.get(k)
                    for k in (
                        "booking",
                        "n0",
                        "n0_star",
                        "n0_search",
                        "n0_components",
                        "n0_note",
                        "reference_light_plan",
                        "reference_light_used",
                    )
                    if last.get(k) is not None
                }
                last = {**pick, **{k: v for k, v in keep.items() if v is not None}}
                last["reference_light_used"] = ref_light_u
                last["soft_budget_applied"] = True
                last["soft_budget_hi"] = hi

    # —— 策略决策卡（Agent 可审计）：light 仅参考，ship 用 full/CoG 路径 ——
    candidates: List[Dict[str, Any]] = []
    ref = last.get("reference_light_plan")
    if isinstance(ref, dict) and ref.get("used"):
        candidates.append(
            {
                "strategy_id": "min_bins_light",
                "used": int(ref.get("used") or 0),
                "weight_utilization": ref.get("weight_utilization"),
                "mid50": ref.get("mid50"),
                "can_fit": True,
                "reference_only": True,
                "ship_ok_hint": False,
                "density_mode": "min_bins_light",
                "note": "柜数下界参考，不可单独出运（CoG 未保证）",
            }
        )
    ship_id = str(last.get("density_mode") or "balance_cog")
    if ship_id in ("min_bins_light", "light_lb_fallback"):
        # 硬禁止 light ship：若误标则改名
        ship_id = "balance_cog"
        last["density_mode"] = ship_id
        last["reference_only"] = False
    candidates.append(
        _candidate_row(
            ship_id,
            last,
            reference_only=False,
            note="完整/紧预算 CoG 路径（默认出运候选）",
        )
    )
    # 去重 strategy_id
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for c in candidates:
        sid = c.get("strategy_id")
        if sid in seen:
            continue
        seen.add(sid)
        uniq.append(c)
    decision = select_packing_strategy(uniq)
    # 若选中的是当前 last，附决策；若选中 light 参考则仍强制用 ship 行
    chosen_id = decision.get("chosen")
    if chosen_id == "min_bins_light" and ship_id != "min_bins_light":
        decision["chosen"] = ship_id
        decision["reason"] = (
            (decision.get("reason") or "")
            + "；覆盖：禁止 light 参考作为出运策略，改用 "
            + ship_id
        )
        for c in uniq:
            if c.get("strategy_id") == ship_id:
                decision["chosen_row"] = c
                break
    last["strategy_decision"] = decision
    last["strategy_candidates"] = uniq
    last["worst_mid50"] = _plan_worst_mid50(last)

    strat_txt = ""
    if decision.get("chosen"):
        strat_txt = f"; 策略={decision.get('chosen')}"
    last["multi_container_explain"] = (
        f"{last.get('n0_note')}; 3D实装={used_u}（相对N0* {gap_txt}）"
        + merge_txt
        + strat_txt
    )
    if decision.get("reason"):
        last["strategy_reason"] = decision.get("reason")
    return last
