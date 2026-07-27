"""Agent6 评估优化智能体 — 空间 + 重量双利用率评分。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.state import PackingState


def _util_band_score(val: float, soft_min: float, good: float, *, higher_is_better: bool = True) -> float:
    """0~100 子分。"""
    v = float(val or 0)
    if not higher_is_better:
        v = 1.0 - v
    if v >= good:
        return 100.0
    if v >= soft_min:
        # soft_min → good 线性 60→100
        t = (v - soft_min) / max(good - soft_min, 1e-6)
        return 60.0 + 40.0 * min(max(t, 0), 1)
    if v <= 0:
        return 0.0
    # 0 → soft_min 线性 0→60
    return 60.0 * (v / max(soft_min, 1e-6))


def agent_evaluator(state: PackingState) -> Dict[str, Any]:
    plan = state.get("container_plan") or {}
    boxes = state.get("boxes") or []
    max_c = int((state.get("plan") or {}).get("max_containers") or state.get("max_containers") or 1)
    orch = state.get("orchestrator") or {}
    targets = ((orch.get("goals") or {}).get("targets") or {})

    # outer_space_util：摆柜几何；booking_volume_util：订柜有效体积
    outer_space = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    space = outer_space
    space_best = float(plan.get("space_utilization_best_container") or space)
    floor = float(plan.get("floor_utilization_avg") or 0)
    weight = float(plan.get("weight_utilization") or 0)
    booking_vol_util = float(plan.get("booking_volume_utilization") or 0)
    booking = plan.get("booking") or state.get("booking") or (state.get("plan") or {}).get("booking") or {}
    can_fit = bool(plan.get("can_fit"))
    unpacked = list(plan.get("unpacked_box_ids") or [])

    # 软目标（主控可覆盖）— 外廓率对钢结构放宽
    space_soft = float(targets.get("space_soft_min") or 0.20)
    weight_soft = float(targets.get("weight_soft_min") or 0.35)
    space_good = float(targets.get("space_good") or 0.40)
    weight_good = float(targets.get("weight_good") or 0.60)

    risks: List[str] = []
    suggestions: List[str] = []
    score = 100.0

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

    if space > 0.98:
        score -= 5
        risks.append("外廓空间极满，绑扎要求高")

    # 体积分子可疑（订柜侧）
    n_vol = int(booking.get("containers_by_volume") or 0)
    n_wt = int(booking.get("containers_by_weight") or 0)
    if booking.get("volume_suspicious") or (n_vol >= max(2, 2 * max(n_wt, 1)) and n_vol > 0):
        score -= 12
        risks.append(
            f"体积可疑：有效体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，"
            f"订柜分子可能偏虚（请查箱填充率/尺寸来源）"
        )
        suggestions.append("audit_booking_volume")

    # —— 指标拆分评分 ——
    # 订柜有效体积率优先；外廓率仅参考（钢结构常 40–60% 正常）
    vol_metric = booking_vol_util if booking_vol_util > 0 else max(space, space_best * 0.95)
    space_sub = _util_band_score(vol_metric, space_soft, space_good)
    floor_sub = _util_band_score(floor, 0.35, 0.70)
    weight_sub = _util_band_score(min(weight, 1.0), weight_soft, weight_good)
    # 重量 45% + 订柜有效体积 35% + 底面积 20%（外廓率不主导扣分）
    util_composite = 0.35 * space_sub + 0.20 * floor_sub + 0.45 * weight_sub

    # 低利用率：仅当「订柜有效体积」与重量双低才重扣；外廓低单独轻提示
    if can_fit and not unpacked:
        if booking_vol_util > 0 and booking_vol_util < space_soft and weight < weight_soft:
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
        elif vol_metric < space_soft:
            score -= 8
            risks.append(
                f"有效体积利用率 {vol_metric:.0%} 低于软目标 {space_soft:.0%}"
                f"（外廓摆柜 {outer_space:.0%}，底面积 {floor:.0%}）"
            )
            suggestions.append("improve_floor_pack")
        elif weight < weight_soft:
            score -= 8
            risks.append(
                f"重量利用率 {weight:.0%} 低于软目标 {weight_soft:.0%}，柜载未吃满"
            )
            suggestions.append("add_cargo_or_downsize_container")

        if vol_metric >= space_good and weight >= weight_good:
            score = min(100, score + 5)

    # 综合分：硬约束分与利用率分融合
    if can_fit and not unpacked and weight <= 1.0:
        score = 0.55 * score + 0.45 * util_composite
    else:
        score = 0.7 * score + 0.3 * util_composite

    # 多柜需求
    need_replan = False
    if (not can_fit or unpacked) and max_c < 8:
        need_replan = True
        suggestions.append(f"建议 max_containers>={max_c + 1}")

    round_ = int(state.get("replan_round") or 0)
    if need_replan and round_ >= 2:
        need_replan = False
        risks.append("已达自动重规划上限，请人工调整箱子或柜型")

    # 成箱结构不通过：装得下也不能算评估通过（交由风险合规打回）
    struct_fail_ids = [
        str(b.get("box_id") or "")
        for b in boxes
        if b.get("structure_conclusion") == "不通过"
        or "结构不通过" in (b.get("special_attributes") or [])
    ]
    if struct_fail_ids:
        score -= 25
        risks.append(f"成箱结构不通过：{', '.join(struct_fail_ids[:8])}，须拆箱/改箱型")
        suggestions.append("split_or_reinforce_boxes")
        suggestions.append("reject_to_box_scheme")

    passed = can_fit and weight <= 1.0 and not unpacked and not struct_fail_ids
    score = max(0, min(100, round(score, 1)))

    if struct_fail_ids and can_fit:
        decision = "REJECT_STRUCTURE"
    elif need_replan:
        decision = "REPLAN"
    elif passed:
        decision = "PASS"
    else:
        decision = "FAIL"

    evaluation = {
        "passed": passed,
        "score": score,
        "decision": decision,
        "structure_fail_box_ids": struct_fail_ids,
        "outer_space_utilization": outer_space,
        "space_utilization": outer_space,  # 兼容旧字段=外廓摆柜率
        "booking_volume_utilization": booking_vol_util,
        "space_best": space_best,
        "floor_utilization_avg": floor,
        "weight_utilization": weight,
        "space_subscore": round(space_sub, 1),
        "floor_subscore": round(floor_sub, 1),
        "weight_subscore": round(weight_sub, 1),
        "util_composite": round(util_composite, 1),
        "volume_basis": "booking_pack_effective+outer_display",
        "n0": booking.get("n0") or plan.get("n0"),
        "containers_by_weight": n_wt,
        "containers_by_volume": n_vol,
        "binding_constraint": booking.get("binding_constraint"),
        "volume_suspicious": bool(booking.get("volume_suspicious")),
        "targets": {
            "space_soft_min": space_soft,
            "weight_soft_min": weight_soft,
            "space_good": space_good,
            "weight_good": weight_good,
        },
        "risks": risks,
        "suggestions": suggestions,
        "need_replan": need_replan,
    }

    updates: Dict[str, Any] = {
        "evaluation": evaluation,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"评估：score={score} passed={passed} replan={need_replan} | "
                    f"外廓摆柜{outer_space:.0%} 订柜有效体积{booking_vol_util:.0%} "
                    f"底面积{floor:.0%} 重量{weight:.0%} 综合{util_composite:.0f}"
                    f"{' 体积可疑' if evaluation.get('volume_suspicious') else ''}"
                ),
            }
        ],
    }
    if need_replan:
        updates["replan_round"] = round_ + 1
        updates["max_containers"] = max_c + 1
    return updates
