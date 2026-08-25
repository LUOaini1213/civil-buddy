"""Agent Middleware · runs in the Civil Buddy runtime, not in the prompt.

Contest track 1: permission, audit, safety, recovery, cost — backend onion.

    permission → sandbox → hitl → tool → audit → cost
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

CHAIN = ("permission", "sandbox", "hitl", "audit", "cost")


def annotate(
    out: Dict[str, Any],
    *,
    gate: str,
    sandbox_mode: str,
    approval: str,
    intent: str,
) -> Dict[str, Any]:
    """Stamp a turn with the middleware chain. Does not invent numbers."""
    sandbox_hits = [s for s in (out.get("sandbox") or []) if isinstance(s, dict)]
    denied = any(s.get("allowed") is False for s in sandbox_hits)
    decisions: List[Dict[str, Any]] = [
        {
            "layer": "permission",
            "sandbox": sandbox_mode,
            "approval": approval,
            "intent": intent,
            "allowed": gate != "read_only",
        },
        {
            "layer": "sandbox",
            "denied": denied,
            "hits": len(sandbox_hits),
            "kernel_jail": False,
        },
        {
            "layer": "hitl",
            "pending": bool(out.get("hitl_pending")),
            "gate": gate,
            "wrote": bool(out.get("wrote")),
        },
        {
            "layer": "audit",
            "run_id": out.get("run_id") or "",
            "events": len(out.get("events") or []),
            "submit_blocked": True,
        },
        {
            "layer": "cost",
            "duration_ms": out.get("duration_ms") or 0,
            "steps": len(out.get("tools_used") or []),
        },
    ]
    out["middleware"] = {
        "schema": "civil.middleware.v1",
        "layer": "runtime",
        "chain": list(CHAIN),
        "gate": gate,
        "decisions": decisions,
        "submit_blocked": True,
        "secret_leak": False,
    }
    return out


def run_turn(
    text: str,
    *,
    expert_id: str = "",
    confirm: bool = False,
    session_id: str = "",
    force_intent: Optional[str] = None,
) -> Dict[str, Any]:
    """One middleware turn. Used by the 3-minute demo and npm run check."""
    from packing_assistant.runtime.agent_loop import run_agent

    return run_agent(
        text,
        session_id=session_id or "mw",
        expert_id=expert_id,
        p0_confirmed=confirm,
        force_intent=force_intent,
    )


def secret_probe() -> Dict[str, Any]:
    """Sandbox must deny writing a secret path. No file is created."""
    from pathlib import Path

    from packing_assistant.runtime.tool_engine import get_engine

    root = Path(__file__).resolve().parents[2]
    envp = root / "demo" / "out" / "mw-probe" / ".env"
    if envp.exists():
        envp.unlink()
    result = get_engine().execute(
        "write_deliverable",
        {"path": str(envp), "text": "SECRET=1"},
        intent="run",
    )
    return {
        "ok": bool(result.get("ok")),
        "error_code": result.get("error_code") or "",
        "exists": envp.exists(),
        "detail": result.get("detail") or "",
    }


def demo_bundle() -> Dict[str, Any]:
    """Happy path + reject + recovery. No API key."""
    happy = run_turn("什么是 GST", session_id="mw-gst")
    reject = run_turn(
        "写一份专项方案讨论提纲",
        expert_id="construction",
        session_id="mw-hitl",
        force_intent="run",
        confirm=False,
    )
    recover = run_turn(
        "出一份装箱作业单 铁架",
        expert_id="pack-ship",
        session_id="mw-pack",
        force_intent="run",
    )
    secret = secret_probe()
    ps = recover.get("pack_ship") if isinstance(recover.get("pack_ship"), dict) else {}
    plan = ps.get("plan") if isinstance(ps.get("plan"), dict) else {}
    if not plan:
        plan = recover
    return {
        "schema": "civil.middleware.demo.v1",
        "chain": list(CHAIN),
        "happy": {
            "intent": happy.get("intent"),
            "wrote": happy.get("wrote"),
            "gst9": "9%" in (happy.get("reply") or ""),
            "run_id": happy.get("run_id"),
            "middleware": happy.get("middleware"),
        },
        "reject": {
            "hitl_pending": reject.get("hitl_pending"),
            "wrote": reject.get("wrote"),
            "files": len(reject.get("files") or reject.get("artifacts") or []),
            "confirm_sentence": "我明白，将由持证人员签认" in (reject.get("reply") or ""),
            "run_id": reject.get("run_id"),
            "middleware": reject.get("middleware"),
        },
        "recover": {
            "utilization": plan.get("utilization"),
            "can_fit": plan.get("can_fit"),
            "mid50": plan.get("mid50"),
            "run_id": recover.get("run_id"),
            "middleware": recover.get("middleware"),
        },
        "secret": secret,
    }
