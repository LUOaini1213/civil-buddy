"""旧 graph A/B 子图分段 resume（LangGraph checkpoint + 磁盘 session 双写）。

流程:
  1) run_team_a_segment → phase=await_user_confirm（可落盘 + LG checkpoint）
  2) 进程重启后 load_resume_state(session_id)
  3) confirm + run_team_b_segment 从 HITL 继续

兼容 harness.run_team_a / run_team_b；本模块提供更明确的 resume API。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def run_team_a_segment(
    user_input: str = "",
    *,
    materials: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "",
    adjust_note: str = "",
    packing_options: Optional[Dict[str, Any]] = None,
    design_facts: Optional[Dict[str, Any]] = None,
    persist_trace: bool = False,
) -> Dict[str, Any]:
    """小 Team A 图：停在 HITL。"""
    from packing_assistant.harness import run_team_a
    from packing_assistant.intent_spec import apply_intent_to_state, intent_from_api

    # NL → IntentSpec 再进旧图（通用 Agent 入口一致）
    spec = intent_from_api(
        user_input=user_input,
        materials=materials,
        packing_options=packing_options,
        source="graph_team_a",
    )
    # run_team_a 内部 make_initial_state；先经 intent 过滤材料
    mats = list(materials or [])
    tmp = apply_intent_to_state(
        {"materials": mats, "user_input": user_input, "packing_options": packing_options or {}},
        spec,
        materials=mats,
        filter_materials=True,
    )
    state = run_team_a(
        tmp.get("user_input") or user_input,
        materials=tmp.get("materials") or mats,
        session_id=session_id,
        adjust_note=adjust_note,
        persist_trace=persist_trace,
        design_facts=design_facts,
        packing_options=tmp.get("packing_options") or packing_options,
    )
    state["intent_spec"] = spec.to_dict()
    state["team_mode"] = "big_team_a_b"
    state["graph_segment"] = "team_a_done_await_hitl"
    state["resume_hint"] = {
        "next": "POST /api/confirm 或 resume_team_b_segment",
        "thread_team_a": state.get("_lg_thread_id") or session_id,
        "thread_team_b": f"{session_id or state.get('session_id')}:team_b",
    }
    try:
        from packing_assistant.session_store import save_session

        save_session(str(session_id or state.get("session_id")), state)
    except Exception:
        pass
    return state


def load_resume_state(session_id: str) -> Optional[Dict[str, Any]]:
    """
    恢复顺序:
      1) 磁盘 session_store
      2) LangGraph team_a thread values
    """
    sid = str(session_id or "").strip()
    if not sid:
        return None

    try:
        from packing_assistant.session_store import load_session

        st = load_session(sid)
        if st and isinstance(st, dict) and (
            st.get("boxes") is not None or st.get("phase")
        ):
            st = dict(st)
            st["_resume_source"] = "session_store"
            return st
    except Exception:
        pass

    try:
        from packing_assistant.graph import create_team_a_app_durable
        from packing_assistant.lg_checkpoint import get_thread_state

        app = create_team_a_app_durable()
        st = get_thread_state(sid, app)
        if st and isinstance(st, dict):
            st = dict(st)
            st["_resume_source"] = "langgraph_team_a"
            st["_lg_thread_id"] = sid
            return st
    except Exception:
        pass

    return None


def resume_team_b_segment(
    state: Optional[Dict[str, Any]] = None,
    *,
    session_id: str = "",
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
    adjust_note: str = "",
    confirmed_box_ids: Optional[List[str]] = None,
    persist_trace: bool = False,
) -> Dict[str, Any]:
    """HITL confirm 后跑小 Team B 图。"""
    from packing_assistant.harness import apply_user_confirmation, run_team_b

    st = state
    if st is None:
        st = load_resume_state(session_id)
    if not st:
        return {
            "status": "error",
            "phase": "error",
            "final_response": f"无法 resume：session={session_id} 无磁盘/LG 状态",
            "errors": ["resume_state_missing"],
        }

    if st.get("user_action") != "confirm":
        st = apply_user_confirmation(
            st,
            action="confirm",
            container_type=container_type or st.get("container_type") or "40HQ",
            max_containers=max_containers,
            adjust_note=adjust_note,
            confirmed_box_ids=confirmed_box_ids,
        )

    result = run_team_b(st, persist_trace=persist_trace)
    result["graph_segment"] = "team_b_done"
    result["team_mode"] = result.get("team_mode") or "big_team_a_b"
    result["resume_from"] = st.get("_resume_source") or "memory"
    try:
        from packing_assistant.session_store import save_session, mark_checkpoint

        sid = str(session_id or result.get("session_id") or st.get("session_id") or "")
        if sid:
            save_session(sid, result)
            mark_checkpoint(sid, status="done")
    except Exception:
        pass
    return result


def describe_resume(session_id: str) -> Dict[str, Any]:
    """调试：当前可 resume 状态摘要。"""
    st = load_resume_state(session_id)
    if not st:
        return {"ok": False, "session_id": session_id, "found": False}
    return {
        "ok": True,
        "session_id": session_id,
        "found": True,
        "source": st.get("_resume_source"),
        "phase": st.get("phase"),
        "n_boxes": len(st.get("boxes") or []),
        "user_action": st.get("user_action"),
        "graph_segment": st.get("graph_segment"),
        "team_mode": st.get("team_mode"),
        "can_resume_team_b": (st.get("phase") or "")
        in ("await_user_confirm", "team_a_running")
        or bool(st.get("boxes")),
    }
