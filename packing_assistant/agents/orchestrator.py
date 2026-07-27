"""主控智能体（第 1 / 9）：开头选柜 + 调度；结尾复核在 finalize。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.state import PackingState
from packing_assistant.tools.container_select import recommend_container

# 完整 9 智能体顺序（主控 + A3 + B5）
AGENT_ROSTER: List[Dict[str, str]] = [
    {"id": "orchestrator", "name": "主控智能体", "team": "主控"},
    {"id": "material_parser", "name": "材料解析智能体", "team": "A"},
    {"id": "structure", "name": "结构计算智能体", "team": "A"},
    {"id": "box_scheme", "name": "装箱方案智能体", "team": "A"},
    {"id": "planner", "name": "规划智能体", "team": "B"},
    {"id": "loader", "name": "装载执行智能体", "team": "B"},
    {"id": "evaluator", "name": "评估优化智能体", "team": "B"},
    {"id": "risk_compliance", "name": "风险合规智能体", "team": "B"},
    {"id": "visualizer", "name": "可视化智能体", "team": "B"},
]


def agent_orchestrator(state: PackingState) -> Dict[str, Any]:
    """
    主控开头：
    - 登记 9 智能体
    - 按材料估算推荐柜型（可覆盖默认 40HQ）
    - 下达二层堆码策略
    - 空间/重量双目标
    """
    raw = (state.get("user_input") or "").strip()
    mats = state.get("materials") or []
    intent = state.get("intent") or "full_process"
    if not intent or intent == "full_process":
        intent = "full_process" if (mats or raw) else "need_materials"

    user_ct = (state.get("container_type") or "").strip() or None
    # 用户未强指定或 auto 时用推荐；若 enable_auto_confirm 且为默认 40HQ 则采纳推荐
    rec = recommend_container(
        materials=mats,
        user_hint=user_ct,
        phase="start",
    )
    recommended = rec["recommended"]
    # 采纳策略：无输入 / 默认 40HQ / 空 → 用推荐；用户明确 20GP 等则保留但记录对照
    adopt = False
    if not user_ct or user_ct.upper() in ("", "AUTO"):
        adopt = True
    elif user_ct.upper() == "40HQ" and state.get("enable_auto_confirm"):
        # demo/auto 路径：默认 HQ 改为推荐，避免柜过大
        adopt = True
    chosen = recommended if adopt else user_ct.upper()

    goals = {
        "primary": ["can_fit", "structure_safe", "cog_balanced", "right_container"],
        "utilization": {
            "space": "solid_outer_aabb_and_floor",
            "weight": "payload_without_overload",
            "stacking": "two_layer_when_height_allows",
            "note": "重货优先小柜；轻泡可 40GP/HQ；单箱高≤1.3m 建议二层堆。",
        },
        "targets": {
            "space_soft_min": 0.25,
            "weight_soft_min": 0.35,
            "space_good": 0.45,
            "weight_good": 0.60,
            "lateral_cog_max": 0.05,
            "prefer_two_layer": True,
        },
    }

    orch = {
        "agent_count": 9,
        "roster": AGENT_ROSTER,
        "intent": intent,
        "goals": goals,
        # 任务域目标（非无限自治）
        "goal": "deliver_valid_pack_plan",
        "goal_desc": "产出可解释的成箱/订柜/拼柜方案（可确认、可风险拦截）",
        "agent_style": "multi_agent_workflow",
        "dispatch": (
            "主控选柜 → TeamA(材料→结构→装箱) → 用户确认 → "
            "TeamB(规划→装载→评估→风险→可视化) → 主控复核柜型"
        ),
        "container_select_start": rec,
        "container_type_chosen": chosen,
        "container_type_user": user_ct,
        "container_adopted_recommendation": adopt,
        "max_containers_hint": int(state.get("max_containers") or 0),
        "materials_in": len(mats),
        "raw_input_preview": raw[:200],
        "stacking_policy": {
            "mode": "prefer_two_layer",
            "max_layer": 2,
            "stackable_max_height_mm": 1300,
            "no_stack_if": ["内容物超长", "超长", "结构不通过"],
            "note": "轻箱/矮箱上二层；重箱与超长件仅底层",
        },
        "tools_policy": "数值由 tools 计算；LLM 仅润色，不改柜数/can_fit",
    }

    updates: Dict[str, Any] = {
        "intent": intent,
        "goal": "deliver_valid_pack_plan",
        "phase": "team_a_running",
        "orchestrator": orch,
        "container_type": chosen,
        "agent_meta": {
            "node": "orchestrator",
            "capability": ["感知", "规划", "追求目标"],
            "tools_used": ["container_select.recommend_container"],
            "artifacts": {"container_type": chosen, "materials_in": len(mats)},
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"【主控·开头】9 智能体流水线启动 | goal=deliver_valid_pack_plan | "
                    f"intent={intent} | 材料={len(mats)} 行 | "
                    f"推荐柜型={recommended}（采纳={adopt}，当前={chosen}）| "
                    f"理由：{'；'.join(rec.get('reasons') or [])[:120]} | "
                    f"策略：二层堆码优先 + 空间/重量双利用率 | "
                    f"形态=多智能体工作流（非单体全能Agent）；tools 算数"
                ),
            }
        ],
    }
    return updates
