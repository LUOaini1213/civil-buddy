"""通用 Agent 工具注册表：按大 Team / 小 Team A / 小 Team B 分簇。

Agent 选工具；数值由 tools 计算（禁止 LLM 写 xyz / 柜数拍脑袋）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    team: str  # big | A | B | shared
    module: str
    description: str
    rule: str = ""


# 产品工具面（可被 NL Agent 调度；与 skills_registry 对齐并扩展）
TOOL_CATALOG: List[ToolSpec] = [
    # —— 大 Team / 共享 ——
    ToolSpec(
        "intent.interpret",
        "意图解析",
        "big",
        "packing_assistant.intent_spec",
        "NL → IntentSpec",
        "通用入口，非线路写死",
    ),
    ToolSpec(
        "container.select",
        "柜型推荐",
        "big",
        "packing_assistant.tools.container_select",
        "按材料推荐柜型",
        "主控开局",
    ),
    ToolSpec(
        "hitl.confirm",
        "人工确认闸",
        "big",
        "packing_assistant.hitl_gates",
        "成箱后等人确认",
        "门禁确定性",
    ),
    ToolSpec(
        "replan.critic",
        "有界重排批评",
        "big",
        "packing_assistant.agents.replan_critic",
        "只改 packing_options / 路由",
        "不写 3D 坐标",
    ),
    ToolSpec(
        "plan.diff",
        "方案 diff",
        "big",
        "packing_assistant.tools.plan_diff",
        "前后方案对比",
    ),
    ToolSpec(
        "export.shipment",
        "出运包导出",
        "big",
        "packing_assistant.export_pack",
        "交付工件打包",
    ),
    ToolSpec(
        "tms.booking",
        "TMS订舱",
        "big",
        "packing_assistant.tms_booking",
        "构建/提交订舱请求（stub 或 HTTP）",
        "不改 3D 布局",
    ),
    ToolSpec(
        "kpi.extract",
        "路由选工具KPI",
        "big",
        "packing_assistant.workteam_kpi",
        "从 state 抽取 workteam KPI",
    ),
    # —— 小 Team A 成箱 ——
    ToolSpec(
        "material.parse",
        "材料解析",
        "A",
        "packing_assistant.agents.material_parser",
        "归一物料，不得编造尺寸重量",
        "不得编造尺寸重量",
    ),
    ToolSpec(
        "structure.calc",
        "结构计算",
        "A",
        "packing_assistant.tools.structure_calc",
        "半严格结构校核",
    ),
    ToolSpec(
        "box.scheme",
        "装箱方案",
        "A",
        "packing_assistant.agents.box_scheme",
        "成箱 / 直通架 / 标准箱",
    ),
    ToolSpec(
        "design.facts",
        "详设事实",
        "A",
        "packing_assistant.tools.design_facts",
        "截面/γ/图纸事实",
    ),
    # —— 小 Team B 拼柜 ——
    ToolSpec(
        "booking.n0",
        "订柜当量 N0",
        "B",
        "packing_assistant.tools.booking",
        "体积/重量订柜当量",
    ),
    ToolSpec(
        "bin3d.pack",
        "3D 装载",
        "B",
        "packing_assistant.tools.bin3d",
        "三维装箱求解",
        "LLM 禁止写 xyz",
    ),
    ToolSpec(
        "packing.run",
        "装载编排",
        "B",
        "packing_assistant.tools.packing",
        "多柜装载与重试",
    ),
    ToolSpec(
        "cog.primary",
        "重心主检",
        "B",
        "packing_assistant.tools.cog",
        "CTU 中段/横向",
    ),
    ToolSpec(
        "cog.lns",
        "LNS 重心修补",
        "B",
        "packing_assistant.tools.cog_lns",
        "最差柜局部邻域搜索",
    ),
    ToolSpec(
        "cog.lateral",
        "横向偏心修复",
        "B",
        "packing_assistant.tools.cog_lateral",
        "横向偏心",
    ),
    ToolSpec(
        "cog.shift",
        "重心平移",
        "B",
        "packing_assistant.tools.cog_shift",
        "沿柜长平移",
    ),
    ToolSpec(
        "cog.slab",
        "配重板",
        "B",
        "packing_assistant.tools.cog_slab",
        "中段配重",
    ),
    ToolSpec(
        "cog.repair",
        "重心综合修复",
        "B",
        "packing_assistant.tools.cog_repair",
        "R0–R4 管线",
    ),
    ToolSpec(
        "layout.quality",
        "布局质量",
        "B",
        "packing_assistant.tools.layout_quality",
        "空隙/半柜检测",
    ),
    ToolSpec(
        "evaluate.plan",
        "方案评估",
        "B",
        "packing_assistant.agents.evaluator",
        "双利用率 + need_replan",
    ),
    ToolSpec(
        "risk.rules",
        "风险合规",
        "B",
        "packing_assistant.tools.risk_rules",
        "出运门禁",
    ),
    ToolSpec(
        "load.sequence",
        "装货顺序",
        "B",
        "packing_assistant.tools.load_sequence",
        "现场装货序",
    ),
    ToolSpec(
        "visualize.layout",
        "可视化",
        "B",
        "packing_assistant.tools.visualize",
        "侧视/俯视图",
    ),
    ToolSpec(
        "por.manifest",
        "POR 清单",
        "B",
        "packing_assistant.tools.por_manifest",
        "POR 溯源表",
    ),
    ToolSpec(
        "secure.work_order",
        "绑扎工单",
        "B",
        "packing_assistant.tools.secure_work_order",
        "绑扎要点",
    ),
    ToolSpec(
        "vgm.draft",
        "VGM 草稿",
        "B",
        "packing_assistant.tools.vgm_draft",
        "草稿须人签",
    ),
]


def list_tools(*, team: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = []
    for t in TOOL_CATALOG:
        if team and t.team != team:
            continue
        rows.append(
            {
                "id": t.id,
                "name": t.name,
                "team": t.team,
                "module": t.module,
                "description": t.description,
                "rule": t.rule,
            }
        )
    return rows


def tools_for_agent_prompt() -> str:
    """给 LLM/主控的工具面简述。"""
    lines = ["可用工具（按 Team 分簇；数值必须由 tool 计算）："]
    for team, label in (
        ("big", "大 Team"),
        ("A", "小 Team A 成箱"),
        ("B", "小 Team B 拼柜"),
    ):
        lines.append(f"\n[{label}]")
        for t in TOOL_CATALOG:
            if t.team == team:
                lines.append(f"  - {t.id}: {t.description}" + (f" ({t.rule})" if t.rule else ""))
    return "\n".join(lines)


def get_tool(tool_id: str) -> Optional[ToolSpec]:
    for t in TOOL_CATALOG:
        if t.id == tool_id:
            return t
    return None
