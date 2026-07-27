"""Agent7 风险合规：CTU/行业偏载标准 + 知识库阈值。

改进（联网实践 + e2e 误报）：
- 重心：用柜内尺寸算偏心率（前后 40–60% 为优，左右 ±5% 中心带）
- 不再把「未采用的中间箱型试算 notes」当阻断风险
- 仅采信最终 boxes[].structure_conclusion
- 空隙率：大件稀疏只 warning，不拖垮总分
- 评分去重、封顶更合理
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from packing_assistant.knowledge import risk_thresholds
from packing_assistant.state import PackingState
from packing_assistant.tools.consolidation import CONTAINER_SPECS


def agent_risk_compliance(state: PackingState) -> Dict[str, Any]:
    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    evaluation = state.get("evaluation") or {}
    constraints = state.get("structure_constraints") or []
    thr = risk_thresholds()

    items: List[Dict[str, Any]] = []
    risks: List[str] = []
    blockers: List[str] = []
    seen_msg: set = set()

    def add(
        code: str,
        severity: str,
        message: str,
        source: str,
        box_id=None,
        *,
        score: float = 0,
        raw_value: Any = None,
        block: bool = False,
    ):
        key = f"{code}|{box_id}|{message}"
        if key in seen_msg:
            return
        seen_msg.add(key)
        items.append(
            {
                "code": code,
                "severity": severity,
                "box_id": box_id,
                "message": message,
                "source": source,
                "score": score,
                "raw_value": raw_value,
            }
        )
        risks.append(message if not box_id else f"{box_id} {message}")
        if block:
            blockers.append(message if not box_id else f"{box_id} {message}")

    # —— 最终箱结构/属性（唯一结构真相源）——
    for b in boxes:
        bid = b.get("box_id")
        special = b.get("special_attributes") or []
        if "超长" in special:
            add(
                "OVERLENGTH",
                "medium",
                "超长件，沿柜长摆放并加强绑扎",
                "box_special",
                bid,
                score=8,
            )
        if "需加固" in special or "结构需加强" in special:
            add(
                "REINFORCE",
                "medium",
                f"需加固：{b.get('reinforcement') or '见结构方案'}",
                "structure",
                bid,
                score=8,
            )
        if b.get("structure_conclusion") == "不通过" or "结构不通过" in special:
            add(
                "STRUCTURE_FAIL",
                "high",
                "成箱结构校核不通过",
                "structure",
                bid,
                score=18,
                block=True,
            )
        g = float(b.get("gross_weight_kg") or 0)
        if g > 2000:
            add(
                "HEAVY_BOX",
                "medium",
                f"单箱毛重 {g:.0f}kg，需全项校核与铁箱",
                "weight",
                bid,
                score=10,
                raw_value=g,
            )
        elif g > 1000:
            add(
                "HEAVY_BOX",
                "low",
                f"单箱毛重 {g:.0f}kg，优先铁箱/钢骨箱",
                "weight",
                bid,
                score=4,
                raw_value=g,
            )

    # —— 超重 ——
    wutil = float(plan.get("weight_utilization") or 0)
    ow = thr.get("overweight") or {}
    warn_w, block_w = float(ow.get("warn") or 0.9), float(ow.get("block") or 1.0)
    if wutil >= block_w:
        add(
            "OVERWEIGHT",
            "critical",
            f"重量利用率 {wutil:.0%} 超限",
            "weight",
            None,
            score=28,
            raw_value=wutil,
            block=True,
        )
    elif wutil >= warn_w:
        add(
            "OVERWEIGHT",
            "medium",
            f"重量利用率 {wutil:.0%} 接近限重（预警）",
            "weight",
            None,
            score=10,
            raw_value=wutil,
        )

    # —— 装不下 ——
    if not plan.get("can_fit"):
        add(
            "NOT_FIT",
            "high",
            plan.get("message") or "当前柜型无法全部装下",
            "layout",
            None,
            score=22,
            block=True,
        )
    for uid in plan.get("unpacked_box_ids") or []:
        add("UNPACKED", "high", "未装入集装箱", "layout", uid, score=15, block=True)

    # —— 空隙率 / 指标拆分 ——
    space = float(plan.get("outer_space_utilization") or plan.get("space_utilization") or 0)
    weight_u = float(plan.get("weight_utilization") or 0)
    floor_u = float(plan.get("floor_utilization_avg") or 0)
    book_u = float(plan.get("booking_volume_utilization") or 0)
    booking = plan.get("booking") or state.get("booking") or {}
    void_ratio = 1.0 - space
    vr = thr.get("void_ratio") or {}
    if vr.get("warn") is not None and void_ratio >= float(vr["warn"]) and space < 0.5:
        add(
            "VOID_HIGH",
            "low",
            f"外廓空隙率 {void_ratio:.0%}（大件/铁架常见），注意绑扎；底面积 {floor_u:.0%}",
            "layout",
            None,
            score=3,
            raw_value=void_ratio,
        )
    # 体积分子可疑
    n_vol = int(booking.get("containers_by_volume") or 0)
    n_wt = int(booking.get("containers_by_weight") or 0)
    if booking.get("volume_suspicious") or (n_vol >= max(2, 2 * max(n_wt, 1)) and n_vol > 0):
        add(
            "VOLUME_SUSPICIOUS",
            "medium",
            booking.get("warning")
            or f"有效体积柜数 {n_vol} ≥ 2×重量柜数 {n_wt}，订柜体积分子可能偏虚",
            "booking",
            None,
            score=6,
            raw_value={"n_vol": n_vol, "n_wt": n_wt},
        )
    # 订柜有效体积 + 重量双低（不用外廓率单独重罚）
    if plan.get("can_fit") and book_u > 0 and book_u < 0.25 and weight_u < 0.35:
        add(
            "UTIL_DUAL_LOW",
            "medium",
            f"订柜有效体积率 {book_u:.0%} 与重量 {weight_u:.0%} 双低，可评估是否减柜",
            "layout",
            None,
            score=6,
            raw_value={"booking_vol": book_u, "weight": weight_u},
        )
    elif plan.get("can_fit") and weight_u >= 0.55 and space < 0.35:
        add(
            "UTIL_WEIGHT_OK_SPACE_LOW",
            "low",
            f"重量利用率 {weight_u:.0%} 尚可，外廓摆柜率 {space:.0%} 偏低（钢结构/铁架常见，≠少装）",
            "layout",
            None,
            score=2,
            raw_value=weight_u,
        )

    # —— 重心偏心率（CTU/行业：左右偏心宜 ≤5%；前后宜在 40–60% 柜深）——
    cog = _cog_metrics(plan)
    if cog:
        # 左右：偏心率 = |cy - W/2| / (W/2)
        lat_ecc = cog["lateral_eccentricity"]
        long_pos = cog["longitudinal_position"]  # 0~1 从前到后
        # 知识库阈值（兼容旧 |半区差| 与新偏心率）
        lat_warn = float((thr.get("cog_transverse") or {}).get("warn") or 0.05)
        lat_block = float((thr.get("cog_transverse") or {}).get("block") or 0.15)
        # 若配置仍是旧的 0.2/0.35（半区差），映射到偏心率更严的 5%/15%
        if lat_warn >= 0.15:
            lat_warn = 0.05
        if lat_block >= 0.3:
            lat_block = 0.15

        # 更严：>5% medium；>10% high；≥15% block
        if lat_ecc >= lat_block or lat_ecc >= 0.15:
            add(
                "COG_LAT",
                "high",
                f"左右重心偏心率 {lat_ecc:.1%}（宜≤5%，≥15% 阻断）",
                "layout",
                None,
                score=18,
                raw_value=lat_ecc,
                block=True,
            )
        elif lat_ecc >= 0.10:
            add(
                "COG_LAT",
                "high",
                f"左右重心偏心率 {lat_ecc:.1%}（>10%，建议重排并排/配重）",
                "layout",
                None,
                score=14,
                raw_value=lat_ecc,
            )
        elif lat_ecc >= lat_warn:
            add(
                "COG_LAT",
                "medium",
                f"左右重心偏心率 {lat_ecc:.1%}（建议≤5%）",
                "layout",
                None,
                score=10,
                raw_value=lat_ecc,
            )

        # 前后：理想 0.4–0.6
        if long_pos < 0.35 or long_pos > 0.65:
            sev = "high" if long_pos < 0.25 or long_pos > 0.75 else "medium"
            add(
                "COG_LONG",
                sev,
                f"前后重心位于柜深 {long_pos:.0%} 处（宜 40%–60%）",
                "layout",
                None,
                score=14 if sev == "high" else 8,
                raw_value=long_pos,
                block=(sev == "high"),
            )

    # —— 重货在上 ——
    hot = _heavy_on_top_ratio(plan, boxes)
    ht = thr.get("heavy_on_top_ratio") or {}
    if hot is not None and hot > 0:
        if ht.get("block") is not None and hot >= float(ht["block"]):
            add(
                "HEAVY_ON_TOP",
                "high",
                f"上层重货占比 {hot:.0%} 过高",
                "layout",
                None,
                score=14,
                raw_value=hot,
                block=True,
            )
        elif ht.get("warn") is not None and hot >= float(ht["warn"]):
            add(
                "HEAVY_ON_TOP",
                "medium",
                f"上层重货占比 {hot:.0%}（预警）",
                "layout",
                None,
                score=8,
                raw_value=hot,
            )

    # —— 评估提示（低权重；与已写 UTIL 去重）——
    for r in evaluation.get("risks") or []:
        if any(r[:12] in x or x[:12] in r for x in risks):
            continue
        if "实心外廓" in r or "双低" in r:
            add("EVAL", "low", r, "evaluation", None, score=2)
        elif "偏低" in r or "稀疏" in r or "柜载" in r:
            add("EVAL", "low", r, "evaluation", None, score=2)
        elif r not in risks:
            add("EVAL", "low", r, "evaluation", None, score=3)

    # —— 约束加固（仅 need_reinforcement，不引用失败试装）——
    for c in constraints:
        if c.get("need_reinforcement") and c.get("reinforcement_plan"):
            # 跳过「待成箱」且最终箱已通过的组
            if c.get("structure_conclusion") == "不通过":
                continue
            msg = f"加固建议（{c.get('recommended_box_type')}）：{c.get('reinforcement_plan')}"
            add("CONSTRAINT", "low", msg, "structure", None, score=3)

    hard_block = bool(blockers)

    # 评分：单项扣分封顶；能装下且无硬阻断时保底 40
    score = 100.0
    for it in items:
        score -= min(float(it.get("score") or 5), 20)
    score = max(5, min(100, int(score)))
    if plan.get("can_fit") and not hard_block:
        score = max(score, 40)

    if any(i["severity"] == "critical" for i in items) or any(
        "超重" in b for b in blockers
    ):
        level = "critical"
    elif blockers or any(i["severity"] == "high" for i in items):
        level = "high"
    elif any(i["severity"] == "medium" for i in items):
        level = "medium"
    else:
        level = "low"

    passed = (not hard_block) and score >= 55
    if plan.get("can_fit") and not any("结构" in b for b in blockers):
        if level == "critical" and not hard_block:
            level = "high"

    explanation = _explain(passed, level, score, items, plan, thr, hard_block)

    try:
        from packing_assistant.llm import chat, llm_available

        if llm_available() and items:
            # 只给最终事实，避免 LLM 被脏 notes 带偏
            facts = {
                "can_fit": plan.get("can_fit"),
                "outer_space_utilization": plan.get("outer_space_utilization")
                or plan.get("space_utilization"),
                "booking_volume_utilization": plan.get("booking_volume_utilization"),
                "weight_utilization": plan.get("weight_utilization"),
                "note": "外廓摆柜≠订柜有效体积；勿把 outer 当订柜分子",
                "engine": plan.get("engine"),
                "boxes": [
                    {
                        "box_id": b.get("box_id"),
                        "box_type": b.get("box_type"),
                        "gross_kg": b.get("gross_weight_kg"),
                        "structure": b.get("structure_conclusion"),
                        "special": b.get("special_attributes"),
                    }
                    for b in boxes
                ],
                "risks": risks[:12],
                "blockers": blockers,
                "compliance_score": score,
                "level": level,
            }
            llm_exp = chat(
                system=(
                    "你是货运合规顾问。仅根据给定 JSON 事实写中文结论与建议，"
                    "150字内。禁止编造不存在的箱型失败或柜内装不下的矛盾。"
                    "若 can_fit=true 且 blockers 为空，不要说「无法装入集装箱」。"
                ),
                user=str(facts),
                temperature=0.15,
                max_tokens=400,
            )
            if llm_exp and not llm_exp.startswith("[LLM_ERROR]"):
                explanation = llm_exp
            elif llm_exp and llm_exp.startswith("[LLM_ERROR]"):
                explanation = explanation + f"\n（LLM：{llm_exp}）"
    except Exception:
        pass

    # 决策语义：
    # - 有 blockers（结构不通过/超重等）→ REJECT 打回
    # - 无 blockers 但分数低/等级 medium → WARN（可讨论出运，须人工关注）
    # - 通过 → PASS
    struct_blocks = [b for b in blockers if "结构" in b]
    if hard_block and struct_blocks:
        decision = "REJECT"
        reject_to = "box_scheme"  # 回团队A改箱/拆件
        reject_reason = "成箱结构不通过，打回装箱方案智能体拆箱或改箱型加固"
        need_revision = True
    elif hard_block:
        decision = "REJECT"
        reject_to = "await_user_confirm"
        reject_reason = "存在合规阻断项，打回人工确认/调整后重跑"
        need_revision = True
    elif not plan.get("can_fit"):
        decision = "REJECT"
        reject_to = "planner"
        reject_reason = "未能全部装入集装箱，打回规划/加柜"
        need_revision = True
    elif not passed:
        # 无硬阻断：装得下但评分偏低 → 警告，不打回装箱
        decision = "WARN"
        reject_to = ""
        reject_reason = ""
        need_revision = False
    elif level in ("high", "medium"):
        decision = "WARN"
        reject_to = ""
        reject_reason = ""
        need_revision = False
    else:
        decision = "PASS"
        reject_to = ""
        reject_reason = ""
        need_revision = False

    risk_report = {
        "passed": passed,
        "compliance_score": score,
        "level": level,
        "decision": decision,
        "need_revision": need_revision,
        "reject_to": reject_to,
        "reject_reason": reject_reason,
        "items": items,
        "risks": risks,
        "blockers": blockers,
        "explanation": explanation,
        "principles": thr.get("loading_principles") or [],
        "cog": cog,
    }

    msg = (
        f"风险合规：level={level} score={score} passed={passed} "
        f"decision={decision} blockers={len(blockers)}"
    )
    if need_revision:
        msg += f" ⛔打回→{reject_to or '人工'}：{reject_reason}"

    updates: Dict[str, Any] = {
        "risk_report": risk_report,
        "risks": risks,
        "messages": [{"role": "assistant", "content": msg}],
    }
    if need_revision:
        updates["phase"] = "need_revision"
        updates["status"] = "rejected"
    return updates


def _cog_metrics(plan: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """按柜内尺寸 + 体积/质量代理计算重心。"""
    layout = plan.get("layout") or []
    if not layout:
        return None
    ctype = plan.get("container_type") or "40HQ"
    spec = CONTAINER_SPECS.get(ctype) or CONTAINER_SPECS.get("40HQ") or {}
    L = float(spec.get("长_m") or 12.032) * 1000
    W = float(spec.get("宽_m") or 2.352) * 1000
    H = float(spec.get("高_m") or 2.698) * 1000

    mx = my = mz = 0.0
    m_tot = 0.0
    for p in layout:
        pos, size = p.get("position") or {}, p.get("size") or {}
        dx = max(float(size.get("dx") or 1), 1)
        dy = max(float(size.get("dy") or 1), 1)
        dz = max(float(size.get("dz") or 1), 1)
        # 体积代理质量
        m = dx * dy * dz
        cx = float(pos.get("x") or 0) + dx / 2
        cy = float(pos.get("y") or 0) + dy / 2
        cz = float(pos.get("z") or 0) + dz / 2
        mx += m * cx
        my += m * cy
        mz += m * cz
        m_tot += m
    if m_tot <= 0:
        return None
    gx, gy, gz = mx / m_tot, my / m_tot, mz / m_tot
    # 偏心率：相对中心半宽
    lat_ecc = abs(gy - W / 2) / (W / 2) if W > 0 else 0
    long_pos = gx / L if L > 0 else 0.5
    height_ratio = gz / H if H > 0 else 0
    return {
        "gx_mm": round(gx, 1),
        "gy_mm": round(gy, 1),
        "gz_mm": round(gz, 1),
        "lateral_eccentricity": round(lat_ecc, 4),
        "longitudinal_position": round(long_pos, 4),
        "height_ratio": round(height_ratio, 4),
    }


def _heavy_on_top_ratio(plan: Dict[str, Any], boxes: List[Dict[str, Any]]) -> Optional[float]:
    layout = plan.get("layout") or []
    if not layout:
        return None
    wmap = {b.get("box_id"): float(b.get("gross_weight_kg") or 0) for b in boxes}
    total = sum(wmap.get(p.get("box_id"), 1.0) for p in layout) or 1.0
    top_w = 0.0
    for p in layout:
        z = float((p.get("position") or {}).get("z") or 0)
        layer = int(p.get("layer") or 1)
        if z > 100 or layer > 1:
            top_w += wmap.get(p.get("box_id"), 1.0)
    return top_w / total


def _explain(passed, level, score, items, plan, thr, hard_block) -> str:
    if hard_block:
        head = "存在阻断项，需整改后再出运。"
    elif passed:
        head = "规则侧可讨论出运，正式前仍需 VGM 与人工复核。"
    else:
        head = "存在关注风险，建议优化后出运。"
    outer_u = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    book_u = float(plan.get("booking_volume_utilization") or 0)
    util = (
        f"外廓摆柜 {outer_u:.0%}，"
        f"订柜有效体积 {book_u:.0%}，"
        f"重量 {float(plan.get('weight_utilization') or 0):.0%}，"
        f"can_fit={plan.get('can_fit')}。"
    )
    top = "；".join(i["message"] for i in items[:3]) or "无明显风险"
    return f"{head} 合规分 {score}（{level}）。{util} 关注：{top}"
