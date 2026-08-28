"""What-if：在现有 state 上改约束/过滤材料，重跑同一 Team 闭环，产出 plan_diff。

OptiGuide 风格：求解器重算，LLM 不写坐标。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence


SCENARIOS = {
    "lock_containers": "锁定 max_containers（预算柜）",
    "plus_one_container": "允许比当前多用 1 柜",
    "minus_one_container": "尝试少 1 柜（锁柜）",
    "strict_mid50": "严格 mid50≥55% + cog_rebalance",
    "prefer_min_cabin": "优先少柜（关闭密装锁柜外的加柜偏好）",
    "iron_only": "仅保留铁件/架类材料行",
    "no_long": "排除超长件(L≥6000)",
    "dense_passthrough": "强制当量直通+密装",
}


def list_whatif_scenarios() -> List[Dict[str, str]]:
    return [{"id": k, "label": v} for k, v in SCENARIOS.items()]


def _filter_materials(
    mats: Sequence[Dict[str, Any]], scenario: str
) -> List[Dict[str, Any]]:
    """兼容旧 scenario 名；新逻辑优先走 nl 的 apply_material_selection。"""
    out = [dict(m) for m in mats]
    if scenario in ("iron_only", "keep_iron_family", "material_family_select"):
        # 旧名保留但收紧：仅 FST/铁件族，不用宽泛「架」
        from packing_assistant.nl_whatif import classify_material

        filtered = [
            m
            for m in out
            if classify_material(m) in ("iron", "stainless")
        ]
        return filtered or out
    if scenario in ("no_long", "material_drop_long"):
        return [
            m
            for m in out
            if float(m.get("length_mm") or m.get("L") or 0) < 6000
        ]
    return out


def apply_whatif_to_options(
    base_opts: Optional[Dict[str, Any]],
    *,
    scenario: str,
    max_containers: Optional[int] = None,
    base_used: Optional[int] = None,
) -> Dict[str, Any]:
    opts = dict(base_opts or {})
    used = int(base_used or 0)
    if scenario == "lock_containers" and max_containers:
        opts["lock_max_containers"] = True
        opts["fixed_container_budget"] = True
        opts["meeting_cap"] = True
        opts["container_budget"] = int(max_containers)
    elif scenario == "plus_one_container":
        opts["lock_max_containers"] = False
        if max_containers:
            opts["container_budget"] = int(max_containers)
        elif used:
            opts["container_budget"] = used + 1
    elif scenario == "minus_one_container":
        n = max(1, (max_containers or used or 2) - 1)
        opts["lock_max_containers"] = True
        opts["fixed_container_budget"] = True
        opts["meeting_cap"] = True
        opts["container_budget"] = n
    elif scenario == "strict_mid50":
        opts["cog_aware"] = True
        opts["cog_rebalance"] = True
        opts["r4_target_mid50"] = 0.55
        opts["lns_worst"] = True
        opts["lateral_repair"] = True
        opts["lat_threshold"] = 0.08
        opts["export_strict"] = False  # 仍可 WARN 出运；严格仅抬目标
    elif scenario == "prefer_min_cabin":
        opts["prefer_stack"] = True
        opts["multi_start"] = True
        opts["cog_aware"] = True
    elif scenario == "dense_passthrough":
        opts["crate_passthrough"] = True
        opts["dense_mode"] = True
        opts["standard_boxes"] = False
    # 通用
    opts["single_team_loop"] = True
    opts.setdefault("multi_start", True)
    opts.setdefault("cog_aware", True)
    return opts


def resolve_max_containers(
    scenario: str,
    *,
    request_max: Optional[int],
    base_used: Optional[int],
    base_n0: Optional[int],
) -> int:
    if scenario == "lock_containers" and request_max:
        return max(1, int(request_max))
    if scenario == "plus_one_container":
        base = int(request_max or base_used or base_n0 or 1)
        return base + 1 if not request_max else max(1, int(request_max))
    if scenario == "minus_one_container":
        base = int(request_max or base_used or base_n0 or 2)
        return max(1, base - 1 if not request_max else int(request_max))
    if request_max and int(request_max) > 0:
        return int(request_max)
    # 0 = 自主定柜
    return 0


def snapshot_for_diff(state: Dict[str, Any]) -> Dict[str, Any]:
    """把 pipeline state 压成 plan_diff 友好快照。"""
    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    cog = plan.get("cog") or state.get("cog") or {}
    if isinstance(cog, dict) and cog.get("primary"):
        cog = cog["primary"]
    pp = state.get("packing_plan") or {}
    risk = state.get("risk_report") or {}
    ev = state.get("evaluation") or {}
    return {
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0") or book.get("n0"),
        "weight_utilization": plan.get("weight_utilization"),
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "worst_mid50": plan.get("worst_mid50")
        or (pp.get("metrics") or {}).get("worst_mid50"),
        "metrics": {
            "weight_utilization": plan.get("weight_utilization"),
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
            "outer_space_utilization": plan.get("outer_space_utilization")
            or plan.get("space_utilization"),
            "floor_utilization": plan.get("floor_utilization")
            or plan.get("floor_utilization_avg"),
            "worst_mid50": plan.get("worst_mid50"),
        },
        "stacking": plan.get("stacking") or {},
        "cog": {
            "mass_in_mid50_ratio": cog.get("mass_in_mid50_ratio")
            or plan.get("worst_mid50"),
            "lateral_eccentricity": cog.get("lateral_eccentricity"),
            "longitudinal_position": cog.get("longitudinal_position"),
            "balance": cog.get("balance"),
        },
        "evaluation": {
            "score": ev.get("score"),
            "decision": ev.get("decision"),
        },
        "risk": {
            "decision": risk.get("decision"),
            "ship_ok": risk.get("ship_ok")
            if risk.get("ship_ok") is not None
            else state.get("ship_ok"),
        },
        "ship_ok": state.get("ship_ok") or risk.get("ship_ok"),
        "secure_items": len(
            (state.get("secure_work_order") or {}).get("items")
            or (pp.get("secure_work_order") or {}).get("items")
            or []
        ),
    }


def run_whatif(
    base_state: Dict[str, Any],
    *,
    scenario: str = "",
    max_containers: Optional[int] = None,
    user_input: str = "",
    session_id: str = "",
    nl_query: str = "",
    profile: str = "",
) -> Dict[str, Any]:
    """
    基于 base_state 材料/选项跑 what-if。
    支持 nl_query 自动解析 scenario；返回 score 对比 after_is_better。
    """
    from packing_assistant.harness import public_response, run_agent_pipeline
    from packing_assistant.tools.plan_diff import diff_packing_plans
    from packing_assistant.score_plan import compare_plans
    from packing_assistant.nl_whatif import parse_nl_whatif
    from packing_assistant.packing_profiles import apply_profile

    mats = list(base_state.get("materials") or [])
    if not mats:
        return {"ok": False, "error": "base_state 无 materials，请先跑 /api/pipeline"}

    plan0 = base_state.get("container_plan") or {}
    book0 = base_state.get("booking") or plan0.get("booking") or {}
    used0 = int(plan0.get("containers_used") or 0)
    n0_0 = int(plan0.get("n0") or book0.get("n0") or 0)

    nl_parsed = None
    # 始终带物料画像解析（有 NL 时）；无 NL 但有 scenario 则仅用旧路径
    if nl_query or user_input or not scenario:
        nl_parsed = parse_nl_whatif(nl_query or user_input or "", materials=mats)
        scenario = scenario or nl_parsed.get("scenario") or "material_adaptive"
        if max_containers is None and nl_parsed.get("max_containers"):
            max_containers = nl_parsed["max_containers"]
        if not profile and nl_parsed.get("profile"):
            profile = nl_parsed["profile"]

    # 新 scenario 名放行
    allowed = set(SCENARIOS) | {
        "custom",
        "material_adaptive",
        "material_family_select",
        "material_drop_long",
        "keep_iron_family",
    }
    if scenario not in allowed:
        return {
            "ok": False,
            "error": f"unknown scenario: {scenario}",
            "scenarios": list_whatif_scenarios(),
            "nl_parsed": nl_parsed,
        }

    # —— 选料：优先物料感知 ——
    mats2: List[Dict[str, Any]]
    if nl_parsed and (nl_query or user_input):
        from packing_assistant.nl_whatif import apply_material_selection

        mats2, sel_notes = apply_material_selection(mats, nl_parsed)
        if nl_parsed.get("notes") is not None and sel_notes:
            # 已含在 notes
            pass
    else:
        mats2 = _filter_materials(mats, scenario)

    # —— options：NL 已按 cargo_mode 生成则合并 ——
    opts = apply_whatif_to_options(
        base_state.get("packing_options"),
        scenario=scenario if scenario in SCENARIOS else "prefer_min_cabin",
        max_containers=max_containers,
        base_used=used0,
    )
    if nl_parsed and isinstance(nl_parsed.get("packing_options"), dict):
        # 物料自适应 options 覆盖默认
        for k, v in nl_parsed["packing_options"].items():
            if k in ("scheme_reason", "lock_weight_warning"):
                continue
            opts[k] = v
    if profile:
        opts = apply_profile(opts, profile)
    mc = resolve_max_containers(
        scenario if scenario in SCENARIOS else "lock_containers",
        request_max=max_containers,
        base_used=used0,
        base_n0=n0_0,
    )
    if opts.get("lock_max_containers") and mc > 0:
        opts["container_budget"] = mc
    if max_containers and max_containers > 0 and opts.get("lock_max_containers"):
        mc = int(max_containers)
        opts["container_budget"] = mc

    label = SCENARIOS.get(scenario) or (
        (nl_parsed or {}).get("scheme_id") or scenario
    )
    text = user_input or nl_query or f"What-if: {label}"
    sid = session_id or str(base_state.get("session_id") or "whatif")
    scheme_tag = re.sub(r"[^\w\-]+", "_", str((nl_parsed or {}).get("scheme_id") or scenario))[
        :40
    ]

    after_state = run_agent_pipeline(
        text,
        materials=mats2,
        container_type=str(
            base_state.get("container_type")
            or plan0.get("container_type")
            or "40HQ"
        ),
        max_containers=mc,
        enable_auto_confirm=True,
        session_id=f"{sid}-whatif-{scheme_tag}",
        save_artifacts=True,
        packing_options=opts,
        goal=str(base_state.get("goal") or "deliver_valid_pack_plan"),
    )

    before_snap = snapshot_for_diff(base_state)
    after_snap = snapshot_for_diff(after_state)
    before_pp = {
        **(base_state.get("packing_plan") or {}),
        **before_snap,
        "metrics": before_snap.get("metrics"),
        "cog": before_snap.get("cog"),
        "stacking": before_snap.get("stacking"),
        "evaluation": before_snap.get("evaluation"),
    }
    after_pp = {
        **(after_state.get("packing_plan") or {}),
        **after_snap,
        "metrics": after_snap.get("metrics"),
        "cog": after_snap.get("cog"),
        "stacking": after_snap.get("stacking"),
        "evaluation": after_snap.get("evaluation"),
    }
    pdiff = diff_packing_plans(before_pp, after_pp)
    score_cmp = compare_plans(before_snap, after_snap)
    extra = [score_cmp.get("narrative") or ""]
    if before_snap.get("n0") != after_snap.get("n0"):
        extra.append(f"订舱N0: {before_snap.get('n0')} → {after_snap.get('n0')}")
    if before_snap.get("worst_mid50") != after_snap.get("worst_mid50"):
        extra.append(
            f"worst_mid50: {before_snap.get('worst_mid50')} → {after_snap.get('worst_mid50')}"
        )
    bc = (before_snap.get("cog") or {}).get("lateral_eccentricity")
    ac = (after_snap.get("cog") or {}).get("lateral_eccentricity")
    if bc != ac:
        extra.append(f"lat: {bc} → {ac}")
    if before_snap.get("ship_ok") != after_snap.get("ship_ok"):
        extra.append(f"ship_ok: {before_snap.get('ship_ok')} → {after_snap.get('ship_ok')}")
    if score_cmp.get("after_is_better"):
        extra.append("判定：after 更优 ✓")
    pdiff["narrative"] = (pdiff.get("narrative") or "") + "\n" + "\n".join(x for x in extra if x)
    pdiff["whatif_extra"] = extra
    pdiff["score_compare"] = score_cmp

    pub = public_response(after_state)
    return {
        "ok": True,
        "scenario": scenario,
        "scenario_label": label,
        "nl_parsed": nl_parsed,
        "scheme_id": (nl_parsed or {}).get("scheme_id"),
        "material_profile": (nl_parsed or {}).get("material_profile"),
        "scheme_notes": (nl_parsed or {}).get("notes") or [],
        "materials_before": len(mats),
        "materials_after": len(mats2),
        "max_containers": mc,
        "packing_options": opts,
        "before": before_snap,
        "after": after_snap,
        "plan_diff": pdiff,
        "score_compare": score_cmp,
        "after_is_better": score_cmp.get("after_is_better"),
        "winner_label": score_cmp.get("label"),
        "public": pub,
        "state": after_state,
        "dual_metric_note": "订舱看 N0/booking_volume；3D 用柜看 containers_used（二者可不相同）",
    }
