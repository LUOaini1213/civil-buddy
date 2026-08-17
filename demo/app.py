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
from config import DEMO_ROOT, DEEPSEEK_MODEL, OUT_ROOT
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

    return {"ok": True, "deepseek": has_key(), "model": DEEPSEEK_MODEL, "context": policy()}


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
        raise HTTPException(400, "未配置 DEEPSEEK_API_KEY")

    session = body.session_id or uuid.uuid4().hex[:12]
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    ids = [i for i in body.expert_ids if get_expert(i)]
    if not ids:
        ids = resolve_mentions(body.message)

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
