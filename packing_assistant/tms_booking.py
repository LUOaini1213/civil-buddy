"""TMS / 订舱接口（适配层）。

产品边界：
  - 装柜 Agent 产出 N0、柜数、箱清单、POR/VGM 草稿
  - 本模块把「订舱请求」标准化，可对接外部 TMS（HTTP stub 或内存）

环境:
  PACKING_TMS_URL       外部 TMS base URL（空=本地 stub）
  PACKING_TMS_API_KEY   可选 Bearer
  PACKING_TMS_MODE      stub | http（默认 stub）
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from packing_assistant.config import TRACE_DIR


def tms_mode() -> str:
    m = (os.getenv("PACKING_TMS_MODE") or "stub").strip().lower()
    if m in ("http", "remote", "api"):
        return "http"
    return "stub"


def tms_base_url() -> str:
    return (os.getenv("PACKING_TMS_URL") or "").rstrip("/")


def build_booking_request(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 PackingState 构建标准订舱请求（TMS 入站契约）。"""
    plan = state.get("container_plan") or {}
    booking = state.get("plan") or {}
    book = booking.get("booking") or plan.get("booking") or {}
    ispec = state.get("intent_spec") or {}
    boxes = state.get("boxes") or []
    materials = state.get("materials") or []
    n0 = plan.get("n0") or book.get("n0") or booking.get("n0")
    used = plan.get("containers_used")
    ctype = state.get("container_type") or "40HQ"

    lines: List[Dict[str, Any]] = []
    for b in boxes[:200]:
        if not isinstance(b, dict):
            continue
        lines.append(
            {
                "box_id": b.get("id") or b.get("box_id"),
                "name": b.get("name") or b.get("label"),
                "L_mm": b.get("outer_L") or b.get("L") or b.get("length_mm"),
                "W_mm": b.get("outer_W") or b.get("W") or b.get("width_mm"),
                "H_mm": b.get("outer_H") or b.get("H") or b.get("height_mm"),
                "net_kg": b.get("net_kg") or b.get("weight_kg"),
                "gross_kg": b.get("gross_kg") or b.get("total_weight_kg"),
            }
        )

    req = {
        "schema": "packing.tms.booking_request.v1",
        "request_id": f"bk-{uuid.uuid4().hex[:12]}",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": state.get("session_id"),
        "run_id": state.get("run_id"),
        "source": "packing_assistant",
        "intent": {
            "raw_nl": ispec.get("raw_nl") or state.get("user_input"),
            "scheme_id": ispec.get("scheme_id"),
            "cargo_mode": ispec.get("cargo_mode"),
            "container_budget": ispec.get("container_budget"),
            "goal": state.get("goal"),
        },
        "equipment": {
            "container_type": ctype,
            "n0_estimate": n0,
            "containers_used_3d": used,
            "request_qty": int(used or n0 or 1),
            "lock_budget": bool(
                (state.get("packing_options") or {}).get("lock_max_containers")
            ),
        },
        "cargo": {
            "n_materials": len(materials),
            "n_boxes": len(boxes),
            "net_kg": sum(
                float(m.get("total_weight_kg") or m.get("weight_kg") or 0)
                for m in materials
                if isinstance(m, dict)
            ),
            "box_lines": lines,
        },
        "compliance": {
            "can_fit": plan.get("can_fit"),
            "ship_ok": state.get("ship_ok"),
            "risk_decision": (state.get("risk_report") or {}).get("decision"),
            "worst_mid50": plan.get("worst_mid50"),
        },
        "artifacts": {
            "por_manifest": bool(
                state.get("por_manifest")
                or (state.get("packing_plan") or {}).get("por_manifest")
            ),
            "vgm_draft": bool(state.get("vgm_draft")),
            "secure_work_order": bool(
                state.get("secure_work_order")
                or (state.get("packing_plan") or {}).get("secure_work_order")
            ),
        },
        "booking_detail": {
            "binding_constraint": book.get("binding_constraint"),
            "booking_volume_m3": book.get("volume_m3")
            or plan.get("booking_volume_m3"),
            "weight_utilization": plan.get("weight_utilization"),
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
        },
    }
    return req


def _stub_submit(req: Dict[str, Any]) -> Dict[str, Any]:
    """本地 stub：落盘并返回伪订舱号。"""
    out_dir = Path(TRACE_DIR).resolve().parent / "tms"
    out_dir.mkdir(parents=True, exist_ok=True)
    bid = f"STUB-{req.get('request_id', uuid.uuid4().hex[:8])}"
    path = out_dir / f"{bid}.json"
    resp = {
        "ok": True,
        "mode": "stub",
        "booking_id": bid,
        "status": "draft_accepted",
        "message": "本地 stub 已接受订舱草稿（未连真实 TMS）",
        "request_id": req.get("request_id"),
        "equipment_confirmed": req.get("equipment"),
        "next_actions": [
            "人工在 TMS 确认柜型与船期",
            "回写 booking_id 到 session",
            "出运前刷新 VGM / 装货顺序",
        ],
        "stored_path": str(path),
    }
    path.write_text(
        json.dumps({"request": req, "response": resp}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resp


def _http_submit(req: Dict[str, Any]) -> Dict[str, Any]:
    base = tms_base_url()
    if not base:
        return {
            "ok": False,
            "mode": "http",
            "error": "PACKING_TMS_URL 未配置",
        }
    url = f"{base}/api/v1/bookings"
    headers = {"Content-Type": "application/json"}
    key = (os.getenv("PACKING_TMS_API_KEY") or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        import urllib.request

        data = json.dumps(req, ensure_ascii=False).encode("utf-8")
        r = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(r, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {"raw": body}
            return {
                "ok": True,
                "mode": "http",
                "http_status": getattr(resp, "status", 200),
                "response": parsed,
            }
    except Exception as e:
        return {"ok": False, "mode": "http", "error": str(e), "url": url}


def submit_booking(
    state: Dict[str, Any],
    *,
    mode: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    提交订舱。

    dry_run=True：只构建 request 不提交。
    """
    req = build_booking_request(state)
    if dry_run:
        return {
            "ok": True,
            "mode": "dry_run",
            "request": req,
            "message": "仅预览订舱请求，未提交",
        }
    m = (mode or tms_mode()).lower()
    if m == "http":
        resp = _http_submit(req)
    else:
        resp = _stub_submit(req)
    resp["request"] = req
    # 回写摘要到 state 友好字段
    resp["booking_summary"] = {
        "booking_id": resp.get("booking_id")
        or (resp.get("response") or {}).get("booking_id"),
        "status": resp.get("status") or (resp.get("response") or {}).get("status"),
        "container_type": (req.get("equipment") or {}).get("container_type"),
        "request_qty": (req.get("equipment") or {}).get("request_qty"),
        "can_fit": (req.get("compliance") or {}).get("can_fit"),
        "ship_ok": (req.get("compliance") or {}).get("ship_ok"),
    }
    return resp


def attach_booking_to_state(
    state: Dict[str, Any], booking_result: Dict[str, Any]
) -> Dict[str, Any]:
    """把订舱结果写入 state（不改布局）。"""
    s = dict(state)
    s["tms_booking"] = {
        "booking_id": (booking_result.get("booking_summary") or {}).get("booking_id")
        or booking_result.get("booking_id"),
        "status": (booking_result.get("booking_summary") or {}).get("status")
        or booking_result.get("status"),
        "mode": booking_result.get("mode"),
        "ok": booking_result.get("ok"),
        "request_id": (booking_result.get("request") or {}).get("request_id"),
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": booking_result.get("booking_summary") or {},
    }
    return s


def list_stub_bookings(limit: int = 20) -> List[Dict[str, Any]]:
    out_dir = Path(TRACE_DIR).resolve().parent / "tms"
    if not out_dir.is_dir():
        return []
    files = sorted(out_dir.glob("STUB-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for p in files[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            resp = data.get("response") or {}
            req = data.get("request") or {}
            rows.append(
                {
                    "path": str(p),
                    "booking_id": resp.get("booking_id"),
                    "status": resp.get("status"),
                    "request_id": req.get("request_id"),
                    "session_id": req.get("session_id"),
                    "request_qty": (req.get("equipment") or {}).get("request_qty"),
                }
            )
        except Exception:
            continue
    return rows
