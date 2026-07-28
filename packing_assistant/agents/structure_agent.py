"""Agent2 结构计算：按材料特征给约束，不提前对「错误箱型」硬失败。

改进点（相对 e2e 误报）：
- 不再用「单件最小箱型」对多件短料做失败试算（会把 20 件连接板误判 1.1 米框装不下）
- 约束以推荐箱型 + 加固触发为主；硬结构结论留给 Agent3 成箱后
- 安全系数/加固触发来自知识库
"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.adapters import material_api_to_internal
from packing_assistant.knowledge import (
    get_box_spec,
    reinforcement_advice,
    safety_factor_for_box,
)
from packing_assistant.state import PackingState
from packing_assistant.tools.packing import STANDARD_BOX_TYPES, _normalize_material, _pick_box_type_for_item


def agent_structure(state: PackingState) -> Dict[str, Any]:
    materials = state.get("materials") or []
    constraints: List[Dict[str, Any]] = []
    notes: List[str] = []
    prefer_iron = False

    # 按「推荐箱型」分组（仅建议，不做多件塞入小箱的失败试算）
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for mat in materials:
        internal = material_api_to_internal(mat)
        norm = _normalize_material(internal, 1)
        box_type = _pick_box_type_for_item(norm)
        # 短多件若被选到 1.1 米框：改为「待装箱贪心」，约束记为建议升级到 2/3 米级
        L = float(mat.get("length_mm") or 0)
        qty = int(mat.get("quantity") or 1)
        if qty >= 5 and L < 1500 and "1.1" in box_type:
            # 多件小料：推荐 2米框/木箱，避免虚假「装不下」
            for cand in ("2米框", "2米铁架", "3米木箱", "4米铁架"):
                if cand in STANDARD_BOX_TYPES:
                    box_type = cand
                    break
        groups.setdefault(box_type, []).append(mat)
        if "铁" in box_type or "框" in box_type or "笼" in box_type:
            prefer_iron = True

    for box_type, mats in groups.items():
        spec = STANDARD_BOX_TYPES.get(box_type) or {}
        kb = get_box_spec(box_type) or {}
        ids = [m.get("id") or "" for m in mats]
        total_w = sum(float(m.get("total_weight_kg") or 0) for m in mats)
        max_piece_L = max(float(m.get("length_mm") or 0) for m in mats)
        max_unit = max(float(m.get("weight_kg") or 0) for m in mats)
        max_payload = float(spec.get("最大载荷_kg") or kb.get("max_payload_kg") or 2000)
        sf = safety_factor_for_box(box_type, total_w + float(spec.get("自重_kg") or 0))

        advice = reinforcement_advice(max_piece_L, max_unit, total_w + float(spec.get("自重_kg") or 0))
        need = bool(advice) or total_w > max_payload * 0.85
        plan = "；".join(advice) if advice else ""
        if total_w > max_payload:
            need = True
            plan = (plan + "；" if plan else "") + f"组净重 {total_w:.0f}kg 接近/超过设计载荷 {max_payload:.0f}kg，建议拆箱"
            notes.append(f"{box_type} 组净重偏高，建议拆分或升级箱型")

        # 半严格/强制半严格策略提示
        strategy = kb.get("calc_strategy") or spec.get("calc_strategy") or "simple"
        if strategy in ("semi_strict", "forced_semi_strict"):
            notes.append(f"{box_type}：结构策略={strategy}，安全系数≥{sf}")

        constraints.append(
            {
                "material_ids": [i for i in ids if i],
                "recommended_box_type": box_type,
                "max_load_kg": max_payload,
                "need_reinforcement": need,
                "reinforcement_plan": plan,
                "reason": plan or f"推荐箱型 {box_type}，组净重 {total_w:.0f}kg，γ={sf}",
                "structure_conclusion": "待成箱校核",  # 最终以 Agent3 为准
                "safety_factor": sf,
                "calc_strategy": strategy,
            }
        )

    if any(m.get("category") == "超长件" or float(m.get("length_mm") or 0) >= 4000 for m in materials):
        prefer_iron = True
        notes.append("存在超长件：优先铁架，拼柜沿柜长、禁止竖放、加强绑扎")

    if any(float(m.get("weight_kg") or 0) >= 200 for m in materials):
        notes.append("存在重件：底部托盘/横梁，重下轻上")

    advice_global = {
        "prefer_iron_box": prefer_iron or True,
        "safety_factor": 2.0 if prefer_iron else 1.8,
        "note": "成箱后由装箱智能体做半严格结构校核；本步仅输出约束与加固建议",
    }

    tools_used = [
        "packing.pick_box_type",
        "knowledge.box_spec",
        "knowledge.reinforcement_advice",
    ]
    return {
        "structure_constraints": constraints,
        "global_advice": advice_global,
        "structure_notes": notes,
        "agent_meta": {
            "node": "structure",
            "capability": ["使用工具", "推理与规划"],
            "tools_used": tools_used,
            "artifacts": {
                "constraint_groups": len(constraints),
                "prefer_iron": prefer_iron,
            },
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"结构约束完成：{len(constraints)} 组推荐箱型约束"
                    f"（本步仅建议；半严格校核在装箱成箱后执行）"
                    f"｜tools={','.join(tools_used)}"
                ),
            }
        ],
    }
