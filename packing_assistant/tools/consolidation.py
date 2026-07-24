"""
拼柜工具：箱子列表 + 柜型 → 布局、利用率、结论。

计算用纯 Python。此处为线性一维排布的骨架实现，后续可换 3D 装箱。
"""

from __future__ import annotations

from typing import Any, Dict, List

def _load_container_specs() -> Dict[str, Dict[str, float]]:
    try:
        from packing_assistant.knowledge import container_specs_for_tools

        specs = container_specs_for_tools()
        if specs:
            return specs
    except Exception:
        pass
    return {
        "20GP": {"长_m": 5.898, "宽_m": 2.352, "高_m": 2.385, "最大载重_kg": 21000},
        "40GP": {"长_m": 12.032, "宽_m": 2.352, "高_m": 2.385, "最大载重_kg": 26680},
        "40HQ": {"长_m": 12.032, "宽_m": 2.352, "高_m": 2.698, "最大载重_kg": 26480},
        "45HQ": {"长_m": 13.556, "宽_m": 2.352, "高_m": 2.698, "最大载重_kg": 27700},
    }


# 柜型内尺寸 ← knowledge base
CONTAINER_SPECS: Dict[str, Dict[str, float]] = _load_container_specs()

# 布局配色循环
_COLORS = ["blue", "green", "orange", "purple", "teal", "brown", "pink", "gray"]


def run_consolidation(
    boxes: List[Dict[str, Any]],
    container_type: str = "40HQ",
) -> Dict[str, Any]:
    """
    拼柜算法入口。

    输入: boxes 列表 + 柜型
    输出: {
      "柜型", "结论", "空间利用率", "重量利用率", "布局": [...]
    }

    TODO: 替换为真实 2D/3D 拼柜（层叠、并排、重心）。
    当前实现：按箱子长度沿柜长方向一维贪心摆放。
    """
    ctype = container_type if container_type in CONTAINER_SPECS else "40HQ"
    spec = CONTAINER_SPECS[ctype]
    max_len = spec["长_m"]
    max_weight = spec["最大载重_kg"]

    layout: List[Dict[str, Any]] = []
    cursor = 0.0
    total_weight = 0.0
    used_length = 0.0
    overflow: List[str] = []

    for i, box in enumerate(boxes):
        dims = box.get("外尺寸_mm") or {}
        length_m = float(dims.get("长") or 0) / 1000.0
        if length_m <= 0:
            length_m = 1.0
        weight = float(box.get("毛重_kg") or 0)
        box_id = box.get("箱号") or f"BOX-{i + 1:02d}"

        if cursor + length_m > max_len + 1e-6:
            overflow.append(box_id)
            # 仍记录布局，起始位置标记为溢出区（便于出图与风险）
            start = cursor
        else:
            start = cursor
            cursor += length_m
            used_length = max(used_length, cursor)

        total_weight += weight
        layout.append(
            {
                "箱号": box_id,
                "起始位置_m": round(start, 3),
                "长度_m": round(length_m, 3),
                "层级": 1,
                "颜色": _COLORS[i % len(_COLORS)],
            }
        )

    space_ratio = (used_length / max_len * 100) if max_len else 0.0
    weight_ratio = (total_weight / max_weight * 100) if max_weight else 0.0

    if overflow:
        conclusion = f"放不下：{', '.join(overflow)} 超出柜长"
    elif weight_ratio > 100:
        conclusion = "空间可装下，但总重超限"
    elif space_ratio > 95:
        conclusion = "可以装下，空间较紧，建议复核"
    else:
        conclusion = "可以顺利装下"

    return {
        "柜型": ctype,
        "结论": conclusion,
        "空间利用率": f"{space_ratio:.0f}%",
        "重量利用率": f"{weight_ratio:.0f}%",
        "布局": layout,
        "详情": {
            "柜内长_m": max_len,
            "已用长_m": round(used_length, 3),
            "总毛重_kg": round(total_weight, 1),
            "最大载重_kg": max_weight,
            "溢出箱号": overflow,
        },
    }
