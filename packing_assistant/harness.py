"""
主控门面：团队A → 用户确认 → 团队B。

Agent 闭环入口：run_pipeline / run_agent_pipeline
  感知→规划→工具→行动→finalize；可选落盘 output/runs/<run_id>/
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
        "enable_auto_confirm": enable_auto_confirm,
        "agent_steps": [],
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
    app = create_team_a_app()
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
    result = app.invoke(state)
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
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
    app = create_team_b_app()
    result = app.invoke(state)
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
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
) -> Dict[str, Any]:
    """
    单一 Agent 闭环入口（逐步 9 智能体，显式 tool 轨迹）。

    材料→结构→成箱→HITL→规划→装载→评估→风险→出图→finalize。
    enable_auto_confirm=False 时停在确认闸门（HITL）。
    返回 state 含 agent_steps[] 与 artifact_paths。
    """
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

    agents = [
        ("orchestrator", "主控·感知/目标", agent_orchestrator),
        ("material_parser", "材料解析·感知", agent_material_parser),
        ("structure", "结构计算", agent_structure),
        ("box_scheme", "装箱方案", agent_box_scheme),
        ("present_team_a", "HITL确认闸门", agent_present_team_a),
        ("planner", "规划(N0)", agent_planner),
        ("loader", "装载(3D)", agent_loader),
        ("evaluator", "评估", agent_evaluator),
        ("risk_compliance", "风险合规", agent_risk_compliance),
        ("visualizer", "可视化", agent_visualizer),
        ("finalize", "主控收口·目标", agent_finalize),
    ]

    state = make_initial_state(
        user_input=raw_input or "agent_pipeline",
        materials=materials,
        container_type=container_type,
        enable_auto_confirm=enable_auto_confirm,
        max_containers=int(max_containers or 0),
        goal=goal,
        session_id=session_id,
    )
    if packing_options:
        state["packing_options"] = dict(packing_options)
    else:
        state["packing_options"] = {
            "standard_boxes": True,
            "mix_mode": True,
            "max_box_net_kg": 2000,
        }

    steps: List[Dict[str, Any]] = []
    for node, title, fn in agents:
        upd = fn(state) or {}
        for k, v in upd.items():
            if k in (
                "messages",
                "traces",
                "errors",
                "validation_warnings",
                "agent_steps",
            ) and isinstance(v, list):
                state[k] = list(state.get(k) or []) + v
            else:
                state[k] = v

        if node == "present_team_a" and enable_auto_confirm:
            # ③ 总闸：auto 确认并写 user_confirm step
            state = apply_user_confirmation(
                state,
                action="confirm",
                container_type=state.get("container_type") or container_type,
                max_containers=int(max_containers or 0),
            )

        last = ""
        for m in reversed(state.get("messages") or []):
            if m.get("content"):
                last = str(m["content"])
                break
        meta = upd.get("agent_meta") if isinstance(upd.get("agent_meta"), dict) else {}
        step: Dict[str, Any] = {
            "node": node,
            "title": title,
            "message": last[:900],
            "role": "agent",
            "tools_used": meta.get("tools_used") or [],
            "capability": meta.get("capability") or [],
            "artifacts": meta.get("artifacts") or {},
        }
        if node == "material_parser":
            step["perception"] = state.get("perception") or state.get("materials_summary")
        if node == "planner":
            pl = state.get("plan") or {}
            step["planning_reasons"] = pl.get("planning_reasons") or []
            step["n0"] = pl.get("n0")
            step["binding"] = (pl.get("booking") or {}).get("binding_constraint")
        if node == "loader":
            p = state.get("container_plan") or {}
            step["containers_used"] = p.get("containers_used")
            step["can_fit"] = p.get("can_fit")
            step["retry_steps"] = (meta.get("artifacts") or {}).get("retry_steps")
        if node == "risk_compliance":
            rr = state.get("risk_report") or {}
            step["decision"] = rr.get("decision")
            step["suggested_actions"] = rr.get("suggested_actions") or []
        if node == "visualizer":
            step["artifacts"] = meta.get("artifacts") or step.get("artifacts") or {}
        if node == "finalize":
            step["goal_status"] = state.get("goal_status") or {}
            step["ship_ok"] = state.get("ship_ok")
        steps.append(step)

        # 同步 apply_user_confirmation 注入的 user_confirm
        if node == "present_team_a" and enable_auto_confirm:
            for st in state.get("agent_steps") or []:
                if isinstance(st, dict) and st.get("node") == "user_confirm":
                    if not any(x.get("node") == "user_confirm" for x in steps):
                        steps.append(st)
                    break

        # ③ 总闸：非 auto 时 present 后写 hitl_wait 再停（不再用 planner 前死代码）
        if node == "present_team_a" and not enable_auto_confirm:
            wait = {
                "node": "hitl_wait",
                "title": "等待用户确认（总分总分总·第③段总闸）",
                "message": (
                    "phase=await_user_confirm；请 POST /api/confirm 后进入团队B；"
                    "HITL 为环境反馈｜tools=hitl.confirm_gate"
                ),
                "tools_used": ["hitl.confirm_gate"],
                "capability": ["感知环境"],
                "status": "ok",
            }
            steps.append(wait)
            state["agent_steps"] = list(state.get("agent_steps") or []) + [wait]
            break

    state["agent_steps"] = steps
    if save_artifacts:
        state = _attach_artifacts(state, steps=steps)
    return state


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
    return {
        "intent": state.get("intent") or "full_process",
        "phase": state.get("phase"),
        "status": state.get("status"),
        "session_id": state.get("session_id"),
        "packing_plan_id": state.get("packing_plan_id"),
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
        "views": state.get("views") or {},
        "image_data": state.get("image_data") or {},
        "legend": state.get("legend") or [],
        "run_id": state.get("run_id"),
        "artifact_paths": state.get("artifact_paths") or {},
        "agent_steps": steps,
        "messages": state.get("messages") or [],
        "traces": state.get("traces") or [],
        "design_facts": state.get("design_facts") or {},
        "design_facts_status": _design_facts_status(state),
        "nl_revision": state.get("nl_revision") or {},
    }


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
