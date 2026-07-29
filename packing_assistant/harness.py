"""
主控门面：大 Team（编排+HITL+critic+收口）⊃ 小 Team A 成箱 + 小 Team B 拼柜。

通用 Agent：NL → IntentSpec → 多工具；入口 run_pipeline / run_agent_pipeline。
可选落盘 output/runs/<run_id>/。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from packing_assistant.config import DEFAULT_CONTAINER_TYPE, HarnessMeta, normalize_container_type
from packing_assistant.graph import create_app, create_team_a_app, create_team_b_app
from packing_assistant.trace import new_run_id, save_trace

# 合法目标（输入可声明；finalize 对照是否达成）
VALID_GOALS = (
    "deliver_valid_pack_plan",
    "minimize_containers",
    "safe_to_ship",
)


def make_initial_state(
    *,
    user_input: str = "",
    session_id: str = "",
    materials: Optional[List[Dict[str, Any]]] = None,
    boxes: Optional[List[Dict[str, Any]]] = None,
    container_type: str = DEFAULT_CONTAINER_TYPE,
    enable_auto_confirm: bool = False,
    run_id: Optional[str] = None,
    adjust_note: str = "",
    max_containers: int = 0,
    goal: str = "deliver_valid_pack_plan",
) -> Dict[str, Any]:
    """
    max_containers=0 表示不设业务目标柜数，由订柜 N0 + 3D 递增决定。
    仅当用户显式给正整数时才作为 3D 搜索封顶。
    goal: deliver_valid_pack_plan | minimize_containers | safe_to_ship
    """
    rid = run_id or new_run_id()
    g = (goal or "deliver_valid_pack_plan").strip()
    if g not in VALID_GOALS:
        g = "deliver_valid_pack_plan"
    # 详设结构事实（文件 + 可选注入）
    try:
        from packing_assistant.tools.design_facts import load_design_facts

        _design_facts = load_design_facts()
    except Exception:
        _design_facts = {}
    return {
        "user_input": user_input or "",
        "session_id": session_id or rid,
        "run_id": rid,
        "phase": "team_a_running",
        "status": "success",
        "intent": "full_process",
        "goal": g,
        "design_facts": _design_facts,
        "packing_plan_id": "",
        "final_response": "",
        "harness_meta": HarnessMeta().to_dict(),
        "user_action": None,
        "container_type": normalize_container_type(container_type),
        "max_containers": int(max_containers or 0),
        "adjust_note": adjust_note or "",
        "confirmed_box_ids": [],
        "materials": list(materials or []),
        "materials_summary": {},
        "perception": {},
        "structure_constraints": [],
        "global_advice": {},
        "boxes": list(boxes or []),
        "structure_notes": [],
        "team_a_summary": {},
        "user_prompt": {},
        "display_markdown": "",
        "plan": {},
        "container_plan": {},
        "evaluation": {},
        "risk_report": {},
        "risks": [],
        "goal_status": {},
        "views": {},
        "image_data": {},
        "legend": [],
        "messages": [],
        "traces": [],
        "errors": [],
        "validation_warnings": [],
        "replan_round": 0,
        "ship_replan_round": 0,
        "enable_auto_confirm": enable_auto_confirm,
        "agent_steps": [],
        "team_mode": "big_team_a_b",
        "intent_spec": {},
        "team_architecture": {},
    }


def run_team_a(
    user_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "",
    adjust_note: str = "",
    persist_trace: bool = False,
    design_facts: Optional[Dict[str, Any]] = None,
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """只跑团队A，停在 await_user_confirm。"""
    from packing_assistant.graph import create_team_a_app_durable
    from packing_assistant.lg_checkpoint import invoke_with_checkpoint

    app = create_team_a_app_durable()
    state = make_initial_state(
        user_input=user_input,
        materials=materials,
        session_id=session_id,
        adjust_note=adjust_note,
        enable_auto_confirm=False,
    )
    if design_facts:
        from packing_assistant.tools.design_facts import merge_design_facts

        state["design_facts"] = merge_design_facts(
            state.get("design_facts") or {}, design_facts
        )
    if packing_options:
        state["packing_options"] = {
            **(state.get("packing_options") or {}),
            **packing_options,
        }
    tid = str(session_id or state.get("session_id") or state.get("run_id") or "team_a")
    result = invoke_with_checkpoint(app, state, tid)
    if (result.get("phase") or "") == "await_user_confirm":
        try:
            from packing_assistant.hitl_summary import build_hitl_summary

            result = {**result, "hitl_summary": build_hitl_summary(result)}
        except Exception:
            pass
    # 双写：LangGraph sqlite + 文件 session（API resume）
    try:
        from packing_assistant.session_store import save_session

        save_session(tid, result)
    except Exception:
        pass
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
    result = {**result, "_lg_thread_id": tid, "_lg_checkpoint": True}
    return result


def revise_plan_nl(
    state: Dict[str, Any],
    instruction: str,
    *,
    rerun_team_a: bool = True,
) -> Dict[str, Any]:
    """
    自然语言改方案：解析指令 → 更新 materials/design_facts/柜型 → 可选重跑团队A。
    """
    from packing_assistant.tools.nl_revision import revise_with_natural_language

    s = revise_with_natural_language(dict(state), instruction)
    if not rerun_team_a:
        return s
    # 重跑成箱（保留 design_facts / materials / packing_options）
    return run_team_a(
        s.get("user_input") or instruction,
        materials=s.get("materials"),
        session_id=str(s.get("session_id") or ""),
        adjust_note=s.get("adjust_note") or instruction,
        design_facts=s.get("design_facts"),
        packing_options=s.get("packing_options"),
    )


def apply_user_confirmation(
    state: Dict[str, Any],
    *,
    action: str,
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
    adjust_note: str = "",
    confirmed_box_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    写入用户确认结果。

    max_containers:
      - None：保留 state 原值（默认 0=自主定柜，不写死目标柜数）
      - 正整数：仅作 3D 搜索封顶，不是「必须装成 N 柜」
    """
    s = dict(state)
    s["user_action"] = action
    s["container_type"] = normalize_container_type(container_type)
    if max_containers is not None:
        s["max_containers"] = max(0, int(max_containers))
    # else: 保留已有 max_containers（0=自主）
    s["adjust_note"] = adjust_note or ""
    s["confirmed_box_ids"] = list(confirmed_box_ids or [])
    # 总分总分总 · 第③段「总」闸门：显式写入 agent_steps（HITL 环境反馈）
    ctype = s["container_type"]
    step = {
        "node": "user_confirm" if action == "confirm" else f"user_{action}",
        "title": "用户确认闸门" if action == "confirm" else f"用户·{action}",
        "message": (
            f"【HITL·总闸】action={action} 柜型={ctype} "
            f"max_containers={s.get('max_containers', 0)} "
            f"confirmed_boxes={len(s.get('confirmed_box_ids') or [])}；"
            f"作为环境反馈进入团队B拼柜（非流程断裂）"
            f"｜tools=hitl.confirm_gate"
        ),
        "role": "user",
        "tools_used": ["hitl.confirm_gate"],
        "capability": ["感知环境", "使用工具"],
        "artifacts": {
            "action": action,
            "container_type": ctype,
            "max_containers": s.get("max_containers"),
        },
        "status": "ok",
    }
    prev = list(s.get("agent_steps") or [])
    prev.append(step)
    s["agent_steps"] = prev
    msgs = list(s.get("messages") or [])
    msgs.append({"role": "user", "content": step["message"]})
    s["messages"] = msgs
    return s


def run_team_b(state: Dict[str, Any], *, persist_trace: bool = False) -> Dict[str, Any]:
    """用户 confirm 后跑团队B。"""
    if state.get("user_action") != "confirm":
        return {
            **state,
            "status": "error",
            "final_response": "未确认，不能进入拼柜。请 action=confirm 并选择柜型。",
            "phase": state.get("phase") or "await_user_confirm",
        }
    from packing_assistant.graph import create_team_b_app_durable
    from packing_assistant.lg_checkpoint import invoke_with_checkpoint

    app = create_team_b_app_durable()
    tid = str(
        state.get("session_id")
        or state.get("_lg_thread_id")
        or state.get("run_id")
        or "team_b"
    )
    # team B 用独立 namespace 后缀，避免与 team A 节点名冲突混淆
    result = invoke_with_checkpoint(app, state, f"{tid}:team_b")
    try:
        from packing_assistant.session_store import save_session

        save_session(str(state.get("session_id") or tid), result)
    except Exception:
        pass
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
    result = {**result, "_lg_thread_id": tid, "_lg_checkpoint": True}
    return result


def run_pipeline(
    raw_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    container_type: str = DEFAULT_CONTAINER_TYPE,
    user_instruction: Optional[str] = None,
    persist_trace: bool = False,
    enable_auto_reroute: bool = False,
    enable_auto_confirm: bool = True,
    max_containers: int = 0,
    packing_options: Optional[Dict[str, Any]] = None,
    revision: Optional[Dict[str, Any]] = None,
    goal: str = "deliver_valid_pack_plan",
    save_artifacts: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    全流程（默认自动确认柜型，便于 demo/eval）。

    若 enable_auto_confirm=False，仅跑团队A并返回等待确认状态。
    packing_options / revision 可控制单箱净重上限与改箱模式。
    max_containers=0：自主定柜（N0+3D），不写死目标柜数。
    save_artifacts=True：落盘 output/runs/<run_id>/（体现「采取行动」）。
    """
    # 兼容旧参数名
    user_input = raw_input or kwargs.get("user_input") or ""
    if user_instruction and not user_input:
        user_input = user_instruction
    if "max_containers" in kwargs:
        mc = int(kwargs.get("max_containers") or 0)
    else:
        mc = int(max_containers or 0)
    g = kwargs.get("goal") or goal

    if not enable_auto_confirm:
        result = run_team_a(
            user_input,
            materials=materials,
            persist_trace=persist_trace,
        )
        if save_artifacts:
            result = _attach_artifacts(result)
        return result

    app = create_app()
    initial = make_initial_state(
        user_input=user_input,
        materials=materials,
        container_type=container_type,
        enable_auto_confirm=True,
        max_containers=mc,
        goal=str(g or "deliver_valid_pack_plan"),
    )
    if packing_options:
        initial["packing_options"] = dict(packing_options)
    if revision:
        initial["revision"] = dict(revision)
    result = app.invoke(initial)
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
    if save_artifacts:
        result = _attach_artifacts(result)
    return result


def run_agent_pipeline(
    raw_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    container_type: str = DEFAULT_CONTAINER_TYPE,
    max_containers: int = 0,
    enable_auto_confirm: bool = True,
    goal: str = "deliver_valid_pack_plan",
    packing_options: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    save_artifacts: bool = True,
    on_event: Optional[Any] = None,
    agent_mode: str = "steps",
    max_llm_rounds: int = 12,
) -> Dict[str, Any]:
    """
    大 Team 主入口。

    agent_mode:
      - steps: 固定专业节点调度（默认，IntentSpec + A→HITL→B）
      - llm_toolcall: LLM 多轮 tool-call（无 Key 时自动 policy fallback）
      - auto: 有 LLM Key 则 llm_toolcall，否则 steps
    """
    mode = _resolve_agent_mode(agent_mode)
    if mode == "llm_toolcall":
        from packing_assistant.agent_loop import run_llm_agent_loop

        return run_llm_agent_loop(
            raw_input,
            materials=materials,
            container_type=container_type,
            max_containers=max_containers,
            enable_auto_confirm=enable_auto_confirm,
            goal=goal,
            packing_options=packing_options,
            session_id=session_id,
            save_artifacts=save_artifacts,
            max_rounds=max_llm_rounds,
            on_event=on_event,
            force_llm=True,
        )

    from packing_assistant.teams.big_team import run_big_team

    return run_big_team(
        raw_input,
        materials=materials,
        container_type=container_type,
        max_containers=max_containers,
        enable_auto_confirm=enable_auto_confirm,
        goal=goal,
        packing_options=packing_options,
        session_id=session_id,
        save_artifacts=save_artifacts,
        on_event=on_event,
    )


def iter_agent_pipeline(
    raw_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    container_type: str = DEFAULT_CONTAINER_TYPE,
    max_containers: int = 0,
    enable_auto_confirm: bool = True,
    goal: str = "deliver_valid_pack_plan",
    packing_options: Optional[Dict[str, Any]] = None,
    session_id: str = "",
    save_artifacts: bool = True,
    on_event: Optional[Any] = None,
    agent_mode: str = "steps",
    max_llm_rounds: int = 12,
):
    """逐步 yield 事件。agent_mode 同 run_agent_pipeline。"""
    mode = _resolve_agent_mode(agent_mode)
    if mode == "llm_toolcall":
        from packing_assistant.agent_loop import iter_llm_agent_loop

        yield from iter_llm_agent_loop(
            raw_input,
            materials=materials,
            container_type=container_type,
            max_containers=max_containers,
            enable_auto_confirm=enable_auto_confirm,
            goal=goal,
            packing_options=packing_options,
            session_id=session_id,
            save_artifacts=save_artifacts,
            max_rounds=max_llm_rounds,
            on_event=on_event,
            force_llm=True,
        )
        return

    from packing_assistant.teams.big_team import iter_big_team_run

    yield from iter_big_team_run(
        raw_input,
        materials=materials,
        container_type=container_type,
        max_containers=max_containers,
        enable_auto_confirm=enable_auto_confirm,
        goal=goal,
        packing_options=packing_options,
        session_id=session_id,
        save_artifacts=save_artifacts,
        on_event=on_event,
    )


def _resolve_agent_mode(agent_mode: str) -> str:
    """steps | llm_toolcall；auto 看 Key / env。"""
    m = (agent_mode or "steps").strip().lower()
    if m in ("llm", "llm_toolcall", "toolcall", "agent"):
        return "llm_toolcall"
    if m == "auto":
        try:
            from packing_assistant.agent_loop import llm_agent_enabled
            from packing_assistant.llm import llm_available

            if llm_available() or llm_agent_enabled():
                return "llm_toolcall"
        except Exception:
            pass
        return "steps"
    try:
        from packing_assistant.agent_loop import llm_agent_enabled

        if llm_agent_enabled() and m == "steps":
            # env 强制开 LLM 路径
            return "llm_toolcall"
    except Exception:
        pass
    return "steps"


def _attach_artifacts(
    state: Dict[str, Any],
    *,
    steps: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """落盘 Run 产物并挂到 state.artifact_paths。"""
    try:
        from packing_assistant.run_artifacts import save_run_artifacts

        paths = save_run_artifacts(state, steps=steps or state.get("agent_steps"))
        out = dict(state)
        out["artifact_paths"] = paths
        return out
    except Exception as e:
        out = dict(state)
        out["artifact_paths"] = {"error": str(e)}
        return out


def _needs_box_revision(state: Dict[str, Any]) -> bool:
    rr = state.get("risk_report") or {}
    if rr.get("decision") == "REJECT" and (rr.get("reject_to") or "") == "box_scheme":
        return True
    if rr.get("need_revision") and any("结构" in str(b) for b in (rr.get("blockers") or [])):
        return True
    if (state.get("evaluation") or {}).get("decision") == "REJECT_STRUCTURE":
        return True
    fails = [
        b
        for b in (state.get("boxes") or [])
        if b.get("structure_conclusion") == "不通过"
    ]
    return bool(fails) and bool((state.get("container_plan") or {}).get("can_fit"))


def run_pipeline_with_revision(
    raw_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    container_type: str = DEFAULT_CONTAINER_TYPE,
    max_containers: int = 6,
    max_revision_rounds: int = 2,
    initial_max_box_net_kg: float = 3200.0,
    persist_trace: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    全流程 + 结构/合规打回自动改箱重跑。

    策略：
    - 第 0 轮：正常装箱（已按 max_box_net_kg 预拆重货）
    - 若 REJECT→box_scheme：降低单箱净重上限，revision_mode=True，重跑 A+B
    - 最多 max_revision_rounds 次改箱
    """
    mats = list(materials or [])
    history: List[Dict[str, Any]] = []
    cap = float(initial_max_box_net_kg)
    state: Dict[str, Any] = {}

    for rnd in range(max_revision_rounds + 1):
        rev = None
        opts = {"max_box_net_kg": cap}
        if rnd > 0:
            # 逐轮收紧：3200 → 2500 → 1800 …
            cap = max(1200.0, min(cap * 0.75, 2500.0 if rnd == 1 else cap * 0.75))
            rev = {
                "active": True,
                "round": rnd,
                "max_box_net_kg": cap,
                "reason": "structure_or_compliance_reject",
            }
            opts["revision_mode"] = True
            opts["max_box_net_kg"] = cap

        state = run_pipeline(
            raw_input or f"revision_round={rnd}",
            materials=mats,
            container_type=container_type,
            max_containers=max_containers,
            packing_options=opts,
            revision=rev,
            enable_auto_confirm=True,
            persist_trace=persist_trace and rnd == 0,
            **{k: v for k, v in kwargs.items() if k not in ("materials",)},
        )
        rr = state.get("risk_report") or {}
        snap = {
            "round": rnd,
            "max_box_net_kg": cap,
            "boxes": len(state.get("boxes") or []),
            "struct_fail": sum(
                1
                for b in (state.get("boxes") or [])
                if b.get("structure_conclusion") == "不通过"
            ),
            "can_fit": (state.get("container_plan") or {}).get("can_fit"),
            "containers_used": (state.get("container_plan") or {}).get("containers_used"),
            "risk_decision": rr.get("decision"),
            "risk_level": rr.get("level"),
            "status": state.get("status"),
            "phase": state.get("phase"),
            "ship_ok": state.get("ship_ok"),
        }
        history.append(snap)

        if not _needs_box_revision(state):
            break
        if rnd >= max_revision_rounds:
            # 仍失败：保留打回状态
            break

    state = dict(state)
    state["revision_history"] = history
    state["revision_rounds_used"] = len(history) - 1
    # 汇总消息
    msgs = list(state.get("messages") or [])
    msgs.append(
        {
            "role": "assistant",
            "content": (
                f"改箱闭环：共 {len(history)} 轮；"
                + " → ".join(
                    f"r{h['round']} box={h['boxes']} fail={h['struct_fail']} "
                    f"fit={h['can_fit']} risk={h['risk_decision']}"
                    for h in history
                )
            ),
        }
    )
    state["messages"] = msgs
    return state


def public_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """对外 API 形状（主控输出）。含 agent_steps 供前端底部可视化。"""
    steps = list(state.get("agent_steps") or [])
    if not steps:
        # 兜底：从 messages 合成可读步骤
        for i, m in enumerate(state.get("messages") or []):
            if not isinstance(m, dict):
                continue
            content = str(m.get("content") or "").strip()
            if not content:
                continue
            steps.append(
                {
                    "node": f"message_{i}",
                    "title": "输出" if m.get("role") == "assistant" else str(m.get("role") or "msg"),
                    "message": content[:4000],
                    "role": m.get("role") or "assistant",
                    "tools_used": [],
                }
            )
    plan = state.get("container_plan") or {}
    booking = state.get("booking") or plan.get("booking") or (state.get("plan") or {}).get("booking") or {}
    volume_summary = {
        "formula": "N0=max(N_weight,N_volume); V_eff=pack_effective≠outer",
        "n0": plan.get("n0") or booking.get("n0") or (state.get("plan") or {}).get("n0"),
        "containers_used": plan.get("containers_used"),
        "binding_constraint": booking.get("binding_constraint"),
        "volume_m3_eff": booking.get("volume_m3") or plan.get("booking_volume_m3"),
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "fill_ratio_eta": booking.get("fill_ratio") or 0.82,
        "volume_source": booking.get("volume_source") or booking.get("mode"),
        "note": "订柜看 booking_volume；外廓 outer 仅 3D/展示",
    }
    # PackingPlan 工件（若 finalize 未写则补建）
    packing_plan = state.get("packing_plan")
    if not packing_plan:
        try:
            from packing_assistant.packing_plan import build_packing_plan

            packing_plan = build_packing_plan(state)
        except Exception:
            packing_plan = {}
    hitl_gates = state.get("hitl_gates")
    if not hitl_gates:
        try:
            from packing_assistant.hitl_gates import evaluate_hitl_gates

            hitl_gates = evaluate_hitl_gates(state)
        except Exception:
            hitl_gates = {}
    return {
        "intent": state.get("intent") or "full_process",
        "phase": state.get("phase"),
        "status": state.get("status"),
        "session_id": state.get("session_id"),
        "packing_plan_id": state.get("packing_plan_id")
        or (packing_plan or {}).get("plan_id"),
        "packing_plan": packing_plan or {},
        "hitl_gates": hitl_gates or {},
        "load_sequence": state.get("load_sequence") or {},
        "vgm_draft": state.get("vgm_draft") or {},
        "plan_diff": state.get("plan_diff") or {},
        "secure_work_order": state.get("secure_work_order")
        or (packing_plan or {}).get("secure_work_order")
        or {},
        "por_manifest": state.get("por_manifest")
        or (packing_plan or {}).get("por_manifest")
        or {},
        "per_cabin_cog": (packing_plan or {}).get("per_cabin_cog")
        or list(((plan.get("cog_bundle") or {}).get("per_container") or [])),
        "r_pipeline": (packing_plan or {}).get("r_pipeline") or [],
        "profile_id": (state.get("packing_options") or {}).get("profile_id")
        or (packing_plan or {}).get("profile_id"),
        "replan_proposal": state.get("replan_proposal") or {},
        "final_response": state.get("final_response") or "",
        "materials": state.get("materials") or [],
        "boxes": state.get("boxes") or [],
        "summary": state.get("team_a_summary") or {},
        "perception": state.get("perception") or state.get("materials_summary") or {},
        "structure_notes": state.get("structure_notes") or [],
        "user_prompt": state.get("user_prompt") or {},
        "plan": state.get("plan") or {},
        "booking": booking,
        "container_plan": plan,
        "volume_summary": volume_summary,
        "evaluation": state.get("evaluation") or {},
        "risk_report": state.get("risk_report") or {},
        "risks": state.get("risks") or [],
        "goal": state.get("goal"),
        "goal_status": state.get("goal_status") or {},
        "ship_ok": state.get("ship_ok"),
        "team_mode": state.get("team_mode") or "big_team_a_b",
        "agent_style": state.get("agent_style") or "",
        "intent_spec": state.get("intent_spec") or {},
        "team_architecture": state.get("team_architecture") or {},
        "graph_segment": state.get("graph_segment"),
        "tms_booking": state.get("tms_booking") or {},
        "team_loop_round": state.get("team_loop_round"),
        "replan_round": state.get("replan_round"),
        "ship_replan_round": state.get("ship_replan_round"),
        "views": state.get("views") or {},
        "scene3d": state.get("scene3d") or {},
        "cog": (
            (plan.get("cog") if isinstance(plan.get("cog"), dict) else None)
            or ((plan.get("cog_bundle") or {}).get("worst") if isinstance(plan.get("cog_bundle"), dict) else None)
            or ((plan.get("cog_bundle") or {}).get("primary") if isinstance(plan.get("cog_bundle"), dict) else None)
            or state.get("cog")
            or (state.get("risk_report") or {}).get("cog")
            or (packing_plan or {}).get("cog")
            or {}
        ),
        "cog_bundle": plan.get("cog_bundle") or state.get("cog_bundle") or {},
        "worst_mid50": plan.get("worst_mid50")
        or ((plan.get("cog_bundle") or {}).get("worst_mid50")),
        "image_data": state.get("image_data") or {},
        "legend": state.get("legend") or [],
        "display_metrics": state.get("display_metrics") or {},
        "run_id": state.get("run_id"),
        "artifact_paths": state.get("artifact_paths") or {},
        "agent_steps": steps,
        "messages": state.get("messages") or [],
        "traces": state.get("traces") or [],
        "design_facts": state.get("design_facts") or {},
        "design_facts_status": _design_facts_status(state),
        "nl_revision": state.get("nl_revision") or {},
        "hitl_summary": state.get("hitl_summary")
        or _maybe_hitl_summary(state),
        "harness_version": (state.get("harness_meta") or {}).get("harness_version")
        or "",
    }


def _maybe_hitl_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    if (state.get("phase") or "") != "await_user_confirm":
        return {}
    try:
        from packing_assistant.hitl_summary import build_hitl_summary

        return build_hitl_summary(state)
    except Exception:
        return {}


def _design_facts_status(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from packing_assistant.tools.design_facts import facts_status_summary

        return facts_status_summary(state.get("design_facts"))
    except Exception:
        return {"has_detailed_facts": False, "message": "design_facts 不可用"}


def format_trace_report(state: Dict[str, Any]) -> str:
    lines = [
        f"run_id={state.get('run_id')}",
        f"phase={state.get('phase')}",
        f"harness={(state.get('harness_meta') or {}).get('harness_version')}",
        "-" * 48,
    ]
    for ev in state.get("traces") or []:
        flag = "OK" if ev.get("status") == "ok" else "ERR"
        lines.append(
            f"[{flag}] {str(ev.get('node')):22} {ev.get('duration_ms', 0):>8} ms"
        )
        if ev.get("error"):
            lines.append(f"       error: {ev['error']}")
    return "\n".join(lines)
