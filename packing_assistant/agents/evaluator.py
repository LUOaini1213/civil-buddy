"""Agent6 评估优化智能体 — 订柜有效体积 + 外廓展示 + 重量 三指标评分。

按联网评审（docs/evaluator-web-review.md）改进：
- 硬约束优先：can_fit / 超重 / 结构不通过|待详设
- 软分：订柜有效体积 + 重量 + 底面积；**外廓不进主分**
- 权重可配置；按 binding=weight|volume|both 自适应
- 可选柜数惩罚（used > N0）
- space_subscore 仅兼容别名，真名 booking_volume_subscore
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from packing_assistant.state import PackingState


def _util_band_score(val: float, soft_min: float, good: float, *, higher_is_better: bool = True) -> float:
    """0~100 子分。"""
    v = float(val or 0)
    if not higher_is_better:
        v = 1.0 - v
    if v >= good:
        return 100.0
    if v >= soft_min:
        t = (v - soft_min) / max(good - soft_min, 1e-6)
        return 60.0 + 40.0 * min(max(t, 0), 1)
    if v <= 0:
        return 0.0
    return 60.0 * (v / max(soft_min, 1e-6))


def _resolve_weights(
    targets: Dict[str, Any],
    binding: str,
) -> Tuple[float, float, float, str]:
    """
    返回 (w_booking_vol, w_floor, w_weight, policy_name)，三者之和=1。
    显式配置优先；否则按 binding 自适应。
    """
    # 显式：orchestrator.goals.targets 或 evaluation_weights
    ew = targets.get("evaluation_weights") or targets.get("util_weights") or {}
    if ew:
        wb = float(ew.get("booking_volume") or ew.get("volume") or 0.35)
        wf = float(ew.get("floor") or 0.20)
        ww = float(ew.get("weight") or 0.45)
        s = wb + wf + ww
        if s <= 0:
            return 0.35, 0.20, 0.45, "default_invalid_override"
        return wb / s, wf / s, ww / s, "configured"

    b = (binding or "both").lower()
    if b in ("volume", "v", "vol"):
        # 轻泡/体积主导：抬高订柜有效体积
        return 0.50, 0.20, 0.30, "adaptive_volume_binding"
    if b in ("weight", "w", "wt"):
        # 重量主导（钢结构常见）
        return 0.25, 0.20, 0.55, "adaptive_weight_binding"
    # both / 未知
    return 0.35, 0.20, 0.45, "adaptive_both"


def agent_evaluator(state: PackingState) -> Dict[str, Any]:
    plan = state.get("container_plan") or {}
    boxes = state.get("boxes") or []
    max_c = int((state.get("plan") or {}).get("max_containers") or state.get("max_containers") or 1)
    orch = state.get("orchestrator") or {}
    targets = dict(((orch.get("goals") or {}).get("targets") or {}))
    # state 级可覆盖
    if isinstance(state.get("evaluation_weights"), dict):
        targets["evaluation_weights"] = state["evaluation_weights"]

    outer_space = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    space_best = float(plan.get("space_utilization_best_container") or outer_space)
    floor = float(plan.get("floor_utilization_avg") or 0)
    weight = float(plan.get("weight_utilization") or 0)
    raw_booking_u = plan.get("booking_volume_utilization")
    booking_vol_util = float(raw_booking_u or 0)
    # 评分用 cap 到 1.0，展示仍可保留原值
    booking_vol_for_score = min(max(booking_vol_util, 0.0), 1.0)

    booking = (
        plan.get("booking")
        or state.get("booking")
        or (state.get("plan") or {}).get("booking")
        or {}
    )
    can_fit = bool(plan.get("can_fit"))
    unpacked = list(plan.get("unpacked_box_ids") or [])
    binding = str(booking.get("binding_constraint") or "both")
    n0 = int(booking.get("n0") or plan.get("n0") or 0)
    used = int(plan.get("containers_used") or 0)

    # 软目标（主控可覆盖）— 订柜有效体积对钢结构放宽
    space_soft = float(targets.get("space_soft_min") or targets.get("booking_vol_soft_min") or 0.20)
    weight_soft = float(targets.get("weight_soft_min") or 0.35)
    space_good = float(targets.get("space_good") or targets.get("booking_vol_good") or 0.40)
    weight_good = float(targets.get("weight_good") or 0.60)
    floor_soft = float(targets.get("floor_soft_min") or 0.35)
    floor_good = float(targets.get("floor_good") or 0.70)
    # 柜数惩罚：used > n0 时每多一柜扣分（可关）
    container_penalty_per = float(targets.get("extra_container_penalty") or 4.0)
    enable_container_penalty = targets.get("penalize_extra_containers")
    if enable_container_penalty is None:
        enable_container_penalty = True

    w_book, w_floor, w_weight, weight_policy = _resolve_weights(targets, binding)

    risks: List[str] = []
    suggestions: List[str] = []
    score = 100.0

    # —— 硬约束 ——
    if not can_fit or unpacked:
        score -= 40
        risks.append(f"未能全部装入：{', '.join(unpacked[:8]) or '存在溢出'}")
        suggestions.append("increase_max_containers")
        if (state.get("container_type") or "") != "45HQ":
            suggestions.append("try_45hq")

    if weight > 1.0:
        score -= 30
        risks.append("重量利用率超过 100%，超重")
        suggestions.append("split_heavy")
        suggestions.append("increase_max_containers")
    elif weight > 0.95:
        score -= 5
        risks.append("重量接近上限，建议复核 VGM")

    if outer_space > 0.98:
        score -= 5
        risks.append("外廓空间极满，绑扎要求高（外廓≠订柜）")

    n_vol = int(booking.get("containers_by_volume") or 0)
    n_wt = int(booking.get("containers_by_weight") or 0)
    if booking.get("volume_suspicious") or (n_vol >= max(2, 2 * max(n_wt, 1)) and n_vol > 0):
        score -= 12
        risks.append(
            f"体积可疑：有效体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，"
            f"订柜分子可能偏虚（请查箱填充率/尺寸来源）"
        )
        suggestions.append("audit_booking_volume")

    # 柜数经济性：3D 用柜明显高于 N0
    if (
        enable_container_penalty
        and can_fit
        and n0 > 0
        and used > n0
    ):
        extra = used - n0
        pen = min(extra * container_penalty_per, 20.0)
        score -= pen
        risks.append(
            f"3D 用柜 {used} > 订柜 N0={n0}（+{extra}），经济性扣分 {pen:.0f}；"
            f"订舱仍以 N0 口径为准，工程可备注合箱争取贴近 N0"
        )
        suggestions.append("improve_pack_toward_n0")

    # —— 利用率子分 ——
    booking_known = plan.get("booking_volume_utilization") is not None
    if not booking_known:
        try:
            v_eff = float(booking.get("volume_m3") or 0)
            usable = float(booking.get("usable_m3_per_container") or 0)
            used_n = int(used or n0 or max_c or 1)
            if usable > 0 and used_n > 0 and (
                v_eff > 0 or booking.get("volume_m3") is not None
            ):
                booking_vol_util = round(min(v_eff / (usable * used_n), 9.99), 4)
                booking_vol_for_score = min(max(booking_vol_util, 0.0), 1.0)
                booking_known = True
        except Exception:
            pass

    if booking_known:
        booking_vol_sub = _util_band_score(booking_vol_for_score, space_soft, space_good)
        volume_basis_score = "booking_volume"
    else:
        booking_vol_sub = 50.0
        volume_basis_score = "booking_unknown"
        risks.append(
            "订柜有效体积率缺失，体积子分按中性计分（不用外廓摆柜率顶替订柜）"
        )
        suggestions.append("enrich_booking_volume_utilization")

    floor_sub = _util_band_score(floor, floor_soft, floor_good)
    weight_sub = _util_band_score(min(weight, 1.0), weight_soft, weight_good)
    util_composite = (
        w_book * booking_vol_sub + w_floor * floor_sub + w_weight * weight_sub
    )

    # 低利用率提示（外廓永不主导订舱）
    if can_fit and not unpacked:
        if booking_known and booking_vol_for_score < space_soft and weight < weight_soft:
            score -= 15
            risks.append(
                f"订柜有效体积率 {booking_vol_util:.0%} 与重量 {weight:.0%} 双低，"
                f"可评估是否可减柜（勿仅因外廓率低加柜）"
            )
            suggestions.append("tighter_pack")
        elif outer_space < 0.25 and weight >= weight_soft:
            score -= 3
            risks.append(
                f"外廓摆柜率 {outer_space:.0%} 偏低但重量已用 {weight:.0%}；"
                f"钢结构/铁架常见，不等于货没装够"
            )
        elif booking_known and booking_vol_for_score < space_soft:
            score -= 8
            risks.append(
                f"订柜有效体积率 {booking_vol_util:.0%} 低于软目标 {space_soft:.0%}"
                f"（外廓摆柜 {outer_space:.0%}，底面积 {floor:.0%}）"
            )
            suggestions.append("improve_floor_pack")
        elif weight < weight_soft:
            score -= 8
            risks.append(
                f"重量利用率 {weight:.0%} 低于软目标 {weight_soft:.0%}，柜载未吃满"
            )
            suggestions.append("add_cargo_or_downsize_container")

        if booking_known and booking_vol_for_score >= space_good and weight >= weight_good:
            score = min(100, score + 5)

    # 综合分：硬约束分与利用率分融合
    if can_fit and not unpacked and weight <= 1.0:
        score = 0.55 * score + 0.45 * util_composite
    else:
        score = 0.7 * score + 0.3 * util_composite

    need_replan = False
    if (not can_fit or unpacked) and max_c < 8:
        need_replan = True
        suggestions.append(f"建议 max_containers>={max_c + 1}")

    round_ = int(state.get("replan_round") or 0)
    if need_replan and round_ >= 2:
        need_replan = False
        risks.append("已达自动重规划上限，请人工调整箱子或柜型")

    struct_fail_ids = [
        str(b.get("box_id") or "")
        for b in boxes
        if b.get("structure_conclusion") == "不通过"
        or "结构不通过" in (b.get("special_attributes") or [])
    ]
    struct_pending_ids = [
        str(b.get("box_id") or "")
        for b in boxes
        if b.get("structure_conclusion") == "待详设"
        or "待详设" in (b.get("special_attributes") or [])
    ]
    if struct_fail_ids:
        score -= 25
        risks.append(f"成箱结构不通过：{', '.join(struct_fail_ids[:8])}，须拆箱/改箱型")
        suggestions.append("split_or_reinforce_boxes")
        suggestions.append("reject_to_box_scheme")
    if struct_pending_ids:
        score -= 20
        risks.append(
            f"结构待详设：{', '.join(struct_pending_ids[:8])}，"
            f"须提供详设截面/图纸或自然语言指定后重算"
        )
        suggestions.append("provide_structure_design_facts")
        suggestions.append("nl_revise_sections")

    passed = (
        can_fit
        and weight <= 1.0
        and not unpacked
        and not struct_fail_ids
        and not struct_pending_ids
    )
    score = max(0, min(100, round(score, 1)))

    if (struct_fail_ids or struct_pending_ids) and can_fit:
        decision = "REJECT_STRUCTURE"
    elif need_replan:
        decision = "REPLAN"
    elif passed:
        decision = "PASS"
    else:
        decision = "FAIL"

    metrics_table = {
        "booking_volume_utilization": {
            "value": booking_vol_util if booking_known else None,
            "role": "订舱/有效体积（主）",
            "in_score": True,
            "weight": round(w_book, 3),
            "subscore": round(booking_vol_sub, 1),
        },
        "weight_utilization": {
            "value": weight,
            "role": "载重（主）",
            "in_score": True,
            "weight": round(w_weight, 3),
            "subscore": round(weight_sub, 1),
        },
        "floor_utilization_avg": {
            "value": floor,
            "role": "底面积（辅）",
            "in_score": True,
            "weight": round(w_floor, 3),
            "subscore": round(floor_sub, 1),
        },
        "outer_space_utilization": {
            "value": outer_space,
            "role": "外廓摆柜（仅展示/轻提示，不进订舱主分）",
            "in_score": False,
            "weight": 0.0,
            "subscore": None,
        },
    }

    evaluation = {
        "passed": passed,
        "score": score,
        "decision": decision,
        "structure_fail_box_ids": struct_fail_ids,
        "structure_pending_design_ids": struct_pending_ids,
        # 双口径
        "outer_space_utilization": outer_space,
        "space_utilization": outer_space,  # 兼容：仅外廓
        "booking_volume_utilization": booking_vol_util if booking_known else None,
        "booking_volume_known": booking_known,
        "space_best": space_best,
        "floor_utilization_avg": floor,
        "weight_utilization": weight,
        # 子分：真名 + 弃用别名
        "booking_volume_subscore": round(booking_vol_sub, 1),
        "floor_subscore": round(floor_sub, 1),
        "weight_subscore": round(weight_sub, 1),
        "space_subscore": round(booking_vol_sub, 1),  # DEPRECATED alias → booking_volume_subscore
        "space_subscore_deprecated": True,
        "space_subscore_means": "booking_volume_subscore",
        "util_composite": round(util_composite, 1),
        "util_weights": {
            "booking_volume": round(w_book, 3),
            "floor": round(w_floor, 3),
            "weight": round(w_weight, 3),
            "policy": weight_policy,
            "binding": binding,
        },
        "metrics_table": metrics_table,
        "volume_basis": "booking_pack_effective+outer_display_only",
        "volume_basis_score": volume_basis_score,
        "n0": n0 or booking.get("n0") or plan.get("n0"),
        "containers_used": used,
        "containers_by_weight": n_wt,
        "containers_by_volume": n_vol,
        "binding_constraint": binding,
        "volume_suspicious": bool(booking.get("volume_suspicious")),
        "targets": {
            "booking_vol_soft_min": space_soft,
            "booking_vol_good": space_good,
            "space_soft_min": space_soft,  # 兼容旧名=订柜有效体积软目标
            "weight_soft_min": weight_soft,
            "space_good": space_good,
            "weight_good": weight_good,
            "floor_soft_min": floor_soft,
            "floor_good": floor_good,
            "penalize_extra_containers": enable_container_penalty,
            "extra_container_penalty": container_penalty_per,
        },
        "risks": risks,
        "suggestions": suggestions,
        "need_replan": need_replan,
        "note": (
            "评分：硬约束(装下/超重/结构) + 软分(订柜有效体积/重量/底面积)；"
            "外廓摆柜率不进订舱主分。space_subscore 为废弃别名=booking_volume_subscore。"
        ),
    }

    tools_used = [
        "evaluator.dual_util",
        "evaluator.adaptive_weights",
        "booking.volume_metrics",
    ]
    updates: Dict[str, Any] = {
        "evaluation": evaluation,
        "agent_meta": {
            "node": "evaluator",
            "capability": ["推理与规划", "使用工具"],
            "tools_used": tools_used,
            "artifacts": {
                "score": score,
                "decision": decision,
                "weights": evaluation["util_weights"],
                "booking_volume_utilization": booking_vol_util if booking_known else None,
                "outer_space_utilization": outer_space,
                "need_replan": need_replan,
            },
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"评估：score={score} decision={decision} replan={need_replan} | "
                    f"订柜有效体积"
                    f"{f'{booking_vol_util:.0%}' if booking_known else '未知'}"
                    f"(子分{booking_vol_sub:.0f}×{w_book:.0%}) "
                    f"重量{weight:.0%}(×{w_weight:.0%}) "
                    f"底面积{floor:.0%}(×{w_floor:.0%}) "
                    f"外廓{outer_space:.0%}(不进主分) "
                    f"权重策略={weight_policy} binding={binding} "
                    f"N0={n0 or '-'} used={used or '-'} "
                    f"综合利用{util_composite:.0f}"
                    f"{' 体积可疑' if evaluation.get('volume_suspicious') else ''}"
                    f"｜tools={','.join(tools_used)}"
                ),
            }
        ],
    }
    if need_replan:
        updates["replan_round"] = round_ + 1
        updates["max_containers"] = max_c + 1
    return updates
