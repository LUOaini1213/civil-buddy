"""P2 骨架：VGM 提交接口、证据包、运价、轻量倾覆分（非 FEM）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def tip_slide_score(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    轻量稳性启发式：高重心 + 高 lat + 可叠未支撑 → 倾覆/滑动风险分 0–100（高=差）。
    """
    cog = plan.get("cog") or {}
    if isinstance(cog, dict) and cog.get("primary"):
        cog = cog["primary"]
    hr = float(cog.get("height_ratio") or 0.4)
    lat = float(cog.get("lateral_eccentricity") or 0)
    mid = float(cog.get("mass_in_mid50_ratio") or plan.get("worst_mid50") or 0.5)
    lq = plan.get("layout_quality") or {}
    gap = float(lq.get("max_horizontal_gap_mm") or 0)
    floor_only = 1.0 if lq.get("stackable_floor_only") else 0.0

    tip = max(0.0, (hr - 0.45) / 0.35) * 40.0  # 高度
    slide = min(1.0, lat / 0.12) * 25.0 + min(1.0, gap / 800.0) * 15.0
    mid_pen = max(0.0, 0.55 - mid) / 0.55 * 15.0
    stack_pen = floor_only * 5.0
    risk = min(100.0, tip + slide + mid_pen + stack_pen)
    level = "low" if risk < 30 else ("medium" if risk < 55 else "high")
    return {
        "schema": "stability.tip_slide.v1",
        "risk_score": round(risk, 1),
        "level": level,
        "parts": {
            "tip_from_height": round(tip, 1),
            "slide_from_lat_gap": round(slide, 1),
            "mid50_penalty": round(mid_pen, 1),
            "stack_floor_only": round(stack_pen, 1),
        },
        "note": "启发式，非完整力学仿真",
    }


def draft_vgm_submit(
    state: Dict[str, Any],
    *,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """VGM 提交骨架：默认 dry_run，不调用外部承运人；未人签则硬拦。"""
    from packing_assistant.tools.vgm_draft import is_vgm_signed

    vgm = state.get("vgm_draft") or {}
    if not isinstance(vgm, dict):
        vgm = {}
    rows = vgm.get("per_container") or vgm.get("containers") or []
    signed = is_vgm_signed(state)
    if not signed:
        return {
            "schema": "vgm.submit.v1",
            "status": "blocked_unsigned",
            "dry_run": True,
            "accepted": False,
            "blocks_until_signed": True,
            "human_signoff_required": True,
            "checklist_item_id": "vgm_signed",
            "payload_preview": {
                "method": 2,
                "totals": vgm.get("totals"),
                "containers": (rows or [])[:5],
            },
            "message": (
                "拒绝提交：VGM 尚未托运人签署。"
                "请先 record_human_signoff 或勾选装前检查 vgm_signed。"
            ),
        }
    return {
        "schema": "vgm.submit.v1",
        "status": "dry_run" if dry_run else "not_configured",
        "dry_run": dry_run,
        "accepted": bool(dry_run),
        "payload_preview": {
            "method": 2,
            "totals": vgm.get("totals"),
            "containers": (rows or [])[:5],
        },
        "message": (
            "Dry-run：本地已人签，仍未连接承运人 API。配置 VGM_SUBMIT_URL 后可真提交。"
            if dry_run
            else "承运人端点未配置"
        ),
        "blocks_until_signed": False,
        "human_signoff_required": True,
        "signed_local": True,
    }


def build_evidence_pack(
    state: Dict[str, Any],
    *,
    output_dir: str | Path = "output/evidence",
) -> Dict[str, Any]:
    """索赔/审计证据包骨架：清单 + 路径索引（照片位占位）。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rid = state.get("run_id") or state.get("session_id") or "run"
    folder = out / str(rid)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "evidence.pack.v1",
        "run_id": rid,
        "ts": datetime.now(timezone.utc).isoformat(),
        "items": [
            {"type": "packing_plan", "ref": "state.packing_plan"},
            {"type": "por_manifest", "ref": "state.por_manifest"},
            {"type": "secure_work_order", "ref": "state.secure_work_order"},
            {"type": "side_images", "ref": "state.image_data"},
            {"type": "photo_slot", "id": "door_end", "status": "pending_upload"},
            {"type": "photo_slot", "id": "mid_bay", "status": "pending_upload"},
            {"type": "photo_slot", "id": "seal", "status": "pending_upload"},
        ],
        "note": "照片需现场上传填槽；本包为索引骨架",
    }
    path = folder / "evidence_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["path"] = str(path)
    return manifest


def estimate_freight_stub(
    plan: Dict[str, Any],
    *,
    usd_per_40hq: float = 1200.0,
) -> Dict[str, Any]:
    """运价占位：按用柜数 × 单价。"""
    used = int(plan.get("containers_used") or plan.get("n0") or 1)
    total = used * usd_per_40hq
    return {
        "schema": "freight.estimate.v1",
        "currency": "USD",
        "containers": used,
        "unit_price_40hq": usd_per_40hq,
        "total": total,
        "note": "占位估算，非真实订舱价；对接运价 API 后替换",
    }
