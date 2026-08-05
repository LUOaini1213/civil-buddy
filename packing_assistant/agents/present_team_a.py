"""团队A 完成后：生成用户确认载荷，进入 await_user_confirm。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from packing_assistant.state import PackingState
from packing_assistant.trace import new_run_id


def agent_present_team_a(state: PackingState) -> Dict[str, Any]:
    boxes = state.get("boxes") or []
    materials = state.get("materials") or []
    mat_sum = state.get("materials_summary") or {}
    ta = state.get("team_a_summary") or {}
    notes = list(state.get("structure_notes") or [])

    plan_id = state.get("packing_plan_id") or f"PKG-{new_run_id()}"
    suggested = _suggest_containers(boxes)
    reason = _suggest_reason(boxes, ta)

    # 箱型统计
    by_type: Dict[str, Dict[str, Any]] = {}
    heaviest_id, heaviest_w = "", -1.0
    longest_id, longest_l = "", -1.0
    for b in boxes:
        bt = b.get("box_type") or "未知"
        g = float(b.get("gross_weight_kg") or 0)
        L = float((b.get("outer_size_mm") or {}).get("length") or 0)
        rec = by_type.setdefault(bt, {"box_type": bt, "count": 0, "gross_weight_kg": 0.0})
        rec["count"] += 1
        rec["gross_weight_kg"] = round(rec["gross_weight_kg"] + g, 2)
        if g > heaviest_w:
            heaviest_w, heaviest_id = g, b.get("box_id") or ""
        if L > longest_l:
            longest_l, longest_id = L, b.get("box_id") or ""

    summary = {
        "material_line_count": mat_sum.get("material_line_count") or len(materials),
        "total_pieces": mat_sum.get("total_pieces") or 0,
        "total_material_weight_kg": mat_sum.get("total_weight_kg") or 0,
        "box_count": len(boxes),
        "total_net_weight_kg": ta.get("total_net_weight_kg") or 0,
        "total_gross_weight_kg": ta.get("total_gross_weight_kg") or 0,
        "structure_overall": ta.get("structure_overall") or "",
        "structure_pass": ta.get("pass") or 0,
        "structure_reinforce": ta.get("reinforce") or 0,
        "structure_fail": ta.get("fail") or 0,
        "suggested_container_types": suggested,
        "container_suggestion_reason": reason,
        # 透传装箱模式指标（标准箱/混装/dense）
        "dense_mode": ta.get("dense_mode"),
        "standard_boxes": ta.get("standard_boxes"),
        "mix_mode": ta.get("mix_mode"),
        "packing_mode": ta.get("packing_mode"),
        "boxes_outer_volume_m3": ta.get("boxes_outer_volume_m3"),
        "cargo_item_volume_m3": ta.get("cargo_item_volume_m3"),
        "avg_crate_fill": ta.get("avg_crate_fill"),
        "standard_box_type_counts": ta.get("standard_box_type_counts"),
        "max_box_net_kg": ta.get("max_box_net_kg"),
        "pass": ta.get("pass") or 0,
        "reinforce": ta.get("reinforce") or 0,
        "fail": ta.get("fail") or 0,
    }

    # HITL 作为工具节点：环境反馈（确认/改方案/取消），非流程断裂
    hitl_auto = bool(state.get("enable_auto_confirm"))
    hitl_policy = {
        "mode": "auto_confirm" if hitl_auto else "await_user",
        "timeout_note": (
            "demo/API 可 enable_auto_confirm 跳过闸门；正式路径等待用户 confirm/revise/cancel"
        ),
        "as_tool": "hitl.confirm_gate",
        "feedback": "用户选择柜型与 action，作为下游 planner/loader 的环境输入",
    }

    user_prompt = {
        "title": "请确认装箱方案并选择集装箱类型",
        "required_fields": ["action", "container_type"],
        "hitl_policy": hitl_policy,
        "container_options": [
            {"value": "40HQ", "label": "40HQ 高柜", "recommended": "40HQ" in suggested},
            {"value": "40GP", "label": "40GP 平柜", "recommended": "40GP" in suggested},
            {"value": "20GP", "label": "20GP", "recommended": "20GP" in suggested},
            {"value": "45HQ", "label": "45HQ", "recommended": "45HQ" in suggested},
        ],
        "actions": [
            {
                "action": "confirm",
                "label": "确认并拼柜",
                "description": "按当前箱子列表进入团队B拼柜",
            },
            {
                "action": "revise",
                "label": "调整后重算装箱",
                "description": "根据 adjust_note 重跑团队A",
            },
            {"action": "cancel", "label": "取消", "description": "结束本轮"},
        ],
        "hint": "未确认前不会进行三维拼柜计算",
    }

    md = _render_markdown(plan_id, summary, materials, boxes, notes, suggested, reason)

    # 非标件检验 v2（规则；可选 PACKING_NS_LLM 影子 enrich）
    ns_report = state.get("nonstandard_report")
    ns_summary = state.get("nonstandard_summary")
    try:
        import os

        from packing_assistant.tools.nonstandard_inspect import public_summary, run_and_attach

        enrich = bool((state.get("packing_options") or {}).get("ns_llm_enrich")) or (
            os.environ.get("PACKING_NS_LLM", "").strip() in ("1", "true", "TRUE")
        )
        if not ns_report or not isinstance(ns_report, dict):
            attached = run_and_attach({**state, "materials": materials, "boxes": boxes}, enrich=enrich)
            ns_report = attached.get("nonstandard_report")
            ns_summary = attached.get("nonstandard_summary") or public_summary(ns_report or {})
            if attached.get("structure_notes"):
                notes = list(attached["structure_notes"])
        else:
            ns_summary = ns_summary or public_summary(ns_report)
    except Exception:
        ns_report = ns_report if isinstance(ns_report, dict) else {}
        ns_summary = ns_summary if isinstance(ns_summary, dict) else {}

    if ns_summary and isinstance(ns_summary, dict):
        summary = {
            **summary,
            "nonstandard_overall": ns_summary.get("overall"),
            "nonstandard_counts": (ns_summary.get("dashboard") or {}).get("counts_for_ui"),
            "nonstandard_ns": (ns_summary.get("summary") or {}).get("n_nonstandard_materials"),
        }

    # demo 自动确认（HITL 工具：auto 模式 = 跳过等待）
    auto = bool(state.get("enable_auto_confirm"))
    phase = "await_user_confirm"
    user_action = state.get("user_action")
    status = "success"
    final = md
    agent_meta = {
        "node": "present_team_a",
        "capability": ["感知环境", "使用工具"],
        "tools_used": ["hitl.confirm_gate", "nonstandard.inspect"],
        "artifacts": {
            "hitl_mode": hitl_policy["mode"],
            "box_count": len(boxes),
            "suggested_containers": suggested,
            "nonstandard_overall": (ns_summary or {}).get("overall"),
        },
    }

    ns_line = ""
    if ns_summary:
        ns_line = (
            f"｜nonstandard={ns_summary.get('overall')} "
            f"ns={(ns_summary.get('summary') or {}).get('n_nonstandard_materials')}"
        )

    if auto and not user_action:
        # container 可沿用 state 或建议
        ctype = state.get("container_type") or (suggested[0] if suggested else "40HQ")
        return {
            "packing_plan_id": plan_id,
            "phase": "team_b_running",
            "status": status,
            "team_a_summary": summary,
            "user_prompt": user_prompt,
            "display_markdown": md,
            "structure_notes": notes,
            "user_action": "confirm",
            "container_type": ctype,
            "agent_meta": agent_meta,
            "nonstandard_report": ns_report,
            "nonstandard_summary": ns_summary,
            "final_response": f"【HITL·自动确认】柜型 {ctype}，进入拼柜…\n\n" + md[:500],
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"【HITL 工具节点】mode=auto_confirm 柜型={ctype}；"
                        f"确认闸门作为环境反馈（非流程断裂），下游继续规划/装载"
                        f"｜tools=hitl.confirm_gate,nonstandard.inspect{ns_line}"
                    ),
                }
            ],
        }

    if not boxes:
        status = "need_more_info"
        final = "未生成有效箱子，请补充材料尺寸与重量。"
        phase = "await_user_confirm"

    return {
        "packing_plan_id": plan_id,
        "phase": phase,
        "status": status,
        "team_a_summary": summary,
        "user_prompt": user_prompt,
        "display_markdown": md,
        "structure_notes": notes,
        "final_response": final,
        "agent_meta": agent_meta,
        "nonstandard_report": ns_report,
        "nonstandard_summary": ns_summary,
        "stats": {
            "by_box_type": list(by_type.values()),
            "heaviest_box_id": heaviest_id,
            "heaviest_box_gross_kg": heaviest_w if heaviest_w >= 0 else 0,
            "longest_box_id": longest_id,
            "longest_box_length_mm": longest_l if longest_l >= 0 else 0,
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "【HITL 工具节点】mode=await_user：请确认柜型后进入拼柜；"
                    "超时策略=保持 await_user_confirm 直至 confirm/revise/cancel"
                    f"｜tools=hitl.confirm_gate,nonstandard.inspect{ns_line}"
                ),
            }
        ],
    }


def _suggest_containers(boxes: List[Dict[str, Any]]) -> List[str]:
    try:
        from packing_assistant.knowledge import prefer_container

        prefer = prefer_container()
    except Exception:
        prefer = "40HQ"
    if not boxes:
        return [prefer]
    max_len = max(float((b.get("outer_size_mm") or {}).get("length") or 0) for b in boxes)
    gross = sum(float(b.get("gross_weight_kg") or 0) for b in boxes)
    n = len(boxes)
    if max_len > 12000:
        return ["45HQ", prefer]
    if max_len > 5900 or gross > 20000:
        return [prefer, "40GP"] if prefer == "40HQ" else ["40HQ", "40GP"]
    # 3+ 箱且 ≥3.5m：勿首推 20GP（并排+纵向常要 40 尺）
    if max_len >= 3500 and n >= 3:
        return [prefer, "40GP"] if prefer == "40HQ" else ["40HQ", "40GP"]
    if max_len <= 5000 and gross < 15000 and n <= 2:
        return [prefer, "20GP"]
    return [prefer]


def _suggest_reason(boxes: List[Dict[str, Any]], ta: Dict[str, Any]) -> str:
    n = len(boxes)
    g = ta.get("total_gross_weight_kg") or 0
    return f"共 {n} 箱、总毛重约 {g} kg，建议优先 40HQ 评估装载。"


def _render_markdown(
    plan_id: str,
    summary: Dict[str, Any],
    materials: List[Dict[str, Any]],
    boxes: List[Dict[str, Any]],
    notes: List[str],
    suggested: List[str],
    reason: str,
) -> str:
    lines = [
        "# 装箱方案确认单",
        "",
        f"**方案编号**：{plan_id}",
        f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "**项目**：REDACTED-PROJECT · 钢结构件",
        "",
        "## 一、结论摘要",
        "",
        f"- 材料：{summary.get('material_line_count')} 种 / {summary.get('total_pieces')} 件 / {summary.get('total_material_weight_kg')} kg",
        f"- 箱子：{summary.get('box_count')} 个；净重 {summary.get('total_net_weight_kg')} kg；毛重 {summary.get('total_gross_weight_kg')} kg",
        f"- 结构：{summary.get('structure_overall')}（通过 {summary.get('structure_pass')} / 需加强 {summary.get('structure_reinforce')} / 不通过 {summary.get('structure_fail')}）",
        f"- 建议柜型：{', '.join(suggested)}",
        f"- 说明：{reason}",
        "",
        "> 请确认装箱方案并选择集装箱类型后，再进入拼柜计算。",
        "",
        "## 二、装箱明细",
        "",
    ]
    for b in boxes:
        outer = b.get("outer_size_mm") or {}
        attrs = ", ".join(b.get("special_attributes") or []) or "无"
        lines.append(
            f"### {b.get('box_id')} · {b.get('box_type')}\n"
            f"- 外尺寸：{outer.get('length')}×{outer.get('width')}×{outer.get('height')} mm\n"
            f"- 净重/毛重：{b.get('net_weight_kg')} / {b.get('gross_weight_kg')} kg\n"
            f"- 属性：{attrs}；加固：{b.get('reinforcement') or '无'}\n"
            f"- 内容："
            + ", ".join(
                f"{c.get('name')}×{c.get('quantity')}" for c in (b.get("content") or [])
            )
        )
        lines.append("")

    lines.append("## 三、结构提示")
    lines.append("")
    if notes:
        for n in notes[:15]:
            lines.append(f"- {n}")
    else:
        lines.append("- 无明显阻断项；出运前请人工复核。")
    lines.append("")
    lines.append("## 四、请您确认")
    lines.append("")
    lines.append("柜型：[ ] 40HQ  [ ] 40GP  [ ] 20GP  [ ] 45HQ")
    lines.append("")
    lines.append("操作：确认并拼柜 / 调整后重算 / 取消")
    lines.append("")
    lines.append("*本页仅含装箱方案，不含三维拼柜布局。*")
    return "\n".join(lines)
