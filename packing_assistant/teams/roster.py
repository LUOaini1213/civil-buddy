"""大 Team / 小 Team A / 小 Team B 名册。"""

from __future__ import annotations

from typing import Any, Dict, List

TEAM_ARCHITECTURE: Dict[str, Any] = {
    "mode": "big_team_wraps_a_b",
    "description": (
        "一个大 Team 包两个小 Team；"
        "Agent 以 NL 为通用入口，自主调度多工具；"
        "小 Team A=成箱专业组，小 Team B=拼柜专业组。"
    ),
    "big_team": {
        "id": "big",
        "name": "大 Team",
        "roles": ["编排", "HITL闸门", "有界critic", "收口"],
        "nodes": ["intent", "orchestrator", "hitl", "replan_critic", "finalize"],
    },
    "team_a": {
        "id": "A",
        "name": "小 Team A · 成箱",
        "roles": ["材料解析", "结构计算", "装箱方案", "展示确认"],
        "nodes": ["material_parser", "structure", "box_scheme", "present_team_a"],
    },
    "team_b": {
        "id": "B",
        "name": "小 Team B · 拼柜",
        "roles": ["规划", "装载", "评估", "风险合规", "可视化"],
        "nodes": [
            "planner",
            "loader",
            "evaluator",
            "risk_compliance",
            "visualizer",
        ],
    },
    "agent_style": "nl_general_agent_with_tools",
    "tool_policy": "数值由 tools 计算；LLM/NL 只解释意图与调度，不写 xyz/柜数拍脑袋",
    "bounds": {"inner_replan": 3, "ship_replan": 2},
}

# 完整角色名册（主控 + A + B + 收口/批评）
AGENT_ROSTER: List[Dict[str, str]] = [
    {"id": "intent", "name": "意图解析", "team": "big", "role": "NL→IntentSpec"},
    {"id": "orchestrator", "name": "主控编排", "team": "big", "role": "开局调度"},
    {"id": "material_parser", "name": "材料解析", "team": "A", "role": "成箱"},
    {"id": "structure", "name": "结构计算", "team": "A", "role": "成箱"},
    {"id": "box_scheme", "name": "装箱方案", "team": "A", "role": "成箱"},
    {"id": "present_team_a", "name": "成箱展示/HITL", "team": "A", "role": "闸门接口"},
    {"id": "planner", "name": "规划(N0)", "team": "B", "role": "拼柜"},
    {"id": "loader", "name": "装载(3D)", "team": "B", "role": "拼柜"},
    {"id": "evaluator", "name": "评估优化", "team": "B", "role": "拼柜"},
    {"id": "risk_compliance", "name": "风险合规", "team": "B", "role": "拼柜"},
    {"id": "visualizer", "name": "可视化", "team": "B", "role": "拼柜"},
    {"id": "replan_critic", "name": "有界批评", "team": "big", "role": "闭环"},
    {"id": "finalize", "name": "主控收口", "team": "big", "role": "收口"},
]
