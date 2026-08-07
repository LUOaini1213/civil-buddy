"""Team B 有界辩论：critic ↔ planner 1～2 轮，tools 仍裁决 xyz/柜数。

默认开启（可用 packing_options.bounded_debate=false 关闭）。
不调用 LLM 写坐标；planner 侧为确定性反方意见，最终仍走 replan→tools 重装。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

# 辩论回合上限：1 = critic 提案 + planner 回应；2 = 再加 critic 收口
MAX_DEBATE_ROUNDS = 2


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
    }


def planner_counter_proposal(
    state: Dict[str, Any],
    critic_prop: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Planner 确定性反方：基于当前装载快照，对 critic 提案表态。
    返回 {stance, reasons, packing_options_delta, accept_route, note}
    stance: accept | modify | reject_soft
    """
    snap = _plan_snapshot(state)
    delta = dict(critic_prop.get("packing_options_delta") or {})
    route = str(critic_prop.get("route") or "planner")
    reasons_c = list(critic_prop.get("reasons") or [])
    mid = snap.get("worst_mid50")
    used = int(snap.get("containers_used") or 0)
    ref = int(snap.get("reference_light_used") or 0)
    can_fit = snap.get("can_fit")
    strat = str(delta.get("strategy_request") or "")

    stance = "accept"
    planner_reasons: List[str] = []
    pdelta: Dict[str, Any] = {}

    # 已能装且 mid 尚可：反对无脑加柜
    if (
        can_fit is True
        and mid is not None
        and mid >= 0.55
        and "raise_bins" in strat
    ):
        stance = "modify"
        pdelta["strategy_request"] = "densify_soft_budget_cog"
        pdelta.pop("container_budget_soft", None)
        if ref > 0:
            pdelta["container_budget_soft"] = max(ref, min(used, ref + 2))
        pdelta["cog_rebalance"] = True
        pdelta["multi_start"] = True
        pdelta["prefer_stack"] = True
        # strip pure bin-raise hints if critic only wanted more cabins
        planner_reasons.append(
            f"planner：can_fit 且 mid50={mid:.0%}≥55%，反对 raise_bins → densify/再平衡"
        )

    # mid 过低：接受 critic，可再强调 rebalance
    elif mid is not None and mid < 0.55:
        stance = "accept"
        pdelta["cog_rebalance"] = True
        pdelta["r4_repair"] = True
        pdelta["multi_start"] = True
        planner_reasons.append(
            f"planner：mid50={mid:.0%}<55%，接受 critic 并强调 r4/multi_start"
        )

    # 未装下：接受加柜/密装
    elif can_fit is False:
        stance = "accept"
        pdelta["prefer_stack"] = True
        pdelta["multi_start"] = True
        planner_reasons.append("planner：can_fit=False，接受 critic 密装/加柜策略")

    # 柜数虚高：倾向 densify
    elif can_fit is True and ref > 0 and used > ref + 2:
        stance = "modify"
        pdelta["strategy_request"] = "densify_soft_budget_cog"
        pdelta["container_budget_soft"] = min(used, ref + 3)
        pdelta["_soft_budget_densify_done"] = True
        pdelta["cog_rebalance"] = True
        planner_reasons.append(
            f"planner：used={used}>light+2({ref}) → 压 soft_budget densify"
        )

    else:
        stance = "accept"
        planner_reasons.append("planner：无强反方意见，采纳 critic 提案")

    # box_scheme 路由一般不拦
    if route == "box_scheme":
        stance = "accept"
        planner_reasons = ["planner：成箱路径由 critic 主导，planner 附议"]

    accept_route = route if stance != "reject_soft" else "planner"
    note = "；".join(planner_reasons + reasons_c[:1])
    return {
        "stance": stance,
        "reasons": planner_reasons,
        "packing_options_delta": pdelta,
        "accept_route": accept_route,
        "note": note,
        "snapshot": snap,
    }


def _merge_delta(base: Dict[str, Any], *extras: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for d in extras:
        if not d:
            continue
        out.update(d)
    return out


def run_bounded_debate(
    state: Dict[str, Any],
    *,
    max_rounds: int = MAX_DEBATE_ROUNDS,
) -> Dict[str, Any]:
    """
    跑有界辩论并返回可 merge 的 state 片段（含 replan_proposal / packing_options）。

    流程：
      1) critic 提案（agent_replan_critic）
      2) planner 确定性反方
      3) 若 modify 且 rounds≥2：critic 收口合并 delta
      4) tools 仍在外环 planner/loader 重跑（本函数不写 xyz）
    """
    opts = dict(state.get("packing_options") or {})
    if opts.get("bounded_debate") is False:
        from packing_assistant.agents.replan_critic import agent_replan_critic

        return agent_replan_critic(state) or {}

    max_rounds = max(1, min(int(max_rounds or MAX_DEBATE_ROUNDS), 2))
    transcript: List[Dict[str, Any]] = []

    # —— Turn 1: Critic ——
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
            "stop": bool(prop.get("stop")),
        }
    )

    if prop.get("stop"):
        crit_upd["bounded_debate"] = {
            "schema": "bounded_debate.v1",
            "enabled": True,
            "rounds": 1,
            "max_rounds": max_rounds,
            "closed": True,
            "outcome": "critic_stop",
            "transcript": transcript,
            "tools_adjudicate": True,
            "note": "critic 判定停止自动重排；tools 不重跑",
        }
        return crit_upd

    # —— Turn 2: Planner ——
    preply = planner_counter_proposal(state, prop)
    transcript.append(
        {
            "turn": 2,
            "speaker": "planner",
            "role": "planner",
            "stance": preply.get("stance"),
            "reasons": list(preply.get("reasons") or [])[:6],
            "delta_keys": list((preply.get("packing_options_delta") or {}).keys())[:12],
            "accept_route": preply.get("accept_route"),
        }
    )

    final_delta = _merge_delta(
        prop.get("packing_options_delta") or {},
        preply.get("packing_options_delta") or {},
    )
    final_route = str(preply.get("accept_route") or prop.get("route") or "planner")
    outcome = f"planner_{preply.get('stance')}"

    # —— Turn 3 (optional): Critic 收口 ——
    if max_rounds >= 2 and preply.get("stance") == "modify":
        # critic soft close：接受 planner 修改，标记 debate_closed
        final_delta["bounded_debate_closed"] = True
        transcript.append(
            {
                "turn": 3,
                "speaker": "replan_critic",
                "role": "critic",
                "stance": "close",
                "reasons": [
                    "critic 收口：采纳 planner 修改后的 densify/再平衡取向",
                    f"route={final_route}",
                ],
                "delta_keys": list(final_delta.keys())[:12],
            }
        )
        outcome = "critic_close_after_modify"
    else:
        final_delta["bounded_debate_closed"] = True

    # 应用最终 options
    base_opts = dict(crit_upd.get("packing_options") or state.get("packing_options") or {})
    new_opts = {**base_opts, **final_delta}
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
        "transcript": transcript,
        "tools_adjudicate": True,
        "note": (
            "有界辩论结束：critic/planner 只改 packing_options；"
            "柜数/xyz/CoG 仍由后续 tools（planner/loader）裁决"
        ),
    }

    out = dict(crit_upd)
    out["packing_options"] = new_opts
    out["replan_proposal"] = prop_out
    out["bounded_debate"] = debate
    msgs = list(out.get("messages") or [])
    msgs.append(
        {
            "role": "assistant",
            "content": (
                f"【bounded_debate】{outcome} · turns={len(transcript)} · "
                f"route={final_route} · tools 将重跑装载"
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
    """对外摘要（public_response）。"""
    st = state or {}
    d = st.get("bounded_debate")
    if not isinstance(d, dict) or not d.get("enabled"):
        return {}
    return {
        "schema": d.get("schema") or "bounded_debate.v1",
        "rounds": d.get("rounds"),
        "outcome": d.get("outcome"),
        "tools_adjudicate": True,
        "transcript": (d.get("transcript") or [])[:6],
        "note": d.get("note"),
    }
