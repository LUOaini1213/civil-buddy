"""Workteam 路由 / 选工具 KPI。

从 PackingState / agent_steps / replan 事件抽取可聚合指标，
供影子评测、网关、CI 使用。
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Sequence


# LLM 调度白名单（agent_loop 可选手）
LLM_ALLOWED_TOOLS = {
    "intent.interpret",
    "container.select",
    "team_a.run",
    "team_a.rebox",
    "hitl.check",
    "hitl.confirm",
    "hitl.confirm_gate",
    "team_b.plan_load_eval",
    "team_b.risk",
    "team_b.visualize",
    "replan.critic",
    "replan_critic.closed_loop",
    "finalize.run",
    "container_select.recommend_container",
    "finish",
    "tms.booking",
    "kpi.extract",
}

# 确定性 tool 名前缀（steps 路径大量此类）
ALLOWED_TOOL_PREFIXES = (
    "intent.",
    "container",
    "team_a.",
    "team_b.",
    "hitl.",
    "replan.",
    "finalize.",
    "material",
    "structure",
    "box_scheme",
    "packing.",
    "knowledge.",
    "booking.",
    "volume",
    "bin3d.",
    "engine:",
    "evaluator.",
    "risk",
    "layout",
    "visualize.",
    "views.",
    "cog.",
    "load",
    "por.",
    "secure",
    "vgm.",
    "plan.",
    "export.",
    "tms.",
    "kpi.",
)

# 明确禁止（LLM 不得选）
DENIED_TOOL_PATTERNS = (
    "set_xyz",
    "write_coord",
    "forge_weight",
    "skip_risk",
    "force_ship_ok",
)

KNOWN_NODES = {
    "intent",
    "orchestrator",
    "material_parser",
    "structure",
    "box_scheme",
    "present_team_a",
    "planner",
    "loader",
    "evaluator",
    "risk_compliance",
    "visualizer",
    "finalize",
    "replan_critic",
    "llm_scheduler",
    "hitl_wait",
    "user_confirm",
}


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def extract_tool_sequence(state: Dict[str, Any]) -> List[str]:
    """从 agent_steps 抽取工具序列（扁平）。"""
    tools: List[str] = []
    for s in state.get("agent_steps") or []:
        if not isinstance(s, dict):
            continue
        for t in s.get("tools_used") or []:
            tools.append(str(t))
        # llm path 可能把 tool 放 title
        title = str(s.get("title") or "")
        if title.startswith("tool:"):
            tools.append(title.split("tool:", 1)[-1].strip())
        node = str(s.get("node") or "")
        if node in ("llm_scheduler",) and s.get("tools_used"):
            pass
    return tools


def extract_node_sequence(state: Dict[str, Any]) -> List[str]:
    return [
        str(s.get("node"))
        for s in (state.get("agent_steps") or [])
        if isinstance(s, dict) and s.get("node")
    ]


def extract_routes(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """critic / replan 路由记录。"""
    routes: List[Dict[str, Any]] = []
    prop = state.get("replan_proposal") or {}
    if prop:
        routes.append(
            {
                "source": "final_replan_proposal",
                "route": prop.get("route"),
                "stop": prop.get("stop"),
                "reasons": prop.get("reasons") or [],
            }
        )
    for s in state.get("agent_steps") or []:
        if not isinstance(s, dict):
            continue
        if s.get("node") == "replan_critic" or "replan" in str(s.get("title") or "").lower():
            routes.append(
                {
                    "source": "agent_step",
                    "route": s.get("route"),
                    "message": (s.get("message") or "")[:200],
                    "replan_round": s.get("replan_round"),
                    "ship_replan_round": s.get("ship_replan_round"),
                }
            )
    return routes


def compute_kpis(state: Dict[str, Any]) -> Dict[str, Any]:
    """单次 run 的 KPI 字典。"""
    plan = state.get("container_plan") or {}
    rr = state.get("risk_report") or {}
    ispec = state.get("intent_spec") or {}
    tools = extract_tool_sequence(state)
    nodes = extract_node_sequence(state)
    routes = extract_routes(state)
    tool_counts = dict(Counter(tools))
    node_counts = dict(Counter(nodes))

    def _tool_allowed(t: str) -> bool:
        tl = t.lower()
        if any(d in tl for d in DENIED_TOOL_PATTERNS):
            return False
        if t in LLM_ALLOWED_TOOLS:
            return True
        return any(tl.startswith(p.lower()) or p.lower() in tl for p in ALLOWED_TOOL_PREFIXES)

    unknown_tools = [t for t in tools if not _tool_allowed(t)]
    denied_tools = [
        t for t in tools if any(d in t.lower() for d in DENIED_TOOL_PATTERNS)
    ]

    unknown_nodes = [
        n for n in nodes if n not in KNOWN_NODES and not str(n).startswith("message_")
    ]

    # LLM 路径：调度工具是否在白名单
    llm_tool_violations = []
    if "llm" in str(state.get("agent_style") or "").lower() or any(
        n == "llm_scheduler" for n in nodes
    ):
        for t in tools:
            # 只检查 scheduler 级工具（无点号域的短名或白名单族）
            base = t.split(":")[0]
            if base in LLM_ALLOWED_TOOLS or t in LLM_ALLOWED_TOOLS:
                continue
            if _tool_allowed(t) and "." in t:
                # 子 agent 内部 tools 允许
                continue
            if t in ("finish",):
                continue
            # policy_fallback 会调到内部 tools — 不算违规
            if _tool_allowed(t):
                continue
            llm_tool_violations.append(t)

    # 选工具质量代理：是否覆盖关键阶段
    has_intent = any(
        x in tools or x in nodes
        for x in ("intent.interpret", "intent", "orchestrator")
    )
    has_team_a = any(
        n in nodes for n in ("material_parser", "box_scheme", "structure")
    ) or "team_a.run" in tools
    has_team_b = any(
        n in nodes for n in ("planner", "loader", "evaluator")
    ) or "team_b.plan_load_eval" in tools
    has_risk = "risk_compliance" in nodes or "team_b.risk" in tools
    has_finalize = "finalize" in nodes or "finalize.run" in tools

    mid50 = plan.get("worst_mid50")
    if mid50 is None:
        cog = plan.get("cog") or state.get("cog") or {}
        if isinstance(cog, dict):
            mid50 = cog.get("mass_in_mid50_ratio")

    kpis = {
        "team_mode": state.get("team_mode"),
        "agent_style": state.get("agent_style") or "",
        "scheme_id": ispec.get("scheme_id") or "",
        "cargo_mode": ispec.get("cargo_mode") or "",
        "n_steps": len(state.get("agent_steps") or []),
        "n_tools": len(tools),
        "n_unique_tools": len(set(tools)),
        "tool_sequence": tools[:40],
        "tool_counts": tool_counts,
        "node_sequence": nodes[:40],
        "node_counts": node_counts,
        "replan_round": int(state.get("replan_round") or 0),
        "ship_replan_round": int(state.get("ship_replan_round") or 0),
        "team_loop_round": int(state.get("team_loop_round") or 0),
        "routes": routes[:12],
        "n_route_events": len(routes),
        "unknown_tools": unknown_tools[:20],
        "denied_tools": denied_tools[:20],
        "unknown_nodes": unknown_nodes[:20],
        "illegal_tool_calls": len(denied_tools) + len(llm_tool_violations),
        "llm_tool_violations": llm_tool_violations[:20],
        "coverage": {
            "intent_or_orch": has_intent,
            "team_a": has_team_a,
            "team_b": has_team_b,
            "risk": has_risk,
            "finalize": has_finalize,
        },
        "coverage_score": sum(
            [has_intent, has_team_a, has_team_b, has_risk, has_finalize]
        )
        / 5.0,
        "outcome": {
            "can_fit": plan.get("can_fit"),
            "containers_used": plan.get("containers_used"),
            "n0": plan.get("n0") or (state.get("plan") or {}).get("n0"),
            "ship_ok": state.get("ship_ok"),
            "risk_decision": rr.get("decision"),
            "mid50": mid50,
            "n_boxes": len(state.get("boxes") or []),
            "phase": state.get("phase"),
        },
    }
    return kpis


def compare_kpis(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """比较两次 run 的 KPI（如 steps vs llm）。"""
    oa = (a or {}).get("outcome") or {}
    ob = (b or {}).get("outcome") or {}
    can_fit_match = bool(oa.get("can_fit")) == bool(ob.get("can_fit"))
    used_a = int(oa.get("containers_used") or 0)
    used_b = int(ob.get("containers_used") or 0)
    used_match = used_a == used_b or (used_a > 0 and used_b > 0 and abs(used_a - used_b) <= 1)
    ship_match = bool(oa.get("ship_ok")) == bool(ob.get("ship_ok"))
    return {
        "can_fit_match": can_fit_match,
        "containers_used_match": used_match,
        "containers_used_delta": used_b - used_a,
        "ship_ok_match": ship_match,
        "coverage_score_delta": _f(b.get("coverage_score")) - _f(a.get("coverage_score")),
        "n_steps_delta": int(b.get("n_steps") or 0) - int(a.get("n_steps") or 0),
        "replan_round_delta": int(b.get("replan_round") or 0)
        - int(a.get("replan_round") or 0),
        "illegal_tools_a": int(a.get("illegal_tool_calls") or 0),
        "illegal_tools_b": int(b.get("illegal_tool_calls") or 0),
        "agree_core": can_fit_match and used_match,
    }


def aggregate_kpi_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """多 case 聚合。"""
    n = len(rows)
    if n == 0:
        return {"n": 0, "ok": False}
    agree = sum(1 for r in rows if (r.get("compare") or {}).get("agree_core"))
    can_fit = sum(1 for r in rows if (r.get("compare") or {}).get("can_fit_match"))
    illegal = sum(
        int((r.get("steps_kpi") or {}).get("illegal_tool_calls") or 0)
        + int((r.get("llm_kpi") or {}).get("illegal_tool_calls") or 0)
        for r in rows
    )
    avg_cov_steps = sum(_f((r.get("steps_kpi") or {}).get("coverage_score")) for r in rows) / n
    avg_cov_llm = sum(_f((r.get("llm_kpi") or {}).get("coverage_score")) for r in rows) / n
    return {
        "n": n,
        "agree_core_rate": agree / n,
        "can_fit_match_rate": can_fit / n,
        "illegal_tool_calls_total": illegal,
        "avg_coverage_steps": round(avg_cov_steps, 3),
        "avg_coverage_llm": round(avg_cov_llm, 3),
        "target_agree_core": 0.90,
        "pass_agree_core": (agree / n) >= 0.90 if n else False,
        "pass_illegal_zero": illegal == 0,
    }
