"""主控汇总 + 结尾柜型复核。"""

from __future__ import annotations

from typing import Any, Dict

from packing_assistant.state import PackingState
from packing_assistant.tools.container_select import compare_after_load


def agent_finalize(state: PackingState) -> Dict[str, Any]:
    if state.get("user_action") == "cancel":
        return {
            "phase": "cancelled",
            "status": "success",
            "final_response": "已取消本轮拼柜。",
        }

    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    evaluation = state.get("evaluation") or {}
    risk_report = state.get("risk_report") or {}
    risks = state.get("risks") or risk_report.get("risks") or []
    blockers = list(risk_report.get("blockers") or [])
    image = state.get("image_data") or {}
    side_path = (image.get("side") or {}).get("path")

    orch = dict(state.get("orchestrator") or {})
    current_ct = (
        plan.get("container_type")
        or state.get("container_type")
        or orch.get("container_type_chosen")
        or "40HQ"
    )

    # —— 主控结尾：再检查一次柜型 ——
    end_review = compare_after_load(boxes, str(current_ct), plan)
    orch["container_select_end"] = end_review
    orch["container_review_done"] = True

    space = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    space_best = float(plan.get("space_utilization_best_container") or space)
    floor = float(plan.get("floor_utilization_avg") or 0)
    weight = float(plan.get("weight_utilization") or 0)

    start_rec = (orch.get("container_select_start") or {}).get("recommended")
    end_rec = end_review.get("recommended")
    switch = end_review.get("suggest_switch")

    # 合规：仅 REJECT（硬阻断/装不下）打回；WARN 可讨论出运
    risk_passed = bool(risk_report.get("passed"))
    risk_decision = str(risk_report.get("decision") or "")
    need_revision = bool(
        risk_report.get("need_revision")
        or risk_decision == "REJECT"
        or blockers
    )
    reject_to = risk_report.get("reject_to") or ""
    reject_reason = risk_report.get("reject_reason") or ""
    ship_ok = bool(plan.get("can_fit")) and not need_revision and risk_decision != "REJECT"
    # 缺尺寸 / 成箱阻断：硬否出运
    if state.get("materials_incomplete") or state.get("ship_ok") is False:
        ship_ok = False
    errs = state.get("errors") or []
    if any("missing_dims" in str(e).lower() or "缺尺寸" in str(e) for e in errs):
        ship_ok = False
    if not (state.get("boxes") or []) and state.get("materials"):
        # 有料无箱且非纯演示空跑 → 不可 ship
        ta = state.get("team_a_summary") or {}
        if ta.get("packing_mode") == "blocked_missing_dims":
            ship_ok = False
    # 可选：装前检查表强制
    _cl: Dict[str, Any] = {}
    try:
        from packing_assistant.pre_ship_checklist import (
            apply_checklist_to_ship_ok,
            build_pre_ship_checklist,
        )

        _cl = build_pre_ship_checklist(
            state, checked=(state.get("pre_ship_checked") or {})
        )
        ship_ok = apply_checklist_to_ship_ok(ship_ok, _cl)
    except Exception:
        _cl = {}

    # 二层堆码统计
    layout = plan.get("layout") or []
    layer2 = sum(1 for p in layout if int(p.get("layer") or 1) >= 2 or float((p.get("position") or {}).get("z") or 0) > 0)
    stack_note = (
        f"二层箱数 {layer2}/{len(layout)}"
        if layout
        else "无布局"
    )

    # 比赛用：大 Team 决策摘要（标准箱 / replan / feas）
    ta = state.get("team_a_summary") or {}
    std_audit = state.get("standard_box_audit") or {}
    feas = state.get("cargo_feasibility") or {}
    prop = state.get("replan_proposal") or {}
    # 收口知识引用（双口径 / 红线 / 评分）；不改 ship_ok 判定
    kb_evidence: list = []
    try:
        from packing_assistant.kb_bindings import brief_evidence

        q = (
            "双口径 ship_ok 出运"
            if ship_ok
            else f"红线 不可出运 {risk_decision} {prop.get('failure_class') or ''}"
        )
        kb_evidence = brief_evidence("finalize", q, max_snips=3)
    except Exception:
        kb_evidence = []

    decision_summary = {
        "container_type": current_ct,
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0") or (state.get("plan") or {}).get("n0"),
        "ship_ok": ship_ok,
        "risk_decision": risk_decision,
        "replan_round": state.get("replan_round"),
        "ship_replan_round": state.get("ship_replan_round"),
        "last_replan_route": prop.get("route"),
        "failure_class": prop.get("failure_class"),
        "n_boxes": len(boxes),
        "standard_box_hit_rate": std_audit.get("hit_rate")
        or ta.get("standard_box_hit_rate"),
        "box_type_counts": std_audit.get("by_type")
        or ta.get("standard_box_type_counts"),
        "feas_ok": feas.get("ok"),
        "team_mode": state.get("team_mode") or "big_team_a_b",
        "kb_evidence": kb_evidence,
    }

    lines = [
        "# 拼柜方案结果",
        "",
        "## 大 Team 决策摘要",
        "",
        f"- **组织**：大 Team ⊃ A 成箱 + B 拼柜 · mode=`{decision_summary['team_mode']}`",
        f"- **柜型/柜数**：{current_ct} · used={decision_summary.get('containers_used')} · N0={decision_summary.get('n0')}",
        f"- **can_fit / ship_ok**：{decision_summary.get('can_fit')} / **{ship_ok}**",
        f"- **风险**：{risk_decision or '—'} · replan_r={decision_summary.get('replan_round')} ship_r={decision_summary.get('ship_replan_round')}",
        f"- **标准箱命中**：{decision_summary.get('standard_box_hit_rate')}",
        f"- **可行性门禁**：feas_ok={decision_summary.get('feas_ok')}",
        f"- **箱型分布**：{decision_summary.get('box_type_counts')}",
        "",
    ]
    if kb_evidence:
        lines.append("## 知识库依据（窄接 finalize）")
        lines.append("")
        for ev in kb_evidence[:3]:
            lines.append(
                f"- `{ev.get('path')}` — {ev.get('title')}: {ev.get('snippet')}"
            )
        lines.append("")
    if need_revision or not ship_ok:
        lines.extend(
            [
                "## ⛔ 主控裁决：打回 / 不可出运",
                "",
                f"**能否出运**：**否**",
                f"**合规决策**：{risk_decision or 'REJECT'}（level={risk_report.get('level')}）",
                f"**打回目标**：{reject_to or 'await_user_confirm / 团队A 装箱方案'}",
                f"**打回原因**：{reject_reason or '风险合规未通过或存在阻断项'}",
            ]
        )
        if blockers:
            lines.append("**阻断项**：")
            for b in blockers[:12]:
                lines.append(f"- {b}")
        lines.append("")
        lines.append(
            "> 装得下（can_fit）不等于可出运。存在结构/合规阻断时须整改后在**同一 Team 闭环**内重跑。"
        )
        lines.append("")
    else:
        lines.extend(
            [
                "## ✅ 主控裁决：可讨论出运",
                "",
                f"**能否出运**：**是**（规则侧通过；正式前仍需 VGM 与人工复核）",
                "",
            ]
        )

    lines.extend(
        [
        f"**主控流水线**：单 Team 有界闭环（内环≤3 / 出运外环≤2）",
        f"**任务目标**：{orch.get('goal') or state.get('goal') or 'deliver_valid_pack_plan'}"
        f"（{orch.get('goal_desc') or '可解释成箱/订柜/拼柜方案'}）",
        f"**Agent 形态**：分工编排 + 工具执行 + 可选 HITL；"
        f"**数值由 tools 计算，非 LLM 编造**",
        f"**方案编号（装箱）**：{state.get('packing_plan_id') or '-'}",
        f"**柜型（实际）**：{current_ct}",
        f"**主控开头推荐**：{start_rec or '-'}",
        f"**主控结尾推荐**：{end_rec or '-'}"
        + (f" ⚠️ 建议换柜为 {end_rec}" if switch else "（维持）"),
        f"**箱数**：{len(boxes)}",
        f"**能否装下（几何）**：{plan.get('can_fit')}",
        f"**能否出运（合规）**：{'是' if ship_ok else '否'}",
    ]
    )
    booking = plan.get("booking") or state.get("booking") or (state.get("plan") or {}).get("booking") or {}
    n0 = plan.get("n0") or booking.get("n0") or (state.get("plan") or {}).get("n0")
    used_3d = plan.get("containers_used")
    # 固定双口径：订柜 N0（汇报） vs 3D 建议柜数（摆柜上界）— 禁止合成一个硬报
    lines.extend(
        [
            f"**订柜 N0**（重量+有效体积，给订舱/汇报）：**{n0 if n0 is not None else '-'}**",
            f"**3D 建议柜数**（当量外廓 can_fit 上界）：**{used_3d if used_3d is not None else '-'}**"
            + (
                f"（自 N0={n0} 递增）"
                if n0 is not None and used_3d is not None and int(used_3d or 0) > int(n0 or 0)
                else ""
            ),
            f"**外廓摆柜率**（仅布局松紧，不作订柜；铁架常见偏低）：{space:.0%}"
            f"（最满柜 {space_best:.0%}，底面积均 {floor:.0%}）",
            f"**订柜有效体积率**：{float(plan.get('booking_volume_utilization') or 0):.0%}"
            f"（V_eff=min(outer, content×k)，非空心架实心）",
            f"**重量利用率**：{weight:.0%}",
            f"**堆码**：{stack_note}；策略=优先二层（矮箱/铁笼上二层，超长仅底层）",
        ]
    )
    if booking:
        lines.append(
            f"**自主定柜明细**：重量柜={booking.get('containers_by_weight')} "
            f"有效体积柜={booking.get('containers_by_volume')} "
            f"绑定={booking.get('binding_constraint')} "
            f"PAYLOAD={booking.get('payload_kg')}kg η={booking.get('fill_ratio')}"
        )
        if booking.get("volume_suspicious") or booking.get("warning"):
            lines.append(f"**体积可疑 WARN**：{booking.get('warning') or 'N_volume≥2×N_weight'}")
        if n0 is not None and used_3d is not None and int(used_3d or 0) > int(n0 or 0):
            lines.append(
                f"**口径说明**：3D={used_3d} > 订柜 N0={n0} 属成箱/摆柜上界，"
                f"不是又一次体积虚高；订舱仍以 N0 为准，工程可备注精细合箱争取贴近 N0。"
            )

    opts = state.get("packing_options") or {}
    if ta.get("standard_boxes") or opts.get("standard_boxes", True):
        mix_on = ta.get("mix_mode") if ta.get("mix_mode") is not None else opts.get("mix_mode", True)
        counts = ta.get("standard_box_type_counts") or {}
        count_s = "、".join(f"{k}×{v}" for k, v in list(counts.items())[:8]) or "-"
        lines.append(
            f"**装箱模式**：标准箱库外廓"
            f"{'+跨长度档混装' if mix_on else ''}；"
            f"箱型分布 {count_s}；"
            f"箱外廓合计 {ta.get('boxes_outer_volume_m3', '-')} m³，"
            f"货件 {ta.get('cargo_item_volume_m3', '-')} m³，"
            f"箱内填充均 {float(ta.get('avg_crate_fill') or 0):.0%}"
        )
    elif ta.get("dense_mode") or opts.get("dense_mode"):
        lines.append(
            f"**装箱模式**：密装 dense（贴货外廓，不强制 1150 宽/1.2m 层高）；"
            f"箱外廓合计 {ta.get('boxes_outer_volume_m3', '-')} m³，"
            f"货件体积 {ta.get('cargo_item_volume_m3', '-')} m³，"
            f"箱内填充均 {float(ta.get('avg_crate_fill') or 0):.0%}"
        )
    lines.extend(
        [
        f"**利用综合分**：{evaluation.get('util_composite', '-')} "
        f"（订柜有效体积子分 {evaluation.get('booking_volume_subscore') or evaluation.get('space_subscore', '-')} / "
        f"底面积子分 {evaluation.get('floor_subscore', '-')} / "
        f"重量子分 {evaluation.get('weight_subscore', '-')}）",
        f"**评估分**：{evaluation.get('score', '-') }（passed={evaluation.get('passed')} "
        f"decision={evaluation.get('decision', '-')}）",
        f"**合规分**：{risk_report.get('compliance_score', '-') }（level={risk_report.get('level')} "
        f"decision={risk_decision or '-'}）",
        "",
        "## 主控选柜说明",
        ]
    )
    for r in (end_review.get("reasons") or [])[:6]:
        lines.append(f"- {r}")
    if not end_review.get("reasons"):
        lines.append("- （无额外说明）")

    lines.append("")
    lines.append("## 风险摘要")
    if risks:
        for r in risks[:20]:
            lines.append(f"- {r}")
    else:
        lines.append("- 无明显风险")
    lines.append("")
    lines.append("## 合规说明")
    lines.append(risk_report.get("explanation") or "无")
    lines.append("")
    lines.append("## 布局")
    lines.append("- 三视角数据：views.top/side/front 已生成")
    if side_path:
        lines.append(f"- 侧视 PNG：{side_path}")
    lines.append(f"- 装载引擎：{plan.get('engine', 'unknown')}")
    lines.append("")
    lines.append("---")
    lines.append(end_review.get("review_message") or "主控复核完成。")
    if need_revision or not ship_ok:
        lines.append(
            f"**流程状态：已打回** → 请按「{reject_to or 'box_scheme'}」整改后重跑；"
            "在合规通过前不得作为正式出运方案。"
        )
    else:
        lines.append("团队B 完成。如需改柜型请重新确认。")

    final = "\n".join(lines)

    # 默认关闭 LLM 润色：UI/网关路径上 DeepSeek 慢或挂起会表现为「整页卡住」。
    # 需要润色时设 PACKING_FINALIZE_LLM=1。
    try:
        import os

        from packing_assistant.llm import chat, llm_available, llm_config

        _want_llm = (os.getenv("PACKING_FINALIZE_LLM") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if _want_llm and llm_available():
            polished = chat(
                system=(
                    "你是货运装箱顾问。根据结构化结果写简洁专业的中文汇总，"
                    "必须点明：实际柜型、主控是否建议换柜、"
                    "外廓摆柜率/订柜有效体积率/重量利用率（三者分开，勿把外廓当订柜）、"
                    "能否装下 vs 能否出运；若合规 REJECT 必须明确写「打回/不可出运」。"
                    "保留关键数字，不要编造。控制在 400 字内。"
                ),
                user=final,
                temperature=0.2,
                max_tokens=800,
            )
            if polished and not polished.startswith("[LLM_ERROR]"):
                cfg = llm_config()
                final = (
                    f"{polished}\n\n---\n"
                    f"<details><summary>结构化原文</summary>\n\n{final}\n\n</details>\n"
                    f"\n*LLM: {cfg.get('model')}*"
                )
            elif polished and polished.startswith("[LLM_ERROR]"):
                final = final + f"\n\n> LLM 润色失败：{polished}"
    except Exception:
        pass

    if not boxes:
        status = "need_more_info"
        phase = "done"
    elif need_revision or not ship_ok:
        status = "rejected"
        phase = "need_revision"
    else:
        status = "success"
        phase = "done"

    # 显式裁决（前端横幅 / 状态栏，不依赖 PDF）
    try:
        from packing_assistant.verdict import build_verdict

        _pre = {
            **state,
            "ship_ok": ship_ok,
            "phase": phase,
            "status": status,
            "container_plan": plan,
            "risk_report": risk_report,
            "decision_summary": decision_summary,
        }
        verdict = build_verdict(_pre)
    except Exception:
        verdict = {
            "level": "block" if not ship_ok else "ok",
            "title": "⛔ 不可出运" if not ship_ok else "✅ 可讨论出运",
            "summary": reject_reason or risk_decision or "",
            "headline": f"ship_ok={ship_ok} can_fit={plan.get('can_fit')}",
            "issues": blockers[:5] if not ship_ok else [],
            "show_banner": True,
        }

    # 目标声明与达成判断（评委可指着看）
    goal_name = str(
        state.get("goal")
        or orch.get("goal")
        or "deliver_valid_pack_plan"
    )
    goal_status = {
        "goal": goal_name,
        "achieved": bool(ship_ok and plan.get("can_fit")),
        "ship_ok": ship_ok,
        "can_fit": bool(plan.get("can_fit")),
        "risk_decision": risk_decision or ("PASS" if ship_ok else "REJECT"),
        "verdict": (
            "建议订舱/可讨论出运"
            if ship_ok
            else f"不可出运：{reject_reason or risk_decision or '合规未通过'}"
        ),
        "n0": n0,
        "containers_used": used_3d,
        "criteria": {
            "geometry_ok": bool(plan.get("can_fit")),
            "compliance_ok": risk_decision != "REJECT" and not blockers,
            "has_boxes": bool(boxes),
        },
    }

    # 在 finalize 文案中显式目标块
    goal_block = [
        "",
        "## 目标达成",
        "",
        f"- **goal**: `{goal_name}`",
        f"- **是否达成**: {'是' if goal_status['achieved'] else '否'}",
        f"- **裁决**: {goal_status['verdict']}",
        f"- **几何 can_fit**: {goal_status['can_fit']} | **合规**: {goal_status['risk_decision']}",
        "",
    ]
    # 插入到标题后
    if final.startswith("# 拼柜方案结果"):
        parts = final.split("\n", 2)
        if len(parts) >= 2:
            final = parts[0] + "\n" + "\n".join(goal_block) + (parts[2] if len(parts) > 2 else "")
        else:
            final = final + "\n" + "\n".join(goal_block)
    else:
        final = "\n".join(goal_block) + "\n" + final

    suggested = list(risk_report.get("suggested_actions") or [])
    if suggested and (need_revision or not ship_ok):
        final += "\n\n## 建议行动\n\n" + "\n".join(f"- {a}" for a in suggested[:6])

    # —— 8 条 Agent 工件：PackingPlan / HITL门 / 步骤工单 / VGM草稿 / plan_diff / 绑扎工单 ——
    packing_plan = {}
    hitl_gates = {}
    load_sequence = {}
    vgm_draft = {}
    plan_diff = {}
    secure_work_order = {}
    por_manifest = {}
    try:
        from packing_assistant.tools.secure_work_order import build_secure_work_order

        secure_work_order = build_secure_work_order(plan, boxes)
    except Exception:
        secure_work_order = {}
    try:
        from packing_assistant.tools.por_manifest import build_por_manifest

        por_manifest = build_por_manifest(
            plan, boxes, materials=state.get("materials") or []
        )
    except Exception:
        por_manifest = {}
    try:
        from packing_assistant.packing_plan import build_packing_plan

        packing_plan = build_packing_plan(
            {
                **state,
                "container_plan": plan,
                "evaluation": evaluation,
                "risk_report": risk_report,
                "secure_work_order": secure_work_order,
                "por_manifest": por_manifest,
            },
            previous=state.get("packing_plan") if isinstance(state.get("packing_plan"), dict) else None,
        )
    except Exception:
        packing_plan = {}
    try:
        from packing_assistant.hitl_gates import evaluate_hitl_gates

        hitl_gates = evaluate_hitl_gates(
            {**state, "container_plan": plan, "risk_report": risk_report, "packing_plan": packing_plan}
        )
    except Exception:
        hitl_gates = {}
    try:
        from packing_assistant.tools.load_sequence import build_load_sequence

        load_sequence = build_load_sequence(plan, boxes)
    except Exception:
        load_sequence = {}
    try:
        from packing_assistant.tools.vgm_draft import draft_vgm_method2

        vgm_draft = draft_vgm_method2(plan, boxes)
    except Exception:
        vgm_draft = {}
    try:
        from packing_assistant.tools.plan_diff import diff_packing_plans

        prev_pp = state.get("packing_plan") if isinstance(state.get("packing_plan"), dict) else None
        if prev_pp and packing_plan:
            plan_diff = diff_packing_plans(prev_pp, packing_plan)
    except Exception:
        plan_diff = {}

    if secure_work_order.get("items"):
        final += (
            f"\n\n## 绑扎/空隙工单（WARN，不拦出运）\n\n"
            f"{secure_work_order.get('summary')}\n"
        )
        for it in (secure_work_order.get("items") or [])[:8]:
            final += (
                f"- [{it.get('severity')}] {it.get('type')} "
                f"柜{it.get('container_no') or '-'} {it.get('box_id') or ''}: "
                f"{it.get('action')}\n"
            )
    if por_manifest.get("by_part"):
        final += f"\n\n## POR 装柜单\n\n{por_manifest.get('summary')}\n"
        for p in (por_manifest.get("by_part") or [])[:10]:
            final += (
                f"- {p.get('part_no')}: {p.get('total_kg')}kg / "
                f"{p.get('n_boxes')}箱 → 柜{p.get('containers')}\n"
            )
    # 装前检查表 + 轻量稳性 + 运价占位
    pre_ship_checklist = _cl if isinstance(_cl, dict) else {}
    if not pre_ship_checklist:
        try:
            from packing_assistant.pre_ship_checklist import build_pre_ship_checklist

            pre_ship_checklist = build_pre_ship_checklist(
                state, checked=(state.get("pre_ship_checked") or {})
            )
        except Exception:
            pre_ship_checklist = {}
    stability = {}
    freight = {}
    try:
        from packing_assistant.p2_stubs import estimate_freight_stub, tip_slide_score

        stability = tip_slide_score(plan, boxes)
        freight = estimate_freight_stub(plan)
    except Exception:
        pass
    if pre_ship_checklist.get("items"):
        final += (
            f"\n\n## 装前检查表\n\n{pre_ship_checklist.get('summary')}\n"
            f"（require_for_final={pre_ship_checklist.get('require_for_final_ship_ok')}）\n"
        )
    if stability.get("risk_score") is not None:
        final += (
            f"\n\n## 稳性启发式\n\n"
            f"tip/slide 风险分 **{stability.get('risk_score')}** "
            f"（{stability.get('level')}，非 FEM）\n"
        )
    if freight.get("total") is not None:
        final += (
            f"\n\n## 运价占位\n\n"
            f"约 **{freight.get('total')} {freight.get('currency')}** "
            f"（{freight.get('containers')}×40HQ，非真价）\n"
        )
    if load_sequence.get("steps"):
        final += (
            f"\n\n## 装柜工单\n\n"
            f"{load_sequence.get('message')}\n"
            f"- 首步: {(load_sequence['steps'][0].get('instruction') if load_sequence['steps'] else '-')}\n"
            f"- 末步: {(load_sequence['steps'][-1].get('instruction') if load_sequence['steps'] else '-')}\n"
        )
    if vgm_draft.get("status"):
        tot = vgm_draft.get("totals") or {}
        final += (
            f"\n\n## VGM 草稿 (Method 2)\n\n"
            f"- 状态: **{vgm_draft.get('status')}**（禁止自动申报）\n"
            f"- 货重合计 {tot.get('cargo_kg')} kg + 包装估算 {tot.get('packaging_kg')} kg "
            f"+ 垫料 {tot.get('dunnage_kg')} kg；单柜 VGM 见 per_container\n"
            f"- {vgm_draft.get('disclaimer', '')}\n"
        )
    if packing_plan:
        final += (
            f"\n\n## PackingPlan\n\n"
            f"- schema={packing_plan.get('schema')} v{packing_plan.get('version')} "
            f"id={packing_plan.get('plan_id')}\n"
            f"- mid50={((packing_plan.get('cog') or {}).get('mass_in_mid50_ratio'))} "
            f"stacked={((packing_plan.get('stacking') or {}).get('stacked_placements'))}\n"
        )
    if hitl_gates.get("gates"):
        final += (
            f"\n\n## HITL 门禁\n\n"
            f"- require_hitl={hitl_gates.get('require_hitl')} "
            f"can_auto={hitl_gates.get('can_auto_confirm')}\n"
            f"- {hitl_gates.get('summary')}\n"
        )

    return {
        "phase": phase,
        "status": status,
        "orchestrator": orch,
        "final_response": final,
        "decision_summary": decision_summary,
        "verdict": verdict,
        "kb_evidence": kb_evidence,
        "risks": risks,
        "ship_ok": ship_ok,
        "goal": goal_name,
        "goal_status": goal_status,
        "packing_plan": packing_plan,
        "packing_plan_id": packing_plan.get("plan_id") if packing_plan else state.get("packing_plan_id"),
        "hitl_gates": hitl_gates,
        "load_sequence": load_sequence,
        "vgm_draft": vgm_draft,
        "plan_diff": plan_diff,
        "secure_work_order": secure_work_order,
        "por_manifest": por_manifest,
        "pre_ship_checklist": pre_ship_checklist,
        "stability_tip_slide": stability,
        "freight_estimate": freight,
        "agent_meta": {
            "node": "finalize",
            "capability": ["追求目标", "采取行动"],
            "tools_used": ["container_select.compare_after_load"],
            "plan": "汇总柜型复核与出运裁决",
            "act": "生成 final_response + packing_plan 工件",
            "observe": (
                f"ship_ok={ship_ok} can_fit={plan.get('can_fit')} "
                f"std_hit={decision_summary.get('standard_box_hit_rate')}"
            ),
            "reflect": "可讨论订舱" if ship_ok else "不可出运/需整改",
            "artifacts": {**goal_status, "decision_summary": decision_summary},
        },
        "messages": [{"role": "assistant", "content": final}],
    }
