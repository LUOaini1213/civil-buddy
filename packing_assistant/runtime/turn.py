"""One turn, in whichever mode is configured.

    steps   rule routing + the deterministic pipeline; never calls a model (the default, so a
            machine that merely has a key in its environment does not start talking to it)
    model   the model-driven loop (runtime/model_loop.py)
    auto    model when a model is configured and reachable, steps otherwise

Set it with ``civil --mode``, ``/mode`` in the TUI, ``CIVIL_AGENT_MODE``, or ``agent_mode`` in
civil.toml. Every caller that runs a turn for the CLI goes through ``run_turn``.

Independently of the mode, ``sandbox_backend = os | auto`` moves the turn's tool work into a worker
process the kernel confines (runtime/os_sandbox): the whole deterministic turn in ``steps``; the
file-reading and writing tools in ``model``, while the model conversation stays here with the network.
"""

from __future__ import annotations

from pathlib import Path
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

    from packing_assistant.runtime import os_sandbox
    from packing_assistant.runtime.workspace import active

    chosen, notice = resolve_mode(mode)
    try:
        backend, sandbox_notice = os_sandbox.resolve_backend()
    except PermissionError as exc:          # sandbox_backend=os and it cannot be had: refuse, do not quietly run unconfined
        return {"ok": False, "schema": "civil.agent.v1", "error_code": "sandbox_unavailable", "reply": str(exc), "wrote": False,
                "files": [], "artifacts": [], "submit_blocked": True, "intent": "chat", "agent_mode": chosen, "session_id": session_id}
    worker = None
    try:
        if backend == "os":
            try:
                worker = os_sandbox.Worker(active()).__enter__()
            except (os_sandbox.WorkerError, OSError) as exc:
                if load_config().sandbox_backend == "os":
                    return {"ok": False, "schema": "civil.agent.v1", "error_code": "sandbox_unavailable", "wrote": False, "files": [],
                            "artifacts": [], "submit_blocked": True, "intent": "chat", "agent_mode": chosen, "session_id": session_id,
                            "reply": "系统级沙箱没有启动，本轮未执行：" + str(exc)}
                backend, sandbox_notice = "app", "系统级沙箱没有启动（" + str(exc)[:120] + "）；本轮只有应用层策略。"
        out: Dict[str, Any] = {}
        if chosen == "model":
            from packing_assistant.runtime.model_loop import run_model_agent

            out = run_model_agent(text, session_id=session_id, expert_id=skill, p0_confirmed=confirm,
                                  history=history, approve=approve, cancel_event=cancel_event, worker=worker)
            asked = mode or load_config().agent_mode
            if asked == "auto" and out.get("error_code") == "model_unavailable" and not out.get("tools_run"):
                notice = "模型接口不可用（" + str(out.get("reply") or "")[:80] + "）；本轮按 steps 执行。"
                chosen = "steps"
        if chosen != "model":
            if worker is not None:
                out = worker.call("run_agent", text=text, session_id=session_id, expert_id=skill, p0_confirmed=confirm)["out"]
            else:
                out = run_agent(text, session_id=session_id, expert_id=skill, p0_confirmed=confirm, cancel_event=cancel_event)
    except os_sandbox.WorkerError as exc:
        out = {"ok": False, "schema": "civil.agent.v1", "error_code": "sandbox_worker_failed", "wrote": False, "files": [],
               "artifacts": [], "submit_blocked": True, "intent": "chat", "agent_mode": chosen, "session_id": session_id,
               "reply": "沙箱工作进程中断，本轮没有完成：" + str(exc)}
    finally:
        confined = dict(worker.confined) if worker is not None else {}
        if worker is not None:
            worker.close()
    if confined:
        from packing_assistant.office_job import publish_root_copy

        for item in list(out.get("files") or []):
            copied = publish_root_copy(Path(str(item.get("path") or ""))) if isinstance(item, dict) else None
            if copied is not None and all(f.get("path") != str(copied) for f in out["files"]):
                out["files"].append({"name": copied.name, "path": str(copied), "tool": "office__xlsx"})
                out.setdefault("artifacts", []).append(str(copied))
    out["sandbox_backend"] = ({"backend": confined.get("backend"), "enforces": confined.get("enforces"), "selftest": confined.get("selftest")}
                              if confined else {"backend": "app", "enforces": {"write": False, "spawn": False, "network": False}})
    notices = [n for n in (notice, sandbox_notice) if n]
    if notices:
        out["mode_notice"] = " ".join(notices)
        out["reply"] = out["mode_notice"] + "\n\n" + str(out.get("reply") or "")
    return out
