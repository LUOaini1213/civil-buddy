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

    space = float(plan.get("space_utilization") or 0)
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

    # 二层堆码统计
    layout = plan.get("layout") or []
    layer2 = sum(1 for p in layout if int(p.get("layer") or 1) >= 2 or float((p.get("position") or {}).get("z") or 0) > 0)
    stack_note = (
        f"二层箱数 {layer2}/{len(layout)}"
        if layout
        else "无布局"
    )

    lines = [
        "# 拼柜方案结果",
        "",
    ]
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
            "> 装得下（can_fit）不等于可出运。存在结构/合规阻断时必须整改后重跑 Team A→确认→Team B。"
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
        f"**主控流水线**：{orch.get('agent_count') or 9} 智能体（含主控，首尾选柜）",
        f"**方案编号（装箱）**：{state.get('packing_plan_id') or '-'}",
        f"**柜型（实际）**：{current_ct}",
        f"**主控开头推荐**：{start_rec or '-'}",
        f"**主控结尾推荐**：{end_rec or '-'}"
        + (f" ⚠️ 建议换柜为 {end_rec}" if switch else "（维持）"),
        f"**箱数**：{len(boxes)}",
        f"**能否装下（几何）**：{plan.get('can_fit')}",
        f"**能否出运（合规）**：{'是' if ship_ok else '否'}",
        f"**用柜数**：{plan.get('containers_used')}",
        f"**空间利用率（箱体外廓实心长方体）**：{space:.0%}"
        f"（最满柜 {space_best:.0%}，底面积均 {floor:.0%}；"
        f"货 {float(plan.get('cargo_solid_volume_m3') or 0):.2f} m³ / "
        f"柜 {float(plan.get('container_inner_volume_m3') or 0):.1f} m³）",
        f"**重量利用率**：{weight:.0%}",
        f"**堆码**：{stack_note}；策略=优先二层（矮箱/铁笼上二层，超长仅底层）",
        f"**利用综合分**：{evaluation.get('util_composite', '-')} "
        f"（空间子分 {evaluation.get('space_subscore', '-')} / "
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

    try:
        from packing_assistant.llm import chat, llm_available, llm_config

        if llm_available():
            polished = chat(
                system=(
                    "你是货运装箱顾问。根据结构化结果写简洁专业的中文汇总，"
                    "必须点明：实际柜型、主控是否建议换柜、容积/重量利用率、"
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

    return {
        "phase": phase,
        "status": status,
        "orchestrator": orch,
        "final_response": final,
        "risks": risks,
        "ship_ok": ship_ok,
        "messages": [{"role": "assistant", "content": final}],
    }
