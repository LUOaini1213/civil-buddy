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
    packing_opts = dict(state.get("packing_options") or {})
    export_strict = bool(
        packing_opts.get("export_strict")
        or (plan.get("stacking") or {}).get("export_strict")
    )

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
        if b.get("structure_conclusion") == "待详设" or "待详设" in special:
            add(
                "STRUCTURE_AWAIT_DESIGN",
                "high",
                "未提供详设结构事实，不可作正式出运结构依据（请提交截面/图纸或用自然语言指定）",
                "structure",
                bid,
                score=16,
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
    cog = _cog_metrics(plan, boxes)
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

        # 更严：>5% medium；>10% high；≥15% 默认 block
        # 大票多柜 + mid50 已过出运软线：横向偏心改 WARN（避免压柜成功后仍 hard REJECT）
        n_used = int(plan.get("containers_used") or 0)
        mid_soft = None
        try:
            mid_soft = float(
                (plan.get("worst_mid50") if plan.get("worst_mid50") is not None else None)
                or cog.get("mass_in_mid50_ratio")
            )
        except Exception:
            mid_soft = None
        multi_soft_lat = n_used >= 6 and mid_soft is not None and mid_soft + 1e-9 >= 0.55
        if lat_ecc >= lat_block or lat_ecc >= 0.15:
            if multi_soft_lat:
                add(
                    "COG_LAT",
                    "high",
                    f"左右重心偏心率 {lat_ecc:.1%}（宜≤5%；大票多柜 mid50≥55% 降为预警非硬阻断）",
                    "layout",
                    None,
                    score=14,
                    raw_value=lat_ecc,
                    block=False,
                )
            else:
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

        # CTU 60/50：质量在柜长中段 50% 带的占比；仅极端阻断
        mid50 = cog.get("mass_in_mid50_ratio")
        mid50_ok = cog.get("mid50_ok")
        if mid50 is not None:
            mid50_f = float(mid50)
            if mid50_f < 0.40:
                add(
                    "COG_MID50",
                    "high",
                    f"中段50%质量占比 {mid50_f:.0%}（CTU 60/50 宜≥60%，<40% 阻断）",
                    "layout",
                    None,
                    score=16,
                    raw_value=mid50_f,
                    block=True,
                )
            elif mid50_ok is False or mid50_f < 0.60:
                # 出运严模式：<60% 即阻断；日常仅 medium
                add(
                    "COG_MID50",
                    "high" if export_strict else "medium",
                    f"中段50%质量占比 {mid50_f:.0%}（CTU 60/50 宜≥60%"
                    f"{'，出运模式阻断' if export_strict else '，建议重货移向柜中段'}）",
                    "layout",
                    None,
                    score=14 if export_strict else 8,
                    raw_value=mid50_f,
                    block=bool(export_strict),
                )

        # 垂直重心：>0.55 警告；>0.70 或 export_strict 且>0.60 阻断
        height_ratio = cog.get("height_ratio")
        vertical_ok = cog.get("vertical_ok")
        if height_ratio is not None:
            hr = float(height_ratio)
            if hr > 0.70 or (export_strict and hr > 0.60):
                add(
                    "COG_HEIGHT",
                    "high",
                    f"重心高度比 {hr:.0%}（宜≤55% 舱高，过高阻断）",
                    "layout",
                    None,
                    score=16,
                    raw_value=hr,
                    block=True,
                )
            elif vertical_ok is False or hr > 0.55:
                add(
                    "COG_HEIGHT",
                    "medium" if hr <= 0.70 else "high",
                    f"重心高度比 {hr:.0%}（宜≤55% 舱高，过高不利稳性）",
                    "layout",
                    None,
                    score=10 if hr <= 0.70 else 14,
                    raw_value=hr,
                )

    # —— CTU 水平空隙 ~15cm + 集中载荷 + 可叠未叠 ——
    lq = plan.get("layout_quality")
    if not isinstance(lq, dict):
        try:
            from packing_assistant.tools.layout_quality import analyze_layout_quality

            lq = analyze_layout_quality(plan, boxes, void_limit_mm=150.0)
        except Exception:
            lq = {}
    if lq:
        max_gap = float(lq.get("max_horizontal_gap_mm") or 0)
        n_over = int(lq.get("gaps_over_limit") or 0)
        # 空隙：日常仅 warning（中段堆码两端空档常见）；出运严模式 + 中等空隙才阻断
        if n_over > 0 or max_gap > 150:
            # 超大空档(>1m)多为分堆，提示加固；150–400mm 才是典型 rattling 空隙
            rattling = 150 < max_gap <= 800
            sev = "medium"
            do_block = False
            if export_strict and rattling:
                sev = "high"
                do_block = max_gap > 200
            elif max_gap > 800:
                sev = "medium"  # 分堆：加固/填缝建议，不硬杀叠高方案
            add(
                "VOID_GAP_15CM",
                sev,
                f"同层水平空隙最大 {max_gap:.0f}mm（CTU 宜≤150mm 否则须加固/填缝），超限条数 {n_over}",
                "layout",
                None,
                score=10 if export_strict else 5,
                raw_value={"max_gap_mm": max_gap, "over": n_over, "rattling": rattling},
                block=do_block,
            )
        for fl in (lq.get("concentrated_load_flags") or [])[:8]:
            code = str(fl.get("code") or "CONCENTRATED_LOAD")
            # 0.25P 垫梁：WARN 分，不 block（ship_ok 不拦）
            add(
                code if code.startswith("PAD_") else "CONCENTRATED_LOAD",
                "medium",
                f"{fl.get('box_id')}: 毛重 {fl.get('weight_kg')}kg"
                + (
                    f" ({float(fl.get('payload_fraction') or 0):.0%}P)"
                    if fl.get("payload_fraction")
                    else f" / 底面 {fl.get('footprint_m2')}m²"
                )
                + f" — {fl.get('hint')}",
                "layout",
                fl.get("box_id"),
                score=7 if code == "PAD_BEAM_025P" else 6,
                raw_value=fl,
                block=False,
            )
        if lq.get("stackable_floor_only"):
            add(
                "STACKABLE_FLOOR_ONLY",
                "low" if not export_strict else "medium",
                f"可叠箱约 {lq.get('stackable_count')} 件但均未上二层，检查 prefer_stack/限高",
                "layout",
                None,
                score=4 if not export_strict else 8,
                raw_value=lq.get("stackable_count"),
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
    cog_blocks = [
        b
        for b in blockers
        if any(k in str(b) for k in ("重心", "中段50%", "偏心", "COG", "60/50"))
    ]
    # 可自动闭环重排（非仅人工）：结构→box_scheme；装不下/重心→planner
    auto_replanable = False
    if hard_block and struct_blocks:
        decision = "REJECT"
        reject_to = "box_scheme"  # 回团队A改箱/拆件
        reject_reason = "成箱结构不通过，打回装箱方案智能体拆箱或改箱型加固"
        need_revision = True
        auto_replanable = True
    elif hard_block and cog_blocks:
        decision = "REJECT"
        reject_to = "planner"
        reject_reason = "重心/60/50 不合规，打回规划·装载重排"
        need_revision = True
        auto_replanable = True
    elif hard_block:
        # 其它硬阻断：优先尝试 planner 闭环，仍失败再人工
        decision = "REJECT"
        reject_to = "planner"
        reject_reason = "存在合规阻断项，先自动重排；仍失败则人工确认"
        need_revision = True
        auto_replanable = True
    elif not plan.get("can_fit"):
        decision = "REJECT"
        reject_to = "planner"
        reject_reason = "未能全部装入集装箱，打回规划/加柜"
        need_revision = True
        auto_replanable = True
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
        # 重心软问题：仅 mid50<40% 或未做过出运重排时自动打回一次；≥40% 停损可出运
        ship_r = int(state.get("ship_replan_round") or 0)
        mid_v = None
        try:
            mid_v = float(cog.get("mass_in_mid50_ratio")) if cog and cog.get("mass_in_mid50_ratio") is not None else None
        except Exception:
            mid_v = None
        bal = str((cog or {}).get("balance") or "")
        if mid_v is not None and mid_v < 0.40:
            auto_replanable = True
            reject_to = "planner"
            need_revision = True
            decision = "REJECT"
            reject_reason = "mid50 低于出运硬线 40%，自动重排"
        elif mid_v is not None and mid_v < 0.55 and ship_r < 1:
            auto_replanable = True
            reject_to = "planner"
            need_revision = True
            decision = "REJECT"
            reject_reason = "mid50 未达 55%，自动重排一轮（之后停损）"
        elif bal == "block" and (mid_v is None or mid_v < 0.40):
            auto_replanable = True
            reject_to = "planner"
            need_revision = True
            decision = "REJECT"
            reject_reason = "重心 balance=block，自动重排"
        # else: 保持 WARN，可讨论出运（停损）
    else:
        decision = "PASS"
        reject_to = ""
        reject_reason = ""
        need_revision = False

    # REJECT 后建议行动（规则，不 LLM 瞎改数字）
    suggested_actions = _suggested_actions(
        decision=decision,
        blockers=blockers,
        items=items,
        plan=plan,
        reject_to=reject_to,
    )

    # 与 finalize 对齐：几何装下 + 决策非 REJECT → 可讨论/可出运
    # WARN 也算 ship_ok（须绑扎复核，但不自动打回）
    ship_ok = bool(plan.get("can_fit")) and decision in ("PASS", "WARN") and not hard_block

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
        "suggested_actions": suggested_actions,
        "explanation": explanation,
        "principles": thr.get("loading_principles") or [],
        "cog": cog,
        "layout_quality": lq if isinstance(lq, dict) else {},
        "export_strict": export_strict,
        "auto_replanable": bool(auto_replanable),
        "ship_ok": ship_ok,
        # 指标别名：前端/出图脚本常读 floor_utilization
        "metrics": {
            "outer_space_utilization": plan.get("outer_space_utilization")
            or plan.get("space_utilization"),
            "booking_volume_utilization": plan.get("booking_volume_utilization"),
            "floor_utilization": plan.get("floor_utilization_avg")
            or plan.get("floor_utilization"),
            "weight_utilization": plan.get("weight_utilization"),
            "containers_used": plan.get("containers_used"),
            "can_fit": plan.get("can_fit"),
        },
    }

    tools_used = ["risk_rules.thresholds", "risk_compliance.cog_metrics", "layout_quality"]
    msg = (
        f"【风险】level={level} score={score} passed={passed} "
        f"decision={decision} blockers={len(blockers)}"
    )
    if need_revision:
        loop_hint = "（将自动闭环重排）" if auto_replanable else ""
        msg += f" ⛔打回→{reject_to or '人工'}{loop_hint}：{reject_reason}"
    if suggested_actions:
        msg += f" 建议：{'；'.join(suggested_actions[:4])}"
    msg += f"｜tools={','.join(tools_used)}"

    updates: Dict[str, Any] = {
        "risk_report": risk_report,
        "risks": risks,
        "ship_ok": ship_ok,
        "agent_meta": {
            "node": "risk_compliance",
            "capability": ["使用工具", "追求目标"],
            "tools_used": tools_used,
            "artifacts": {
                "decision": decision,
                "level": level,
                "ship_ok": ship_ok,
                "blockers": len(blockers),
                "suggested_actions": suggested_actions,
                "auto_replanable": auto_replanable,
                "reject_to": reject_to,
            },
        },
        "messages": [{"role": "assistant", "content": msg}],
    }
    # 可自动重排时不立刻锁死 phase=need_revision（留给 harness 闭环）
    if need_revision and not auto_replanable:
        updates["phase"] = "need_revision"
        updates["status"] = "rejected"
    elif need_revision and auto_replanable:
        updates["phase"] = "team_b_running"
        updates["status"] = "running"
    return updates


def _suggested_actions(
    *,
    decision: str,
    blockers: List[str],
    items: List[Dict[str, Any]],
    plan: Dict[str, Any],
    reject_to: str,
) -> List[str]:
    """规则建议：减载/换柜/加固/加柜，不改数字。"""
    acts: List[str] = []
    joined = " ".join(blockers) + " " + " ".join(str(i.get("message") or "") for i in items)
    if decision == "PASS" and not blockers:
        acts.append("规则侧可讨论出运；正式前完成 VGM 与人工复核")
        return acts
    if "结构" in joined or reject_to == "box_scheme":
        acts.append("加固：按结构方案加垫木/钢骨或拆重件改箱型后重跑装箱")
    if "超重" in joined or "重量利用率" in joined:
        acts.append("减载：拆分超重箱或分票出运，使单柜 ≤ PAYLOAD")
    if not plan.get("can_fit") or "未装入" in joined or "无法全部装下" in joined:
        acts.append("加柜：接受 3D 递增后的用柜数，或合箱压外廓后再装")
    if "重心" in joined or "偏心" in joined or "中段50%" in joined:
        acts.append("配重/重排：左右对称摆放，重货靠近柜中线/中段50%")
    if "高度比" in joined:
        acts.append("降重心：重箱底层、限层叠高，避免上层堆满轻货抬高 COG")
    if "上层重货" in joined:
        acts.append("堆码调整：重箱改底层，矮轻箱上二层")
    if decision == "REJECT" and not acts:
        acts.append("按阻断项整改后自 Team A 或确认闸门重跑")
    if decision == "WARN" and not acts:
        acts.append("可讨论出运，但须人工关注 WARN 项并做好绑扎记录")
    if reject_to == "await_user_confirm":
        acts.append("HITL：人工确认柜型/箱清单后重新进入拼柜")
    # 去重保序
    seen = set()
    out: List[str] = []
    for a in acts:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out[:6]


def _cog_metrics(
    plan: Dict[str, Any],
    boxes: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, float]]:
    """按柜内尺寸 + 毛重优先/体积代理计算重心（主柜）。"""
    try:
        from packing_assistant.tools.cog import compute_cog_bundle

        bundle = compute_cog_bundle(plan, boxes)
        if not bundle:
            return None
        primary = bundle.get("primary") or {}
        # 兼容旧字段 + 扩展
        return {
            "gx_mm": primary.get("gx_mm"),
            "gy_mm": primary.get("gy_mm"),
            "gz_mm": primary.get("gz_mm"),
            "lateral_eccentricity": primary.get("lateral_eccentricity"),
            "longitudinal_position": primary.get("longitudinal_position"),
            "height_ratio": primary.get("height_ratio"),
            "mass_in_mid50_ratio": primary.get("mass_in_mid50_ratio"),
            "mid50_ok": primary.get("mid50_ok"),
            "vertical_ok": primary.get("vertical_ok"),
            "mass_basis": primary.get("mass_basis"),
            "balance": primary.get("balance"),
            "labels": primary.get("labels"),
            "thresholds": primary.get("thresholds"),
            "per_container": bundle.get("per_container") or [],
            "caption": bundle.get("caption"),
        }
    except Exception:
        return None


def _heavy_on_top_ratio(plan: Dict[str, Any], boxes: List[Dict[str, Any]]) -> Optional[float]:
    """重压轻占比：上层箱毛重 > 1.25× 支撑箱均重 的上层质量 / 总质量。

    注意：等重正常叠层不算「重货在上」（旧实现把任意 z>0 都当重货会误杀叠高）。
    """
    layout = plan.get("layout") or []
    if not layout:
        return None
    wmap = {b.get("box_id"): float(b.get("gross_weight_kg") or 0) for b in boxes}
    total = sum(wmap.get(p.get("box_id"), 0.0) for p in layout) or 1.0
    # 建顶面索引
    supports_at: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    for p in layout:
        pos = p.get("position") or {}
        size = p.get("size") or {}
        z = int(pos.get("z") or 0)
        dz = int(size.get("dz") or 0)
        top = z + dz
        supports_at.setdefault(top, []).append(p)

    bad_w = 0.0
    for p in layout:
        pos = p.get("position") or {}
        size = p.get("size") or {}
        z = int(pos.get("z") or 0)
        if z <= 0:
            continue
        uw = wmap.get(p.get("box_id"), 0.0)
        if uw <= 0:
            continue
        px, py = float(pos.get("x") or 0), float(pos.get("y") or 0)
        dx, dy = float(size.get("dx") or 0), float(size.get("dy") or 0)
        under = []
        for s in supports_at.get(z, []):
            sp, ss = s.get("position") or {}, s.get("size") or {}
            sx, sy = float(sp.get("x") or 0), float(sp.get("y") or 0)
            sdx, sdy = float(ss.get("dx") or 0), float(ss.get("dy") or 0)
            if not (px + dx <= sx or sx + sdx <= px or py + dy <= sy or sy + sdy <= py):
                under.append(wmap.get(s.get("box_id"), 0.0))
        if not under:
            continue
        avg_u = sum(under) / len(under)
        if avg_u > 0 and uw > avg_u * 1.25:
            bad_w += uw
    return bad_w / total


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
