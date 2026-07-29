"""状态：大 Team ⊃ 小 Team A（成箱）+ 小 Team B（拼柜）；NL IntentSpec 驱动。"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, TypedDict

import operator


class PackingState(TypedDict, total=False):
    # —— 大 Team / 会话 ——
    user_input: str
    session_id: str
    run_id: str
    phase: str  # team_a_running | await_user_confirm | team_b_running | done | cancelled
    status: str  # success | need_more_info | error
    intent: str  # full_process | packing_only | consolidation_only | adjust
    intent_spec: Dict[str, Any]  # NL→结构化意图（通用 Agent 契约）
    team_mode: str  # big_team_a_b
    team_architecture: Dict[str, Any]
    agent_roster: List[Dict[str, Any]]
    available_tools: List[Dict[str, Any]]
    material_profile: Dict[str, Any]
    packing_plan_id: str
    packing_plan: Dict[str, Any]  # packing.plan.v1 工件
    hitl_gates: Dict[str, Any]
    hitl_summary: Dict[str, Any]
    load_sequence: Dict[str, Any]
    vgm_draft: Dict[str, Any]
    plan_diff: Dict[str, Any]
    replan_proposal: Dict[str, Any]
    packing_options: Dict[str, Any]
    final_response: str
    harness_meta: Dict[str, Any]
    orchestrator: Dict[str, Any]  # 大 Team 主控：名册、双利用率目标
    goal: str  # deliver_valid_pack_plan | minimize_containers | safe_to_ship
    goal_status: Dict[str, Any]
    ship_ok: bool
    design_facts: Dict[str, Any]  # 详设结构事实（截面/γ/图纸）
    nl_revision: Dict[str, Any]  # 最近一次自然语言改方案

    # —— 用户确认（大 Team HITL）——
    user_action: Optional[str]  # confirm | revise | cancel | None
    container_type: str
    max_containers: int
    adjust_note: str
    confirmed_box_ids: List[str]

    # —— 小 Team A 成箱 ——
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

    # —— 小 Team B 拼柜 ——
    plan: Dict[str, Any]
    container_plan: Dict[str, Any]
    evaluation: Dict[str, Any]
    risk_report: Dict[str, Any]
    risks: List[str]
    views: Dict[str, Any]
    scene3d: Dict[str, Any]  # 等轴测 3D 场景（主柜）
    cog: Dict[str, Any]  # 重心/偏心（primary + per_container）
    display_metrics: Dict[str, Any]
    image_data: Dict[str, Any]
    legend: List[Dict[str, Any]]

    # —— 观测 ——
    messages: Annotated[List[Any], operator.add]
    traces: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    validation_warnings: Annotated[List[str], operator.add]
    replan_round: int
    ship_replan_round: int  # 出运闭环打回次数
    team_loop_round: int
    enable_auto_confirm: bool  # demo/eval 自动确认
    agent_steps: Annotated[List[Dict[str, Any]], operator.add]  # 逐步 tool 轨迹（节点累加）
    agent_meta: Dict[str, Any]  # 最近一步元数据
    artifact_paths: Dict[str, Any]  # 落盘路径
