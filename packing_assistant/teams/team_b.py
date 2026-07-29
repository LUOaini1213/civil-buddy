"""小 Team B · 拼柜专业组。

规划 → 装载 → 评估；风险 → 可视化（尾段由大 Team 串）。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

AgentFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def team_b_loop_nodes() -> List[Tuple[str, str]]:
    return [
        ("planner", "小TeamB·规划(N0)"),
        ("loader", "小TeamB·装载(3D)"),
        ("evaluator", "小TeamB·评估"),
    ]


def team_b_tail_nodes() -> List[Tuple[str, str]]:
    return [
        ("risk_compliance", "小TeamB·风险合规"),
        ("visualizer", "小TeamB·可视化"),
    ]


def team_b_agents() -> Dict[str, AgentFn]:
    from packing_assistant.agents import (
        agent_evaluator,
        agent_loader,
        agent_planner,
        agent_risk_compliance,
        agent_visualizer,
    )

    return {
        "planner": agent_planner,
        "loader": agent_loader,
        "evaluator": agent_evaluator,
        "risk_compliance": agent_risk_compliance,
        "visualizer": agent_visualizer,
    }
