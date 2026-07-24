"""Agent3 装箱方案智能体。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.adapters import boxes_to_api, material_api_to_internal
from packing_assistant.state import PackingState
from packing_assistant.tools.packing import run_packing


def agent_box_scheme(state: PackingState) -> Dict[str, Any]:
    materials = state.get("materials") or []
    constraints = state.get("structure_constraints") or []

    internal = [material_api_to_internal(m) for m in materials]
    # 把 material id 写入内部便于 content 回填
    for src, dst in zip(materials, internal):
        dst["加工件编号"] = src.get("id") or ""
        dst["id"] = src.get("id") or ""

    ctype = (
        (state.get("orchestrator") or {}).get("container_type_chosen")
        or state.get("container_type")
        or "40HQ"
    )
    result = run_packing(internal, container_type=str(ctype))
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
        },
        "messages": [
            {
                "role": "assistant",
                "content": f"装箱完成：{len(boxes)} 箱 — {summary.get('结论', '')}",
            }
        ],
    }
