"""小 Team A · 成箱专业组。

材料解析 → 结构计算 → 装箱方案 → 展示（HITL 接口）。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

AgentFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def team_a_nodes() -> List[Tuple[str, str]]:
    return [
        ("material_parser", "小TeamA·材料解析"),
        ("structure", "小TeamA·结构计算"),
        ("box_scheme", "小TeamA·装箱方案"),
        ("present_team_a", "小TeamA·成箱展示/HITL"),
    ]


def team_a_agents() -> Dict[str, AgentFn]:
    from packing_assistant.agents import (
        agent_box_scheme,
        agent_material_parser,
        agent_present_team_a,
        agent_structure,
    )

    return {
        "material_parser": agent_material_parser,
        "structure": agent_structure,
        "box_scheme": agent_box_scheme,
        "present_team_a": agent_present_team_a,
    }


def team_a_rebox_nodes() -> List[Tuple[str, str]]:
    """打回成箱时（不含 present）。"""
    return [
        ("structure", "小TeamA·结构(闭环重做)"),
        ("box_scheme", "小TeamA·装箱(闭环重做)"),
    ]
