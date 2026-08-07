"""Team B 有界辩论：critic ↔ planner 1～2 轮，tools 仍裁决 xyz/柜数。

默认开启（packing_options.bounded_debate=false 关闭）。
确定性协议、几乎零 LLM 成本；对 raise_bins vs densify 做冲突消解。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

# 辩论回合：1 critic+planner；2 再加 critic 收口
MAX_DEBATE_ROUNDS = 2

# critic 若提加柜、planner 改 densify 时，从最终 delta 剔除的键
_RAISE_BINS_KEYS: Set[str] = {
    "container_budget_soft",  # may re-set by densify path
}


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _plan_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = state.get("container_plan") or {}
    cog = plan.get("cog") or {}
    if isinstance(cog, dict) and cog.get("primary"):
        cog = cog["primary"]
    mid = plan.get("worst_mid50")
    if mid is None and isinstance(plan.get("cog_bundle"), dict):
        mid = plan["cog_bundle"].get("worst_mid50")
    if mid is None and isinstance(cog, dict):
        mid = cog.get("mass_in_mid50_ratio")
    return {
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0"),
        "worst_mid50": _f(mid),
        "reference_light_used": plan.get("reference_light_used"),
        "balance": (cog or {}).get("balance") if isinstance(cog, dict) else None,
        "ship_ok": state.get("ship_ok"),
        "unpacked": bool(plan.get("unpacked_box_ids")),
    }


def planner_counter_proposal(
    state: Dict[str, Any],
    critic_prop: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Planner 确定性反方。
    stance: accept | modify | reject_soft
    """
    snap = _plan_snapshot(state)
    delta = dict(critic_prop.get("packing_options_delta") or {})
    route = str(critic_prop.get("route") or "planner")
    mid = snap.get("worst_mid50")
    used = int(snap.get("containers_used") or 0)
    ref = int(snap.get("reference_light_used") or 0)
    can_fit = snap.get("can_fit")
    strat = str(delta.get("strategy_request") or "")
    bal = str(snap.get("balance") or "")

    stance = "accept"
    planner_reasons: List[str] = []
    pdelta: Dict[str, Any] = {}
    drop_keys: List[str] = []

    # box_scheme：成箱优先，planner 不挡
    if route == "box_scheme":
        return {
            "stance": "accept",
            "reasons": ["planner：成箱路径由 critic 主导，planner 附议"],
            "packing_options_delta": {},
            "drop_keys": [],
            "accept_route": "box_scheme",
            "note": "box_scheme accept",
            "snapshot": snap,
        }

    # 未装下 / 有 unpacked：接受密装加柜
    if can_fit is False or snap.get("unpacked"):
        stance = "accept"
        pdelta["prefer_stack"] = True
        pdelta["multi_start"] = True
        pdelta["dense_mode"] = True
        planner_reasons.append("planner：can_fit=False/有未装件 → 接受密装+multi_start")

    # mid 过低：接受 + 强化 R4
    elif mid is not None and mid < 0.55:
        stance = "accept"
        pdelta["cog_rebalance"] = True
        pdelta["r4_repair"] = True
        pdelta["r4_target_mid50"] = max(0.60, float(delta.get("r4_target_mid50") or 0.60))
        pdelta["multi_start"] = True
        pdelta["lns_worst"] = True
        planner_reasons.append(
            f"planner：mid50={mid:.0%}<55%，接受 critic 并强化 r4/lns"
        )

    # 已能装 + mid 尚可 + critic 想加柜 → 改 densify（核心优化）
    elif (
        can_fit is True
        and mid is not None
        and mid >= 0.55
        and ("raise_bins" in strat or delta.get("container_budget_soft") is not None)
        and used > 0
        and (ref <= 0 or used <= ref + 4)
    ):
        # 若 used 已远大于 light，下面 densify 分支更合适；此处防无脑抬柜
        if "raise_bins" in strat or (
            isinstance(delta.get("container_budget_soft"), (int, float))
            and int(delta["container_budget_soft"]) > used
        ):
            stance = "modify"
            pdelta["strategy_request"] = "densify_soft_budget_cog"
            pdelta["cog_rebalance"] = True
            pdelta["multi_start"] = True
            pdelta["prefer_stack"] = True
            pdelta["r4_repair"] = True
            pdelta["r4_target_mid50"] = 0.60
            if ref > 0:
                pdelta["container_budget_soft"] = max(ref, min(used, ref + 2))
            else:
                pdelta["container_budget_soft"] = used  # 锁当前柜数 densify
            drop_keys.append("strategy_request_raise")  # marker
            planner_reasons.append(
                f"planner：can_fit 且 mid50={mid:.0%}≥55%，反对 raise_bins → densify 锁柜"
            )

    # mid 55–60% 薄缓冲：不抬柜，压 densify + r4
    elif can_fit is True and mid is not None and 0.55 <= mid < 0.60:
        stance = "modify"
        pdelta["strategy_request"] = "densify_soft_budget_cog"
        pdelta["cog_rebalance"] = True
        pdelta["r4_repair"] = True
        pdelta["r4_target_mid50"] = 0.62
        pdelta["multi_start"] = True
        pdelta["prefer_stack"] = True
        if ref > 0:
            pdelta["container_budget_soft"] = max(ref, min(used, ref + 2))
        else:
            pdelta["container_budget_soft"] = used
        planner_reasons.append(
            f"planner：mid50={mid:.0%} 薄缓冲(55–60%) → densify+r4，禁止抬柜空转"
        )

    # 柜数虚高
    elif can_fit is True and ref > 0 and used > ref + 2:
        stance = "modify"
        pdelta["strategy_request"] = "densify_soft_budget_cog"
        pdelta["container_budget_soft"] = min(used, ref + 3)
        pdelta["_soft_budget_densify_done"] = True
        pdelta["cog_rebalance"] = True
        pdelta["multi_start"] = True
        planner_reasons.append(
            f"planner：used={used}>light+2({ref}) → soft_budget densify"
        )

    # balance block：接受再平衡
    elif bal == "block":
        stance = "accept"
        pdelta["cog_rebalance"] = True
        pdelta["r4_repair"] = True
        pdelta["multi_start"] = True
        planner_reasons.append("planner：balance=block，接受 CoG 再平衡")

    else:
        stance = "accept"
        planner_reasons.append("planner：无强反方意见，采纳 critic 提案")

    accept_route = route if stance != "reject_soft" else "planner"
    return {
        "stance": stance,
        "reasons": planner_reasons,
        "packing_options_delta": pdelta,
        "drop_keys": drop_keys,
        "accept_route": accept_route,
        "note": "；".join(planner_reasons),
        "snapshot": snap,
    }


def _merge_delta(
    critic_delta: Dict[str, Any],
    planner_delta: Dict[str, Any],
    *,
    stance: str,
    drop_raise: bool,
) -> Dict[str, Any]:
    """冲突消解：planner modify 时 densify 覆盖 raise_bins。"""
    out = dict(critic_delta or {})
    if drop_raise or (
        stance == "modify"
        and "densify" in str((planner_delta or {}).get("strategy_request") or "")
    ):
        # 去掉抬柜倾向
        if str(out.get("strategy_request") or "").find("raise_bins") >= 0:
            out.pop("strategy_request", None)
        # 若 planner 给出 budget，覆盖更大的 soft budget
        p_soft = (planner_delta or {}).get("container_budget_soft")
        c_soft = out.get("container_budget_soft")
        if p_soft is not None and c_soft is not None:
            try:
                if int(c_soft) > int(p_soft):
                    out["container_budget_soft"] = int(p_soft)
            except (TypeError, ValueError):
                pass
    out.update(planner_delta or {})
    return out


def run_bounded_debate(
    state: Dict[str, Any],
    *,
    max_rounds: int = MAX_DEBATE_ROUNDS,
) -> Dict[str, Any]:
    """
    有界辩论 → merge state 片段。
    tools 仍在外环 planner/loader 重跑。
    """
    opts = dict(state.get("packing_options") or {})
    if opts.get("bounded_debate") is False:
        from packing_assistant.agents.replan_critic import agent_replan_critic

        return agent_replan_critic(state) or {}

    max_rounds = max(1, min(int(max_rounds or MAX_DEBATE_ROUNDS), 2))
    # 允许 packing_options.bounded_debate_rounds 覆盖
    try:
        if opts.get("bounded_debate_rounds") is not None:
            max_rounds = max(1, min(int(opts["bounded_debate_rounds"]), 2))
    except (TypeError, ValueError):
        pass

    transcript: List[Dict[str, Any]] = []
    hist = list(state.get("bounded_debate_history") or [])

    from packing_assistant.agents.replan_critic import agent_replan_critic

    crit_upd = agent_replan_critic(state) or {}
    prop = dict(crit_upd.get("replan_proposal") or {})
    transcript.append(
        {
            "turn": 1,
            "speaker": "replan_critic",
            "role": "critic",
            "route": prop.get("route"),
            "stance": "propose",
            "reasons": list(prop.get("reasons") or [])[:6],
            "delta_keys": list((prop.get("packing_options_delta") or {}).keys())[:12],
            "strategy": (prop.get("packing_options_delta") or {}).get("strategy_request"),
            "stop": bool(prop.get("stop")),
        }
    )

    if prop.get("stop"):
        debate = {
            "schema": "bounded_debate.v1",
            "enabled": True,
            "rounds": 1,
            "max_rounds": max_rounds,
            "closed": True,
            "outcome": "critic_stop",
            "transcript": transcript,
            "tools_adjudicate": True,
            "improved": False,
            "note": "critic 判定停止自动重排；tools 不重跑",
        }
        hist.append({"outcome": "critic_stop", "rounds": 1})
        crit_upd["bounded_debate"] = debate
        crit_upd["bounded_debate_history"] = hist[-5:]
        return crit_upd

    preply = planner_counter_proposal(state, prop)
    drop_raise = bool(preply.get("drop_keys")) or (
        preply.get("stance") == "modify"
        and "densify" in str((preply.get("packing_options_delta") or {}).get("strategy_request") or "")
    )
    transcript.append(
        {
            "turn": 2,
            "speaker": "planner",
            "role": "planner",
            "stance": preply.get("stance"),
            "reasons": list(preply.get("reasons") or [])[:6],
            "delta_keys": list((preply.get("packing_options_delta") or {}).keys())[:12],
            "strategy": (preply.get("packing_options_delta") or {}).get("strategy_request"),
            "accept_route": preply.get("accept_route"),
            "snapshot": preply.get("snapshot"),
        }
    )

    final_delta = _merge_delta(
        prop.get("packing_options_delta") or {},
        preply.get("packing_options_delta") or {},
        stance=str(preply.get("stance") or "accept"),
        drop_raise=drop_raise,
    )
    final_route = str(preply.get("accept_route") or prop.get("route") or "planner")
    outcome = f"planner_{preply.get('stance')}"
    improved = preply.get("stance") == "modify"

    if max_rounds >= 2 and preply.get("stance") == "modify":
        final_delta["bounded_debate_closed"] = True
        transcript.append(
            {
                "turn": 3,
                "speaker": "replan_critic",
                "role": "critic",
                "stance": "close",
                "reasons": [
                    "critic 收口：采纳 planner densify/再平衡，放弃无脑抬柜",
                    f"route={final_route}",
                    f"strategy={final_delta.get('strategy_request')}",
                ],
                "delta_keys": list(final_delta.keys())[:12],
                "strategy": final_delta.get("strategy_request"),
            }
        )
        outcome = "critic_close_after_modify"
        improved = True
    else:
        final_delta["bounded_debate_closed"] = True

    base_opts = dict(crit_upd.get("packing_options") or state.get("packing_options") or {})
    # 最终 options：critic 的 packing_options 再盖 final_delta
    new_opts = {**base_opts, **final_delta}
    # 若 planner 反抬柜，确保 strategy 不是 raise
    if drop_raise and "raise_bins" in str(new_opts.get("strategy_request") or ""):
        new_opts["strategy_request"] = "densify_soft_budget_cog"

    prop_out = dict(prop)
    prop_out["packing_options_delta"] = final_delta
    prop_out["packing_options_next"] = new_opts
    prop_out["route"] = final_route
    prop_out["bounded_debate"] = True
    prop_out["debate_outcome"] = outcome
    reasons = list(prop.get("reasons") or [])
    reasons.extend(list(preply.get("reasons") or []))
    prop_out["reasons"] = reasons[:10]
    prop_out["route_reason"] = reasons[0] if reasons else prop_out.get("route_reason")

    debate = {
        "schema": "bounded_debate.v1",
        "enabled": True,
        "rounds": len(transcript),
        "max_rounds": max_rounds,
        "closed": True,
        "outcome": outcome,
        "improved": improved,
        "transcript": transcript,
        "tools_adjudicate": True,
        "final_strategy": new_opts.get("strategy_request"),
        "final_route": final_route,
        "note": (
            "有界辩论结束：只改 packing_options；"
            "柜数/xyz/CoG 由后续 tools（planner/loader）裁决"
        ),
    }
    hist.append(
        {
            "outcome": outcome,
            "rounds": len(transcript),
            "improved": improved,
            "strategy": new_opts.get("strategy_request"),
        }
    )

    out = dict(crit_upd)
    out["packing_options"] = new_opts
    out["replan_proposal"] = prop_out
    out["bounded_debate"] = debate
    out["bounded_debate_history"] = hist[-5:]
    if final_route and "max_containers" in crit_upd:
        # densify 路径：不因 critic 抬柜而抬 max_containers
        if drop_raise and preply.get("snapshot", {}).get("containers_used"):
            try:
                u = int(preply["snapshot"]["containers_used"])
                if int(out.get("max_containers") or 0) > u + 1:
                    out["max_containers"] = max(u, int(new_opts.get("container_budget_soft") or u))
            except (TypeError, ValueError, KeyError):
                pass

    msgs = list(out.get("messages") or [])
    msgs.append(
        {
            "role": "assistant",
            "content": (
                f"【bounded_debate】{outcome} · turns={len(transcript)} · "
                f"route={final_route} · strategy={new_opts.get('strategy_request')} · "
                f"improved={improved} · tools 将重跑装载"
            ),
            "agent": "bounded_debate",
        }
    )
    out["messages"] = msgs
    meta = dict(out.get("agent_meta") or {})
    meta["bounded_debate"] = True
    meta["tools_used"] = list(meta.get("tools_used") or []) + [
        "bounded_debate.critic_planner"
    ]
    out["agent_meta"] = meta
    return out


def debate_public_summary(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """对外摘要。"""
    st = state or {}
    d = st.get("bounded_debate")
    if not isinstance(d, dict) or not d.get("enabled"):
        return {}
    return {
        "schema": d.get("schema") or "bounded_debate.v1",
        "rounds": d.get("rounds"),
        "outcome": d.get("outcome"),
        "improved": d.get("improved"),
        "final_strategy": d.get("final_strategy"),
        "final_route": d.get("final_route"),
        "tools_adjudicate": True,
        "transcript": (d.get("transcript") or [])[:6],
        "history_n": len(st.get("bounded_debate_history") or []),
        "note": d.get("note"),
    }
