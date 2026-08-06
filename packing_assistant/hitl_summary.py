"""HITL 确认闸门：高密度摘要卡（供前端 / resume）。"""

from __future__ import annotations

from typing import Any, Dict, List


def build_hitl_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    boxes = state.get("boxes") or []
    mats = state.get("materials") or []
    plan = state.get("plan") or {}
    booking = state.get("booking") or plan.get("booking") or {}
    up = state.get("user_prompt") or {}
    opts = up.get("container_options") or []
    recommended = next((o for o in opts if o.get("recommended")), None)
    ctype = (
        (recommended or {}).get("value")
        or state.get("container_type")
        or "40HQ"
    )

    total_gross = sum(float(b.get("gross_weight_kg") or 0) for b in boxes)
    await_design = sum(
        1
        for b in boxes
        if b.get("structure_conclusion") == "待详设" or "待详设" in (b.get("special_attributes") or [])
    )
    fail_struct = sum(1 for b in boxes if b.get("structure_conclusion") == "不通过")
    oversize = sum(1 for b in boxes if "超长" in (b.get("special_attributes") or []))

    preview = []
    for b in boxes[:8]:
        outer = b.get("outer_size_mm") or {}
        preview.append(
            {
                "box_id": b.get("box_id"),
                "box_type": b.get("box_type"),
                "gross_weight_kg": b.get("gross_weight_kg"),
                "outer": f"{outer.get('length')}×{outer.get('width')}×{outer.get('height')}",
                "structure": b.get("structure_conclusion") or "—",
            }
        )

    n0 = plan.get("n0") or booking.get("n0")
    binding = booking.get("binding_constraint") or plan.get("binding_constraint")
    n0_components = plan.get("n0_components") or booking.get("n0_components") or {}
    n0_note = plan.get("n0_note") or booking.get("n0_note") or ""
    # Team A 结束后尚未跑 Planner 时：用成箱结果现算 N0*（供人确认「几柜」）
    if boxes and (n0 is None or not n0_components):
        try:
            from packing_assistant.tools.booking import compute_booking

            booking = compute_booking(
                boxes=boxes,
                container_type=str(ctype),
                fill_ratio=0.82,
            )
            n0 = booking.get("n0")
            binding = booking.get("binding_constraint") or binding
            n0_components = booking.get("n0_components") or {}
            n0_note = booking.get("n0_note") or n0_note
        except Exception:
            pass

    # 标准箱型分布（评委可见）
    type_counts: Dict[str, int] = {}
    for b in boxes:
        t = str(b.get("box_type") or b.get("base_box_type") or "未知")
        type_counts[t] = type_counts.get(t, 0) + 1
    audit = state.get("standard_box_audit") or {}
    if audit.get("by_type"):
        type_counts = dict(audit.get("by_type") or type_counts)
    type_hint = " · ".join(
        f"{k}×{v}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:6]
    ) or "—"
    hit_rate = audit.get("hit_rate")
    if hit_rate is None and boxes:
        try:
            from packing_assistant.knowledge import validate_boxes_against_kb

            audit = validate_boxes_against_kb(boxes)
            hit_rate = audit.get("hit_rate")
            type_counts = dict(audit.get("by_type") or type_counts)
            type_hint = " · ".join(
                f"{k}×{v}"
                for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:6]
            )
        except Exception:
            hit_rate = None

    # VGM 人签可见卡（装前必填提示，非自动申报）
    vgm_card = None
    try:
        from packing_assistant.tools.vgm_draft import build_vgm_status_public

        vg = build_vgm_status_public(state)
        hs = vg.get("human_signoff") or {}
        vgm_card = {
            "id": "vgm_signoff",
            "title": "VGM 人签",
            "value": "已签" if hs.get("signed") else (vg.get("status") or "待签"),
            "hint": hs.get("pending_action")
            or vg.get("note")
            or "须托运人签署；禁止自动申报",
            "level": "ok" if hs.get("signed") else "warn",
            "checklist_item_id": hs.get("checklist_item_id") or "vgm_signed",
            "ui_visible": True,
        }
    except Exception:
        vgm_card = {
            "id": "vgm_signoff",
            "title": "VGM 人签",
            "value": "待签",
            "hint": "出运前须 VGM 草稿 + 托运人签署",
            "level": "warn",
            "checklist_item_id": "vgm_signed",
            "ui_visible": True,
        }

    cards = [
        {
            "id": "boxes",
            "title": "成箱",
            "value": str(len(boxes)),
            "hint": f"材料 {len(mats)} 条 · 毛重合计 {total_gross:.0f} kg",
        },
        {
            "id": "standard_frames",
            "title": "标准箱架",
            "value": (
                f"{float(hit_rate):.0%}" if hit_rate is not None else str(len(type_counts))
            ),
            "hint": f"分布 {type_hint}",
            "level": (
                "ok"
                if hit_rate is None or float(hit_rate) >= 0.90
                else "warn"
            ),
        },
        {
            "id": "container",
            "title": "推荐柜型",
            "value": str(ctype),
            "hint": "确认后进入小 Team B 拼柜",
        },
        {
            "id": "n0",
            "title": "建议柜数 N0*",
            "value": "—" if n0 is None else str(n0),
            "hint": (
                f"{n0_note or ('绑定 ' + str(binding or '—'))} "
                f"· 确认后 3D 可能 +0~1 柜"
            ),
            "level": "ok" if n0 is not None else "warn",
        },
        {
            "id": "n0_break",
            "title": "N0* 分量",
            "value": (
                f"重{n0_components.get('weight', '—')}/"
                f"体{n0_components.get('volume', '—')}/"
                f"底{n0_components.get('geom_floor', '—')}/"
                f"槽{n0_components.get('geom_slot', '—')}"
                if n0_components
                else "—"
            ),
            "hint": "max(重量,体积,底面几何,槽位) · 工具计算非 LLM 拍脑袋",
        },
        {
            "id": "structure",
            "title": "结构",
            "value": "待详设" if await_design else ("不通过" if fail_struct else "可讨论"),
            "hint": f"待详设 {await_design} · 不通过 {fail_struct} · 超长 {oversize}",
            "level": "warn" if await_design or fail_struct else "ok",
        },
    ]
    if vgm_card:
        cards.append(vgm_card)

    # 非标检验摘要卡
    ns = state.get("nonstandard_summary") or state.get("nonstandard_report") or {}
    if not ns.get("overall") and (mats or boxes):
        try:
            from packing_assistant.tools.nonstandard_inspect import (
                inspect_nonstandard,
                public_summary,
            )

            full = inspect_nonstandard(
                materials=mats,
                boxes=boxes,
                container_type=str(ctype),
                case_id=str(state.get("session_id") or ""),
                packing_options=state.get("packing_options") or {},
            )
            ns = public_summary(full)
        except Exception:
            ns = {}
    ns_overall = str(ns.get("overall") or "")
    ns_ui = ((ns.get("dashboard") or {}).get("counts_for_ui")) or {}
    ns_sum = ns.get("summary") or {}
    if ns_overall:
        cards.append(
            {
                "id": "nonstandard",
                "title": "非标检验",
                "value": ns_overall,
                "hint": (
                    f"非标物料 {ns_sum.get('n_nonstandard_materials', '—')} · "
                    f"超长{ns_ui.get('overlength', 0)} 重件{ns_ui.get('heavy', 0)} "
                    f"定制{ns_ui.get('custom_shape', 0)} 结构{ns_ui.get('struct_pending', 0)}"
                ),
                "level": (
                    "err"
                    if ns_overall == "FAIL"
                    else ("warn" if ns_overall in ("WARN", "NEED_DESIGN") else "ok")
                ),
            }
        )

    actions = [
        {"id": "confirm", "label": "确认并拼柜", "primary": True},
        {"id": "revise_nl", "label": "自然语言改方案", "primary": False},
        {"id": "cancel", "label": "取消", "primary": False, "danger": True},
    ]

    sid = state.get("session_id")
    rid = state.get("run_id")
    ck = state.get("_checkpoint") or {}
    return {
        "phase": state.get("phase") or "await_user_confirm",
        "session_id": sid,
        "thread_id": ck.get("thread_id") or sid,
        "run_id": rid,
        "checkpoint_status": ck.get("status") or "interrupted",
        "durable": True,
        "packing_plan_id": state.get("packing_plan_id"),
        "recommended_container": ctype,
        "container_options": opts,
        "n_boxes": len(boxes),
        "n_materials": len(mats),
        "total_gross_kg": round(total_gross, 1),
        "box_type_distribution": type_counts,
        "standard_box_hit_rate": hit_rate,
        "n0": n0,
        "n0_star": n0,
        "n0_components": n0_components,
        "n0_note": n0_note,
        "binding": binding,
        "booking_preview": {
            "n0": n0,
            "n0_components": n0_components,
            "n0_note": n0_note,
            "binding": binding,
            "note": "成箱后预估；Team B 3D 实装可能微调",
        },
        "structure_await_design": await_design,
        "structure_fail": fail_struct,
        "overlength_boxes": oversize,
        "nonstandard": {
            "overall": ns_overall or None,
            "counts": ns_ui,
            "summary": ns_sum,
            "top_risks": ((ns.get("dashboard") or {}).get("top_risks") or ns.get("top_risks") or [])[:10],
            "checklist": ns.get("checklist"),
            "ship_gate": ns.get("ship_gate"),
            "strategy_hints": ns.get("strategy_hints") or [],
        },
        "cards": cards,
        "boxes_preview": preview,
        "actions": actions,
        "resume": {
            "endpoint": "POST /api/confirm",
            "checkpoint_resume": f"POST /api/checkpoints/{sid or 'session'}/resume",
            "body_example": {
                "session_id": sid,
                "action": "confirm",
                "container_type": ctype,
                "max_containers": 0,
            },
            "note": "checkpoint 已落盘；进程重启后仍可 resume 团队 B",
        },
        "message": (
            f"请确认柜型（推荐 {ctype}）后进入拼柜。"
            f"成箱 {len(boxes)} 只 · 建议订柜 N0*={n0 if n0 is not None else '—'} "
            f"({n0_note or '工具估算'}) · 毛重 {total_gross:.0f} kg"
            + (f"；{await_design} 箱待详设" if await_design else "")
            + (f"；非标检验 {ns_overall}" if ns_overall else "")
            + "。确认后 3D 实装可能 +0~1 柜；柜数由 tools 计算非 LLM 拍脑袋。"
            + " 状态已持久化，可安全关闭后 resume。"
        ),
    }
