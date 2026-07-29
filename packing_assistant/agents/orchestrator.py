"""主控智能体（第 1 / 9）：开头选柜 + 调度；结尾复核在 finalize。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.state import PackingState
from packing_assistant.tools.container_select import recommend_container

# 大 Team ⊃ 小 Team A/B（与 teams.roster 对齐）
try:
    from packing_assistant.teams.roster import AGENT_ROSTER as _ROSTER

    AGENT_ROSTER: List[Dict[str, str]] = list(_ROSTER)
except Exception:
    AGENT_ROSTER = [
        {"id": "orchestrator", "name": "主控编排", "team": "big"},
        {"id": "material_parser", "name": "材料解析", "team": "A"},
        {"id": "structure", "name": "结构计算", "team": "A"},
        {"id": "box_scheme", "name": "装箱方案", "team": "A"},
        {"id": "planner", "name": "规划", "team": "B"},
        {"id": "loader", "name": "装载", "team": "B"},
        {"id": "evaluator", "name": "评估", "team": "B"},
        {"id": "risk_compliance", "name": "风险合规", "team": "B"},
        {"id": "visualizer", "name": "可视化", "team": "B"},
        {"id": "finalize", "name": "收口", "team": "big"},
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
            # 订柜有效体积软目标（非外廓）；命名保留 space_* 兼容
            "space_soft_min": 0.20,
            "booking_vol_soft_min": 0.20,
            "weight_soft_min": 0.35,
            "space_good": 0.40,
            "booking_vol_good": 0.40,
            "weight_good": 0.60,
            "floor_soft_min": 0.35,
            "floor_good": 0.70,
            "lateral_cog_max": 0.05,
            "prefer_two_layer": True,
            # 评估权重：不填则按 binding 自适应；也可显式指定
            # "evaluation_weights": {"booking_volume": 0.35, "floor": 0.20, "weight": 0.45},
            "penalize_extra_containers": True,
            "extra_container_penalty": 4.0,
        },
    }

    goal_name = str(state.get("goal") or "deliver_valid_pack_plan")
    goal_descs = {
        "deliver_valid_pack_plan": "产出可解释的成箱/订柜/拼柜方案（可确认、可风险拦截）",
        "minimize_containers": "在可装下且合规前提下尽量少柜（仍由 N0+3D 决定，非 LLM 报数）",
        "safe_to_ship": "优先合规与结构安全，风险 REJECT 则不可出运",
    }
    ispec = state.get("intent_spec") or {}
    orch = {
        "agent_count": len(AGENT_ROSTER),
        "roster": AGENT_ROSTER,
        "intent": intent,
        "intent_spec_summary": {
            "scheme_id": ispec.get("scheme_id"),
            "cargo_mode": ispec.get("cargo_mode"),
            "container_budget": ispec.get("container_budget"),
            "source": ispec.get("source"),
        },
        "goals": goals,
        "goal": goal_name,
        "goal_desc": goal_descs.get(goal_name, goal_descs["deliver_valid_pack_plan"]),
        "agent_style": "nl_general_agent_with_tools",
        "architecture": "big_team_wraps_a_b",
        "dispatch": (
            "大Team(NL→IntentSpec+编排) → 小TeamA(材料→结构→成箱) → HITL闸 → "
            "小TeamB(规划→装载→评估→风险→可视化) → 大Team(有界critic+收口)"
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
        "tools_policy": "数值由 tools 计算；NL/LLM 只解释意图与调度，不写 xyz/柜数拍脑袋",
        "loop": "NL意图 → 小TeamA成箱 → HITL → 小TeamB拼柜(有界重试) → 收口",
    }

    updates: Dict[str, Any] = {
        "intent": intent,
        "goal": goal_name,
        "phase": "team_a_running",
        "orchestrator": orch,
        "container_type": chosen,
        "agent_meta": {
            "node": "orchestrator",
            "capability": ["感知", "规划", "追求目标"],
            "tools_used": ["container_select.recommend_container"],
            "artifacts": {
                "container_type": chosen,
                "materials_in": len(mats),
                "goal": goal_name,
            },
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"【大Team·主控】NL通用Agent | arch=big⊃A+B | goal={goal_name} | "
                    f"intent={intent} | scheme={ispec.get('scheme_id') or '-'} | "
                    f"材料={len(mats)} 行 | 推荐柜型={recommended}（采纳={adopt}，当前={chosen}）| "
                    f"理由：{'；'.join(rec.get('reasons') or [])[:100]} | "
                    f"调度：A成箱→HITL→B拼柜→critic有界→收口 | tools算数"
                ),
            }
        ],
    }
    return updates
