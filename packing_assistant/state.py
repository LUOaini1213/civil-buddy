"""最终架构状态：主控 + 团队A + 用户确认 + 团队B。"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict

import operator


class PackingState(TypedDict, total=False):
    # —— 主控 / 会话 ——
    user_input: str
    session_id: str
    run_id: str
    phase: str  # team_a_running | await_user_confirm | team_b_running | done | cancelled
    status: str  # success | need_more_info | error
    intent: str  # full_process | packing_only | consolidation_only | adjust
    packing_plan_id: str
    final_response: str
    harness_meta: Dict[str, Any]
    orchestrator: Dict[str, Any]  # 主控：9 智能体名册、双利用率目标
    goal: str  # deliver_valid_pack_plan | minimize_containers | safe_to_ship
    goal_status: Dict[str, Any]
    ship_ok: bool

    # —— 用户确认 ——
    user_action: Optional[str]  # confirm | revise | cancel | None
    container_type: str
    max_containers: int
    adjust_note: str
    confirmed_box_ids: List[str]

    # —— 团队A ——
    materials: List[Dict[str, Any]]
    materials_summary: Dict[str, Any]
    perception: Dict[str, Any]  # 跑前状态摘要（感知）
    structure_constraints: List[Dict[str, Any]]
    global_advice: Dict[str, Any]
    boxes: List[Dict[str, Any]]
    structure_notes: List[str]
    team_a_summary: Dict[str, Any]
    user_prompt: Dict[str, Any]
    display_markdown: str

    # —— 团队B ——
    plan: Dict[str, Any]
    container_plan: Dict[str, Any]
    evaluation: Dict[str, Any]
    risk_report: Dict[str, Any]
    risks: List[str]
    views: Dict[str, Any]
    image_data: Dict[str, Any]
    legend: List[Dict[str, Any]]

    # —— 观测 ——
    messages: Annotated[List[Any], operator.add]
    traces: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    validation_warnings: Annotated[List[str], operator.add]
    replan_round: int
    enable_auto_confirm: bool  # demo/eval 自动确认
    agent_steps: Annotated[List[Dict[str, Any]], operator.add]  # 逐步 tool 轨迹（节点累加）
    agent_meta: Dict[str, Any]  # 最近一步元数据
    artifact_paths: Dict[str, Any]  # 落盘路径
