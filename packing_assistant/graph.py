"""
LangGraph 子图（分段 resume 用）：

大 Team 产品主路径在 teams.big_team / agent_loop；
本模块保留旧 A/B 子图，供:
  - run_team_a → HITL → run_team_b（/api/team-a + /api/confirm）
  - graph_resume.load_resume_state（磁盘 + Sqlite checkpoint）

小 Team A: 材料 → 结构 → 成箱 → present（无 confirm 则 END）
小 Team B: 规划 → 装载 → 评估(可回规划) → 风险 → 可视化 → finalize
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from langgraph.graph import END, START, StateGraph

from packing_assistant.agents import (
    agent_box_scheme,
    agent_evaluator,
    agent_finalize,
    agent_loader,
    agent_material_parser,
    agent_orchestrator,
    agent_planner,
    agent_present_team_a,
    agent_risk_compliance,
    agent_structure,
    agent_visualizer,
)
from packing_assistant.state import PackingState
from packing_assistant.trace import instrument_node


def _after_present(state: PackingState) -> Literal["planner", "__end__"]:
    """团队A 展示后：仅自动确认或已带 confirm 时进入团队B。"""
    if state.get("user_action") == "confirm" or state.get("enable_auto_confirm"):
        # present_team_a 在 auto 时已设 user_action=confirm
        if state.get("user_action") == "confirm":
            return "planner"
    return "__end__"


def _after_evaluator(
    state: PackingState,
) -> Literal["planner", "risk_compliance"]:
    ev = state.get("evaluation") or {}
    # 结构不通过不能靠加柜重规划解决，直接进风险合规打回
    if ev.get("decision") == "REJECT_STRUCTURE" or ev.get("structure_fail_box_ids"):
        return "risk_compliance"
    if ev.get("need_replan") and int(state.get("replan_round") or 0) <= 2:
        return "planner"
    return "risk_compliance"


def _after_risk(
    state: PackingState,
) -> Literal["visualizer", "finalize"]:
    """
    有硬阻断时仍出可视化便于看布局，但 finalize 会标 rejected/打回。
    （自动回 box_scheme 需跨 TeamA 会话，由 harness/HITL 承接 reject_to。）
    """
    return "visualizer"


def build_team_a_graph() -> StateGraph:
    g = StateGraph(PackingState)
    # 9 智能体：主控 + A3 + B5（B 在 confirm 后接）
    g.add_node("orchestrator", instrument_node("orchestrator", agent_orchestrator))
    g.add_node("material_parser", instrument_node("material_parser", agent_material_parser))
    g.add_node("structure", instrument_node("structure", agent_structure))
    g.add_node("box_scheme", instrument_node("box_scheme", agent_box_scheme))
    g.add_node("present_team_a", instrument_node("present_team_a", agent_present_team_a))

    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "material_parser")
    g.add_edge("material_parser", "structure")
    g.add_edge("structure", "box_scheme")
    g.add_edge("box_scheme", "present_team_a")
    g.add_conditional_edges(
        "present_team_a",
        _after_present,
        {"planner": "planner", "__end__": END},
    )
    # 自动确认时接到团队B节点（需注册）
    g.add_node("planner", instrument_node("planner", agent_planner))
    g.add_node("loader", instrument_node("loader", agent_loader))
    g.add_node("evaluator", instrument_node("evaluator", agent_evaluator))
    g.add_node("risk_compliance", instrument_node("risk_compliance", agent_risk_compliance))
    g.add_node("visualizer", instrument_node("visualizer", agent_visualizer))
    g.add_node("finalize", instrument_node("finalize", agent_finalize))

    g.add_edge("planner", "loader")
    g.add_edge("loader", "evaluator")
    g.add_conditional_edges(
        "evaluator",
        _after_evaluator,
        {"planner": "planner", "risk_compliance": "risk_compliance"},
    )
    g.add_edge("risk_compliance", "visualizer")
    g.add_edge("visualizer", "finalize")
    g.add_edge("finalize", END)
    return g


def build_team_b_graph() -> StateGraph:
    """用户确认后仅跑团队B。"""
    g = StateGraph(PackingState)
    g.add_node("planner", instrument_node("planner", agent_planner))
    g.add_node("loader", instrument_node("loader", agent_loader))
    g.add_node("evaluator", instrument_node("evaluator", agent_evaluator))
    g.add_node("risk_compliance", instrument_node("risk_compliance", agent_risk_compliance))
    g.add_node("visualizer", instrument_node("visualizer", agent_visualizer))
    g.add_node("finalize", instrument_node("finalize", agent_finalize))

    g.add_edge(START, "planner")
    g.add_edge("planner", "loader")
    g.add_edge("loader", "evaluator")
    g.add_conditional_edges(
        "evaluator",
        _after_evaluator,
        {"planner": "planner", "risk_compliance": "risk_compliance"},
    )
    g.add_edge("risk_compliance", "visualizer")
    g.add_edge("visualizer", "finalize")
    g.add_edge("finalize", END)
    return g


def build_graph() -> StateGraph:
    """全图（含 auto_confirm 时一气呵成）。"""
    return build_team_a_graph()


def create_app(checkpointer: Optional[Any] = None):
    graph = build_graph()
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def create_team_a_app(checkpointer: Optional[Any] = None):
    """仅团队A，present 后若无 confirm 则结束。"""
    g = StateGraph(PackingState)
    g.add_node("orchestrator", instrument_node("orchestrator", agent_orchestrator))
    g.add_node("material_parser", instrument_node("material_parser", agent_material_parser))
    g.add_node("structure", instrument_node("structure", agent_structure))
    g.add_node("box_scheme", instrument_node("box_scheme", agent_box_scheme))
    g.add_node("present_team_a", instrument_node("present_team_a", agent_present_team_a))
    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "material_parser")
    g.add_edge("material_parser", "structure")
    g.add_edge("structure", "box_scheme")
    g.add_edge("box_scheme", "present_team_a")
    g.add_edge("present_team_a", END)
    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


def create_team_b_app(checkpointer: Optional[Any] = None):
    graph = build_team_b_graph()
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def create_app_with_memory():
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return create_app(checkpointer=MemorySaver())
    except Exception:
        return create_app()


def create_app_with_sqlite():
    """持久化 Sqlite checkpointer（断进程可 get_state resume）。"""
    try:
        from packing_assistant.lg_checkpoint import get_checkpointer

        cp = get_checkpointer()
        if cp is not None:
            return create_app(checkpointer=cp)
    except Exception:
        pass
    return create_app_with_memory()


def create_team_a_app_durable():
    from packing_assistant.lg_checkpoint import get_checkpointer

    return create_team_a_app(checkpointer=get_checkpointer())


def create_team_b_app_durable():
    from packing_assistant.lg_checkpoint import get_checkpointer

    return create_team_b_app(checkpointer=get_checkpointer())
