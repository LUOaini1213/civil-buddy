"""
FastAPI 网关：对接主控 Harness + 静态 Vue2 前端。

启动:
  pip install fastapi uvicorn
  set SKJOLBER_URL=http://127.0.0.1:8080
  uvicorn gateway.app:app --reload --port 8000

无管理员：用户目录 JDK17 + Maven 起 skjolber 即可，见 scripts/start_skjolber_user.ps1
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 保证可 import packing_assistant
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 加载仓库根 .env（含 SKJOLBER_URL，无需系统环境变量 / 管理员）
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass
# 默认指向本机 skjolber（服务未起时 health 会 fail，装载回退 Python 3D）
if not (os.getenv("SKJOLBER_URL") or "").strip():
    os.environ["SKJOLBER_URL"] = "http://127.0.0.1:8080"

from packing_assistant.harness import (  # noqa: E402
    apply_user_confirmation,
    public_response,
    run_agent_pipeline,
    run_pipeline,
    run_team_a,
    run_team_b,
)
from packing_assistant.skjolber_client import health_check  # noqa: E402

# 简易会话缓存（生产请换 Redis）
_SESSIONS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="Packing Multi-Agent Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class TeamARequest(BaseModel):
    user_input: str = ""
    session_id: str = "default"
    materials: Optional[List[Dict[str, Any]]] = None
    adjust_note: str = ""


class ConfirmRequest(BaseModel):
    session_id: str = "default"
    packing_plan_id: str = ""
    action: str = Field(..., description="confirm | revise | cancel")
    container_type: str = "40HQ"
    # 0 = 自主定柜（N0 起 3D 递增），禁止把业务目标写死成 2
    max_containers: int = 0
    adjust_note: str = ""
    confirmed_box_ids: List[str] = Field(default_factory=list)


class DemoRequest(BaseModel):
    user_input: str = "演示材料清单"
    container_type: str = "40HQ"
    session_id: str = "demo"


@app.get("/")
def index():
    index_html = FRONTEND_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return {"message": "frontend/index.html missing", "docs": "/docs"}


@app.get("/api/health")
def api_health():
    sk = health_check()
    return {
        "gateway": "UP",
        "skjolber_url": os.getenv("SKJOLBER_URL") or "",
        "skjolber": sk,
    }


@app.post("/api/team-a")
def api_team_a(body: TeamARequest):
    state = run_team_a(
        body.user_input,
        materials=body.materials,
        session_id=body.session_id,
        adjust_note=body.adjust_note,
    )
    _SESSIONS[body.session_id] = state
    return public_response(state)


@app.post("/api/confirm")
def api_confirm(body: ConfirmRequest):
    state = _SESSIONS.get(body.session_id)
    if not state:
        raise HTTPException(400, "session 不存在，请先调用 /api/team-a")

    if body.action == "cancel":
        state = {**state, "phase": "cancelled", "user_action": "cancel",
                 "final_response": "已取消", "status": "success"}
        _SESSIONS[body.session_id] = state
        return public_response(state)

    if body.action == "revise":
        state = run_team_a(
            state.get("user_input") or "",
            materials=state.get("materials"),
            session_id=body.session_id,
            adjust_note=body.adjust_note or "用户调整",
        )
        _SESSIONS[body.session_id] = state
        return public_response(state)

    if body.action != "confirm":
        raise HTTPException(400, "action 必须是 confirm | revise | cancel")

    state = apply_user_confirmation(
        state,
        action="confirm",
        container_type=body.container_type,
        max_containers=body.max_containers,
        adjust_note=body.adjust_note,
        confirmed_box_ids=body.confirmed_box_ids,
    )
    state = run_team_b(state)
    _SESSIONS[body.session_id] = state
    return public_response(state)


class PipelineRequest(BaseModel):
    """单一 Agent 闭环入口：材料→…→风险→出图→裁决，落盘 + 可下载路径。"""

    user_input: str = "Agent pipeline"
    materials: Optional[List[Dict[str, Any]]] = None
    container_type: str = "40HQ"
    session_id: str = "pipeline"
    max_containers: int = 0
    # True=跳过确认闸门自动跑到 finalize；False=停在 HITL
    enable_auto_confirm: bool = True
    goal: str = Field(
        default="deliver_valid_pack_plan",
        description="deliver_valid_pack_plan | minimize_containers | safe_to_ship",
    )
    save_artifacts: bool = True
    # graph=LangGraph 全图；steps=逐步 9 Agent 显式 trace（推荐答辩）
    mode: str = "steps"


@app.post("/api/demo")
def api_demo(body: DemoRequest):
    """兼容入口：全自动闭环 + 落盘（等同 /api/pipeline auto）。"""
    state = run_agent_pipeline(
        body.user_input,
        container_type=body.container_type,
        enable_auto_confirm=True,
        max_containers=0,
        session_id=body.session_id,
        save_artifacts=True,
    )
    _SESSIONS[body.session_id] = state
    resp = public_response(state)
    resp["agent_loop"] = "感知→规划→工具→行动→finalize"
    return resp


@app.post("/api/pipeline")
def api_pipeline(body: PipelineRequest):
    """
    **Agent 单一入口**：自动跑全程（可开关 confirm）→ finalize。

    返回：goal_status、agent_steps（tool 轨迹）、artifact_paths（落盘可下载）。
    """
    if (body.mode or "steps").lower() == "graph":
        state = run_pipeline(
            body.user_input,
            materials=body.materials,
            container_type=body.container_type,
            enable_auto_confirm=body.enable_auto_confirm,
            max_containers=int(body.max_containers or 0),
            goal=body.goal,
            save_artifacts=body.save_artifacts,
        )
        steps = state.get("agent_steps") or []
    else:
        state = run_agent_pipeline(
            body.user_input,
            materials=body.materials,
            container_type=body.container_type,
            max_containers=int(body.max_containers or 0),
            enable_auto_confirm=body.enable_auto_confirm,
            goal=body.goal,
            session_id=body.session_id,
            save_artifacts=body.save_artifacts,
        )
        steps = state.get("agent_steps") or []

    _SESSIONS[body.session_id] = state
    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    paths = state.get("artifact_paths") or {}
    return {
        "ok": True,
        "agent_definition": {
            "style": "multi_agent_workflow",
            "goal": state.get("goal") or body.goal,
            "capabilities": ["感知环境", "推理与规划", "使用工具", "采取行动", "追求目标"],
            "loop": "感知清单与状态 → 规划订柜策略 → 调用成箱/3D/风险工具 → 生成方案与图 → 推进至可裁决结论（可 HITL）",
            "note": "分角色流水线；数值由 tools 计算，非 LLM 编造",
        },
        "run_id": state.get("run_id"),
        "artifact_paths": paths,
        "goal_status": state.get("goal_status") or {},
        "perception": state.get("perception") or state.get("materials_summary") or {},
        "planning_reasons": (state.get("plan") or {}).get("planning_reasons") or [],
        "steps": steps,
        "summary": {
            "boxes": len(state.get("boxes") or []),
            "n0": book.get("n0") or plan.get("n0"),
            "containers_used": plan.get("containers_used"),
            "can_fit": plan.get("can_fit"),
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
            "outer_space_utilization": plan.get("outer_space_utilization")
            or plan.get("space_utilization"),
            "weight_utilization": plan.get("weight_utilization"),
            "risk_decision": (state.get("risk_report") or {}).get("decision"),
            "suggested_actions": (state.get("risk_report") or {}).get("suggested_actions")
            or [],
            "ship_ok": state.get("ship_ok"),
            "phase": state.get("phase"),
        },
        "public": public_response(state),
    }


class TraceRequest(BaseModel):
    """逐步返回各 Agent 摘要，用于证明 Agent 链路在跑。"""

    user_input: str = "Agent API trace"
    materials: Optional[List[Dict[str, Any]]] = None
    container_type: str = "40HQ"
    session_id: str = "trace"
    max_containers: int = 0
    goal: str = "deliver_valid_pack_plan"
    enable_auto_confirm: bool = True


@app.post("/api/pipeline/trace")
def api_pipeline_trace(body: TraceRequest):
    """
    兼容入口：等同 POST /api/pipeline mode=steps。
    本地逐步调用 9 Agent，返回每步 message + tools_used + 落盘路径。
    """
    state = run_agent_pipeline(
        body.user_input,
        materials=body.materials,
        container_type=body.container_type,
        max_containers=int(body.max_containers or 0),
        enable_auto_confirm=body.enable_auto_confirm,
        goal=body.goal,
        session_id=body.session_id,
        save_artifacts=True,
    )
    _SESSIONS[body.session_id] = state
    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    steps = state.get("agent_steps") or []
    return {
        "ok": True,
        "agent_definition": {
            "style": "multi_agent_workflow",
            "goal": state.get("goal") or "deliver_valid_pack_plan",
            "capabilities": ["感知", "规划", "使用工具", "采取行动", "追求目标(任务域)"],
            "note": "分角色流水线，非单体全能聊天 Agent；数值由 tools 计算",
        },
        "note": "数字由 tools 计算；Agent 负责任务分工、闸门、结构/风险裁决与过程可解释",
        "run_id": state.get("run_id"),
        "artifact_paths": state.get("artifact_paths") or {},
        "goal_status": state.get("goal_status") or {},
        "steps": steps,
        "summary": {
            "boxes": len(state.get("boxes") or []),
            "n0": book.get("n0") or plan.get("n0"),
            "containers_used": plan.get("containers_used"),
            "can_fit": plan.get("can_fit"),
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
            "outer_space_utilization": plan.get("outer_space_utilization")
            or plan.get("space_utilization"),
            "weight_utilization": plan.get("weight_utilization"),
            "risk_decision": (state.get("risk_report") or {}).get("decision"),
            "phase": state.get("phase"),
        },
        "public": public_response(state),
    }


@app.get("/api/session/{session_id}")
def api_session(session_id: str):
    state = _SESSIONS.get(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return public_response(state)


@app.get("/api/test-shipments")
def api_test_shipments():
    """读取 test 跑批汇总。"""
    p = ROOT / "output" / "test_shipments" / "summary.json"
    if not p.exists():
        return {"ok": False, "message": "尚未跑批，请先 python scripts/run_test_shipments.py"}
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/test-shipments/report")
def api_test_report():
    p = ROOT / "output" / "test_shipments" / "report.html"
    if not p.exists():
        raise HTTPException(404, "report.html 不存在，请先跑批")
    return FileResponse(p)


class PdfRunRequest(BaseModel):
    filename: str = ""
    container_type: str = "40HQ"
    session_id: str = "pdf-run"
    # project=同一 PDF 全部材料拼柜；per_container=仅第一柜（旧行为）
    mode: str = "project"


@app.post("/api/run-pdf")
def api_run_pdf(body: PdfRunRequest):
    """解析 test 下指定 PDF：默认同一项目拼柜（全部材料合并优化柜数）。"""
    from packing_assistant.tools.packing_list_parser import parse_packing_list_pdf
    from packing_assistant.tools.dims_override import apply_dims_override

    test_dir = ROOT / "test"
    path = None
    if body.filename:
        cand = test_dir / body.filename
        if cand.exists():
            path = cand
    if path is None:
        pdfs = sorted(test_dir.glob("*.pdf"))
        if not pdfs:
            raise HTTPException(404, "test/ 下无 PDF")
        path = pdfs[0]

    pl = parse_packing_list_pdf(path)
    mats = apply_dims_override(pl.get("materials") or [])
    if not mats:
        raise HTTPException(400, f"未能从 {path.name} 解析材料")

    mode = (body.mode or "project").strip().lower()
    pdf_ctns = pl.get("containers") or []
    if mode == "per_container":
        ctn = pdf_ctns[0] if pdf_ctns else None
        group = [m for m in mats if m.get("container_no") == ctn] if ctn else mats
        if not group:
            group = mats
        label = f"PDF:{path.name}:{ctn or 'ALL'}"
    else:
        # 同一项目：合并全部材料
        ctn = ",".join(pdf_ctns) if pdf_ctns else "PROJECT"
        group = mats
        label = f"PDF:{path.name}:PROJECT"

    # 按净重粗估柜数，避免整票重货 can_fit=False
    net = sum(float(m.get("total_weight_kg") or 0) for m in group)
    max_ctn = min(max(int(net / 18000) + 1, 1), 12)

    state = run_pipeline(
        raw_input=label,
        materials=group,
        container_type=body.container_type,
        enable_auto_confirm=True,
        max_containers=max_ctn,
    )
    # 若估少了，逐步加柜
    plan = state.get("container_plan") or {}
    if not plan.get("can_fit"):
        for mc in range(max_ctn + 1, 13):
            state = run_pipeline(
                raw_input=label,
                materials=group,
                container_type=body.container_type,
                enable_auto_confirm=True,
                max_containers=mc,
            )
            plan = state.get("container_plan") or {}
            if plan.get("can_fit"):
                break

    _SESSIONS[body.session_id] = state
    resp = public_response(state)
    resp["pdf_file"] = path.name
    resp["container_no"] = ctn
    resp["mode"] = mode
    resp["materials_used"] = len(group)
    resp["pdf_containers"] = pdf_ctns
    return resp
