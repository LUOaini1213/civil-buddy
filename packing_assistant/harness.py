"""
主控门面：团队A → 用户确认 → 团队B。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from packing_assistant.config import DEFAULT_CONTAINER_TYPE, HarnessMeta, normalize_container_type
from packing_assistant.graph import create_app, create_team_a_app, create_team_b_app
from packing_assistant.trace import new_run_id, save_trace


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
) -> Dict[str, Any]:
    """
    max_containers=0 表示不设业务目标柜数，由订柜 N0 + 3D 递增决定。
    仅当用户显式给正整数时才作为 3D 搜索封顶。
    """
    rid = run_id or new_run_id()
    return {
        "user_input": user_input or "",
        "session_id": session_id or rid,
        "run_id": rid,
        "phase": "team_a_running",
        "status": "success",
        "intent": "full_process",
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
        "views": {},
        "image_data": {},
        "legend": [],
        "messages": [],
        "traces": [],
        "errors": [],
        "validation_warnings": [],
        "replan_round": 0,
        "enable_auto_confirm": enable_auto_confirm,
    }


def run_team_a(
    user_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "",
    adjust_note: str = "",
    persist_trace: bool = False,
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
    result = app.invoke(state)
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
    return result


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
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    全流程（默认自动确认柜型，便于 demo/eval）。

    若 enable_auto_confirm=False，仅跑团队A并返回等待确认状态。
    packing_options / revision 可控制单箱净重上限与改箱模式。
    max_containers=0：自主定柜（N0+3D），不写死目标柜数。
    """
    # 兼容旧参数名
    user_input = raw_input or kwargs.get("user_input") or ""
    if user_instruction and not user_input:
        user_input = user_instruction
    if "max_containers" in kwargs:
        mc = int(kwargs.get("max_containers") or 0)
    else:
        mc = int(max_containers or 0)

    if not enable_auto_confirm:
        return run_team_a(
            user_input,
            materials=materials,
            persist_trace=persist_trace,
        )

    app = create_app()
    initial = make_initial_state(
        user_input=user_input,
        materials=materials,
        container_type=container_type,
        enable_auto_confirm=True,
        max_containers=mc,
    )
    if packing_options:
        initial["packing_options"] = dict(packing_options)
    if revision:
        initial["revision"] = dict(revision)
    result = app.invoke(initial)
    if persist_trace:
        result = {**result, "trace_path": save_trace(result)}
    return result


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
    """对外 API 形状（主控输出）。"""
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
        "structure_notes": state.get("structure_notes") or [],
        "user_prompt": state.get("user_prompt") or {},
        "plan": state.get("plan") or {},
        "container_plan": state.get("container_plan") or {},
        "evaluation": state.get("evaluation") or {},
        "risk_report": state.get("risk_report") or {},
        "risks": state.get("risks") or [],
        "views": state.get("views") or {},
        "image_data": state.get("image_data") or {},
        "legend": state.get("legend") or [],
        "run_id": state.get("run_id"),
        "traces": state.get("traces") or [],
    }


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
