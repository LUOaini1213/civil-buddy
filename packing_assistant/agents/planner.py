"""Agent4 规划智能体。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.state import PackingState


def agent_planner(state: PackingState) -> Dict[str, Any]:
    boxes = state.get("boxes") or []
    # 仅拼用户确认的箱
    confirmed = state.get("confirmed_box_ids") or []
    if confirmed:
        boxes = [b for b in boxes if b.get("box_id") in confirmed]

    ctype = state.get("container_type") or "40HQ"
    max_c = int(state.get("max_containers") or 1)

    # 优先级：超长/重货先装
    def sort_key(b: Dict[str, Any]):
        special = b.get("special_attributes") or []
        L = float((b.get("outer_size_mm") or {}).get("length") or 0)
        g = float(b.get("gross_weight_kg") or 0)
        long = 1 if ("超长" in special or L >= 5800) else 0
        return (-long, -g, -L)

    ordered = sorted(boxes, key=sort_key)
    priority = [b.get("box_id") for b in ordered if b.get("box_id")]

    rules: List[str] = []
    if any(
        "超长" in (b.get("special_attributes") or [])
        or "内容物超长" in (b.get("special_attributes") or [])
        for b in boxes
    ):
        rules.append("内容物超长件沿柜长摆放，禁止竖放、禁止上叠")
        rules.append("超长件可靠端墙，其余箱并排占满柜宽以提底面积利用率")
    if any(float(b.get("gross_weight_kg") or 0) > 200 for b in boxes):
        rules.append("单箱毛重>200kg必须底层")
    if any("需加固" in (b.get("special_attributes") or []) for b in boxes):
        rules.append("需加固箱注意垫木与绑扎")

    gross = sum(float(b.get("gross_weight_kg") or 0) for b in boxes)
    if gross > 25000:
        max_c = max(max_c, 2)
        rules.append("总毛重偏高，允许最多双柜")

    # 双利用率 + 二层堆码
    rules.append("目标：在可装下前提下尽量提高底面积与重量利用率")
    rules.append("可并排铁架优先左右贴放，避免全部居中单列")
    stackable_ids = [
        b.get("box_id")
        for b in boxes
        if b.get("stackable")
        or (
            float((b.get("outer_size_mm") or {}).get("height") or 9999) <= 1300
            and "超长" not in (b.get("special_attributes") or [])
        )
    ]
    bottom_ids = [
        b.get("box_id")
        for b in boxes
        if b.get("prefer_bottom")
        or "超长" in (b.get("special_attributes") or [])
        or "内容物超长" in (b.get("special_attributes") or [])
        or float(b.get("gross_weight_kg") or 0) >= 800
    ]
    if stackable_ids:
        rules.append(
            f"二层堆码：允许上二层的箱 {', '.join(str(x) for x in stackable_ids[:8])}；"
            f"底层优先 {', '.join(str(x) for x in bottom_ids[:8]) or '重箱/超长'}"
        )
        rules.append("第二层仅堆在有支撑的箱顶，超长件禁止上二层")

    # 优先序：底层件先装
    if bottom_ids:
        priority = sorted(
            priority,
            key=lambda bid: (0 if bid in bottom_ids else 1, priority.index(bid) if bid in priority else 99),
        )

    plan = {
        "strategy": "长度优先 + 重货下沉 + 并排占底 + 二层堆码",
        "container_type": ctype,
        "max_containers": max_c,
        "priority_order": priority,
        "special_rules": rules,
        "stackable_box_ids": stackable_ids,
        "bottom_box_ids": bottom_ids,
        "prefer_two_layer": True,
        "utilization_goals": {
            "space": "maximize_floor_then_volume",
            "weight": "fill_payload_without_overload",
            "stacking": "two_layer",
        },
    }

    # replan hints
    eval_ = state.get("evaluation") or {}
    if eval_.get("need_replan") and eval_.get("suggestions"):
        plan["strategy"] = plan["strategy"] + " | 根据评估调整"
        plan["special_rules"] = rules + list(eval_.get("suggestions") or [])

    return {
        "plan": plan,
        "phase": "team_b_running",
        "boxes": boxes if confirmed else state.get("boxes") or boxes,
        "messages": [
            {
                "role": "assistant",
                "content": f"规划完成：{ctype} ×≤{max_c}，优先序 {len(priority)} 箱",
            }
        ],
    }
