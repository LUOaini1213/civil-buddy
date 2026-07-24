"""Agent3 装箱方案智能体。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.adapters import boxes_to_api, material_api_to_internal
from packing_assistant.state import PackingState
from packing_assistant.tools.packing import run_packing


def agent_box_scheme(state: PackingState) -> Dict[str, Any]:
    materials = state.get("materials") or []
    constraints = state.get("structure_constraints") or []
    rev = state.get("revision") or {}
    packing_opts = state.get("packing_options") or {}

    internal = [material_api_to_internal(m) for m in materials]
    # 把 material id 写入内部便于 content 回填
    for src, dst in zip(materials, internal):
        dst["加工件编号"] = src.get("id") or ""
        dst["id"] = src.get("id") or ""

    ctype = (
        state.get("container_type")
        or (state.get("orchestrator") or {}).get("container_type_chosen")
        or "40HQ"
    )
    # 拼柜模块高度：20GP 二层模块过矮，长件/大票用 20GP 模块会结构大批失败。
    # 装箱阶段按「实际可拼柜型」抬升到至少 40GP/40HQ。
    max_L = max((float(m.get("length_mm") or 0) for m in materials), default=0)
    total_w = sum(float(m.get("total_weight_kg") or 0) for m in materials)
    if str(ctype).upper() == "20GP" and (max_L >= 4000 or total_w >= 8000):
        ctype = "40HQ"
    max_net = float(
        rev.get("max_box_net_kg")
        or packing_opts.get("max_box_net_kg")
        or 3200.0
    )
    revision_mode = bool(rev.get("active") or packing_opts.get("revision_mode"))
    # 默认：标准箱库外廓 + 跨长度档混装（短件塞进长标准箱）
    # dense_mode 仅在明确关闭 standard 时生效
    standard_boxes = packing_opts.get("standard_boxes")
    if standard_boxes is None:
        standard_boxes = packing_opts.get("standard_outer")
    if standard_boxes is None:
        standard_boxes = True  # 默认标准化
    standard_boxes = bool(standard_boxes)
    mix_mode = packing_opts.get("mix_mode")
    if mix_mode is None:
        mix_mode = True
    mix_mode = bool(mix_mode)
    dense_mode = bool(
        packing_opts.get("dense_mode")
        or packing_opts.get("dense")
        or rev.get("dense_mode")
    )
    if standard_boxes:
        dense_mode = False
    result = run_packing(
        internal,
        container_type=str(ctype),
        max_box_net_kg=max_net,
        revision_mode=revision_mode,
        dense_mode=dense_mode,
        standard_boxes=standard_boxes,
        mix_mode=mix_mode,
    )
    boxes_raw = result.get("箱子列表") or []
    boxes = boxes_to_api(boxes_raw)

    # 用约束补充加固文案
    reinforce_types = {
        c.get("recommended_box_type"): c
        for c in constraints
        if c.get("need_reinforcement")
    }
    for b in boxes:
        c = reinforce_types.get(b.get("box_type"))
        if c and c.get("reinforcement_plan"):
            b["reinforcement"] = c["reinforcement_plan"]
            attrs = list(b.get("special_attributes") or [])
            if "需加固" not in attrs:
                attrs.append("需加固")
            b["special_attributes"] = attrs

        # content material_id 回填
        for item in b.get("content") or []:
            if not item.get("material_id"):
                # 按名称匹配
                for m in materials:
                    if m.get("name") == item.get("name"):
                        item["material_id"] = m.get("id") or ""
                        break

    summary = result.get("结构汇总") or {}
    note_parts = []
    if standard_boxes or summary.get("standard_boxes"):
        counts = summary.get("standard_box_type_counts") or {}
        count_s = ",".join(f"{k}×{v}" for k, v in list(counts.items())[:6])
        note_parts.append(
            f"标准箱库{'+混装' if mix_mode else ''} "
            f"外廓{summary.get('boxes_outer_volume_m3', '?')}m³/"
            f"货{summary.get('cargo_item_volume_m3', '?')}m³ "
            f"填充均{float(summary.get('avg_crate_fill') or 0):.0%}"
            + (f" [{count_s}]" if count_s else "")
        )
    elif dense_mode or summary.get("dense_mode"):
        note_parts.append(
            f"密装外廓 dense "
            f"箱外廓{summary.get('boxes_outer_volume_m3', '?')}m³/"
            f"货件{summary.get('cargo_item_volume_m3', '?')}m³ "
            f"箱内填充均{float(summary.get('avg_crate_fill') or 0):.0%}"
        )
    if revision_mode or summary.get("revision_mode"):
        note_parts.append(
            f"改箱 max_net={max_net:.0f}kg 拆分后料行={summary.get('item_chunks_after_split', '?')}"
        )
    note = f"（{'；'.join(note_parts)}）" if note_parts else ""
    return {
        "boxes": boxes,
        "team_a_summary": {
            "box_count": len(boxes),
            "pass": summary.get("通过", 0),
            "reinforce": summary.get("需加强", 0),
            "fail": summary.get("不通过", 0),
            "total_net_weight_kg": summary.get("总净重_kg", 0),
            "total_gross_weight_kg": summary.get("总毛重_kg", 0),
            "structure_overall": summary.get("结论", ""),
            "max_box_net_kg": summary.get("max_box_net_kg", max_net),
            "revision_mode": bool(revision_mode or summary.get("revision_mode")),
            "dense_mode": bool(dense_mode or summary.get("dense_mode")),
            "standard_boxes": bool(standard_boxes or summary.get("standard_boxes")),
            "mix_mode": bool(mix_mode if mix_mode is not None else summary.get("mix_mode")),
            "packing_mode": summary.get("packing_mode") or "",
            "boxes_outer_volume_m3": summary.get("boxes_outer_volume_m3"),
            "cargo_item_volume_m3": summary.get("cargo_item_volume_m3"),
            "avg_crate_fill": summary.get("avg_crate_fill"),
            "standard_box_type_counts": summary.get("standard_box_type_counts"),
        },
        "messages": [
            {
                "role": "assistant",
                "content": f"装箱完成：{len(boxes)} 箱 — {summary.get('结论', '')}{note}",
            }
        ],
    }
