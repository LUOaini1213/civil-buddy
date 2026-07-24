"""
风险规则检查：超重、超尺寸、稳定性等。

以规则为主；可选 LLM 润色文案在节点层完成。
"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.tools.consolidation import CONTAINER_SPECS


def check_risks(
    boxes: List[Dict[str, Any]],
    container_plan: Dict[str, Any],
) -> List[str]:
    """
    返回风险提示字符串列表。
    """
    risks: List[str] = []

    if not boxes:
        risks.append("无箱子数据，无法完成装柜评估。")
        return risks

    ctype = container_plan.get("柜型") or "40HQ"
    spec = CONTAINER_SPECS.get(ctype, CONTAINER_SPECS["40HQ"])
    max_h = spec["高_m"] * 1000  # mm
    max_w = spec["宽_m"] * 1000

    total_weight = 0.0
    for box in boxes:
        box_id = box.get("箱号") or "?"
        dims = box.get("外尺寸_mm") or {}
        h = float(dims.get("高") or 0)
        w = float(dims.get("宽") or 0)
        L = float(dims.get("长") or 0)
        gross = float(box.get("毛重_kg") or 0)
        total_weight += gross
        special = box.get("特殊属性") or []

        if h > max_h:
            risks.append(f"{box_id} 高度 {h:.0f}mm 超过 {ctype} 内高 {max_h:.0f}mm。")
        if w > max_w:
            risks.append(f"{box_id} 宽度 {w:.0f}mm 超过 {ctype} 内宽 {max_w:.0f}mm。")
        if L > 5800:
            risks.append(f"{box_id} 长度 {L:.0f}mm，属于超长件，需确认舱门与加固方案。")
        if gross > 3000:
            risks.append(f"{box_id} 毛重 {gross:.0f}kg 偏高，注意叉车与底托承重。")
        if "超长" in special:
            risks.append(f"{box_id} 标记为超长，建议单独装载或使用开顶/框架柜复核。")
        if "超重关注" in special:
            risks.append(f"{box_id} 标记超重关注，建议复核单箱限重与重心。")
        if "结构不通过" in special or box.get("结构结论") == "不通过":
            sc = box.get("结构计算") or {}
            detail = "；".join((sc.get("风险点") or [])[:3]) or "见结构计算"
            risks.append(f"{box_id} 结构计算不通过：{detail}")
        elif "结构需加强" in special or box.get("结构结论") == "需加强":
            sc = box.get("结构计算") or {}
            beam = (sc.get("底梁建议") or {}).get("截面建议_mm") or "加大底梁"
            risks.append(f"{box_id} 结构需加强：建议底梁 {beam}，并复核绑扎。")
        else:
            sc = box.get("结构计算") or {}
            if sc.get("结论") == "通过":
                util = sc.get("结构利用率") or "-"
                # 仅高利用率提示
                try:
                    if float(str(util).replace("%", "")) >= 80:
                        risks.append(
                            f"{box_id} 结构利用率 {util} 偏高，装运前建议复核底梁与垫木。"
                        )
                except ValueError:
                    pass

    max_load = spec["最大载重_kg"]
    if total_weight > max_load:
        risks.append(
            f"总毛重 {total_weight:.0f}kg 超过 {ctype} 最大载重 {max_load:.0f}kg。"
        )

    detail = container_plan.get("详情") or {}
    overflow = detail.get("溢出箱号") or []
    if overflow:
        risks.append(f"以下箱子按当前一维布局超出柜长：{', '.join(overflow)}。")

    conclusion = container_plan.get("结论") or ""
    if "放不下" in conclusion or "超限" in conclusion:
        risks.append(f"拼柜结论提示风险：{conclusion}")

    # 稳定性粗检：单层总长接近满载时提示绑扎
    space = container_plan.get("空间利用率") or "0%"
    try:
        space_pct = float(str(space).replace("%", ""))
        if space_pct >= 90:
            risks.append("空间利用率 ≥ 90%，装柜较满，需加强绑扎与防位移措施。")
    except ValueError:
        pass

    if not risks:
        risks.append("未发现明显规则风险；正式出运前仍建议人工复核。")

    return risks
