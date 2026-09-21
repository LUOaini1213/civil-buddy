"""Local CAD workspace: bounded, temporary memory; geometry never comes from chat.

Uploaded drawings and previews expire on restart or after 30 minutes. Only an
explicit export with the product confirmation phrase returns deliverable bytes.
No source drawing, model, or API key is persisted by these routes.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import importlib.util
import io
import json
import math
from pathlib import Path
from threading import BoundedSemaphore, RLock
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException, MultiPartParser

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = "我明白，将由持证人员签认"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_JSON_BYTES = 512 * 1024
TTL_SECONDS = 30 * 60
DEPENDENCIES = {"ezdxf": "ezdxf", "shapely": "shapely", "trimesh": "trimesh", "mapbox_earcut": "mapbox-earcut"}


class MemoryStore:
    """Immutable snapshots, random identifiers, TTL and a total serialized budget."""

    def __init__(self, *, max_items: int = 16, max_bytes: int = 64 * 1024 * 1024, ttl: float = TTL_SECONDS):
        self.max_items, self.max_bytes, self.ttl = max_items, max_bytes, ttl
        self._items: OrderedDict[str, tuple[float, int, dict]] = OrderedDict()
        self._lock = RLock()

    def _expire(self) -> None:
        now = time.monotonic()
        for key in [key for key, (created, _, _) in self._items.items() if now - created >= self.ttl]:
            del self._items[key]

    def put(self, value: dict) -> str:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        if size > self.max_bytes:
            raise ValueError("模型或图纸超过本机预览缓存上限，请减少图层或实体。")
        with self._lock:
            self._expire()
            while self._items and (len(self._items) >= self.max_items or sum(v[1] for v in self._items.values()) + size > self.max_bytes):
                self._items.popitem(last=False)
            key = uuid4().hex
            self._items[key] = (time.monotonic(), size, deepcopy(value))
            return key

    def get(self, key: str) -> dict:
        with self._lock:
            self._expire()
            if key not in self._items:
                raise HTTPException(410, "图纸或模型已过期、服务已重启或缓存已释放，请重新上传并生成。")
            return deepcopy(self._items[key][2])


DOCUMENTS = MemoryStore(max_items=8, max_bytes=32 * 1024 * 1024)
MODELS = MemoryStore(max_items=12, max_bytes=64 * 1024 * 1024)
COMPUTE = BoundedSemaphore(2)


async def local_request(request: Request) -> None:
    # Do not accept cross-site form submissions to this loopback tool. Requests
    # without Origin (CLI/tests) remain valid; the server binds loopback by default.
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urlsplit(origin)
        except ValueError as exc:
            raise HTTPException(403, "请求来源无效。") from exc
        if parsed.scheme not in {"http", "https"} or parsed.netloc != request.url.netloc:
            raise HTTPException(403, "CAD 操作只接受当前工作台页面的请求。")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "CAD 操作只接受当前工作台页面的请求。")


router = APIRouter(dependencies=[Depends(local_request)])


class BuildIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    # The shared geometry core validates the complete config, including booleans,
    # finite dimensions, role/layer names, source handles and solid confirmation.
    config: dict


class CommandIn(BuildIn):
    message: str = Field(min_length=1, max_length=1000)
    selected_id: str | None = Field(default=None, max_length=128)


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    confirmation: str = Field(max_length=80)
    format: Literal["glb", "json", "zip"] = "zip"


def capabilities() -> dict:
    missing = [package for module, package in DEPENDENCIES.items() if importlib.util.find_spec(module) is None]
    return {
        "ok": True, "available": not missing, "missing_dependencies": missing,
        "install_command": "python -m pip install -r requirements-cad.txt",
        "modes": ["building", "section"], "units": ["mm", "cm", "m", "in", "ft"],
        "max_upload_bytes": MAX_UPLOAD_BYTES, "session_ttl_seconds": TTL_SECONDS,
        "storage": "temporary-memory", "formats": ["dxf"], "exports": ["glb", "json", "zip"],
    }


def require_dependencies() -> None:
    state = capabilities()
    if not state["available"]:
        raise HTTPException(503, "CAD 依赖未安装，请运行：" + state["install_command"])


def compute(fn, *args):
    if not COMPUTE.acquire(blocking=False):
        raise HTTPException(429, "已有建模任务正在处理，请稍后重试。")
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        COMPUTE.release()


async def bounded_body(request: Request, limit: int) -> bytes:
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "请求过大，请减少图纸大小或参数数量。")
        chunks.append(chunk)
    return b"".join(chunks)


async def read_json(request: Request, schema):
    from pydantic import ValidationError
    data = await bounded_body(request, MAX_JSON_BYTES)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("参数必须是有限数值")
        return number

    def invalid_constant(value):
        raise ValueError("不允许 NaN 或 Infinity")

    try:
        return schema.model_validate(json.loads(data, parse_float=finite_float, parse_constant=invalid_constant))
    except ValidationError as exc:
        # Do not echo entire drawings or arbitrary client-supplied objects.
        raise HTTPException(422, "请求参数不合法：" + str(exc.errors(include_input=False, include_url=False))) from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HTTPException(422, "请求必须是有效 JSON，且所有数值必须有限。") from exc


@router.get("/cad")
def cad_page():
    return FileResponse(ROOT / "demo/static/cad.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/cad/capabilities")
def cad_capabilities():
    return capabilities()


@router.get("/api/cad/examples/{mode}")
def cad_example(mode: Literal["building", "section"]):
    names = {"building": "synthetic-building-mm.dxf", "section": "synthetic-hollow-section-mm.dxf"}
    return FileResponse(ROOT / "examples/cad-to-3d" / names[mode], media_type="application/dxf", filename=names[mode])


@router.post("/api/cad/import")
async def cad_import(request: Request):
    require_dependencies()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "multipart/form-data":
        raise HTTPException(400, "上传格式无效，请仅上传一份 DXF 文件。")
    payload = await bounded_body(request, MAX_UPLOAD_BYTES + 64 * 1024)

    async def stream():
        yield payload
        yield b""

    parser = MultiPartParser(request.headers, stream(), max_files=1, max_fields=0)
    # Starlette normally spills uploads >1 MiB to disk. This request has already
    # passed a hard body limit; keep its spool entirely in memory. max_file_size
    # is the name used by earlier supported Starlette versions.
    parser.spool_max_size = parser.max_file_size = MAX_UPLOAD_BYTES + 64 * 1024 + 1
    try:
        form = await parser.parse()
    except (MultiPartException, ValueError) as exc:
        # Older supported Starlette releases only clean up MultiPartException;
        # malformed multipart headers can raise the parser's ValueError instead.
        for spool in parser._files_to_close_on_error:
            spool.close()
        raise HTTPException(400, "上传格式无效，请仅上传一份 DXF 文件。") from exc
    try:
        file = form.get("file")
        if not isinstance(file, UploadFile) or len(form) != 1:
            raise HTTPException(422, "请上传一份 DXF 文件。")
        # Names are display metadata only. Never use them as filesystem paths.
        filename = (file.filename or "drawing.dxf").replace("\\", "/").split("/")[-1][:200]
        if not filename.lower().endswith(".dxf"):
            raise HTTPException(415, "首版仅支持 DXF；DWG 请先在 CAD 软件中另存为 DXF。")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await form.close()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413 if data else 422, "DXF 文件不能为空且不能超过 10 MiB。")
    from packing_assistant.cad3d.geometry import inspect_dxf
    document = await run_in_threadpool(compute, inspect_dxf, data, filename)
    try:
        document_id = DOCUMENTS.put(document)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from exc
    return JSONResponse({"ok": True, "document_id": document_id, "document": document}, headers={"Cache-Control": "no-store"})


@router.post("/api/cad/build")
async def cad_build(request: Request):
    body = await read_json(request, BuildIn)
    require_dependencies()
    document = DOCUMENTS.get(body.document_id)
    from packing_assistant.cad3d.geometry import build_model
    model = await run_in_threadpool(compute, build_model, document, body.config)
    if not model.get("objects"):
        raise HTTPException(422, {"message": "没有可生成的实体，请检查图层、闭合轮廓和参数。", "report": model.get("report", [])})
    model["source"] = {"filename": document["filename"], "sha256": document["sha256"], "units": document["units"]}
    try:
        model_id = MODELS.put(model)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from exc
    return JSONResponse({"ok": True, "model_id": model_id, "model": model}, headers={"Cache-Control": "no-store"})


@router.post("/api/cad/command")
async def cad_command(request: Request):
    body = await read_json(request, CommandIn)
    document = DOCUMENTS.get(body.document_id)
    from packing_assistant.cad3d.commands import apply_command
    value = await run_in_threadpool(compute, apply_command, document, body.config, body.message, body.selected_id)
    return JSONResponse({"ok": True, **value}, headers={"Cache-Control": "no-store"})


def export_model(model: dict, format: str) -> tuple[bytes, str, str]:
    record = {"schema": "civil-buddy.cad3d.parameters.v1", "purpose": "geometry-preview-not-certified-bim",
              **{k: v for k, v in model.items() if k != "objects"},
              "objects": [{k: v for k, v in obj.items() if k not in {"vertices", "faces"}} for obj in model["objects"]]}
    parameters = json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
    if format == "json":
        return parameters, "application/json", "cad-parameters.json"
    from packing_assistant.cad3d.geometry import export_glb
    glb = export_glb(model)
    if format == "glb":
        return glb, "model/gltf-binary", "cad-preview.glb"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cad-preview.glb", glb)
        archive.writestr("cad-parameters.json", parameters)
        archive.writestr("README.txt", "Civil Buddy CAD → 3D\n几何预览模型，不是签认件或完整 BIM。\nGLB 长度单位为米、Y 向上；参数记录保留源图单位、原点变换、来源实体与未处理项。\n")
    return stream.getvalue(), "application/zip", "cad-preview.zip"


@router.post("/api/cad/export")
async def cad_export(request: Request):
    body = await read_json(request, ExportIn)
    if body.confirmation != CONFIRMATION:
        raise HTTPException(403, "导出前请完整键入：" + CONFIRMATION)
    model = MODELS.get(body.model_id)
    data, media_type, filename = await run_in_threadpool(compute, export_model, model, body.format)
    return Response(data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
