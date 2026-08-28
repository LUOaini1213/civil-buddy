"""PackingPlan 工件：可版本化、可 HITL/审计 的装柜方案摘要。

LLM 不得写入 placements 坐标；仅由 loader/bin3d 等确定性工具生成。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SCHEMA = "packing.plan.v1"


def build_packing_plan(
    state: Dict[str, Any],
    *,
    plan_id: Optional[str] = None,
    previous: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从 pipeline state 组装标准 PackingPlan。"""
    plan = state.get("container_plan") or {}
    boxes = list(state.get("boxes") or [])
    evaluation = state.get("evaluation") or {}
    risk = state.get("risk_report") or {}
    packing_opts = dict(state.get("packing_options") or {})

    layout = list(plan.get("layout") or [])
    cog = (
        plan.get("cog")
        or state.get("cog")
        or risk.get("cog")
        or {}
    )
    if isinstance(cog, dict) and cog.get("primary"):
        cog_primary = cog["primary"]
    else:
        cog_primary = cog if isinstance(cog, dict) else {}

    stacking = dict(plan.get("stacking") or {})
    layout_quality = dict(plan.get("layout_quality") or risk.get("layout_quality") or {})
    cog_bundle = plan.get("cog_bundle") or state.get("cog_bundle") or {}

    unpacked = list(plan.get("unpacked_box_ids") or [])
    fail_reasons: List[str] = []
    if not plan.get("can_fit"):
        fail_reasons.append(str(plan.get("message") or "can_fit=false"))
    if unpacked:
        fail_reasons.append(f"unpacked={len(unpacked)}")
    for b in risk.get("blockers") or []:
        fail_reasons.append(f"risk:{b}")
    if evaluation.get("decision") in ("FAIL", "REJECT_STRUCTURE", "REPLAN"):
        fail_reasons.append(f"eval:{evaluation.get('decision')}")

    version = 1
    if previous and isinstance(previous, dict):
        try:
            version = int(previous.get("version") or 0) + 1
        except Exception:
            version = 1

    # —— 分柜 mid50 表 ——
    per_cabin: List[Dict[str, Any]] = []
    for c in cog_bundle.get("per_container") or []:
        if not isinstance(c, dict):
            continue
        mid = c.get("mass_in_mid50_ratio")
        per_cabin.append(
            {
                "container_no": c.get("container_no"),
                "mass_in_mid50_ratio": mid,
                "mid50_ok": bool(c.get("mid50_ok"))
                if c.get("mid50_ok") is not None
                else (float(mid or 0) >= 0.60),
                "lateral_eccentricity": c.get("lateral_eccentricity"),
                "longitudinal_position": c.get("longitudinal_position"),
                "height_ratio": c.get("height_ratio"),
                "balance": c.get("balance"),
                "gross_kg": c.get("gross_kg") or c.get("total_mass_kg"),
            }
        )
    per_cabin.sort(key=lambda r: int(r.get("container_no") or 0))

    # —— R0–R4 / LNS / 横偏 before→after ——
    def _ba(prefix: str) -> Dict[str, Any]:
        b = stacking.get(f"{prefix}_mid50_before")
        a = stacking.get(f"{prefix}_mid50_after")
        applied = stacking.get(f"{prefix}_applied") or stacking.get(f"{prefix}_repair_applied")
        if prefix == "lns":
            applied = stacking.get("lns_applied")
            b = stacking.get("lns_mid50_before")
            a = stacking.get("lns_mid50_after")
        if prefix == "lateral":
            applied = stacking.get("lateral_repair_applied")
            return {
                "step": "lateral",
                "applied": bool(applied),
                "lat_before": stacking.get("lat_before"),
                "lat_after": stacking.get("lat_after"),
            }
        return {
            "step": prefix,
            "applied": bool(applied),
            "mid50_before": b,
            "mid50_after": a,
        }

    r_pipeline = [
        {
            "step": "R0",
            "applied": stacking.get("r0_ok") is not None,
            "ok": stacking.get("r0_ok"),
            "mid50_before": stacking.get("r0_worst_mid50_before"),
            "mid50_after": stacking.get("r0_worst_mid50_after"),
        },
        {
            "step": "R1",
            "applied": bool(stacking.get("r1_applied")),
            "shift": stacking.get("r1_shift_applied"),
            "mirror": stacking.get("r1_mirror_applied"),
            "mid50_before": stacking.get("r0_worst_mid50_before"),
            "mid50_after": stacking.get("r0_worst_mid50_after"),
        },
        _ba("r2"),
        _ba("r4"),
        {
            "step": "R3",
            "applied": bool(stacking.get("r3_applied") or packing_opts.get("r3_repack")),
            "note": "partial repack worst cabin",
        },
        _ba("lns"),
        _ba("lateral"),
    ]
    # 规范化 step 名
    for row in r_pipeline:
        if row.get("step") == "r2":
            row["step"] = "R2"
            row["applied"] = bool(stacking.get("r2_slab_applied"))
            row["mid50_before"] = stacking.get("r2_mid50_before")
            row["mid50_after"] = stacking.get("r2_mid50_after")
        if row.get("step") == "r4":
            row["step"] = "R4"
            row["applied"] = bool(stacking.get("r4_repair_applied"))
            row["mid50_before"] = stacking.get("r4_mid50_before")
            row["mid50_after"] = stacking.get("r4_mid50_after")
        if row.get("step") == "lns":
            row["step"] = "LNS"
        if row.get("step") == "lateral":
            row["step"] = "LAT"

    secure = state.get("secure_work_order")
    if not isinstance(secure, dict) or not secure.get("items"):
        try:
            from packing_assistant.tools.secure_work_order import build_secure_work_order

            secure = build_secure_work_order(plan, boxes)
        except Exception:
            secure = {}

    pid = plan_id or state.get("packing_plan_id") or state.get("run_id") or "plan"
    return {
        "schema": SCHEMA,
        "plan_id": str(pid),
        "version": version,
        "ts": datetime.now(timezone.utc).isoformat(),
        "container_type": plan.get("container_type")
        or state.get("container_type")
        or "40HQ",
        "containers_used": plan.get("containers_used"),
        "can_fit": bool(plan.get("can_fit")),
        "engine": plan.get("engine"),
        "n0": plan.get("n0"),
        "metrics": {
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
            "outer_space_utilization": plan.get("outer_space_utilization")
            or plan.get("space_utilization"),
            "weight_utilization": plan.get("weight_utilization"),
            "floor_utilization_avg": plan.get("floor_utilization_avg")
            or plan.get("floor_utilization"),
            "worst_mid50": plan.get("worst_mid50") or cog_bundle.get("worst_mid50"),
        },
        "stacking": stacking,
        "cog": {
            "mass_in_mid50_ratio": cog_primary.get("mass_in_mid50_ratio"),
            "mid50_ok": cog_primary.get("mid50_ok"),
            "longitudinal_position": cog_primary.get("longitudinal_position"),
            "lateral_eccentricity": cog_primary.get("lateral_eccentricity"),
            "height_ratio": cog_primary.get("height_ratio"),
            "balance": cog_primary.get("balance"),
            "worst_mid50": plan.get("worst_mid50") or cog_bundle.get("worst_mid50"),
        },
        "per_cabin_cog": per_cabin,
        "r_pipeline": r_pipeline,
        "secure_work_order": secure,
        "por_manifest": state.get("por_manifest")
        if isinstance(state.get("por_manifest"), dict)
        else {},
        "profile_id": packing_opts.get("profile_id"),
        "layout_quality": layout_quality,
        "placements_count": len(layout),
        "boxes_count": len(boxes),
        "unpacked_box_ids": unpacked[:50],
        "fail_reasons": fail_reasons[:20],
        "packing_options": {
            k: packing_opts.get(k)
            for k in (
                "prefer_stack",
                "export_strict",
                "clearance_mm",
                "multi_start",
                "cog_aware",
                "max_stack_layers",
                "dense_mode",
                "lns_worst",
                "lateral_repair",
            )
            if k in packing_opts or packing_opts.get(k) is not None
        },
        "evaluation": {
            "score": evaluation.get("score"),
            "decision": evaluation.get("decision"),
            "need_replan": evaluation.get("need_replan"),
            "passed": evaluation.get("passed"),
        },
        "risk": {
            "decision": risk.get("decision"),
            "level": risk.get("level"),
            "blockers_n": len(risk.get("blockers") or []),
            "export_strict": risk.get("export_strict"),
            "ship_ok": risk.get("ship_ok"),
        },
        "invariants": {
            "llm_must_not_set_placements": True,
            "geometry_from": "bin3d|skjolber|fallback",
            "secure_work_order_blocks_ship_ok": False,
        },
        "layout_ref": "container_plan.layout",
    }


def attach_packing_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """写入 state['packing_plan']，返回增量。"""
    prev = state.get("packing_plan")
    pp = build_packing_plan(state, previous=prev if isinstance(prev, dict) else None)
    return {"packing_plan": pp, "packing_plan_id": pp.get("plan_id")}
