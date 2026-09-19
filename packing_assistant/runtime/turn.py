"""One turn, in whichever mode is configured.

    steps   rule routing + the deterministic pipeline; never calls a model (the default, so a
            machine that merely has a key in its environment does not start talking to it)
    model   the model-driven loop (runtime/model_loop.py)
    auto    model when a model is configured and reachable, steps otherwise

Set it with ``civil --mode``, ``/mode`` in the TUI, ``CIVIL_AGENT_MODE``, or ``agent_mode`` in
civil.toml. Every caller that runs a turn for the CLI goes through ``run_turn``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


def resolve_mode(requested: str = "") -> Tuple[str, str]:
    """(the mode that will run, why it is not the one asked for — empty when it is)."""
    from packing_assistant.llm import llm_config
    from packing_assistant.runtime.civil_config import AGENT_MODES, _strip_mode, load_config

    asked = _strip_mode(requested, AGENT_MODES, "") if requested else load_config().agent_mode
    if asked == "steps":
        return "steps", ""
    if llm_config().get("api_key"):
        return "model", ""
    if asked == "model":
        return "steps", "agent_mode=model，但没有配置模型 Key（CIVIL_API_KEY / CIVIL_API_BASE / CIVIL_MODEL）；本轮按 steps 执行。"
    return "steps", ""


def run_turn(text: str, *, session_id: str = "", skill: str = "", confirm: bool = False,
             history: Optional[List[Dict[str, str]]] = None, approve: Optional[Callable[[Dict[str, Any]], bool]] = None,
             cancel_event: Any = None, mode: str = "") -> Dict[str, Any]:
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.runtime.civil_config import load_config

    chosen, notice = resolve_mode(mode)
    if chosen == "model":
        from packing_assistant.runtime.model_loop import run_model_agent

        out = run_model_agent(text, session_id=session_id, expert_id=skill, p0_confirmed=confirm,
                              history=history, approve=approve, cancel_event=cancel_event)
        asked = mode or load_config().agent_mode
        if not (asked == "auto" and out.get("error_code") == "model_unavailable" and not out.get("tools_run")):
            return out
        notice = "模型接口不可用（" + str(out.get("reply") or "")[:80] + "）；本轮按 steps 执行。"
    out = run_agent(text, session_id=session_id, expert_id=skill, p0_confirmed=confirm, cancel_event=cancel_event)
    if notice:
        out["mode_notice"] = notice
        out["reply"] = notice + "\n\n" + str(out.get("reply") or "")
    return out
