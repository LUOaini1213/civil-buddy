"""Complete agent loop: understand → Scheduler → ToolEngine (sandbox on writes).

Production default is steps planning. Chat never executes write tools.
Numbers (xyz / can_fit / GST rate) stay in tools and in-repo KB — the loop
only orchestrates. submit_blocked stays true.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from packing_assistant.runtime.bus import get_bus
from packing_assistant.runtime.scheduler import Scheduler, get_scheduler
from packing_assistant.runtime.tool_engine import ToolEngine, get_engine
from packing_assistant.understand import understand

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "demo" / "out"
CONFIRM = "我明白，将由持证人员签认"
FORBIDDEN = ("可以投标", "可以开工", "中标率")
_PIPE_KEYS = (
    "matrix",
    "handoff",
    "review",
    "tech_outline",
    "bidbook_markdown",
    "export_markdown",
    "extract_table_markdown",
    "matrix_csv",
    "p0_reject_scan",
    "submit_block_reason",
)


def _safe_sid(session_id: str) -> str:
    sid = (session_id or "default").replace("..", "_").replace("/", "_").replace("\\", "_")
    return sid or "default"


def _scrub(text: str) -> str:
    reply = text or ""
    for bad in FORBIDDEN:
        if bad in reply and f"不判定{bad}" not in reply and f"不{bad}" not in reply:
            reply = reply.replace(bad, "（禁止断言）")
    return reply


def _explain(text: str, expert_id: str) -> str:
    eid = (expert_id or "").strip()
    if eid:
        from packing_assistant.expert_roster import get_expert
        from packing_assistant.expert_turn import explain_expert

        exp = get_expert(eid)
        if exp:
            return explain_expert(exp, text)
    from packing_assistant.product_turn import explain

    return explain(text)


def _draft_md(expert_id: str, tool: str, text: str) -> str:
    from packing_assistant.expert_roster import get_expert
    from packing_assistant.expert_turn import _draft_markdown

    exp = get_expert(expert_id)
    if not exp:
        return (
            f"# {tool}\n\n内部讨论 AI 草稿。不是签认件，不判定可投标，不判定可以开工。\n\n"
            f"## 用户原文\n\n{(text or '').strip() or '（未提供）'}\n"
        )
    return _draft_markdown(exp, tool, text)


def _plan_calls(
    text: str,
    *,
    expert_id: str,
    session_id: str,
    p0_confirmed: bool,
    packing_summary: Optional[Dict[str, Any]],
    project_name: str,
) -> Dict[str, Any]:
    from packing_assistant.expert_roster import get_expert

    exp = get_expert(expert_id) if expert_id else None
    if exp and exp.risk == "high" and not p0_confirmed:
        return {
            "hitl": True,
            "calls": [],
            "reply": f"高风险岗 {exp.name} 写盘须确认句「{CONFIRM}」。本轮未写盘。",
        }
    sid = _safe_sid(session_id)
    out_dir = _OUT / sid / (exp.id if exp else "ops")
    calls: List[Dict[str, Any]] = []

    if exp and exp.id == "pack-ship":
        from packing_assistant.runtime.session_packing import load_packing_snapshot

        snap = packing_summary if isinstance(packing_summary, dict) else load_packing_snapshot(session_id)
        connected = bool(snap)
        calls.append({"name": "pack-ship__health", "arguments": {"solver": snap}})
        calls.append({"name": "pack-ship__list", "arguments": {}})
        calls.append(
            {
                "name": "pack-ship__plan",
                "arguments": {"solver": snap, "connected": connected, "materials": text},
            }
        )
        calls.append(
            {
                "name": "pack-ship__export",
                "arguments": {"solver": snap, "connected": connected},
            }
        )
        return {"hitl": False, "calls": calls, "connected": connected, "snap": snap}

    if exp is None or exp.id == "bid-parse":
        calls.append(
            {
                "name": "tender.parse",
                "arguments": {
                    "text": text,
                    "source": "agent-loop",
                    "project_name": project_name,
                    "p0_confirmed": p0_confirmed,
                },
            }
        )
        return {"hitl": False, "calls": calls, "out_dir": str(out_dir)}

    tools = [t for t in (exp.exclusive or ()) if "fill_scheme" not in t] or [f"{exp.id}__draft"]
    for tool in tools:
        path = out_dir / f"{tool}.md"
        calls.append(
            {
                "name": "write_deliverable",
                "arguments": {"path": str(path), "text": _draft_md(exp.id, tool, text)},
                "tool_label": tool,
            }
        )
    return {"hitl": False, "calls": calls}


def _merge_pipe(out: Dict[str, Any], result: Dict[str, Any]) -> None:
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    if not isinstance(data, dict):
        return
    for key in _PIPE_KEYS:
        if key in data and data[key] is not None:
            out[key] = data[key]
    if data.get("submit_blocked") is not None:
        out["submit_blocked"] = True


def run_agent(
    text: str,
    *,
    session_id: str = "",
    expert_id: str = "",
    p0_confirmed: bool = False,
    force_intent: Optional[str] = None,
    packing_summary: Optional[Dict[str, Any]] = None,
    project_name: str = "幕墙项目投标应答（草稿）",
    tools: Optional[ToolEngine] = None,
    max_steps: int = 8,
    scheduler: Optional[Scheduler] = None,
) -> Dict[str, Any]:
    from packing_assistant.expert_roster import get_expert, list_experts
    from packing_assistant.otel_hooks import span

    intent = force_intent if force_intent in {"chat", "run", "both"} else understand(text)
    eid = (expert_id or "").strip()
    exp = get_expert(eid) if eid else None
    if eid and not exp:
        return {
            "ok": False,
            "schema": "civil.agent.v1",
            "error": f"unknown expert: {eid}",
            "intent": "chat",
            "wrote": False,
            "submit_blocked": True,
        }
    sid = session_id or f"sess-{uuid4().hex[:8]}"
    sched = scheduler or get_scheduler()
    engine = tools or get_engine()
    bus = get_bus()
    run = sched.create_run(sid, expert_id=eid, intent=intent, max_steps=max_steps)
    if run.error_code == "session_busy":
        return {
            "ok": False,
            "schema": "civil.agent.v1",
            "error_code": "session_busy",
            "intent": intent,
            "wrote": False,
            "submit_blocked": True,
            "run_id": run.run_id,
            "state": run.state,
            "session_id": sid,
        }
    sched.transition(run, "planning")
    bus.emit(run.run_id, "run_started", {"intent": intent, "expert_id": eid})
    messages: List[Dict[str, Any]] = [{"role": "user", "content": text}]
    out: Dict[str, Any] = {
        "ok": True,
        "schema": "civil.agent.v1",
        "intent": intent,
        "wrote": False,
        "reply": "",
        "matrix": None,
        "submit_blocked": True,
        "submit_block_reason": "未成稿或仍是 AI 草稿，不可递交。",
        "run_id": run.run_id,
        "state": run.state,
        "session_id": sid,
        "expert_id": eid,
        "expert_name": exp.name if exp else "",
        "messages": messages,
        "tools_used": [],
        "tools_run": [],
        "artifacts": [],
        "tool_results": [],
        "sandbox": [],
        "files": [],
        "events": [],
        "hitl_pending": False,
        "n_experts": len(list_experts()),
        "error_code": "",
        "agent_mode": "steps",
    }

    def _finish(state_ok: bool = True) -> Dict[str, Any]:
        run.messages = list(messages)
        run.tools_used = list(out["tools_used"])
        run.artifacts = list(out["artifacts"])
        out["messages"] = list(messages)
        out["state"] = run.state
        out["error_code"] = run.error_code or out.get("error_code") or ""
        out["events"] = [e.to_dict() for e in bus.for_run(run.run_id)]
        out["reply"] = _scrub(str(out.get("reply") or ""))
        out["submit_blocked"] = True
        sched.release(sid)
        bus.emit(run.run_id, "run_ended", {"state": run.state, "wrote": out["wrote"]})
        return out

    try:
        with span(
            "civil.agent",
            {"run_id": run.run_id, "intent": intent, "expert_id": eid, "node": "agent_loop"},
        ):
            if intent == "chat":
                reply = _explain(text, eid)
                messages.append({"role": "assistant", "content": reply})
                sched.transition(run, "done")
                out["reply"] = reply
                out["state"] = run.state
                return _finish()

            planned = _plan_calls(
                text,
                expert_id=eid,
                session_id=sid,
                p0_confirmed=p0_confirmed,
                packing_summary=packing_summary,
                project_name=project_name,
            )
            if planned.get("hitl"):
                sched.transition(run, "waiting_hitl")
                reply = str(planned.get("reply") or "高风险写盘须确认句。本轮未写盘。")
                messages.append({"role": "assistant", "content": reply})
                bus.emit(run.run_id, "hitl", {"required": True})
                out["reply"] = reply
                out["hitl_pending"] = True
                out["wrote"] = False
                return _finish()

            if not sched.transition(run, "acting"):
                out["ok"] = False
                out["error_code"] = run.error_code or "illegal_edge"
                out["reply"] = "无法进入 acting。"
                return _finish()

            explain_prefix = _explain(text, eid) if intent == "both" else ""
            pack_ship: Dict[str, Any] = {}
            last_export_md = ""
            last_extract = ""

            for call in planned.get("calls") or []:
                if run.cancelled or run.state in {"cancelled", "failed"}:
                    out["reply"] = "run cancelled"
                    out["wrote"] = False
                    out["error_code"] = "permission_denied"
                    bus.emit(run.run_id, "cancelled", {})
                    return _finish()
                name = str(call.get("name") or "")
                args = dict(call.get("arguments") or {})
                if not sched.transition(run, "waiting_tool"):
                    out["ok"] = False
                    out["error_code"] = run.error_code or "max_steps"
                    out["reply"] = "达到最大步数，请缩小任务范围"
                    messages.append({"role": "assistant", "content": out["reply"]})
                    return _finish()
                bus.emit(run.run_id, "tool_call", {"name": name})
                result = engine.execute(
                    name,
                    args,
                    expert_id=eid,
                    intent="run",
                    cancelled=run.cancelled,
                )
                bus.emit(
                    run.run_id,
                    "tool_result",
                    {"name": name, "error_code": result.get("error_code"), "ok": result.get("ok")},
                )
                messages.append(
                    {
                        "role": "tool",
                        "name": name,
                        "content": str(result.get("detail") or result.get("error_code") or "ok")[:500],
                        "error_code": result.get("error_code"),
                    }
                )
                out["tool_results"].append(
                    {
                        "name": name,
                        "ok": result.get("ok"),
                        "error_code": result.get("error_code"),
                        "duration_ms": result.get("duration_ms"),
                    }
                )
                out["tools_used"].append(name)
                label = str(call.get("tool_label") or name)
                out["tools_run"].append(label)
                if result.get("sandbox"):
                    out["sandbox"].append(result["sandbox"])
                path = (result.get("data") or {}).get("path") if isinstance(result.get("data"), dict) else result.get("path")
                if result.get("ok") and path:
                    out["artifacts"].append(str(path))
                    out["wrote"] = True
                    out["files"].append(
                        {
                            "name": Path(str(path)).name,
                            "path": str(path),
                            "tool": label,
                        }
                    )
                if name == "tender.parse" and result.get("ok"):
                    _merge_pipe(out, result)
                    data = result.get("data") if isinstance(result.get("data"), dict) else result
                    last_extract = str((data or {}).get("extract_table_markdown") or "")
                    out["wrote"] = True
                    ho = (data or {}).get("handoff") if isinstance(data, dict) else None
                    if isinstance(ho, dict) and ho:
                        from packing_assistant.runtime.session_handoff import save_handoff

                        hp = save_handoff(sid, ho)
                        if hp:
                            out["artifacts"].append(str(hp))
                            out["files"].append(
                                {"name": hp.name, "path": str(hp), "tool": "tender.handoff"}
                            )
                if name.startswith("pack-ship__") and result.get("ok"):
                    data = result.get("data") if isinstance(result.get("data"), dict) else result
                    pack_ship[name.split("__", 1)[-1]] = data
                    if name == "pack-ship__export":
                        last_export_md = str((data or {}).get("markdown") or data.get("markdown") or "")
                if run.state == "waiting_tool":
                    sched.transition(run, "acting")

            # Follow-on writes (still through the engine + sandbox).
            follow: List[Dict[str, Any]] = []
            out_dir = _OUT / _safe_sid(sid) / (exp.id if exp else "ops")
            if last_export_md:
                follow.append(
                    {
                        "name": "write_deliverable",
                        "arguments": {
                            "path": str(out_dir / "pack-ship__export.md"),
                            "text": last_export_md,
                        },
                        "tool_label": "pack-ship__export",
                    }
                )
            elif last_extract:
                follow.append(
                    {
                        "name": "write_deliverable",
                        "arguments": {
                            "path": str(out_dir / "tender.parse.md"),
                            "text": last_extract,
                        },
                        "tool_label": "tender.parse",
                    }
                )
            for call in follow:
                if run.cancelled:
                    break
                name = str(call["name"])
                if not sched.transition(run, "waiting_tool"):
                    out["ok"] = False
                    out["error_code"] = run.error_code or "max_steps"
                    out["reply"] = "达到最大步数，请缩小任务范围"
                    messages.append({"role": "assistant", "content": out["reply"]})
                    return _finish()
                result = engine.execute(
                    name,
                    dict(call.get("arguments") or {}),
                    expert_id=eid,
                    intent="run",
                    cancelled=run.cancelled,
                )
                out["tools_used"].append(name)
                out["tools_run"].append(str(call.get("tool_label") or name))
                out["tool_results"].append(
                    {
                        "name": name,
                        "ok": result.get("ok"),
                        "error_code": result.get("error_code"),
                        "duration_ms": result.get("duration_ms"),
                    }
                )
                if result.get("sandbox"):
                    out["sandbox"].append(result["sandbox"])
                path = (result.get("data") or {}).get("path") if isinstance(result.get("data"), dict) else result.get("path")
                if result.get("ok") and path:
                    out["artifacts"].append(str(path))
                    out["wrote"] = True
                    out.setdefault("files", []).append(
                        {
                            "name": Path(str(path)).name,
                            "path": str(path),
                            "tool": str(call.get("tool_label") or name),
                        }
                    )
                messages.append(
                    {
                        "role": "tool",
                        "name": name,
                        "content": str(result.get("error_code") or "ok"),
                        "error_code": result.get("error_code"),
                    }
                )
                if run.state == "waiting_tool":
                    sched.transition(run, "acting")

            if pack_ship:
                plan = pack_ship.get("plan") or {}
                connected = bool(planned.get("connected"))
                out["pack_ship"] = {
                    "source": "solver" if connected else "disconnected",
                    **pack_ship,
                }
                out["wrote"] = True
                out["reply"] = (
                    "装柜证据只抄 solver 快照，未重算 xyz。"
                    if connected
                    else "装柜证据只抄 solver；本轮未接通，utilization/can_fit/mid50/系固待办 为 UNSPECIFIED。"
                )
            elif out.get("matrix"):
                out["reply"] = "已按招标节选进矩阵。仍是 AI 草稿，submit_blocked=true，不可递交。"
            elif out["wrote"]:
                names = ", ".join(out["tools_run"]) or "draft"
                who = exp.name if exp else "经营岗"
                out["reply"] = f"{who} 已出内部讨论草稿（{names}）。不可递交。"
            else:
                out["reply"] = "本轮未写盘。"

            if explain_prefix:
                out["reply"] = explain_prefix + "\n\n" + str(out.get("reply") or "")

            if run.state == "acting":
                sched.transition(run, "done")
            elif run.state not in {"done", "failed", "cancelled", "waiting_hitl"}:
                sched.transition(run, "done")
            messages.append({"role": "assistant", "content": out["reply"]})
            return _finish()
    except Exception as exc:  # noqa: BLE001 — surface as failed run, do not invent numbers
        run.error_code = run.error_code or "unspecified"
        try:
            if run.state not in {"done", "failed", "cancelled"}:
                sched.transition(run, "failed")
        except Exception:
            run.state = "failed"
        out["ok"] = False
        out["error_code"] = run.error_code
        out["reply"] = f"agent failed: {str(exc)[:200]}"
        return _finish()
