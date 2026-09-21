"""Explicit review/apply host for bounded, user-text-derived planning proposals."""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, StrictBool, StrictInt
from starlette.concurrency import run_in_threadpool

try:
    import planning_api as api
except ImportError:
    from demo import planning_api as api

cad = api.cad
router = APIRouter(dependencies=[Depends(cad.local_request)])
PROPOSALS = cad.MemoryStore(max_items=40, max_bytes=16 * 1024 * 1024)


class ContextIn(api.PlanIn):
    method: Literal["cpm", "resource"] = "cpm"
    project_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    expected_revision: StrictInt | None = Field(default=None, ge=1)


class ChatIn(ContextIn):
    message: str = Field(min_length=1, max_length=4000)
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class ApplyIn(ContextIn):
    confirmed: StrictBool = False


def project_context(project):
    return {"project": {k: project[k] for k in ("id", "name", "revision", "can_undo")},
            **{k: project[k] for k in ("plan", "result", "method")}}


def register_proposal(context, proposal=None, action=None):
    from packing_assistant.engineering.planning_agent import plan_digest, propose_command
    from packing_assistant.runtime.cancel import check
    if bool(proposal) == bool(action):
        raise ValueError("排程建议必须且只能包含一种操作。")
    payload = {"context": deepcopy(context), "action": action, "proposal": proposal}
    if proposal:
        expected = propose_command(context["plan"], proposal["source_text"], context["method"])
        if expected != proposal:
            raise ValueError("排程建议与本轮用户输入不一致。")
        payload["changes"] = proposal["changes"]
    else:
        project = context.get("project") or {}
        if action != "undo" or not project.get("id"):
            raise ValueError("请先保存计划；未保存修改可用撤销编辑恢复。")
        current = api.eng.storage_call(api.store().open, project["id"])
        if current["revision"] != project["revision"]:
            raise HTTPException(409, "保存版本已变化，请重新提出撤销。")
        if not current["can_undo"]:
            raise ValueError("当前没有可撤销的已保存版本。")
        if plan_digest(context["plan"]) != plan_digest(current["plan"]) or context["method"] != current["method"]:
            raise ValueError("当前有未保存改参，请先保存或撤销编辑后再撤销保存。")
        previous = api.eng.storage_call(api.store().open, project["id"], current["versions"][-1]["revision"])
        payload["changes"] = [{"parameter": "保存版本", "before": current["revision"], "after": previous["revision"]},
                              {"parameter": "计划工期 / 工作日", "before": current["result"]["duration_workdays"],
                               "after": previous["result"]["duration_workdays"]}]
    check()
    return PROPOSALS.put(payload)


def proposal_record(ident):
    try:
        return PROPOSALS.get(ident)
    except HTTPException as exc:
        if exc.status_code == 410:
            raise HTTPException(410, "排程建议已过期或服务已重启。请重新打开计划并提出建议。") from exc
        raise


def public_proposal(ident):
    saved = proposal_record(ident)
    return {"proposal_id": ident, "action": saved["action"], "changes": saved["changes"],
            "project": saved["context"].get("project"), "method": saved["context"]["method"],
            "plan": saved["context"]["plan"]}


def bind_project(body):
    if not body.project_id:
        if body.expected_revision is not None:
            raise ValueError("修订号必须关联已保存项目。")
        return None
    project = api.eng.storage_call(api.store().open, body.project_id)
    if body.expected_revision != project["revision"]:
        raise HTTPException(409, "保存版本已变化，请重新打开最新计划。")
    return project


@router.post(api.BASE + "/conversation")
async def conversation(request: Request):
    body = await cad.read_json(request, ChatIn)

    def work():
        from packing_assistant.engineering import planning_agent as agent
        from packing_assistant.engineering.planning import validate_plan
        from packing_assistant.runtime.cancel import check
        project = bind_project(body)
        context = {"plan": validate_plan(body.plan), "method": body.method}
        if project:
            context["project"] = project_context(project)["project"]
        if body.run_id:
            context["result"] = api.snapshot(body.plan, body.run_id, body.method)["result"]
        elif project and project["plan"] == context["plan"] and project["method"] == body.method:
            context["result"] = project["result"]
        try:
            result = agent.execute(context, agent.operation(body.message, context), {}, user_text=body.message)
        except (ValueError, PermissionError) as exc:
            result = {"ok": False, "reason": str(exc)}
        check()
        response = {"reply": agent.reply_for([result], context), "ok": result["ok"]}
        if result.get("planning_proposal") or result.get("planning_action"):
            ident = register_proposal(context, result.get("planning_proposal"), result.get("planning_action"))
            response.update(public_proposal(ident))
        return response
    return await cad.operation(request, work)


@router.get(api.BASE + "/proposals/{ident}")
def get_proposal(ident: str):
    return public_proposal(ident)


@router.post(api.BASE + "/proposals/{ident}/apply")
async def apply(ident: str, request: Request):
    body = await cad.read_json(request, ApplyIn)

    def work():
        from packing_assistant.engineering.planning_agent import apply_proposal, plan_digest
        from packing_assistant.runtime.cancel import check
        if not body.confirmed:
            raise HTTPException(403, "请先核对变化并明确点击应用。")
        saved = proposal_record(ident)
        context = saved["context"]
        project = bind_project(body)
        expected = context.get("project") or {}
        if body.project_id != expected.get("id") or body.expected_revision != expected.get("revision"):
            raise HTTPException(409, "建议关联的计划或版本不一致，请重新提出建议。")
        if plan_digest(body.plan) != plan_digest(context["plan"]) or body.method != context["method"]:
            raise HTTPException(409, "输入或计算方法已修改，旧建议未应用，请重新提出建议。")
        if saved["action"] == "undo":
            return {"project": api.eng.storage_call(api.store().undo, project["id"], project["revision"])}
        try:
            result = apply_proposal(body.plan, saved["proposal"], confirmed=True, current_method=body.method)
        except ImportError as exc:
            raise HTTPException(503, "资源排程依赖未就绪，请安装 requirements-planning.txt。") from exc
        except TimeoutError as exc:
            raise HTTPException(504, "资源排程超时，原计划保留，请调整输入后重试。") from exc
        check()
        return {**result, "run_id": api.RUNS.put(result), "saved": False}
    result = await cad.operation(request, work)
    # No cancellable cache publication after a durable undo has committed.
    if "project" in result:
        return await run_in_threadpool(api.project_response, result["project"])
    return result
