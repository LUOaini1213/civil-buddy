from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import run_expert, run_plain
from catalog import catalog_payload, get_expert, resolve_mentions
from config import DEMO_ROOT, OUT_ROOT, llm_model
from kbio import MAX_FILE_BYTES, create_file, delete_file, format_bytes, read_text, write_text
from llm import LLMError, has_key
from rag import list_kb
from store import (
    disable_or_delete_expert,
    set_soft_limit,
    tree_payload,
    upsert_category,
    upsert_expert,
)

app = FastAPI(title="Civil Buddy Workbench")
STATIC = DEMO_ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ChatIn(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    expert_ids: list[str] = Field(default_factory=list)
    confirm_ok: bool = False
    session_id: str = ""


class ExpertIn(BaseModel):
    id: str
    name: str
    category: str
    title: str = ""
    delivers: str = ""
    risk: str = "low"
    aliases: str = ""
    pipeline: str = ""


class CategoryIn(BaseModel):
    id: str
    name: str
    blurb: str = ""


class FileIn(BaseModel):
    path: str
    content: str = ""


class LimitIn(BaseModel):
    kb_soft_limit_kb: int


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    from context import policy
    from packing_assistant.office_job import job_root, job_root_granted, list_job_files

    return {
        "ok": True,
        "product": "civil-codex",
        "product_name": "Civil Buddy",
        "tagline": "土木版 Codex",
        "has_key": has_key(),
        "deepseek": has_key(),
        "model": llm_model(),
        "context": policy(),
        "job": {
            "granted": job_root_granted(),
            "root": str(job_root()) if job_root_granted() else "",
            "n": len(list_job_files()),
        },
    }


@app.get("/api/job")
def job_listing() -> dict:
    from packing_assistant.office_job import job_root, job_root_granted, list_job_files

    return {
        "ok": True,
        "granted": job_root_granted(),
        "root": str(job_root()) if job_root_granted() else "",
        "files": list_job_files(),
        "hint": (
            "说「写一份」会自动抄作业根里的 xlsx/docx/csv/txt，不必再上传。"
            if job_root_granted()
            else "设 CIVIL_JOB_ROOT 为工程文件夹后，本岗直接读该目录，不必上传。禁止 D:\\layout。"
        ),
    }


@app.get("/api/mcp/capabilities")
def mcp_capabilities() -> dict:
    from mcp_surface import initialize_capabilities

    return {"ok": True, "capabilities": initialize_capabilities()}


@app.get("/api/mcp/resources")
def mcp_resources(expert_id: str) -> dict:
    from mcp_surface import list_resources

    exp = get_expert(expert_id)
    if not exp:
        raise HTTPException(404, "unknown expert")
    return {"ok": True, "resources": list_resources(exp.id, exp.category)}


class McpResourceIn(BaseModel):
    uri: str
    expert_id: str = "bid-parse"


@app.post("/api/mcp/resources/read")
def mcp_resource_read(body: McpResourceIn) -> dict:
    from mcp_surface import read_resource

    exp = get_expert(body.expert_id)
    if not exp:
        raise HTTPException(404, "unknown expert")
    return {"ok": True, **read_resource(exp.id, exp.category, body.uri)}


@app.get("/api/mcp/prompts")
def mcp_prompts(expert_id: str = "") -> dict:
    from mcp_surface import list_prompts

    if expert_id and not get_expert(expert_id):
        raise HTTPException(404, "unknown expert")
    return {"ok": True, "prompts": list_prompts(expert_id=expert_id or None)}


class McpPromptIn(BaseModel):
    name: str
    expert_id: str = "bid-parse"
    arguments: dict = Field(default_factory=dict)


@app.post("/api/mcp/prompts/get")
def mcp_prompt_get(body: McpPromptIn) -> dict:
    from mcp_surface import get_prompt

    if not get_expert(body.expert_id):
        raise HTTPException(404, "unknown expert")
    return {"ok": True, **get_prompt(body.name, body.arguments, expert_id=body.expert_id)}


def _mcp_expert_ok(expert_id: str) -> bool:
    return (not expert_id) or bool(get_expert(expert_id)) or expert_id in {"pack-ship"}


@app.get("/api/mcp/tools")
def mcp_tools(expert_id: str = "") -> dict:
    from mcp_surface import list_tools

    if expert_id and not _mcp_expert_ok(expert_id):
        raise HTTPException(404, "unknown expert")
    return {"ok": True, "tools": list_tools(expert_id=expert_id or None)}


class McpToolIn(BaseModel):
    name: str
    expert_id: str = "pack-ship"
    arguments: dict = Field(default_factory=dict)


@app.post("/api/mcp/tools/call")
def mcp_tool_call(body: McpToolIn) -> dict:
    from mcp_surface import call_tool

    if body.expert_id and not _mcp_expert_ok(body.expert_id):
        raise HTTPException(404, "unknown expert")
    return {"ok": True, **call_tool(body.name, body.arguments, expert_id=body.expert_id or None)}


@app.get("/api/skills")
def skills() -> dict:
    from packing_assistant.runtime.expert_skills import catalog

    rows = catalog()
    return {"ok": True, "n": len(rows), "skills": rows, "host": "civil-buddy"}


@app.get("/api/config")
def get_config() -> dict:
    from packing_assistant.runtime.civil_config import load_config

    return {"ok": True, **load_config().to_dict()}


class PolicyIn(BaseModel):
    sandbox: str = ""
    approval: str = ""


@app.post("/api/config")
def set_config(body: PolicyIn) -> dict:
    import os

    from packing_assistant.runtime.civil_config import SANDBOX_MODES, APPROVAL_MODES, load_config

    if body.sandbox:
        os.environ["CIVIL_SANDBOX"] = body.sandbox
    if body.approval:
        os.environ["CIVIL_APPROVAL"] = body.approval
    cfg = load_config()
    if body.sandbox and cfg.sandbox not in SANDBOX_MODES:
        raise HTTPException(400, "bad sandbox")
    if body.approval and cfg.approval not in APPROVAL_MODES:
        raise HTTPException(400, "bad approval")
    return {"ok": True, **cfg.to_dict()}


@app.get("/api/threads")
def threads_list() -> dict:
    from packing_assistant.runtime.threads import list_threads

    rows = [t.to_dict() for t in list_threads()]
    return {"ok": True, "n": len(rows), "threads": rows}


class ThreadIn(BaseModel):
    text: str = ""
    title: str = ""
    skill: str = ""
    confirm_ok: bool = False
    background: bool = False
    thread_id: str = ""


@app.post("/api/threads")
def threads_run(body: ThreadIn) -> dict:
    from packing_assistant.runtime.threads import new_thread, run_on_thread, spawn

    if body.background and body.text.strip():
        return spawn(body.text, skill=body.skill, confirm=body.confirm_ok, title=body.title or body.text[:40])
    tid = (body.thread_id or "").strip()
    if not tid:
        th = new_thread(body.title or body.text[:40] or "新对话", confirm=body.confirm_ok)
        tid = th.thread_id
        if not body.text.strip():
            return {"ok": True, **th.to_dict()}
    return run_on_thread(tid, body.text, skill=body.skill, confirm=body.confirm_ok, background=body.background)


@app.get("/api/threads/{thread_id}")
def thread_one(thread_id: str) -> dict:
    from packing_assistant.runtime.threads import thread_status

    got = thread_status(thread_id)
    if not got.get("ok"):
        raise HTTPException(404, "unknown thread")
    return got


@app.get("/api/catalog")
def catalog() -> dict:
    return catalog_payload()


@app.get("/api/kb/{expert_id}")
def kb(expert_id: str) -> dict:
    exp = get_expert(expert_id)
    if not exp:
        raise HTTPException(404, "unknown expert")
    files = list_kb(exp.id, exp.category)
    total = sum(int(f.get("bytes") or 0) for f in files)
    return {
        "expert": expert_id,
        "files": files,
        "bytes": total,
        "label": format_bytes(total),
    }


@app.get("/api/studio/tree")
def studio_tree() -> dict:
    return tree_payload()


@app.get("/api/studio/file")
def studio_read(path: str) -> dict:
    got = read_text(path)
    if not got:
        raise HTTPException(404, "文件不存在")
    text, st = got
    return {"path": path, "content": text, **st}


@app.put("/api/studio/file")
def studio_write(body: FileIn) -> dict:
    try:
        st = write_text(body.path, body.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **st, "label": format_bytes(st["bytes"])}


@app.post("/api/studio/file")
def studio_create(body: FileIn) -> dict:
    try:
        st = create_file(body.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **st}


@app.delete("/api/studio/file")
def studio_delete(path: str) -> dict:
    try:
        delete_file(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/studio/experts")
def studio_expert(body: ExpertIn) -> dict:
    try:
        exp = upsert_expert(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not exp:
        raise HTTPException(500, "保存失败")
    return exp.to_dict()


@app.delete("/api/studio/experts/{expert_id}")
def studio_expert_del(expert_id: str, delete_kb: bool = True) -> dict:
    if not get_expert(expert_id):
        raise HTTPException(404, "unknown expert")
    disable_or_delete_expert(expert_id, delete_kb=delete_kb)
    return {"ok": True}


@app.post("/api/studio/categories")
def studio_category(body: CategoryIn) -> dict:
    try:
        return upsert_category(body.id, body.name, body.blurb)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/studio/limit")
def studio_limit(body: LimitIn) -> dict:
    return {"kb_soft_limit_kb": set_soft_limit(body.kb_soft_limit_kb), "max_file_bytes": MAX_FILE_BYTES}


@app.post("/api/chat")
def chat(body: ChatIn) -> StreamingResponse:
    if not has_key():
        raise HTTPException(
            400,
            "未配置 API Key。在 demo/.env 写入 CIVIL_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY。",
        )

    session = body.session_id or uuid.uuid4().hex[:12]
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    skill_source = ""
    ids = [i for i in body.expert_ids if get_expert(i)]
    if ids:
        skill_source = "given"
    if not ids:
        ids = resolve_mentions(body.message)
        if ids:
            skill_source = "given"
    if not ids:
        from packing_assistant.runtime.expert_skills import match_skill

        hit = match_skill(body.message)
        if hit and get_expert(hit):
            ids = [hit]
            skill_source = "matched"

    history = []
    for item in body.history[-80:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            history.append({"role": role, "content": content})
    history.append({"role": "user", "content": body.message})
    from context import prepare_history

    history, ctx_report = prepare_history(history)

    def events():
        try:
            yield _sse({"event": "context", "data": ctx_report})
            if ctx_report.get("compressed"):
                yield _sse({"event": "status", "data": {"phase": "compress", "text": ctx_report.get("note")}})
            if not ids:
                gen = run_plain(history)
                for ev in gen:
                    if ev.get("event") == "done" and isinstance(ev.get("data"), dict):
                        ev["data"]["skill"] = ""
                        ev["data"]["skill_source"] = ""
                    yield _sse(ev)
                return
            n = len(ids)
            for i, eid in enumerate(ids):
                exp = get_expert(eid)
                if not exp:
                    continue
                if n > 1:
                    yield _sse(
                        {
                            "event": "status",
                            "data": {"phase": "queue", "text": f"独立专家 {i + 1}/{n}：{exp.name}"},
                        }
                    )
                for ev in run_expert(exp, history, confirm_ok=body.confirm_ok, session_id=session):
                    if ev.get("event") == "done" and isinstance(ev.get("data"), dict):
                        ev["data"]["skill"] = eid
                        ev["data"]["skill_source"] = skill_source or "given"
                    yield _sse(ev)
        except LLMError as exc:
            yield _sse({"event": "error", "data": {"text": str(exc)}})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "data": {"text": f"内部错误：{exc}"}})

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(ev: dict) -> str:
    return f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"


@app.get("/api/file")
def file(path: str) -> FileResponse:
    target = Path(path).resolve()
    try:
        target.relative_to(OUT_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(403, "not a deliverable") from exc
    if not target.is_file():
        raise HTTPException(404, "missing")
    return FileResponse(target)
