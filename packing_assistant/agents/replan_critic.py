"""有界 replan critic：单 Team 闭环内打回重排。

只改 packing_options / max_containers / 路由目标，不改 3D 坐标。
产品口径：1 个 Team 有界闭环（内环≤3 · 出运外环≤2），无「跨团队」语义。
路由：
  - box_scheme：结构不通过 → 同 Team 内重做成箱
  - planner：装不下 / CoG / 空隙 → 同 Team 内重跑规划+3D
  - stop：达上限或不可自动修复
"""

from __future__ import annotations

from typing import Any, Dict, List

MAX_REPLAN_ROUNDS = 3  # loader 环
MAX_SHIP_REPLAN = 2  # 出运打回外环


def agent_replan_critic(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据 evaluation / risk / packing_plan 提出下一轮策略。
    返回 replan_proposal: {stop, route, reasons, packing_options_delta, max_containers}
    """
    evaluation = state.get("evaluation") or {}
    risk = state.get("risk_report") or {}
    plan = state.get("container_plan") or {}
    opts = dict(state.get("packing_options") or {})
    round_ = int(state.get("replan_round") or 0)
    ship_r = int(state.get("ship_replan_round") or 0)
    pp = state.get("packing_plan") or {}

    reasons: List[str] = []
    delta: Dict[str, Any] = {}
    route = "planner"
    max_c = int(
        state.get("max_containers")
        or plan.get("containers_used")
        or plan.get("n0")
        or 8
    )
    max_c = max(max_c, int(plan.get("containers_used") or 1), int(plan.get("n0") or 1))

    # —— 达上限 ——
    if ship_r >= MAX_SHIP_REPLAN and round_ >= MAX_REPLAN_ROUNDS:
        return _stop(max_c, ["已达自动重排上限，请人工改箱/确认"])

    blockers = list(risk.get("blockers") or [])
    risk_dec = str(risk.get("decision") or "")
    reject_to = str(risk.get("reject_to") or "")
    struct_fail = list(evaluation.get("structure_fail_box_ids") or [])
    struct_txt = any("结构" in str(b) for b in blockers) or bool(struct_fail)

    cog = (pp.get("cog") if isinstance(pp, dict) else None) or plan.get("cog") or risk.get("cog") or {}
    if isinstance(cog, dict) and cog.get("primary"):
        cog = cog["primary"]
    mid50 = _f(cog.get("mass_in_mid50_ratio"))
    lat = _f(cog.get("lateral_eccentricity"))
    bal = str(cog.get("balance") or "")
    lq = plan.get("layout_quality") or risk.get("layout_quality") or {}

    need = bool(evaluation.get("need_replan")) or evaluation.get("decision") == "REPLAN"
    if risk_dec == "REJECT" or risk.get("need_revision") or risk.get("auto_replanable"):
        need = True
    if not plan.get("can_fit") or plan.get("unpacked_box_ids"):
        need = True

    if not need and not reasons:
        # 仍检查软问题
        if mid50 is not None and mid50 < 0.60:
            need = True
        if bal == "block":
            need = True
        # 半柜空洞：能装下但过空（与「上次只装半柜被批」同类）
        if plan.get("can_fit") and not opts.get("_hollow_densify_done"):
            ou = _f(plan.get("outer_space_utilization") or plan.get("space_utilization"))
            bu = _f(plan.get("booking_volume_utilization"))
            wu = _f(plan.get("weight_utilization"))
            if (
                ou is not None
                and bu is not None
                and wu is not None
                and ou < 0.30
                and bu < 0.25
                and wu < 0.45
                and ship_r < 1
            ):
                need = True

    if not need:
        return _stop(max_c, ["无需 replan"])

    # —— 结构：打回成箱 ——
    if struct_txt or reject_to == "box_scheme":
        route = "box_scheme"
        delta["dense_mode"] = True
        delta["standard_boxes"] = False
        delta["crate_passthrough"] = True
        delta["max_box_net_kg"] = max(float(opts.get("max_box_net_kg") or 2000), 5000)
        delta["prefer_stack"] = True
        reasons.append("结构/成箱阻断 → box_scheme(crate_passthrough+dense)")

    # —— 装不下：默认加柜；预算锁柜时只压外廓/叠高/再平衡 ——
    lock_max = bool(
        opts.get("lock_max_containers")
        or opts.get("fixed_container_budget")
        or opts.get("meeting_cap")
    )
    budget_cap = int(opts.get("container_budget") or state.get("max_containers") or 0)

    if not plan.get("can_fit") or plan.get("unpacked_box_ids"):
        route = "planner" if route != "box_scheme" else route
        delta["prefer_stack"] = True
        delta["multi_start"] = True
        delta["cog_aware"] = True
        delta["cog_rebalance"] = True
        if lock_max and budget_cap > 0:
            max_c = budget_cap
            delta["dense_mode"] = True
            delta["clearance_mm"] = max(15, int(opts.get("clearance_mm") or 30) - 10)
            delta["max_stack_layers"] = max(3, int(opts.get("max_stack_layers") or 3))
            reasons.append(
                f"未装下但 lock_max_containers → 锁 {max_c} 柜，密装/叠高/CoG 再平衡"
            )
        else:
            max_c = min(40, max(max_c + 1, int(plan.get("containers_used") or 0) + 1))
            reasons.append(f"未装下 → max_containers={max_c} + 叠高/multi_start")

    # —— CoG / 60/50：强制自动再平衡（保持全自动）——
    worst_mid = None
    try:
        plan_wm = plan.get("worst_mid50")
        if plan_wm is not None:
            worst_mid = float(plan_wm)
        elif mid50 is not None:
            worst_mid = mid50
    except Exception:
        worst_mid = mid50

    if worst_mid is not None and worst_mid < 0.60:
        if route != "box_scheme":
            route = "planner"
        delta["cog_aware"] = True
        delta["cog_rebalance"] = True  # try_place + multi_start 中段加重
        delta["multi_start"] = True
        delta["prefer_stack"] = True if worst_mid < 0.40 else bool(opts.get("prefer_stack", True))
        # 第二轮更激进：略减间隙，利于中段填实
        if ship_r >= 1 or worst_mid < 0.40:
            delta["clearance_mm"] = max(15, int(opts.get("clearance_mm") or 30) - 15)
        reasons.append(
            f"最差柜 mid50={worst_mid:.0%}<60% → 自动 cog_rebalance+multi_start"
        )

    if lat is not None and lat >= 0.10:
        if route != "box_scheme":
            route = "planner"
        delta["cog_aware"] = True
        delta["cog_rebalance"] = True
        delta["multi_start"] = True
        reasons.append(f"横向偏心 {lat:.0%} → 自动再平衡")

    if bal == "block" and route != "box_scheme":
        route = "planner"
        delta["cog_aware"] = True
        delta["cog_rebalance"] = True
        delta["multi_start"] = True
        reasons.append("重心 balance=block → 自动中段重排")

    # —— 可叠未叠 / 空隙 ——
    if lq.get("stackable_floor_only"):
        if route != "box_scheme":
            route = "planner"
        delta["prefer_stack"] = True
        delta["max_stack_layers"] = max(3, int(opts.get("max_stack_layers") or 3))
        reasons.append("可叠未叠 → prefer_stack")

    max_gap = _f(lq.get("max_horizontal_gap_mm"))
    if max_gap is not None and max_gap > 400:
        if route != "box_scheme":
            route = "planner"
        delta["prefer_stack"] = True
        delta["multi_start"] = True
        reasons.append(f"水平空隙 {max_gap:.0f}mm → multi_start 紧凑")

    # —— 能装下但过空（半柜被批）：软 densify 一轮，不改柜数 ——
    # 触发：can_fit 且 外廓<30% 且 订舱体积<25% 且 重量<45%，且未做过 hollow densify
    outer_u = _f(plan.get("outer_space_utilization") or plan.get("space_utilization"))
    book_u = _f(plan.get("booking_volume_utilization"))
    wt_u = _f(plan.get("weight_utilization"))
    hollow_done = bool(opts.get("_hollow_densify_done"))
    if (
        plan.get("can_fit")
        and not hollow_done
        and ship_r < 1
        and outer_u is not None
        and book_u is not None
        and wt_u is not None
        and outer_u < 0.30
        and book_u < 0.25
        and wt_u < 0.45
    ):
        if route != "box_scheme":
            route = "planner"
        delta["prefer_stack"] = True
        delta["multi_start"] = True
        delta["cog_rebalance"] = True
        delta["dense_mode"] = True
        delta["clearance_mm"] = max(15, int(opts.get("clearance_mm") or 30) - 10)
        delta["max_stack_layers"] = max(3, int(opts.get("max_stack_layers") or 3))
        delta["_hollow_densify_done"] = True
        reasons.append(
            f"半柜空洞 outer={outer_u:.0%}/book={book_u:.0%}/wt={wt_u:.0%} "
            f"→ 软 densify+叠高一轮（锁柜）"
        )
        # 不为此加柜
        if lock_max and budget_cap > 0:
            max_c = budget_cap

    # 风险 REJECT 但无结构：默认 planner
    if risk_dec == "REJECT" and not struct_txt and route == "planner":
        delta["export_strict"] = False
        if "risk REJECT" not in " ".join(reasons):
            reasons.append("risk REJECT → planner 重排（关闭 export_strict）")

    if not reasons:
        reasons.append("通用重试")

    # 轮次上限：box_scheme 走 ship 轮；planner 走 replan 轮
    if route == "box_scheme" and ship_r >= MAX_SHIP_REPLAN:
        return _stop(max_c, reasons + ["box_scheme 重排已达上限"])
    if route == "planner" and round_ >= MAX_REPLAN_ROUNDS and ship_r >= MAX_SHIP_REPLAN:
        return _stop(max_c, reasons + ["planner 重排已达上限"])

    new_opts = {**opts, **delta}
    new_round = round_ + 1 if route == "planner" else round_
    new_ship = ship_r + 1 if route == "box_scheme" or risk_dec == "REJECT" else ship_r
    if route == "planner" and (risk_dec == "REJECT" or not plan.get("can_fit")):
        new_ship = ship_r + 1

    proposal = {
        "stop": False,
        "route": route,
        "reasons": reasons,
        "packing_options_delta": delta,
        "packing_options_next": new_opts,
        "max_containers": max_c,
        "round": new_round,
        "ship_replan_round": new_ship,
        "auto_closed_loop": True,
    }
    msg = f"route={route}；" + "；".join(reasons)
    return {
        "packing_options": new_opts,
        "max_containers": max_c,
        "replan_round": new_round,
        "ship_replan_round": new_ship,
        "replan_proposal": proposal,
        "phase": "team_b_running",
        "status": "running",
        "messages": [
            {
                "role": "assistant",
                "content": f"【replan_critic·单Team闭环】{msg}",
                "agent": "replan_critic",
            }
        ],
        "agent_meta": {
            "node": "replan_critic",
            "capability": ["规划", "使用工具", "追求目标"],
            "tools_used": ["replan_critic.closed_loop"],
            "team_mode": "single_closed_loop",
            "artifacts": proposal,
        },
    }


def apply_replan_if_needed(state: Dict[str, Any]) -> Dict[str, Any]:
    ev = state.get("evaluation") or {}
    risk = state.get("risk_report") or {}
    if not (
        ev.get("need_replan")
        or ev.get("decision") == "REPLAN"
        or risk.get("decision") == "REJECT"
        or risk.get("need_revision")
        or risk.get("auto_replanable")
    ):
        return {}
    return agent_replan_critic(state)


def _stop(max_c: int, reasons: List[str]) -> Dict[str, Any]:
    return {
        "replan_proposal": {
            "stop": True,
            "route": "stop",
            "reasons": reasons,
            "packing_options_delta": {},
            "max_containers": max_c,
            "auto_closed_loop": False,
        },
        "messages": [
            {
                "role": "assistant",
                "content": "【replan_critic】" + "；".join(reasons),
                "agent": "replan_critic",
            }
        ],
    }


def _f(v: Any) -> Any:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None
