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

    space = float(plan.get("space_utilization") or 0)
    space_best = float(plan.get("space_utilization_best_container") or space)
    floor = float(plan.get("floor_utilization_avg") or 0)
    weight = float(plan.get("weight_utilization") or 0)
    can_fit = bool(plan.get("can_fit"))
    unpacked = list(plan.get("unpacked_box_ids") or [])

    # 软目标（主控可覆盖）
    space_soft = float(targets.get("space_soft_min") or 0.25)
    weight_soft = float(targets.get("weight_soft_min") or 0.35)
    space_good = float(targets.get("space_good") or 0.45)
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
        risks.append("空间极满，绑扎要求高")

    # —— 空间 / 重量 双利用率子分 ——
    # 容积 = 铁箱/木箱外廓实心长方体体积利用率（与 bin3d volume_basis 一致）
    # 底面积单独参考，不顶替容积
    vol_metric = max(space, space_best * 0.95)
    space_sub = _util_band_score(vol_metric, space_soft, space_good)
    floor_sub = _util_band_score(floor, 0.35, 0.70)
    weight_sub = _util_band_score(min(weight, 1.0), weight_soft, weight_good)
    # 双目标主分：容积 40% + 底面积 15% + 重量 45%
    util_composite = 0.40 * space_sub + 0.15 * floor_sub + 0.45 * weight_sub

    # 低利用率扣分与提示
    if can_fit and not unpacked:
        if vol_metric < space_soft and weight < weight_soft:
            score -= 18
            risks.append(
                f"实心外廓容积 {space:.0%}（底面积 {floor:.0%}）与重量 {weight:.0%} 双低，"
                f"建议合箱/并排装载或减少柜数"
            )
            suggestions.append("tighter_pack")
            suggestions.append("merge_boxes")
        elif vol_metric < space_soft:
            score -= 10
            risks.append(
                f"实心外廓容积利用率 {space:.0%} 低于软目标 {space_soft:.0%}"
                f"（底面积 {floor:.0%}）；大件稀疏时请确认并排是否占满柜宽"
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
        "space_utilization": space,
        "space_best": space_best,
        "floor_utilization_avg": floor,
        "weight_utilization": weight,
        "space_subscore": round(space_sub, 1),
        "floor_subscore": round(floor_sub, 1),
        "weight_subscore": round(weight_sub, 1),
        "util_composite": round(util_composite, 1),
        "volume_basis": "solid_outer_aabb",
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
                    f"实心容积{space:.0%}(子分{space_sub:.0f}) "
                    f"底面积{floor:.0%}(子分{floor_sub:.0f}) "
                    f"重量{weight:.0%}(子分{weight_sub:.0f}) 综合{util_composite:.0f}"
                ),
            }
        ],
    }
    if need_replan:
        updates["replan_round"] = round_ + 1
        updates["max_containers"] = max_c + 1
    return updates
