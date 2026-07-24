"""结构校核 Markdown 计算书导出。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def render_structure_report_md(
    struct: Dict[str, Any],
    *,
    outer_mm: Optional[Dict[str, float]] = None,
    module_version: str = "structure-semi-v2",
) -> str:
    """根据 run_structure_calc 结果生成计算书 Markdown。"""
    summary = struct.get("summary") or {}
    sec = struct.get("section_used") or {}
    bottom = struct.get("bottom_bending") or {}
    frame = struct.get("frame_stability") or {}
    local = struct.get("local_bearing") or {}
    lift = struct.get("lifting_points") or {}
    weights = struct.get("重量") or {}
    outer = outer_mm or {}

    def _row(label: str, val: Any) -> str:
        return f"| {label} | {val if val is not None else '-'} |"

    lines: List[str] = [
        "# 包装箱结构校核计算书（工程简化法）",
        "",
        f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 模块 {module_version}*",
        "",
        "## 1. 工程与箱型概况",
        "",
        f"- 箱号：{struct.get('box_id') or '-'}",
        f"- 箱型：{struct.get('box_type') or struct.get('箱型') or '-'}",
        f"- 外尺寸：{outer.get('长') or '-'} × {outer.get('宽') or '-'} × {outer.get('高') or '-'} mm",
        f"- 装载重量（毛重）：{struct.get('total_weight_kg') or weights.get('毛重_kg') or '-'} kg",
        f"- 净重 / 箱自重：{weights.get('净重_kg', '-')} / {weights.get('箱自重_kg', '-')} kg",
        "- 设计用途：出口运输包装结构校核",
        "",
        "## 2. 设计依据与说明",
        "",
        f"- 方法：半严格工程简化计算（策略={summary.get('calc_strategy') or '-'}）",
        f"- 截面来源：{sec.get('source') or 'steel_table / sectionproperties'}",
        f"- 安全系数 γ：{struct.get('safety_factor_gamma') or struct.get('安全系数') or '-'}",
        f"- 设计荷载 Fd：{struct.get('design_load_kg') or '-'} kg",
        "",
        "> **声明：本报告仅用于包装方案校核与内部/比赛展示，"
        "不作为正式施工图审查或第三方认证计算书。**",
        "",
        "## 3. 材料与截面参数",
        "",
        "| 部位 | 型号 | A(cm²) | I(cm⁴) | W(cm³) | i(cm) | 来源 |",
        "|------|------|--------|--------|--------|-------|------|",
    ]

    fd = sec.get("frame_detail") or {}
    bd = sec.get("bottom_beam_detail") or {}
    src = sec.get("source") or "-"
    lines.append(
        f"| 框架 | {sec.get('frame') or fd.get('name') or '-'} | "
        f"{fd.get('A_cm2') or '-'} | {fd.get('I_cm4') or '-'} | "
        f"{fd.get('W_cm3') or '-'} | {fd.get('i_cm') or '-'} | {src} |"
    )
    lines.append(
        f"| 底板纵梁 | {sec.get('bottom_beam') or bd.get('name') or '-'} | "
        f"{bd.get('A_cm2') or '-'} | {bd.get('I_cm4') or '-'} | "
        f"{bd.get('W_cm3') or '-'} | {bd.get('i_cm') or '-'} | {src} |"
    )
    lines += [
        "",
        "## 4. 荷载与分项系数",
        "",
        f"- 货重+箱自重 G = {struct.get('total_weight_kg') or weights.get('毛重_kg') or '-'} kg",
        f"- 系数 γ = {struct.get('safety_factor_gamma') or '-'}",
        f"- 设计荷载 Fd = G×γ = {struct.get('design_load_kg') or '-'} kg",
        "",
        "## 5. 底板抗弯计算",
        "",
        f"- 模型：{bottom.get('model') or '-'}",
        f"- 跨距 L = {bottom.get('span_mm') or '-'} mm",
        f"- 弯矩 M = {bottom.get('moment_Nm') or '-'} N·m",
        f"- 截面模量 W = {bottom.get('section_modulus_Wx_cm3') or '-'} cm³",
        f"- 应力 σ = {bottom.get('stress_MPa') or '-'} MPa",
        f"- 许用 [σ] = {bottom.get('allowable_MPa') or '-'} MPa",
        f"- 挠度 δ = {bottom.get('deflection_mm') or '-'} mm"
        f"（限值 {bottom.get('deflection_limit_mm') or '-'} mm）",
        f"- **结论：{bottom.get('status') or '-'}**",
        f"- 建议：{bottom.get('suggestion') or '无'}",
        "",
        "## 6. 框架稳定性计算",
        "",
        f"- 计算长度 L0 = {frame.get('L0_cm') or '-'} cm"
        f"（k={frame.get('k_factor') or 1.0}）",
        f"- 回转半径 i = {frame.get('section_i_cm') or '-'} cm",
        f"- 长细比 λ = {frame.get('slenderness_lambda') or '-'} "
        f"（公式 {frame.get('lambda_formula') or 'λ=L0/i'}）",
        f"- 允许 λ = {frame.get('lambda_allow') or '-'}，分带：{frame.get('lambda_band') or '-'}",
        f"- 轴力 N = {frame.get('axial_force_N') or '-'} N",
        f"- 应力 σ = {frame.get('stress_MPa') or '-'} MPa"
        f"（许用 {frame.get('allowable_MPa') or '-'}）",
        f"- **结论：{frame.get('status') or '-'}**",
        f"- 建议：{frame.get('suggestion') or '无'}",
        "",
        "## 7. 局部承压计算",
        "",
        f"- 集中力 F = {local.get('force_N') or '-'} N",
        f"- 承压面积 Ac = {local.get('area_mm2') or '-'} mm²",
        f"- 压应力 σc = {local.get('stress_MPa') or '-'} MPa"
        f"（许用 {local.get('allowable_MPa') or '-'}）",
        f"- **结论：{local.get('status') or '-'}**",
        f"- 建议：{local.get('suggestion') or '无'}",
        "",
        "## 8. 吊装点计算",
        "",
        f"- 吊点数量 n = {lift.get('count') or '-'}",
        f"- 单点力 Fi = {lift.get('force_per_point_N') or '-'} N",
        f"- 偏心系数 = {lift.get('eccentricity_factor') or '-'}",
        f"- **结论：{lift.get('status') or '-'}**",
        f"- 建议：{lift.get('suggestion') or '无'}",
        "",
        "## 9. 综合结论与加固建议",
        "",
        f"- 总体结论：**{struct.get('结论') or summary.get('final_conclusion') or '-'}**",
        f"- 风险等级：{summary.get('risk_level') or '-'}",
        f"- 是否需加固：{summary.get('reinforcement_required')}",
        f"- 加固措施：",
    ]
    plan = summary.get("reinforcement_plan") or []
    if plan:
        for p in plan:
            lines.append(f"  - {p}")
    else:
        lines.append("  - 无")
    lines += [
        "",
        f"- 说明：{summary.get('final_conclusion') or '-'}",
        "",
        "## 10. 附录",
        "",
        f"- 截面参数来源：{src}",
        "- 主要假设：简支均布底板、立柱轴压、默认四角吊点对称、γ 含动载简化",
        f"- 软件/模块版本：{module_version}",
        "- 分项 checks：",
        f"  `{summary.get('checks') or {}}`",
        "",
    ]
    return "\n".join(lines)


def write_structure_report(
    struct: Dict[str, Any],
    path: str,
    *,
    outer_mm: Optional[Dict[str, float]] = None,
) -> str:
    md = render_structure_report_md(struct, outer_mm=outer_mm)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path
