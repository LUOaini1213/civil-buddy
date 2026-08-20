"""Every summoned expert uses the same understand → chat | run | both loop.

Writes only exclusive tools (or HITL pending). No 66 personality prompts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import subprocess
import sys

from packing_assistant.expert_roster import ExpertRec, exclusive_tools, get_expert, list_experts
from packing_assistant.sandbox import guarded_write_text
from packing_assistant.understand import understand

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "demo" / "out"
DISCLAIMER = (
    "本文件由 Civil Buddy 根据用户输入生成，仅供内部讨论与起草。"
    "不构成设计文件、法定专项施工方案、交底签认件、监理指令、专家论证材料或开工/竣工验收依据。"
)
CONFIRM = "我明白，将由持证人员签认"
FORBIDDEN = ("可以投标", "可以开工", "中标率")


def _kb_snip(expert: ExpertRec, query: str, limit: int = 900) -> str:
    paths = [
        _ROOT / "demo" / "kb" / expert.category / expert.id / "web-knowledge.md",
        _ROOT / "demo" / "kb" / expert.category / "_shared" / "web-knowledge.md",
    ]
    chunks: List[str] = []
    q = (query or "").strip()
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if q and q in text:
            i = text.find(q)
            chunks.append(text[max(0, i - 80) : i + 400])
        else:
            chunks.append(text[:limit])
        if sum(len(c) for c in chunks) >= limit:
            break
    return "\n".join(chunks)[:limit].strip()


def explain_expert(expert: ExpertRec, text: str) -> str:
    bits = [
        f"本岗：{expert.name}（{expert.category_name} / {expert.id}）。内部讨论 AI 草稿。提问不写盘，不判定可投标。",
        expert.title,
    ]
    blob = text or ""
    if "GST" in blob.upper() or "税率" in blob or expert.id == "finance-tax":
        bits.append(
            "IRAS 页述：The current GST rate in Singapore is 9%（Current GST rates）。税额待持证办税人员按当期文件算。"
        )
    if any(k in blob for k in ("危大", "临边", "专家论证")) or expert.id == "method-hazard":
        bits.append(
            "是否危大、要不要专家论证，须由持证人员按专项目录与现场判定。本岗不判定可以开工。"
        )
    snip = _kb_snip(expert, blob)
    if snip:
        bits.append("本岗可见知识摘录：\n" + snip)
    bits.append("要成稿请明说写/编制/出一份。高风险写盘须确认句：「" + CONFIRM + "」。")
    reply = "\n".join(b for b in bits if b)
    for bad in FORBIDDEN:
        if bad in reply and f"不判定{bad}" not in reply and f"不{bad}" not in reply:
            reply = reply.replace(bad, "（禁止断言）")
    return reply


def _write_tools(expert: ExpertRec) -> List[str]:
    return [t for t in expert.exclusive if "fill_scheme" not in t]


_SCHEME_CHAPTERS = (
    "封面与文件控制",
    "草稿与责任声明",
    "工程概况",
    "编制依据",
    "施工部署与工艺",
    "质量",
    "安全与应急",
    "环保与文明施工",
    "资源计划",
    "验收与资料",
    "附录",
)

_SURVEY_CHAPTERS = (
    "封面与文件控制",
    "草稿与责任声明",
    "任务范围与部位",
    "已知起算",
    "控制网与加密",
    "放样内容",
    "竖向传递",
    "复测与检核",
    "仪器与人员",
    "停测与异常",
    "附录",
)

_DISPATCH_CHAPTERS = (
    "报头",
    "草稿声明",
    "计划接口",
    "当日实际",
    "人机料动态",
    "指令栏",
    "交叉作业与工作面交接",
    "停复工与异常",
    "危大/高处/临边等敏感作业清单",
    "明日条件与待决策",
    "附件表头",
)

_VARIATION_CHAPTERS = (
    "封面与草稿声明",
    "文件类型判定",
    "事实栏",
    "依据栏",
    "工程量栏",
    "价款调整方法",
    "签认栏",
    "与索赔、验工的接口",
    "附件目录",
    "自检",
)

_CLAIM_CHAPTERS = (
    "封面与草稿声明",
    "事件识别",
    "合同时钟",
    "意向通知必备",
    "证据清单",
    "因果与责任栏",
    "费用组成口径",
    "调概专节",
    "与签证、验工接口",
    "自检",
)

_SUBCONTRACT_CHAPTERS = (
    "封面与草稿声明",
    "合同关系",
    "本期完成",
    "合同内价款栏",
    "合同外",
    "扣款表头",
    "质量与质保",
    "农民工工资专节",
    "会签栏",
    "与对上验工、财务接口",
    "自检",
)

_INTERIM_CHAPTERS = (
    "封面与草稿声明",
    "原则",
    "本期范围",
    "计量依据",
    "计量草表",
    "变更、物价、索赔",
    "过程结算与进度款",
    "农民工工资列示",
    "扣减与预留",
    "不予计价警示",
    "报审签认",
    "自检",
)

_PLAN_MASTER_CHAPTERS = (
    "封面与文件控制",
    "草稿声明",
    "编制依据",
    "开竣工口径提示",
    "工作分解",
    "逻辑关系",
    "一级网络与里程碑",
    "关键线路",
    "表达方式",
    "检查与基线",
    "进度变更",
    "待填与禁令",
)

_PLAN_LOOKAHEAD_CHAPTERS = (
    "封面",
    "从总控抽取窗口",
    "近细远粗",
    "制约因素",
    "周承诺",
    "交叉作业",
    "停工条件",
    "与总控的回写",
    "月度形象对照",
    "待填与禁令",
)

_LOOKAHEAD_SKIP = {
    "草稿提纲",
    "总进度计划",
    "总控计划",
    "周计划",
    "月计划",
    "四周滚动",
    "周月计划",
    "四周滚动计划",
    "master",
    "lookahead",
    "制约已清",
    "条件已具备",
    "待填",
    "四周",
}

_LOOKAHEAD_BLOCK = ("未清", "未到", "未交", "无图", "未发", "过期")

_PLAN_RESOURCE_CHAPTERS = (
    "封面与声明",
    "输入清单",
    "劳动力负荷表头",
    "施工机具负荷表头",
    "主要材料与周转料表头",
    "峰值与错峰",
    "冲突提示栏",
    "与周月、采购、资金的接口",
    "优化记录",
    "禁令",
)

_RESOURCE_SKIP = {
    "草稿提纲",
    "资源负荷",
    "资源计划",
    "资源负荷表",
    "峰值",
    "待填",
    "四周",
    "master",
    "lookahead",
}

_PLANT_KEYS = (
    "塔吊",
    "泵车",
    "挖机",
    "吊车",
    "机械",
    "机具",
    "台班",
    "crane",
    "excavator",
    "pump",
    "tower",
)

_MAT_KEYS = (
    "周转",
    "水泥",
    "砂",
    "材料",
    "rebar",
    "concrete",
    "钢筋",
    "模板",
    "混凝土",
)

_RES_QTY = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>人|工日|台班|台|t|吨|kg|m3|m³)",
    re.I,
)

_LAB_MIX_CHAPTERS = (
    "封面与文件控制",
    "草稿声明",
    "选用口径",
    "原材料一致性",
    "调整权限",
    "编制依据",
    "与见证取样、台账的接口",
    "资料目录",
    "禁令",
)

_MIX_TRIAL_YES = ("已有试验数据", "试配记录", "试拌记录", "含水率已测", "试验室配合比已批")
_MIX_GRADE_RE = re.compile(r"([CM]\d{1,3})", re.I)

_LAB_SAMPLE_CHAPTERS = (
    "封面",
    "角色",
    "必须纳入见证取样的类别",
    "比例口径",
    "现场动作提纲",
    "不合格升级",
    "报告效力",
    "与配比、台账、仓管、资料的接口",
    "禁令",
)

_SAMPLE_DEFAULT = (
    "承重结构混凝土试块",
    "承重墙体砌筑砂浆试块",
    "承重结构钢筋及连接接头试件",
    "承重墙的砖和混凝土小型砌块",
    "拌制混凝土和砌筑砂浆的水泥",
    "承重结构混凝土用掺加剂",
    "地下、屋面、厕浴间防水材料",
    "国家规定的其他项目（地方加长项待核）",
)

_SAMPLE_SKIP = {
    "草稿提纲",
    "取样送检清单",
    "见证取样",
    "送检清单",
    "待填",
}

_LAB_RECORD_CHAPTERS = (
    "封面",
    "编号总则",
    "建议分册",
    "原始记录纪律",
    "仪器三件事",
    "公开名称备查",
    "闭合检查表头",
    "接口",
    "禁令",
)

_RECORD_SKIP = {
    "草稿提纲",
    "试验台账",
    "试验台账骨架",
    "待填",
}

_SUPERVISION_CHAPTERS = (
    "文头",
    "致",
    "来文要点复述",
    "原因分析",
    "拟办",
    "完成时限",
    "证据目录",
    "自检",
    "签发",
    "闭合台账行",
    "禁令",
)

_SAFETY_BRIEF_CHAPTERS = (
    "封面",
    "草稿声明",
    "作业部位与范围",
    "作业内容和工序步骤",
    "危险源",
    "防护要点",
    "个人防护",
    "禁止事项与喊停条件",
    "应急要点",
    "依据",
    "签字栏",
)

_QUALITY_CHAPTERS = (
    "封面与声明",
    "划分说明",
    "进场与依据",
    "主控项目检查栏",
    "一般项目检查栏",
    "隐蔽专项",
    "通病防治核对",
    "不符合时的处理路径栏目",
    "资料闭合",
    "签字栏",
)

_ENV_CHAPTERS = (
    "封面",
    "声明",
    "扬尘",
    "弃土与建筑垃圾",
    "污水与泥浆",
    "噪声与夜间",
    "文明施工市容",
    "与商务接口",
    "停工与升级",
    "签字栏",
)

_EMERGENCY_CHAPTERS = (
    "封面与声明",
    "编制说明",
    "综合预案目录",
    "专项预案目录",
    "现场处置方案",
    "应急处置卡",
    "信息报告",
    "演练计划与记录表头",
    "附件",
    "备案与评估节点",
    "禁令",
)

_EMERGENCY_SPECIALS = (
    "高处坠落",
    "物体打击",
    "坍塌",
    "触电",
    "起重机械",
    "火灾爆炸",
    "中毒窒息/有限空间",
    "车辆伤害",
    "疫情或突发环境事件",
)

_EMERGENCY_HINTS = (
    ("火灾", "火灾爆炸"),
    ("fire", "火灾爆炸"),
    ("爆炸", "火灾爆炸"),
    ("坠落", "高处坠落"),
    ("高处", "高处坠落"),
    ("打击", "物体打击"),
    ("坍塌", "坍塌"),
    ("触电", "触电"),
    ("起重", "起重机械"),
    ("有限空间", "中毒窒息/有限空间"),
    ("中毒", "中毒窒息/有限空间"),
    ("车辆", "车辆伤害"),
    ("疫情", "疫情或突发环境事件"),
)

_EQUIP_CHAPTERS = (
    "封面与草稿声明",
    "设备清单表头",
    "进场验收",
    "租赁与台班",
    "维保计划",
    "证件与检验台账",
    "退场与结算附件目录",
    "资料目录",
    "禁令",
)

_EQUIP_SKIP = {
    "草稿提纲",
    "设备台账",
    "维保计划",
    "待填",
}

_CERT_COPY = re.compile(
    r"(合格证|使用登记|作业人员证件|作业证)[:：\s]*([A-Za-z0-9][\w\-./]{2,})"
)

_WH_CHAPTERS = (
    "草稿声明",
    "库区与分类",
    "入库验收",
    "标识与保管",
    "限额领料出库",
    "盘点",
    "收发存表头",
    "危险品台账",
    "禁令",
)

_WH_SKIP = {
    "草稿提纲",
    "收发存",
    "收发存台账",
    "仓管",
    "待填",
}

_MILESTONE_KEYS = ("桩基", "±0", "封顶", "砌筑", "机电", "装饰", "竣工")

_QTY_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>m2|m²|m3|t|吨|kg|工日|项)?",
    re.I,
)

_EVIDENCE_KEYS = (
    "函",
    "通知",
    "停工",
    "天气",
    "影像",
    "照片",
    "试验",
    "会议纪要",
    "回证",
    "letter",
    "notice",
    "photo",
    "record",
)

_VAR_NO_RE = re.compile(r"(?i)\b(?:VO|SI|DC|VAR)[-_./]?\d+[A-Za-z]?\b")

_POINT_RE = re.compile(r"(?i)\b(?:CP|BM|PT|TP|GC|SP)[-_]?\d+[A-Za-z]?\b")
_SENSITIVE_KEYS = (
    "危大",
    "临边",
    "基坑",
    "开挖",
    "起重",
    "脚手架",
    "模板",
    "有限空间",
    "拆除",
    "爆破",
    "高处",
    "PTW",
    "excavation",
    "lifting",
    "scaffold",
)


def _copy_survey_points(blob: str) -> List[str]:
    rows: List[str] = []
    for line in (blob or "").splitlines():
        t = line.strip()
        if not t or "用户未提供" in t:
            continue
        if "点号" in t or "控制点" in t or _POINT_RE.search(t):
            rows.append(t[:200])
    return rows


def _copy_sensitive_jobs(blob: str) -> List[str]:
    hits: List[str] = []
    for line in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = line.strip()
        if not t:
            continue
        if any(k.lower() in t.lower() for k in _SENSITIVE_KEYS):
            hits.append(t[:120])
    return hits


def _survey_record_md(text: str) -> str:
    points = _copy_survey_points(text)
    known = (
        "\n".join(f"- {p}" for p in points)
        if points
        else "| 点号 | 东坐标 | 北坐标 | 高程 | 来源 |\n| --- | --- | --- | --- | --- |\n| [A001] | [A001] | [A001] | [A001] | 用户未给 |"
    )
    lines = [
        "# 测量方案/记录表（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "不是复测签认件。只抄用户已给点号/坐标。缺数 [A001]。条款 UNSPECIFIED。辖区：SG。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SURVEY_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 2:
            lines.append(DISCLAIMER)
        elif i == 3:
            lines.append((text or "").strip()[:200] or "整节待填。[A001]")
        elif i == 4:
            lines.append(known)
            lines.append("")
            lines.append("禁止编造坐标或点号。无用户坐标不编点号。")
        else:
            lines.append("待按用户点号/图纸填写。[A001]")
        lines.append("")
    lines.append("SG：SVY21 / SHD 只写坐标系统名。CN：工程测量标准只写全名。本记录不是施工依据。")
    lines.append("")
    return "\n".join(lines)


def _classify_variation_kind(blob: str) -> str:
    t = blob or ""
    low = t.lower()
    hits: List[str] = []
    if "设计变更" in t or "design change" in low:
        hits.append("设计变更")
    if "工程签证" in t or "签证" in t or "variation" in low:
        hits.append("工程签证")
    if "洽商" in t:
        hits.append("工程洽商")
    if "联系单" in t:
        hits.append("工程联系单")
    if "工程量确认" in t or "qty confirm" in low:
        hits.append("工程量确认单")
    uniq = list(dict.fromkeys(hits))
    if len(uniq) > 1:
        return "混写，须拆开。本表不混写，待用户指定一类。"
    if len(uniq) == 1:
        return uniq[0]
    return "信息不足，待用户指定一类（设计变更 / 工程签证 / 工程洽商 / 工程联系单 / 工程量确认单）。"


def _copy_variation_no(blob: str) -> str:
    rows: List[str] = []
    for line in (blob or "").splitlines():
        t = line.strip()
        if not t:
            continue
        if "变更编号" in t or _VAR_NO_RE.search(t):
            rows.append(t[:160])
    if rows:
        return "\n".join(f"- {r}" for r in rows)
    return "变更编号待填。禁止引用未提供的图号。条款号 UNSPECIFIED。"


def _variation_form_md(text: str) -> str:
    kind = _classify_variation_kind(text)
    basis_no = _copy_variation_no(text)
    facts = (text or "").strip()[:240] or "整节待填。[A001]"
    lines = [
        "# 工程签证 / 设计变更费用口径草稿（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "不构成已签认签证，不替代设计变更通知单。金额 TBD。条款 UNSPECIFIED。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_VARIATION_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(DISCLAIMER)
        elif i == 2:
            lines.append(f"本表文种：**{kind}**。只选一类。")
        elif i == 3:
            lines.append(facts)
            lines.append("")
            lines.append("时间/部位/事由/谁提出：用户未给的格子待填。[A001]")
        elif i == 4:
            lines.append(basis_no)
            lines.append("")
            lines.append("合同条款只写名称，不编条款号。无用户变更编号则依据待填。")
        elif i == 5:
            lines.append("计算式或现场实测待填。单位待填。与原清单对应编码无则新建项待定。[A001]")
        elif i == 6:
            lines.append(
                "只写路径，不填数：有适用单价则用该单价；只有类似单价则参照并说明差异；都没有则协商，人材机口径单价 TBD。"
            )
        elif i == 7:
            lines.append("| 角色 | 姓名 | 日期 |\n| --- | --- | --- |\n| 监理对事实 |  |  |\n| 造价对价款 |  |  |")
            lines.append("")
            lines.append("空栏，不代签。不把现场确认写成已定价。")
        elif i == 8:
            lines.append("指令内调价走本节。指令外损失、逾期失权风险走索赔调概（claim）。当期计量走验工计价（interim）。")
        elif i == 9:
            lines.append("照片/实测草图/变更单扫描/原清单摘录：有则列名，无则写用户未提供。")
        else:
            lines.append("无金额编造。无事后补签装成当时签。不编无来源限额。")
        lines.append("")
    lines.append("SG：PSSCOC 2020 / PSSCOC-lite 2025 / SIA / REDAS 只写合同族名，条款 UNSPECIFIED。")
    lines.append("CN：GF-2017-0201 / GB/T 50500-2024 只写全名；财建〔2004〕369 号程序是否适用看用户合同，不编确认天数。")
    lines.append("")
    return "\n".join(lines)


def _copy_claim_evidence(blob: str) -> str:
    rows: List[str] = []
    for line in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = line.strip()
        if not t or t in {"待列", "待补"}:
            continue
        low = t.lower()
        if any(k in t or k in low for k in _EVIDENCE_KEYS):
            rows.append(t[:160])
    if rows:
        return "\n".join(f"- {r}（只抄用户已给）" for r in rows)
    return (
        "| 证据 | 状态 |\n| --- | --- |\n"
        "| 往来函 / 监理通知 / 停工令 | 待补 |\n"
        "| 天气或停水停电记录 | 待补 |\n"
        "| 人员机械进出场 / 影像 / 试验报告 | 待补 |\n"
        "| 采购合同 / 会议纪要 / 送达回证 | 待补 |"
    )


def _claim_notice_md(text: str) -> str:
    event = (text or "").strip()[:240] or "整节待填。[A001]"
    evidence = _copy_claim_evidence(text)
    lines = [
        "# 索赔意向 / 调概事项草稿（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "不是已送达的索赔报告，不构成调概批复。工期天数 TBD。金额 TBD。条款原文待贴。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_CLAIM_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(DISCLAIMER)
        elif i == 2:
            lines.append(event)
            lines.append("")
            lines.append("费用索赔与工期索赔分列。变更指令内调价优先走变更签证（variation），不重复当索赔。")
        elif i == 3:
            lines.append("用户合同索赔条款原文待贴。不编条款号。时限以用户纸本为准，本表不代填天数。")
            lines.append("")
            lines.append("只提示逾期风险，不断言已失权，不断言一定能要回。")
        elif i == 4:
            lines.append("| 栏 | 内容 |\n| --- | --- |\n| 事件事由 | 只抄用户原文 |\n| 发生时间 | 待填 |\n| 合同依据名称 | 待贴原文 |\n| 可能费用和／或工期 | TBD |\n| 已采取减损 | 待填 |\n| 证据目录 | 见第 5 节 |")
            lines.append("")
            lines.append("不填索赔总价。")
        elif i == 5:
            lines.append(evidence)
        elif i == 6:
            lines.append("事件 → 影响工作面 → 关键线路是否被占（无网络图则工期影响待填）→ 己方有无扩大损失。[A001]")
        elif i == 7:
            lines.append(
                "| 组成 | 单价 |\n| --- | --- |\n| 人工停置 | TBD |\n| 机械停滞 | TBD |\n| 材料仓储或贬值 | TBD |\n| 赶工 | TBD |\n| 利润（是否计取看合同） | TBD |\n| 总部管理费 | TBD |"
            )
        elif i == 8:
            lines.append("政府投资调概只出事项对照表。预备费能覆盖的不调概。本岗不下报批结论。")
        elif i == 9:
            lines.append("能签认的事实先固定在签证。索赔成立后的金额进验工计价或过程结算，无业主确认不编入当期付款。")
        else:
            lines.append("无编造条款号。无编造索赔额。无胜诉或必然支持。")
        lines.append("")
    lines.append("SG：Building and Construction Industry Security of Payment Act 只写全名，时限 UNSPECIFIED。PSSCOC-lite 2025 / Clause 23 Procedure for Claims 只写条名。")
    lines.append("CN：GF-2017-0201 索赔意向/报告天数以用户合同为准。发改投资〔2015〕482 号只写全名。GB 50500 只出现在 CN 栏。")
    lines.append("")
    return "\n".join(lines)


def _parse_subcontract_lines(blob: str) -> List[tuple[str, str, str]]:
    rows: List[tuple[str, str, str]] = []
    for raw in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = raw.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in {"草稿提纲", "待填分包", "待计量"}:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        m = _QTY_RE.search(t)
        if m:
            name = (t[: m.start()] + t[m.end() :]).strip(" ，,") or t[:80]
            unit = m.group("unit") or "TBD"
            rows.append((name[:80], unit, m.group("qty")))
        elif len(t) <= 80:
            rows.append((t[:80], "TBD", "TBD"))
    return rows


def _subcontract_sheet_md(text: str) -> str:
    items = _parse_subcontract_lines(text)
    if items:
        table = "| 分项 | 单位 | 数量 | 合同单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n"
        table += "".join(
            f"| {n} | {u} | {q} | TBD | TBD | 用户细目 |\n" for n, u, q in items
        )
    else:
        table = (
            "| 分项 | 单位 | 数量 | 合同单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n"
            "| [A001] | TBD | TBD | TBD | TBD | 用户未给细目 |\n"
        )
    lines = [
        "# 分包（劳务）结算表头（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "内部对下结算讨论稿，不是已生效结算协议。无总包/业主确认不编金额。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SUBCONTRACT_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(DISCLAIMER)
        elif i == 2:
            lines.append("专业分包或劳务分包待用户指定。禁止把违法转包写成合法分包。合同编号/计价方式待贴。[A001]")
        elif i == 3:
            lines.append(table)
            lines.append("")
            lines.append("量只抄用户任务单或实测。禁止用形象百分比空估。对上未批则本期待填。")
        elif i == 4:
            lines.append("数量 × 合同单价。无合同单价、无总包/业主确认则合价 TBD。")
        elif i == 5:
            lines.append("洽商、签证另表。无签认不进结算。")
        elif i == 6:
            lines.append(
                "| 扣款项 | 金额 |\n| --- | --- |\n| 甲供材领用 / 水电 / 周转料具损坏 | TBD |\n| 质量/安全罚款（须书面通知） | TBD |\n| 预付款抵扣 / 前期末扣清 | TBD |\n| 农民工工资代发已付 / 其他 | TBD |"
            )
            lines.append("")
            lines.append("没有凭证不编扣款。")
        elif i == 7:
            lines.append("缺陷责任期内预留质量保证金。预留比例待按建质〔2017〕138 号与用户合同核对，不另编百分比当结算结论。")
        elif i == 8:
            lines.append("| 栏 | 金额 |\n| --- | --- |\n| 应付人工费 | TBD |\n| 应付分包工程款 | TBD |")
            lines.append("")
            lines.append("两栏分列，不混。保障农民工工资支付条例只写全名。")
        elif i == 9:
            lines.append(
                "| 部门 | 意见 |\n| --- | --- |\n| 现场工长核量 | 未会签 |\n| 工程部 / 安质 / 物资 / 商务 | 未会签 |\n| 项目经理 | 未会签 |"
            )
        elif i == 10:
            lines.append("对下累计原则上不超过对上已计价对应份额。付款申请交 finance-fund，发票税目交 finance-tax。")
        else:
            lines.append("无编造工日单价。无把工人生活费写成已结清工资。本表不下发放结论。")
        lines.append("")
    lines.append("SG：PSSCOC Nominated Sub-Contract / SOP Act 只写全名。")
    lines.append("CN：保障农民工工资支付条例只写全名，金额 TBD。GB 50500 只出现在 CN 栏。")
    lines.append("")
    return "\n".join(lines)


def _interim_measure_md(text: str) -> str:
    items = _parse_subcontract_lines(text)
    header_row = (
        "| 清单编码 | 名称 | 单位 | 合同量 | 上期末开累 | 本期申报 | 监理审 | 业主核 | 单价 | 本期价 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    if items:
        table = header_row + "".join(
            f"| TBD | {n} | {u} | TBD | TBD | {q} | TBD | TBD | TBD | TBD |\n" for n, u, q in items
        )
    else:
        table = header_row + "| TBD | [A001] | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |\n"
    period = "待填"
    blob = text or ""
    if "月" in blob or "季" in blob or "期" in blob:
        period = blob.strip()[:80] or "待填"
    lines = [
        "# 对上验工计价草稿（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "内部报审讨论稿，不是已核准验工报表，不是付款指令。无业主确认不编本期应付。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_INTERIM_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(DISCLAIMER)
        elif i == 2:
            lines.append("有实物工作量的先验工、后计价。不合格、未履行变更程序、超出合同的，不予计价。")
        elif i == 3:
            lines.append(f"期次：{period}。开累与本期分列。起止日期待填。[A001]")
        elif i == 4:
            lines.append("已标价清单及计算规则；经审核施工图及批准变更；质量合格证明。条款原文待贴。")
        elif i == 5:
            lines.append(table)
            lines.append("")
            lines.append("监理审、业主核、单价、本期价无确认则 TBD。不编应付合价。")
        elif i == 6:
            lines.append("只列入已批准文件对应金额或「已批文号 + 金额待填」。未批变更不得计价。")
        elif i == 7:
            lines.append("预付款 / 进度款 / 竣工结算只写财建〔2004〕369 号全名。进度款比例待按财建〔2022〕183 号与用户合同核对，不另编百分比。")
        elif i == 8:
            lines.append("| 栏 | 金额 |\n| --- | --- |\n| 用于支付农民工工资的工程款 | TBD |")
        elif i == 9:
            lines.append("| 项 | 金额 |\n| --- | --- |\n| 预付款抵扣 / 甲供材 / 质保金 / 违约金 | TBD |")
            lines.append("")
            lines.append("有合同和凭证才列。质保金比例待按办法与用户合同核对。")
        elif i == 10:
            lines.append("无开工报告、质量不合格、超图未变、重复计量、超前报量且长期未实施：本期不计价。不作指控。")
        elif i == 11:
            lines.append("承包人编制 → 监理审核 → 建设单位核准。缺一环不写付款结论。")
        else:
            lines.append("无业主确认不编应付合价。价税分开表头保留。")
        lines.append("")
    lines.append("SG：Security of Payment Act payment claim 只写标题，时限 UNSPECIFIED。")
    lines.append("CN：验工计价按用户合同，金额 TBD。GB 50500 只出现在 CN 栏。")
    lines.append("")
    return "\n".join(lines)


def _parse_wbs_names(blob: str) -> List[str]:
    rows: List[str] = []
    for raw in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = raw.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in {"草稿提纲", "总进度计划", "总控计划"}:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if len(t) <= 80:
            rows.append(t[:80])
    return rows


def _plan_master_md(text: str) -> str:
    names = _parse_wbs_names(text)
    if names:
        wbs = "| 编码 | 名称 | 责任单位 | 工程量来源 | 持续时间来源 | 紧前 |\n| --- | --- | --- | --- | --- | --- |\n"
        wbs += "".join(
            f"| TBD | {n} | TBD | 待填 | 待填 | 待填 |\n" for n in names
        )
    else:
        wbs = (
            "| 编码 | 名称 | 责任单位 | 工程量来源 | 持续时间来源 | 紧前 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| TBD | [A001] | TBD | 待填 | 待填 | 待填 |\n"
        )
    blob = text or ""
    miles = [k for k in _MILESTONE_KEYS if k in blob]
    if miles:
        mile_tbl = "| 里程碑 | 日期 |\n| --- | --- |\n" + "".join(f"| {m} | 待填 |\n" for m in miles)
    else:
        mile_tbl = (
            "| 里程碑 | 日期 |\n| --- | --- |\n"
            "| 桩基完成 / ±0.000 / 主体封顶（候选） | 里程碑待填 |\n"
        )
    lines = [
        "# 施工总进度计划（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "不是监理批准件，也不是可据以开工的进度计划。禁止编持续时间和关键线路。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_PLAN_MASTER_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("项目名称/合同工期/计划开工竣工待填。签认栏留空。[A001]")
        elif i == 2:
            lines.append(DISCLAIMER)
        elif i == 3:
            lines.append("只列用户已给名称。无定额或方案则依据栏待补。不默写定额号。条款 UNSPECIFIED。")
        elif i == 4:
            lines.append("开竣工日期争议提示查阅法释〔2020〕25 号第八条、第九条认定顺序。本岗不代法院认定日期。")
        elif i == 5:
            lines.append(wbs)
            lines.append("")
            lines.append("WBS。无图纸清单则工程量与持续时间一律待填。")
        elif i == 6:
            lines.append("紧前、紧后、搭接类型（FS/SS/FF/SF）只写用户确认的工艺顺序。禁止编虚工作逻辑。")
        elif i == 7:
            lines.append(mile_tbl)
            lines.append("")
            lines.append("未给定的里程碑名称可列候选，日期待填。")
        elif i == 8:
            lines.append("关键线路=待计算。用户未提供网络参数时禁止本稿指定。关键线路上的作业变更必须回写本总控。")
        elif i == 9:
            lines.append("本稿出表头+文字逻辑，不假装已出批准用网络图。软件名、图号须来自用户。")
        elif i == 10:
            lines.append("冻结基线版本。偏差先对照总时差，再判断是否动总工期。总时差待计算。")
        elif i == 11:
            lines.append("变更原因、是否关键线路、对里程碑的影响待填。金额与意向书改召唤索赔调概（claim）。")
        else:
            lines.append("无来源数字写待填。禁止断言计划合理、一定能按期竣工。")
        lines.append("")
    lines.append("SG：PSSCOC 工期条款只写族名。Programme 提交以用户合同为准。")
    lines.append("CN：施工组织设计规范 / 工程网络计划技术规程只写全名，不编关键线路。")
    lines.append("")
    return "\n".join(lines)


def _lookahead_blocked(line: str) -> bool:
    t = line or ""
    if any(m in t for m in _LOOKAHEAD_BLOCK):
        return True
    if "制约已清" in t or "条件已具备" in t:
        return False
    return "制约" in t


def _clean_lookahead_job(line: str) -> str:
    t = line or ""
    for m in ("制约已清", "条件已具备"):
        t = t.replace(m, "")
    return re.sub(r"\s+", " ", t).strip(" ，,;；")


def _parse_lookahead(blob: str) -> tuple:
    """(window_jobs, blocked_jobs, can_promise). 制约未清不得写入本周承诺。"""
    raw = blob or ""
    any_cleared = "制约已清" in raw or "条件已具备" in raw
    jobs: List[str] = []
    blocked: List[str] = []
    for piece in raw.replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in _LOOKAHEAD_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t.startswith("第") and "周" in t[:8]:
            continue
        if len(t) > 80:
            t = t[:80]
        name = _clean_lookahead_job(t) or t
        if not name or name in _LOOKAHEAD_SKIP:
            continue
        if _lookahead_blocked(t):
            blocked.append(name)
        elif name not in jobs:
            jobs.append(name)
    can_promise = bool(any_cleared and not blocked and jobs)
    return jobs, blocked, can_promise


def _plan_lookahead_md(text: str) -> str:
    jobs, blocked, can_promise = _parse_lookahead(text)
    week_jobs = "；".join(jobs) if jobs else "待填 [A001]"
    week_block = "；".join(blocked) if blocked else ("制约未清" if not can_promise else "无未清制约")
    four = (
        "| 周次 | 粒度 | 作业 | 制约状态 |\n"
        "| --- | --- | --- | --- |\n"
        f"| 第1周 | 班组、工作面、日顺序 | {week_jobs} | {week_block} |\n"
        f"| 第2周 | 分项与责任人 | {week_jobs} | {week_block} |\n"
        f"| 第3周 | 分项与制约（较粗） | {week_jobs} | {week_block} |\n"
        f"| 第4周 | 分项与制约（较粗） | {week_jobs} | {week_block} |\n"
    )
    if blocked:
        cons = (
            "| 工作 | 制约 | 责任人 | 计划清除日 |\n"
            "| --- | --- | --- | --- |\n"
            + "".join(f"| {n} | 未清 | 待填 | 待填 |\n" for n in blocked)
        )
    else:
        cons = (
            "| 工作 | 制约 | 责任人 | 计划清除日 |\n"
            "| --- | --- | --- | --- |\n"
            "| [A001] | 待填 | 待填 | 待填 |\n"
        )
    if can_promise:
        promise = (
            "| 作业 | 认领人 | 周末兑现 |\n"
            "| --- | --- | --- |\n"
            + "".join(f"| {n} | 待填 | 待对照 |\n" for n in jobs)
        )
        promise_note = "只列入用户已标明条件已具备的工作。工长认领栏待填。"
    else:
        promise = (
            "| 作业 | 认领人 | 周末兑现 |\n"
            "| --- | --- | --- |\n"
            "| （空） | — | — |\n"
        )
        promise_note = "制约未清，不得写入本周承诺。"
    lines = [
        "# 四周滚动计划 / 月度计划（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "必须挂在总控里程碑下。禁止用周计划改合同工期。不是工期签证，不是复工许可。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_PLAN_LOOKAHEAD_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("计划期（哪四周或哪一自然月）待填。对应总控版本号待填。编制人栏空。内部讨论草稿。[A001]")
        elif i == 2:
            lines.append("把总控里落在未来约四周的工作拉到工长能认领的粒度。总控没有该窗口的工作，本栏写待补，不要发明作业。")
            if jobs:
                lines.append("")
                lines.append("本轮点名作业：" + "；".join(jobs))
        elif i == 3:
            lines.append(four)
            lines.append("")
            lines.append("第 1 周量化到班组、工作面、日顺序；第 2 周到分项与责任人；第 3–4 周保留分项与制约，允许较粗。不编持续天数。")
        elif i == 4:
            lines.append(cons)
            lines.append("")
            lines.append("每条制约指定责任人和计划清除日。未清项不得列入第 5 节周承诺。")
        elif i == 5:
            lines.append(promise_note)
            lines.append("")
            lines.append(promise)
            lines.append("")
            lines.append("周末对照承诺兑现（完成项 / 承诺项）。未完成只记原因分类（图、料、人、机、面、天气、指令），不写处罚结论。")
        elif i == 6:
            lines.append(
                "同一工作面或上下立体空间有两个及以上专业时，单列交叉窗口：谁先谁后、防护谁做、吊装禁区、噪音时段。"
                "计划只排窗口。安全措施改召唤安全交底或施工方案，不在本稿编栏杆高度或吊装半径。"
            )
        elif i == 7:
            lines.append(
                "本月可能触发暂停的外部条件，日期待填：大风、暴雨暴雪、能见度不足、高温橙色以上、"
                "冬期测温未达标、台风预警、政府停工令、危大方案未论证、特种设备证件过期。"
                "停工后只列复工条件栏。本岗不签发复工许可，不编风速限值。"
            )
        elif i == 8:
            lines.append(
                "本周若拖的是关键工作或吃完总时差，必须回写总控版本，并提示索赔调概看时限。"
                "非关键工作的小调整可留在四周窗口内，纪要写明未改总工期。"
            )
        elif i == 9:
            lines.append(
                "| 形象部位 | 计划形象 | 实际形象 | 偏差天数 | 原因 | 纠偏 |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |"
            )
            lines.append("")
            lines.append("无现场反馈则实际栏待填。不要把照片描述写成已验收合格。")
        else:
            lines.append(
                "无班组名单、无总控版本、无制约责任人，对应整节待填。"
                "禁止断言本周计划必定兑现、交叉作业已安全、停工后即可实施。"
            )
        lines.append("")
    lines.append("SG：Last Planner lookahead 只写方法名，不是合同工期变更。")
    lines.append("CN：周月计划不是工期签证。")
    lines.append("")
    return "\n".join(lines)


def _resource_kind(line: str) -> str:
    t = line or ""
    low = t.lower()
    if any(k in t or k in low for k in _PLANT_KEYS):
        return "plant"
    if any(k in t for k in ("工", "班组", "劳动力")):
        return "labor"
    if any(k in t or k in low for k in _MAT_KEYS):
        return "mat"
    if "formwork" in low:
        return "labor"
    return "labor"


def _split_resource_qty(line: str) -> tuple:
    t = (line or "").strip()
    m = _RES_QTY.search(t)
    if not m:
        return t, "TBD", "待填"
    name = (t[: m.start()] + t[m.end() :]).strip(" ，,;；") or t
    return name, f"{m.group('qty')}{m.group('unit')}", "用户给定"


def _parse_resource_items(blob: str) -> tuple:
    labor: List[tuple] = []
    plant: List[tuple] = []
    mat: List[tuple] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in _RESOURCE_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if re.match(r"^W\d+$", t, re.I):
            continue
        if len(t) > 80:
            t = t[:80]
        name, qty, src = _split_resource_qty(t)
        if not name or name in _RESOURCE_SKIP:
            continue
        kind = _resource_kind(t)
        row = (name, qty, src)
        if kind == "plant":
            plant.append(row)
        elif kind == "mat":
            mat.append(row)
        else:
            labor.append(row)
    return labor, plant, mat


def _resource_table(kind: str, rows: List[tuple]) -> str:
    if kind == "labor":
        head = (
            "| 工种 | 工作 | 计划时段 | 需用人数 | 来源 | 峰值周 | 可否错峰 |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
        )
        if not rows:
            return head + "| [A001] | 待填 | 待填 | TBD | 待填 | 待填 | 待填 |\n"
        return head + "".join(
            f"| {n} | 待填 | 待填 | {q} | {s} | 待填 | 待填 |\n" for n, q, s in rows
        )
    if kind == "plant":
        head = (
            "| 机械名称 | 规格 | 进场日 | 退场日 | 台班或台数 | 对应工作 | 证件 |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
        )
        if not rows:
            return head + "| [A001] | 待填 | 待填 | 待填 | TBD | 待填 | 待核 |\n"
        return head + "".join(
            f"| {n} | 待填 | 待填 | 待填 | {q} | 待填 | 待核 |\n" for n, q, s in rows
        )
    head = (
        "| 名称 | 需用窗口 | 计划进场 | 计划耗尽 | 堆场 | 甲指或自采 | 数量 |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
    )
    if not rows:
        return head + "| [A001] | 待填 | 待填 | 待填 | 待填 | 待填 | TBD |\n"
    return head + "".join(
        f"| {n} | 待填 | 待填 | 待填 | 待填 | 待填 | {q} |\n" for n, q, s in rows
    )


def _plan_resource_md(text: str) -> str:
    labor, plant, mat = _parse_resource_items(text)
    lines = [
        "# 资源负荷表（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "默认交付是表头和口径说明，不是劳动力需用计划定案，也不是采购订单。本表不报价。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_PLAN_RESOURCE_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(
                "对应总控版本、计划期、资源种类范围待填。[A001] "
                "无定额、无劳务计划、无设备台账、无材料需用表时，数量列全部待填。"
            )
        elif i == 2:
            lines.append(
                "须核对：总控或四周窗口、分部分项工程量来源、定额或企业消耗指标、"
                "劳务班组编制、机械台账与证件、甲指/自采划分、堆场与宿舍上限。缺哪一项，对应资源列不填数。"
            )
        elif i == 3:
            lines.append(_resource_table("labor", labor))
            lines.append("")
            lines.append("只汇总用户已给的人数。来源为定额工日或用户给定；否则待填。禁止按经验编人数。")
        elif i == 4:
            lines.append(_resource_table("plant", plant))
            lines.append("")
            lines.append("特种设备证件待核。无证件不得列入进场安排。数量来自施工部署或用户台账，不来自本岗估算。")
        elif i == 5:
            lines.append(_resource_table("mat", mat))
            lines.append("")
            lines.append("数量来自需用计划或清单。本岗不算量、不组价。到货价改召唤采购；收发存改召唤仓管或现场材料。")
        elif i == 6:
            lines.append(
                "横轴为周或旬，纵轴为数量（有数才画）。峰值时段待填。"
                "错峰口径：总工期不变，利用非关键工作时差削峰填谷。禁止为削峰压缩关键工作持续时间。"
            )
        elif i == 7:
            lines.append(
                "| 项 | 提示 |\n| --- | --- |\n"
                "| 宿舍/食堂容量 | 可能冲突，待用户给上限 |\n"
                "| 塔吊台班窗口 | 可能冲突，待用户给上限 |\n"
                "| 混凝土日供应 | 可能冲突，待用户给上限 |\n"
                "| 作业面人数密度 | 可能冲突，待用户给上限 |\n"
                "| 夜间施工许可 | 可能冲突，待用户给上限 |"
            )
            lines.append("")
            lines.append("只标可能冲突。不写已经超标或已经合规。")
        elif i == 8:
            lines.append(
                "四周滚动看本表「这周人机料是否同时具备」；采购看需用窗口和提前期栏；"
                "资金看大额进场时点栏，金额待填，改召唤资金或验工计价。"
            )
        elif i == 9:
            lines.append("未做均衡，仅列表头。未计算时差，不写移动了哪些非关键工作。")
        else:
            lines.append(
                "不编工日、台班、吨数、综合单价、市场价。"
                "禁止宣称资源已经够用。无证件设备不列入进场安排。"
                "关键线路资源缺口必须回写总控，不得只在本表删掉该工作。"
            )
        lines.append("")
    lines.append("SG：Code of Practice on Buildability 只写标题，最低分 UNSPECIFIED。C-Score 不是劳动力需用计划。")
    lines.append("CN：施工组织设计规范 / 劳动定额只写全名，不编工日。")
    lines.append("")
    return "\n".join(lines)


def _mix_has_trial(blob: str) -> bool:
    t = blob or ""
    if "无试验数据" in t:
        return False
    return any(k in t for k in _MIX_TRIAL_YES)


def _mix_zone(blob: str) -> str:
    t = blob or ""
    if "DUAL" in t:
        return "DUAL"
    if any(k in t for k in ("JGJ", "37 号令", "GB 50", "住建部", "配合比设计规程")):
        return "CN"
    return "SG"


def _lab_mix_md(text: str) -> str:
    blob = text or ""
    has = _mix_has_trial(blob)
    zone = _mix_zone(blob)
    gm = _MIX_GRADE_RE.search(blob)
    grade = gm.group(1).upper() if gm else "[A001] 待填"
    kind = "砂浆" if ("砂浆" in blob or (gm and gm.group(1).upper().startswith("M"))) else "混凝土"
    prep = "预拌" if "预拌" in blob else "现场拌合（待核）"
    if has:
        layer4 = "用户声明已有试验数据：可列换算栏，施工配比数字仍须试验室签认。本稿不编 kg/m³。"
    else:
        layer4 = "无试验数据：不给施工配合比，整节待填。含水率未测不得换算湿料。"
    four = (
        "| 层次 | 本稿 |\n| --- | --- |\n"
        "| 初步（理论）配合比 | 缺原材料密度、含水、需水量则停。用量待填。 |\n"
        "| 基准配合比 | 无试拌记录不锁基准。 |\n"
        "| 试验室配合比 | 强度与耐久性复核通过后才能作为换算起点。 |\n"
        f"| 施工配合比 | {layer4} |\n"
    )
    lines = [
        "# 配比报告提纲（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "本提纲不是法定配合比报告，不是搅拌站开盘依据，不构成浇筑许可。",
        "",
        f"- 辖区：{zone}",
        f"- 种类：{kind} / {prep}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_LAB_MIX_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append(
                f"工程名称待填。部位待填。强度等级/砂浆等级：{grade}。"
                "坍落度或稠度要求待填。全部只引用户或项目包。空签认栏。[A001]"
            )
        elif i == 2:
            lines.append(DISCLAIMER)
            lines.append("")
            lines.append("不是法定配合比报告，不是搅拌站开盘依据。")
        elif i == 3:
            lines.append(four)
            lines.append("")
            lines.append("只写层次，不写用量。砂浆与混凝土分开写，预拌与现场拌合分开写。")
        elif i == 4:
            lines.append(
                "水泥、掺合料、砂、石、外加剂、拌合水须与试配时同一品种、规格、产地口径。"
                "进场复试未出或异常，不得换算施工配比，也不得自行改砂率、水胶比、外加剂掺量。"
            )
        elif i == 5:
            lines.append(
                "试验员可记录含水率和开盘观察，不得口头改配比。"
                "超出批准范围的调整要试验数据 + 试验室主任/技术负责人 + 监理/建设知情。本提纲不代批。"
            )
        elif i == 6:
            if zone in ("CN", "DUAL"):
                lines.append(
                    "公开名称，年份以项目现行有效版为准，状态 unverified / unspecified_clause。"
                    "《普通混凝土配合比设计规程》JGJ 55；《砌筑砂浆配合比设计规程》JGJ/T 98；"
                    "《混凝土质量控制标准》GB 50164；《混凝土结构工程施工质量验收规范》GB 50204；"
                    "《预拌混凝土》GB/T 14902。用户未提供文本则不得写入已核实块，不得摘条款。"
                )
            else:
                lines.append(
                    "公开名称只写族名。条款 unspecified_clause。"
                    "用户未提供文本则不得写入已核实块，不得摘条款。"
                )
        elif i == 7:
            lines.append(
                "| 编号 | 本稿 |\n| --- | --- |\n"
                "| 原材料复试报告编号 | 待填 |\n"
                "| 试配记录编号 | 待填 |\n"
                "| 开盘鉴定记录编号 | 待填 |"
            )
            lines.append("")
            lines.append("有则抄用户，无则待填。编号规则见 lab-record，本岗不编新号。")
        elif i == 8:
            lines.append(
                "试配申请、原材料报告、试拌记录、强度/耐久性试件、批准的试验室配合比、"
                "含水率测定、施工配合比通知单。开盘条件栏待核，本稿不下开盘结论。"
            )
        else:
            lines.append(
                "不编水胶比、砂率、每立方米用量、水泥强度、外加剂掺量。"
                "不把搅拌站经验配比或网上例题当成工程配比。不因商务催省水泥而改单。"
            )
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：SAC laboratory accreditation / CT 06 Ready-Mixed Concrete Producers 只写标题。SS EN 206 / SS 544 只写族名。不得把已过时的 SS 289 / CP 65 当现行配比依据。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：普通混凝土配合比设计规程只写全名，不给施工配比。")
    lines.append("")
    return "\n".join(lines)


def _parse_sample_cats(blob: str) -> List[str]:
    rows: List[str] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in _SAMPLE_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t in {"JGJ", "SAC", "CN", "SG", "DUAL"}:
            continue
        if len(t) > 80:
            t = t[:80]
        if t not in rows:
            rows.append(t)
    return rows


def _lab_sample_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    cats = _parse_sample_cats(blob)
    if not cats:
        cats = list(_SAMPLE_DEFAULT)
    table = (
        "| 类别 | 部位 | 见证人 | 组数 | 升级路径 |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "".join(
            f"| {c} | 待填 | （空） | [A001] | 不合格 24 小时上报；停止相关使用；隔离待处置 |\n"
            for c in cats
        )
    )
    lines = [
        "# 取样送检清单（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "本清单只排计划与缺口，不判定材料合格，不编组数。不是工程质量验收资料。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_LAB_SAMPLE_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("工程名称、施工段、计划周期、检测机构名称待填（须用户给出且为建设委托）。空签认栏。[A001]")
        elif i == 2:
            lines.append(
                "取样员属施工单位；见证人属建设单位或监理。取样员与见证人不得写成同一人同一单位。"
                "建设委托的检测，施工人员须在见证下现场取样；委托单须送检人、见证人签字。"
            )
        elif i == 3:
            lines.append(table)
            lines.append("")
            lines.append("全国公开底线只列名称。地方加长项待核，不编造地方条款。")
        elif i == 4:
            lines.append(
                "涉及结构安全的试块、试件和材料，见证取样和送检比例不得低于有关技术标准规定应取样数量的 30%。"
                "30% 是下限。具体每批组数按该项现行标准 + 用户计划，缺则 [A001]，禁止估算组数。"
            )
        elif i == 5:
            lines.append(
                "按计划取样 → 标识封志 → 共同送检 → 填委托单 → 检测机构核封志。"
                "试样损伤、超时、掉封不得当见证样。"
            )
        elif i == 6:
            lines.append(
                "样品或报告不合格：24 小时内上报，停止相关加工与使用，书面通知监理/建设，隔离待处置。"
                "本清单不代做复检结论。项目试验室负责把报告送达路径写进清单，不冒充主管部门。"
            )
        elif i == 7:
            lines.append(
                "见证取样检测报告须加盖见证取样检测专用章。"
                "非建设单位委托的检测报告不得作为工程质量验收资料。"
                "出厂合格证、供方自检不能替代见证送检。"
            )
        elif i == 8:
            lines.append(
                "未复试或不合格的原材料，lab-mix 不得出施工配比；报告编号连续登记走 lab-record；"
                "实物隔离走 warehouse；资料目录走 supervision。本岗只留接口栏。"
            )
        else:
            lines.append(
                "不写取样合格结论。不编检测数据。"
                "不把监督抽检、企业试验室自检、见证取样混成一种报告。"
            )
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：SAC laboratory accreditation / BCA construction site records 只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：见证取样和送检的规定 / 建设工程质量检测管理办法只写全名。建建〔2000〕211 号只列名称。")
    lines.append("")
    return "\n".join(lines)


def _parse_record_samples(blob: str) -> List[str]:
    rows: List[str] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in _RECORD_SKIP or t in _SAMPLE_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t in {"JGJ", "SAC", "CN", "SG", "DUAL"}:
            continue
        if len(t) > 80:
            t = t[:80]
        if t not in rows:
            rows.append(t)
    return rows


def _lab_record_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    samples = _parse_record_samples(blob)
    if samples:
        table = (
            "| 试样 | 试验项 | 报告编号 | 仪器检定 | 结论 |\n"
            "| --- | --- | --- | --- | --- |\n"
            + "".join(f"| {s} | 待填 | 待核 | 待核 | 待填 |\n" for s in samples)
        )
    else:
        table = (
            "| 试样 | 试验项 | 报告编号 | 仪器检定 | 结论 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 待填 | 待填 | 待核 | 待核 | 待填 |\n"
        )
    lines = [
        "# 试验台账骨架（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "内部讨论用，不是 CMA/CNAS 证书，不是竣工归档正本。不填检测数据，不给合格结论。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_LAB_RECORD_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("工程或试验室名称、年度、台账种类待填。[A001]")
        elif i == 2:
            lines.append(
                "检测合同、委托单、原始记录、检测报告按年度统一编号，编号连续，不得随意抽撤、涂改。"
                "用户未给现行编号规则则只出表头 + [A001] 待填，不发明一套工程代号。"
            )
        elif i == 3:
            lines.append(
                "- 原材料进场复试台账\n"
                "- 混凝土 / 砂浆试配与施工配合比通知台账（只登记编号与日期，用量见 lab-mix）\n"
                "- 试件成型、养护、试压台账\n"
                "- 见证取样送检台账\n"
                "- 检测结果不合格项目台账（单独建册）\n"
                "- 仪器设备台账与检定/校准/期间核查计划\n"
                "- 标准物质与试模、养护室温湿度记录"
            )
            lines.append("")
            lines.append(table)
        elif i == 4:
            lines.append("记录真实、按年连续编号。严禁涂改，笔误杠改并签改人改期。记录、报告、影像与样品标识对同一唯一号。")
        elif i == 5:
            lines.append(
                "检定：对照法定要求给出合格与否，属法制计量。未检、逾期、不合格不得使用。"
                "校准：给出示值误差和不确定度，用于溯源和修正，不等于法定检定。"
                "期间核查：两次检定或校准之间的运行检查，不是再做一次检定。"
                "仪器超检定期不得使用，不得继续出具数据。追溯清单待用户提供，不编报告号。"
            )
        elif i == 6:
            if zone in ("CN", "DUAL"):
                lines.append("《建设工程质量检测管理办法》；《中华人民共和国计量法》。试验方法标准只写名称，正文禁止摘步骤。")
            else:
                lines.append("公开名称只写族名。试验方法标准只写名称，正文禁止摘步骤。条款 unspecified_clause。")
        elif i == 7:
            lines.append(
                "| 检查 | 状态 |\n| --- | --- |\n"
                "| 有取样计划是否有委托单 | 待核 |\n"
                "| 有委托单是否有报告 | 待核 |\n"
                "| 有不合格是否有 24 小时上报和处置 | 待核 |\n"
                "| 有仪器是否在有效期内 | 待核 |"
            )
            lines.append("")
            lines.append("缺一项标缺口。本稿不下归档结论。")
        elif i == 8:
            lines.append("配合比通知单编号给 lab-mix；见证委托单给 lab-sample；资料总目录给 supervision；账物隔离给 warehouse。")
        else:
            lines.append("不编造已完成的检定证书号、报告号、温湿度曲线。不把校准证书改写成法定检定。")
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：SAC laboratory accreditation 只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：建设工程质量检测管理办法只写全名。")
    lines.append("")
    return "\n".join(lines)


def _supervision_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    if any(k in blob for k in ("监理规范", "GB/T 50319", "归档规范")):
        zone = "CN" if zone == "SG" else zone
    notice = blob.strip() or "待填"
    notice = re.sub(r"^写一份\S*\s*", "", notice).strip() or "待填"
    if notice in {"草稿提纲", "监理回复", "待填"}:
        notice = "待填"
    stop_note = (
        "暂停令、复工报审只出目录和拟办提纲。本岗不签发复工。"
        if any(k in blob for k in ("暂停", "复工", "停工"))
        else "若来文是暂停/复工，只出目录和拟办提纲。本岗不签发复工。"
    )
    lines = [
        "# 监理通知回复草稿（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "本回复是资料草稿，不是监理指令。待持证人员审核签发后报出。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SUPERVISION_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("工程名称待填。回复编号待填。对应来文编号/日期待填。[A001]")
        elif i == 2:
            lines.append("致：项目监理机构。抄送栏待填。")
        elif i == 3:
            lines.append(notice[:400])
            lines.append("")
            lines.append("只复述用户提供的事由、部位、条数，不扩写没给的事实。")
        elif i == 4:
            lines.append("管理/工艺/材料/资料。缺事实则待填。[A001]")
        elif i == 5:
            lines.append("逐条对应来文，一条不漏。举一反三和预防只作栏目，不编造已培训记录。")
            lines.append("")
            lines.append(stop_note)
        elif i == 6:
            lines.append("从来文或合同抄，否则 [A001] 待填。")
        elif i == 7:
            lines.append(
                "| 证据 | 本稿 |\n| --- | --- |\n"
                "| 整改前后影像 | 待附 |\n"
                "| 检查记录 | 待附 |\n"
                "| 检测报告 | 待附 |\n"
                "| 方案/交底目录 | 待附 |"
            )
        elif i == 8:
            lines.append("项目技术/质量负责人栏空白。")
        elif i == 9:
            lines.append("本回复为 AI 草稿，待项目经理等持证人员审核签发后报出。")
        elif i == 10:
            lines.append(
                "| 来文号 | 要求闭合日 | 实际回复日 | 复查意见 |\n"
                "| --- | --- | --- | --- |\n"
                "| 待填 | 待填 | 待填 | （空，复查属监理） |"
            )
        else:
            lines.append(
                "不写验收合格、资料已闭合可备案。不冒充总监签发。"
                "不编报告编号、强度、闭合天数。暂停/复工只出目录。"
            )
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：BCA construction site records / record structural plan C-forms 只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：建设工程监理规范只写全名。")
    lines.append("")
    return "\n".join(lines)


def _safety_brief_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    work = re.sub(r"^写一份\S*\s*", "", blob.strip()).strip() or "待填。[A001]"
    if work in {"草稿提纲", "安全交底", "待填"}:
        work = "待填。[A001]"
    lines = [
        "# 安全技术交底草稿（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "给现场技术员的讨论用交底草稿，不是工人口播，也不是签认件。须持证人员按正式文本复核签字后才可实施。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SAFETY_BRIEF_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("工程名称待填。作业部位、工序待填。交底日期待填。交底人/接受人空栏。[A001]")
        elif i == 2:
            lines.append(DISCLAIMER)
        elif i == 3:
            lines.append(work[:200])
            lines.append("")
            lines.append("轴线、楼层、基坑侧未给则 [A001]。禁止虚构图号。")
        elif i == 4:
            lines.append("只列用户或方案里出现的步骤。未给则待填。[A001]")
        elif i == 5:
            lines.append("只写本部位可能碰到的：临边坠落、洞口、物体打击、坍塌、触电、起重碰撞、有限空间、火灾。不抄全集充数。")
        elif i == 6:
            lines.append("栏杆、盖板、安全带挂点、通道、警戒、湿法、通风检测。高度、间距、荷载一律 [A001]，不编毫米数。")
        elif i == 7:
            lines.append("帽、鞋、镜、手套、安全带、呼吸防护。规格待填。[A001]")
        elif i == 8:
            lines.append("无防护不作业；酒后/带病不上高；有限空间未通风检测不进；指挥信号不清不起吊。")
        elif i == 9:
            lines.append("就近撤离方向待填。急救原则：高坠不乱搬、触电先断电。报告对象待填。电话 [A001]。")
        elif i == 10:
            lines.append("用户点名的规范全名。未提供文本则未核实表 + 条款 UNSPECIFIED。")
        else:
            lines.append("| 交底人 | 接受班组 | 安全员 | 日期 |\n| --- | --- | --- | --- |\n| （空） | （空） | （空） | 待填 |")
            lines.append("")
            lines.append("不预填姓名。本稿不下交底完毕结论。")
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：WSH Council toolbox meeting 导则只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：安全技术交底按专项方案实施程序只写标题，本岗不签认。")
    lines.append("")
    return "\n".join(lines)


def _parse_qc_items(blob: str) -> List[str]:
    rows: List[str] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in {"草稿提纲", "质量检查表", "检验批", "待填"}:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t in {"JGJ", "SAC", "CN", "SG", "DUAL", "CONQUAS"}:
            continue
        if len(t) > 80:
            t = t[:80]
        if t not in rows:
            rows.append(t)
    return rows


def _qc_table(title_row: str, items: List[str], empty: str) -> str:
    head = "| 检查内容 | 设计或标准要求 | 实测或观察 | 结果 | 处理意见 |\n| --- | --- | --- | --- | --- |\n"
    if not items:
        return head + f"| {empty} | 待填 | 待填 | 未检 | （空） |\n"
    return head + "".join(
        f"| {it} | 待填 | 待填 | 未检 | （空） |\n" for it in items
    )


def _quality_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    items = _parse_qc_items(blob)
    lot = items[0] if items else "待填"
    lines = [
        "# 质量检查表（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "检验批、隐蔽验收、通病防治的检查栏目。不给合格结论，不替代监理组织验收。",
        "",
        f"- 辖区：{zone}",
        f"- 检验批部位：{lot}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_QUALITY_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("工程/楼栋/检验批部位待填。对应分项名称待填。检查表编号待填。[A001]")
        elif i == 2:
            lines.append("本表覆盖哪一段、哪一层、哪一批待填。用户未给批量、抽样数量则 [A001]，不编最小抽样。")
        elif i == 3:
            lines.append("图纸图号仅用户清单。施工方案讨论稿名称待填。材料报告编号空则待填。禁止自造图号。")
        elif i == 4:
            lines.append(_qc_table("主控", items, "待列主控项 [A001]"))
            lines.append("")
            lines.append("对安全、节能、环保和主要使用功能起决定作用的项。结果=未检。")
        elif i == 5:
            lines.append(_qc_table("一般", [], "待列一般项 [A001]"))
            lines.append("")
            lines.append("外观、尺寸偏差。同样不预填合格。结果=未检。")
        elif i == 6:
            lines.append(_qc_table("隐蔽", [], "待列隐蔽项 [A001]"))
            lines.append("")
            lines.append("隐蔽前通知、影像、旁站记录栏目。未验收不建议进入下道，但不写开工令。")
        elif i == 7:
            lines.append("楼板裂缝、填充墙裂缝、外墙/屋面/门窗渗漏、回填下沉、保护层、线管叠放、抹灰空鼓。只列易发部位和预防动作。")
        elif i == 8:
            lines.append("返工返修后重新检查。检测鉴定、设计核算等路径只列名称，结论待有资质单位。")
        elif i == 9:
            lines.append("施工记录、测量、材料/试块报告与试验室台账是否对得上。缺报告写缺口，不编强度。")
        else:
            lines.append("| 质检员 | 工长 | 技术负责人 | 监理 |\n| --- | --- | --- | --- |\n| （空） | （空） | （空） | （空） |")
            lines.append("")
            lines.append("禁止预填同意验收。")
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：CONQUAS 只写标题，不是本表评分。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：建筑工程施工质量验收统一标准只写全名。条款 UNSPECIFIED。")
    lines.append("")
    return "\n".join(lines)


def _env_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    site = re.sub(r"^写一份\S*\s*", "", blob.strip()).strip() or "待填工地"
    if site in {"草稿提纲", "环保文明清单", "待填"}:
        site = "待填工地"
    rows = (
        "| 项 | 措施栏 | 限值 |\n| --- | --- | --- |\n"
        "| 扬尘 | 围挡、道路硬化冲洗、裸土覆盖、粉料入库存罐 | UNSPECIFIED |\n"
        "| 弃土 | 分类堆放、联单或核准去向待填 | UNSPECIFIED |\n"
        "| 污水 | 沉淀/洗车台排水去向待填，不得直排 | UNSPECIFIED |\n"
        "| 夜间 | 属地夜间限制段待核，连续作业报批单另附 | UNSPECIFIED |\n"
        "| 市容 | 大门、公示牌、堆码、人车分流 | UNSPECIFIED |\n"
    )
    lines = [
        "# 环保文明清单（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "覆盖扬尘、弃土、污水、噪声/夜间施工、市容围挡。不是排污许可，也不是城管销号证明。",
        "",
        f"- 辖区：{zone}",
        f"- 工地：{site[:80]}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_ENV_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("项目、标段、清单日期、责任人空栏、属地区县待填。[A001]")
        elif i == 2:
            lines.append("AI 草稿。措施落实与是否达标由现场和属地监管确认。")
        elif i == 3:
            lines.append(rows)
            lines.append("")
            lines.append("风速阈值用户给才写。监测设备以属地是否要求为准。")
        elif i == 4:
            lines.append("产生部位、暂存点、分类、运输单位、消纳单位、联单编号全部待填。禁止写可随意外运。")
        elif i == 5:
            lines.append("沉淀池/洗车台排水去向待填。不得直排市政管或河道。容量、排放口编号待填。")
        elif i == 6:
            lines.append("昼间/夜间作业时段以属地公告为准。敏感点距离用户给才写。限值 UNSPECIFIED。")
        elif i == 7:
            lines.append("大门、公示牌（建设/监理/施工扬尘责任人和投诉电话）、材料堆码、人员通道与车辆分流。")
        elif i == 8:
            lines.append("安全文明施工费、扬尘防治增加费只列措施事实和影像、验收单名称。费率 TBD，交商务。")
        elif i == 9:
            lines.append("重污染天气、大风、投诉、执法检查——列接到哪一级指令停哪一类作业。本岗不下停工令。")
        else:
            lines.append("| 环保员 | 生产经理 | 资料员 |\n| --- | --- | --- |\n| （空） | （空） | （空） |")
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：NEA Construction Noise Control / Sundays and PH / Noise Management Plan；PUB Earth Control Measures。只列标题，限值 UNSPECIFIED。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：噪声法/扬尘口径只列名称。不编 TSP 限值。")
    lines.append("")
    return "\n".join(lines)


def _named_emergency_specials(blob: str) -> List[str]:
    t = (blob or "").lower()
    raw = blob or ""
    named: List[str] = []
    for hint, spec in _EMERGENCY_HINTS:
        if hint.lower() in t or hint in raw:
            if spec not in named:
                named.append(spec)
    return named


def _emergency_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    named = _named_emergency_specials(blob)
    special_rows = "| 专项 | 本稿 |\n| --- | --- |\n"
    for spec in _EMERGENCY_SPECIALS:
        if spec in named:
            special_rows += f"| {spec} | 本轮点名。只列名称，不展开假场景。 |\n"
        else:
            special_rows += f"| {spec} | 常见名。用户未点名不展开。 |\n"
    drill = (
        "| 时间 | 科目 | 参演单位 | 评估人 | 发现问题 | 修订意见 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |\n"
    )
    lines = [
        "# 生产安全事故应急预案提纲（AI 草稿 · 内部讨论）",
        "",
        DISCLAIMER,
        "",
        "只出目录、演练记录表头和待填附件。不签发预案。联系人通讯录全部 [A001]。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_EMERGENCY_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("单位/项目待填。预案名称待填。版本待填。签署人空栏。联系人通讯录全部 [A001]。")
        elif i == 2:
            lines.append(
                "风险辨识结论栏待填。应急资源调查清单栏：队伍、车辆、担架、灭火器、洗消、医院。"
                "无现场盘点不编数量。医院名称和电话待填。"
            )
        elif i == 3:
            lines.append(
                "1. 组织机构与职责\n"
                "2. 预案体系\n"
                "3. 风险描述\n"
                "4. 预警与信息报告\n"
                "5. 响应分级\n"
                "6. 保障\n"
                "7. 培训演练与管理"
            )
        elif i == 4:
            lines.append(special_rows)
            lines.append("")
            lines.append("用户没点名则只列常见名、不展开假场景。")
        elif i == 5:
            lines.append("按场所：基坑、脚手架、配电房、食堂、宿舍、桩机区。含职责、措施、注意事项。未给场所则待填。")
        elif i == 6:
            lines.append("一岗一卡，短步骤 + 联络人待填。电话 [A001]。")
        elif i == 7:
            lines.append("内部升级顺序待填。向属地应急和行业主管部门报告的内容栏待填。不编已报告结论。")
        elif i == 8:
            lines.append(drill)
            lines.append("")
            lines.append("评估、问题、修订意见待填。本稿不下演练结论。")
        elif i == 9:
            lines.append(
                "| 附件 | 本稿 |\n| --- | --- |\n"
                "| 通讯录 | 待填；电话 [A001] |\n"
                "| 物资台账 | 待填 |\n"
                "| 医院路线 | 医院名称待填；电话 [A001] |\n"
                "| 周边告知 | 待填 |"
            )
        elif i == 10:
            lines.append("公布日、拟备案机关、评估年待用户填。备案条件栏待核，本稿不下备案结论。")
        else:
            lines.append(
                "不编医院名称和电话，不编响应时间分钟数。"
                "有限空间救援强调禁止盲目进入。"
                "本稿不下演练通过结论。"
            )
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：SCDF Emergency Response Plan 只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：生产安全事故应急预案管理办法只写标题。")
    lines.append("")
    return "\n".join(lines)


def _parse_equip_names(blob: str) -> List[str]:
    rows: List[str] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        for key in ("合格证", "使用登记", "作业人员证件", "作业证"):
            if key in t:
                t = t.split(key)[0].strip()
        if not t or t in _EQUIP_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t in {"JGJ", "SAC", "CN", "SG", "DUAL", "MOM"}:
            continue
        if len(t) > 80:
            t = t[:80]
        if t not in rows:
            rows.append(t)
    return rows


def _copy_equip_certs(blob: str) -> List[tuple]:
    found = []
    for m in _CERT_COPY.finditer(blob or ""):
        found.append((m.group(1), m.group(2)))
    return found


def _equip_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    if "特种设备安全法" in blob:
        zone = "CN" if zone == "SG" else zone
    names = _parse_equip_names(blob)
    certs = _copy_equip_certs(blob)
    cert_cell = "特种设备证件待核"
    if certs:
        cert_cell = "；".join(f"{n} {c}（用户给定）" for n, c in certs)
    if names:
        inv = (
            "| 名称 | 规格型号 | 厂编号或备案号 | 自有或租赁 | 计划进退场 | 当前状态 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| {n} | 待填 | 待填 | 待填 | 待填 | 待进场 |\n" for n in names
            )
        )
        gate = (
            "| 设备 | 进场验收 | 证件 | 维保 |\n"
            "| --- | --- | --- | --- |\n"
            + "".join(
                f"| {n} | 待做 | {cert_cell} | 待排 |\n" for n in names
            )
        )
    else:
        inv = (
            "| 名称 | 规格型号 | 厂编号或备案号 | 自有或租赁 | 计划进退场 | 当前状态 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| [A001] | 待填 | 待填 | 待填 | 待填 | 待进场 |\n"
        )
        gate = (
            "| 设备 | 进场验收 | 证件 | 维保 |\n"
            "| --- | --- | --- | --- |\n"
            f"| 待填 | 待做 | {cert_cell} | 待排 |\n"
        )
    cert_tbl = (
        "| 证书名称 | 编号 | 有效期 | 作业项目 | 状态 |\n"
        "| --- | --- | --- | --- | --- |\n"
    )
    if certs:
        cert_tbl += "".join(
            f"| {n} | {c} | 待填 | 待填 | 用户给定 |\n" for n, c in certs
        )
    else:
        cert_tbl += (
            "| 产品合格证 | 待核 | 待填 | 待填 | 待核 |\n"
            "| 使用登记 | 待核 | 待填 | 待填 | 待核 |\n"
            "| 作业人员证件 | 待核 | 待填 | 待填 | 待核 |\n"
        )
    lines = [
        "# 设备台账 / 维保计划（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "内部讨论。不构成特种设备使用登记、安装验收签认、法定专项方案或开工依据。签认栏留空。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_EQUIP_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("标明内部讨论。签认栏留空。[A001]")
        elif i == 2:
            lines.append(inv)
            lines.append("")
            lines.append("无用户清单不编造机号和备案号。只抄用户设备名。")
        elif i == 3:
            lines.append(gate)
            lines.append("")
            lines.append("[A001] 无证件不编进场结论。缺一件写不得进场。本岗不签发使用登记。")
        elif i == 4:
            lines.append("合同要素：谁负责安拆、顶升附着、维保和检测费用；按台班还是包月。无报价则租金和合价 TBD。")
        elif i == 5:
            lines.append("按台分列日常点检、定期保养、故障修理。顶升和附着单独留栏。写过计划不等于已经保养，完成记录栏待填。")
        elif i == 6:
            lines.append(cert_tbl)
            lines.append("")
            lines.append("只抄用户已给证件。过期视同缺失。不编证号。")
        elif i == 7:
            lines.append("进退场单、台班单、维保和修理记录、检测报告复印件、租赁补充协议。金额待填。")
        elif i == 8:
            lines.append("资料目录交给资料监理专家闭合。本岗不宣称资料已闭合。安装拆卸方案交施工方案；是否危大交 method-hazard。")
        else:
            lines.append("不签发使用登记。不编租金、折旧率和综合单价。不宣称通过专家论证或可以投入使用。")
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：MOM lifting equipment / approved crane contractor 只写标题。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：特种设备安全法只写全名。")
    lines.append("")
    return "\n".join(lines)


def _parse_wh_rows(blob: str) -> List[tuple]:
    rows: List[tuple] = []
    for piece in (blob or "").replace("；", "\n").replace(";", "\n").splitlines():
        t = piece.strip()
        t = re.sub(r"^写一份\S*\s*", "", t).strip()
        if not t or t in _WH_SKIP:
            continue
        if t.startswith("#") or t.startswith("内部"):
            continue
        if t in {"JGJ", "SAC", "CN", "SG", "DUAL"}:
            continue
        inbound = "TBD"
        outbound = "TBD"
        m = _RES_QTY.search(t)
        qty = f"{m.group('qty')}{m.group('unit')}" if m else ""
        name = t
        if m:
            name = (t[: m.start()] + t[m.end() :]).strip(" ，,;；") or t
        for key in ("入库", "进场", "出库", "领料", "盘点", "实存"):
            name = name.replace(key, "")
        name = re.sub(r"\s+", " ", name).strip() or t[:80]
        if len(name) > 80:
            name = name[:80]
        if "出库" in t or "领料" in t:
            outbound = qty or "TBD"
        elif "入库" in t or "进场" in t:
            inbound = qty or "TBD"
        elif qty:
            inbound = qty
        rows.append((name, inbound, outbound))
    return rows


def _warehouse_md(text: str) -> str:
    blob = text or ""
    zone = _mix_zone(blob)
    rows = _parse_wh_rows(blob)
    has_count = any(k in blob for k in ("盘点", "实存"))
    if not rows:
        short = (
            "| 物资 | 入库 | 出库 | 结存 | 备注 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 待填物资 | TBD | TBD | TBD | 待填 |\n"
        )
        full = (
            "| 物资 | 规格批次 | 单位 | 期初 | 入库 | 出库 | 账面结存 | 盘点实存 | 差异 | 来源单据号 | 单价 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 待填物资 | 待填 | 待填 | TBD | TBD | TBD | TBD | TBD | TBD | 待填 | TBD |\n"
        )
    else:
        short = (
            "| 物资 | 入库 | 出库 | 结存 | 备注 |\n"
            "| --- | --- | --- | --- | --- |\n"
            + "".join(f"| {n} | {inn} | {out} | TBD | 待填 |\n" for n, inn, out in rows)
        )
        full = (
            "| 物资 | 规格批次 | 单位 | 期初 | 入库 | 出库 | 账面结存 | 盘点实存 | 差异 | 来源单据号 | 单价 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| {n} | 待填 | 待填 | TBD | {inn} | {out} | TBD | TBD | TBD | 待填 | TBD |\n"
                for n, inn, out in rows
            )
        )
    count_note = (
        "有盘点栏。账、卡、物三栏和差异原因待现场填写。未签字确认不得向现场材料提供盈亏数。"
        if has_count
        else "[A001] 无盘点不编盈亏。"
    )
    lines = [
        "# 收发存台账口径（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "内部讨论，不替代正式入库单签认，不替代财务记账，不给材料合格结论。",
        "",
        f"- 辖区：{zone}",
        "",
        "## 用户原文",
        "",
        blob.strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_WH_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 1:
            lines.append("内部讨论。不替代正式入库单签认，不替代财务记账，不给材料合格结论。")
        elif i == 2:
            lines.append(
                "合格区、待检区、不合格隔离区分开。甲指、甲限、自采分堆分账。"
                "危险品单独库位。堆码上盖下垫，留通道。本岗不编间距米数。"
            )
        elif i == 3:
            lines.append(
                "对照采购订单或送货单核名称、规格、数量、批次、外观。"
                "需复试的材料进待检区，试验报告未出不得当作合格料发放。"
                "实收与应收差异记数量，不涂改凑平。"
            )
        elif i == 4:
            lines.append("每垛标明名称、规格、批次、进场日期、状态（合格 / 待检 / 不合格）。不擅自报废数字。")
        elif i == 5:
            lines.append("必须凭限额领料单。无单不发料。超限额走追加审批，不口头超发。")
        elif i == 6:
            lines.append(count_note)
            lines.append("")
            lines.append("至少月清。账物不符先记差异，禁止改台账凑数。[A001] 无盘点不编盈亏。")
        elif i == 7:
            lines.append(short)
            lines.append("")
            lines.append(full)
            lines.append("")
            lines.append("有数只抄用户原文。无数 TBD。单价无询价或合同价则 TBD。FIFO 不是法定检定周期。")
        elif i == 8:
            lines.append(
                "| 物资 | 入库 | 领用 | 退回 | 结存 | 双人复核 |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| 待填 | TBD | TBD | TBD | TBD | 待填 |"
            )
            lines.append("")
            lines.append("消防间距和存储限量以用户平面和安质环要求为准，本岗不编间距米数。")
        else:
            lines.append(
                "不把待检料写成已合格。不给复试合格结论。"
                "不编定额章节和综合单价。塔吊证件交设备管理岗。"
            )
        lines.append("")
    if zone in ("SG", "DUAL"):
        lines.append("SG：Factory Notification 不是损耗公式。")
    if zone in ("CN", "DUAL"):
        lines.append("CN：收发存台账不是特种设备检定周期。")
    lines.append("")
    return "\n".join(lines)


def _dispatch_daily_md(text: str) -> str:
    jobs = _copy_sensitive_jobs(text)
    sensitive = (
        "\n".join(f"- {j}（只列名称；判定交 method-hazard）" for j in jobs)
        if jobs
        else "- （本轮用户未点名敏感作业。判定仍交 method-hazard，本岗不判危大。）"
    )
    lines = [
        "# 调度日报草稿（AI）",
        "",
        DISCLAIMER,
        "",
        "不是调度令、停复工令或工期承诺。缺数 [A001]。本日报不是开工许可。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_DISPATCH_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 2:
            lines.append(DISCLAIMER)
        elif i == 4:
            lines.append((text or "").strip()[:200] or "待填。[A001]")
        elif i == 9:
            lines.append(sensitive)
            lines.append("")
            lines.append("敏感作业只列名称与时段。是否危大、要否 PTW 交 method-hazard。本岗不签发。")
        else:
            lines.append("待按现场记录填写。[A001] 不编产量、工日、台班。")
        lines.append("")
    lines.append("CN：调度日报不是危大文件。SG：BCA construction site records 只写标题。")
    lines.append("")
    return "\n".join(lines)


def _try_fill_scheme_docx(out_dir: Path, project: str) -> Dict[str, Any]:
    """T005: attempt skill fill_scheme_docx; fail → docx_pending."""
    scripts = _ROOT / "skills" / "civil-buddy" / "scripts"
    fill_py = scripts / "fill_scheme_template.py"
    scan_py = scripts / "scan_forbidden_inventions.py"
    template = _ROOT / "skills" / "civil-buddy" / "references" / "templates" / "scheme-cn-a4.docx"
    draft = out_dir / "construction__scheme_draft.md"
    if not fill_py.is_file() or not template.is_file() or not draft.is_file():
        return {"docx_pending": True}
    assumptions = out_dir / "assumptions.md"
    citations = out_dir / "citations.md"
    if not assumptions.is_file():
        guarded_write_text(assumptions, "# 假设\n\n- [A001] 用户未提供的尺寸、荷载一律待填。\n")
    if not citations.is_file():
        guarded_write_text(
            citations,
            "# 已核实\n\n（无）\n\n# 未核实 / UNSPECIFIED\n\n未抽出规范原文。\n",
        )
    docx = out_dir / "专项施工方案-AI草稿.docx"
    cmd = [
        sys.executable,
        str(fill_py),
        "--template",
        str(template),
        "--draft",
        str(draft),
        "--assumptions",
        str(assumptions),
        "--citations",
        str(citations),
        "--jurisdiction",
        "SG",
        "--stamp",
        "AI-DRAFT",
        "--project-name",
        (project or "未命名工程")[:80],
        "--short-name",
        (project or "工程")[:12],
        "--out",
        str(docx),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(scripts),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"docx_pending": True}
    if proc.returncode != 0 or not docx.is_file():
        return {"docx_pending": True}
    if scan_py.is_file():
        try:
            scan = subprocess.run(
                [
                    sys.executable,
                    str(scan_py),
                    "--draft",
                    str(draft),
                    "--docx",
                    str(docx),
                    "--citations",
                    str(citations),
                    "--jurisdiction",
                    "SG",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=str(scripts),
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"docx_pending": True, "docx": str(docx)}
        if scan.returncode != 0:
            return {
                "docx_pending": True,
                "docx": str(docx),
                "p0_reject_scan": {"hits": (scan.stdout or scan.stderr or "")[:400]},
            }
    return {"docx_pending": False, "docx": str(docx)}


def _construction_eleven(text: str) -> str:
    lines = [
        "# 专项施工方案讨论提纲（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "不是法定专项方案，不是签认件。缺数 [A001]。条款 UNSPECIFIED。辖区：SG。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SCHEME_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 2:
            lines.append(DISCLAIMER)
        elif i == 10:
            lines.append("验收结论待持证人员。本页不给合格结论。")
        else:
            lines.append("待按项目 pack / 图纸填写。[A001]")
        lines.append("")
    return "\n".join(lines)


_COVERED = frozenset({"covered", "ok", "done"})
_OPEN = frozenset({"gap", "pending", "missing", "uncovered", "open", "partial", "human_required", "review"})


def _compliance_gaps_md(handoff: Optional[Dict[str, Any]], matrix: Optional[Dict[str, Any]]) -> str:
    rows = (matrix or {}).get("rows") or []
    responded: List[str] = []
    unresponded: List[str] = []
    absent: List[str] = []
    if not rows and not handoff:
        absent.append("本会话无 tender.handoff.json，招标未提供可对照正文。")
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or r.get("exact_text") or r.get("req_id") or "").strip()
        if not title:
            continue
        st = str(r.get("status") or "")
        line = title[:180]
        if st in _COVERED:
            responded.append(line)
        else:
            unresponded.append(line)
    if handoff and not rows:
        for key, label in (("star_items", "★项"), ("scoring_points", "评分点"), ("specials", "专项")):
            items = handoff.get(key) or []
            for it in items:
                text = str((it or {}).get("text") or "")[:180]
                if text:
                    unresponded.append(f"{label}：{text}")
        if not (handoff.get("scoring_points") or handoff.get("star_items") or handoff.get("specials")):
            absent.append("交接在，但未抽出评分点/★/专项；招标未提供这些栏位的正文。")
    lines = [
        "# 废标检查岗 · 三列对照",
        "",
        DISCLAIMER,
        "",
        "不代判废标。须持证人员按招标文件确认。submit_blocked=true。",
        "",
        "## 已响应",
        "",
    ]
    lines.extend([f"- {x}" for x in responded] or ["- （空）"])
    lines.extend(["", "## 未响应", ""])
    lines.extend([f"- {x}" for x in unresponded] or ["- （空）"])
    lines.extend(["", "## 招标未提供", ""])
    lines.extend([f"- {x}" for x in absent] or ["- （本轮无「招标未提供」栏）"])
    lines.extend(["", "条款号 UNSPECIFIED。不判定可投标。", ""])
    return "\n".join(lines)


def _draft_markdown(expert: ExpertRec, tool: str, text: str) -> str:
    return (
        f"# {expert.name} · {tool}\n\n{DISCLAIMER}\n\n"
        f"- 专家：{expert.id}\n- 独有工具：{tool}\n- 产出口径：{expert.delivers}\n"
        f"- 缺的数字 [A001] / UNSPECIFIED\n\n"
        f"## 用户原文\n\n{text.strip() or '（未提供）'}\n\n"
        f"## 草稿\n\n按本岗独有工具出内部讨论提纲。规范只写全名，条款 UNSPECIFIED。"
        f"不是签认件，不判定可投标，不判定可以开工。\n"
    )


def _run_exclusive(
    expert: ExpertRec,
    text: str,
    *,
    confirm_ok: bool,
    session_id: str,
    packing_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tools = _write_tools(expert)
    if expert.risk == "high" and not confirm_ok:
        return {
            "wrote": False,
            "hitl_pending": True,
            "files": [],
            "tools_run": [],
            "reply": f"高风险岗 {expert.name} 写盘须确认句「{CONFIRM}」。本轮未写盘。",
            "submit_blocked": True,
        }
    out_dir = _OUT / session_id / expert.id
    out_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, str]] = []
    ran: List[str] = []

    if expert.id == "bid-parse":
        from packing_assistant.runtime.session_handoff import save_handoff
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        pipe = run_tender_pipeline(text, source="expert-turn", project_name=expert.name)
        path = out_dir / "bid-parse__extract.md"
        guarded_write_text(path, str(pipe.get("extract_table_markdown") or _draft_markdown(expert, "bid-parse__extract", text)))
        files.append({"name": path.name, "path": str(path), "tool": "bid-parse__extract"})
        ran.append("bid-parse__extract")
        ho = pipe.get("handoff") if isinstance(pipe.get("handoff"), dict) else {}
        hp = save_handoff(session_id, ho)
        if hp:
            files.append({"name": hp.name, "path": str(hp), "tool": "tender.handoff"})
            ran.append("tender.handoff")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已按招标解析岗抽出表，并落下 tender.handoff.json 供后岗读。仍是 AI 草稿，submit_blocked=true。",
            "submit_blocked": True,
            "matrix": pipe.get("matrix"),
            "handoff": pipe.get("handoff"),
            "review": pipe.get("review"),
            "submit_block_reason": pipe.get("submit_block_reason"),
        }

    if expert.id == "bid-compliance":
        from packing_assistant.runtime.session_handoff import load_handoff, save_handoff
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        ho = load_handoff(session_id)
        matrix = None
        if text and len(text.strip()) > 40:
            pipe = run_tender_pipeline(text, source="expert-compliance", project_name=expert.name)
            matrix = pipe.get("matrix") if isinstance(pipe.get("matrix"), dict) else None
            if isinstance(pipe.get("handoff"), dict) and pipe.get("handoff"):
                ho = pipe["handoff"]
                save_handoff(session_id, ho)
        md = _compliance_gaps_md(ho, matrix)
        path = out_dir / "bid-compliance__gaps.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "bid-compliance__gaps"})
        ran.append("bid-compliance__gaps")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已按交接/矩阵出三列对照。不代判废标。submit_blocked=true。",
            "submit_blocked": True,
            "handoff": ho,
            "matrix": matrix,
        }

    if expert.id == "bid-tech":
        from packing_assistant.runtime.session_handoff import load_handoff, save_handoff
        from packing_assistant.tools.tender_parse import build_tech_outline_from_handoff, run_tender_pipeline

        ho = load_handoff(session_id)
        if (not ho) and text and len(text.strip()) > 40:
            pipe = run_tender_pipeline(text, source="expert-tech", project_name=expert.name)
            if isinstance(pipe.get("handoff"), dict) and pipe.get("handoff"):
                ho = pipe["handoff"]
                save_handoff(session_id, ho)
        outline = build_tech_outline_from_handoff(ho or {}, project_name=expert.name)
        md = str(outline.get("markdown") or "")
        if not outline.get("from_extracted_scores"):
            md += "\n\n原文未检出评分点。禁止套上个项目技术标目录。条款 UNSPECIFIED。\n"
        path = out_dir / "bid-tech__expand.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "bid-tech__expand"})
        ran.append("bid-tech__expand")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": (
                "已按抽出评分点排技术标目录。"
                if outline.get("from_extracted_scores")
                else "未检出评分点，只出待对照前附表，未套上个项目模板。"
            )
            + " 仍是 AI 草稿，submit_blocked=true。",
            "submit_blocked": True,
            "handoff": ho,
            "tech_outline": outline,
        }

    if expert.id == "pack-ship":
        from packing_assistant.runtime.session_packing import load_packing_snapshot
        from packing_assistant.runtime.tool_engine import get_engine

        snap = packing_summary if isinstance(packing_summary, dict) else load_packing_snapshot(session_id)
        connected = bool(snap)
        eng = get_engine()
        health = eng.execute(
            "pack-ship__health",
            {"solver": snap},
            expert_id="pack-ship",
            intent="run",
        )
        listed = eng.execute("pack-ship__list", {}, expert_id="pack-ship", intent="run")
        plan = eng.execute(
            "pack-ship__plan",
            {"solver": snap, "connected": connected, "materials": text},
            expert_id="pack-ship",
            intent="run",
        )
        exported = eng.execute(
            "pack-ship__export",
            {"solver": snap, "connected": connected},
            expert_id="pack-ship",
            intent="run",
        )
        md = str((exported.get("data") or exported).get("markdown") or exported.get("markdown") or "")
        path = out_dir / "pack-ship__export.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "pack-ship__export"})
        ran.extend(["pack-ship__health", "pack-ship__list", "pack-ship__plan", "pack-ship__export"])
        src = "solver" if connected else "disconnected"
        reply = (
            "装柜证据只抄 solver 快照，未重算 xyz。"
            if connected
            else "装柜证据只抄 solver；本轮未接通，utilization/can_fit/mid50/系固待办 为 UNSPECIFIED。"
        )
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": reply,
            "submit_blocked": True,
            "pack_ship": {
                "source": src,
                "health": health,
                "list": (listed.get("data") or listed).get("names") if isinstance(listed.get("data") or listed, dict) else listed.get("names"),
                "plan": plan.get("data") or plan,
                "export": exported.get("data") or exported,
            },
        }

    if expert.id == "method-hazard":
        blob = text or ""
        sg = "JGJ" not in blob and "37 号令" not in blob
        depth = "未提供"
        height = "未提供"
        md = (
            f"# 危大判定书（AI 草稿）\n\n{DISCLAIMER}\n\n"
            f"- 辖区：{'SG' if sg else 'CN'}\n"
            f"- 作业名称：{blob[:80] or '未说明作业'}\n"
            f"- 触发词：临边 / 开挖 / 起重（仅当用户写了才勾）\n"
            f"- 是否危大：信息不足\n"
            f"- 是否可能超规模需论证：信息不足\n"
            f"- 高度 m：{height}\n- 开挖深度 m：{depth}\n"
        )
        if sg:
            md += (
                "- 依据：Workplace Safety and Health Act / WSH (Construction) Regulations 2007 PTW。"
                "不套用中国危大工程规定。\n"
                "- 建议下一步：交施工方案专家出讨论提纲。本岗不签发 PTW。\n"
            )
        else:
            md += (
                "- 依据：住建部令第 37 号要点 + 用户尺寸（无尺寸则信息不足）。\n"
                "- 建议下一步：交施工方案专家出讨论提纲。\n"
            )
        md += "\n本岗不签发、不给开工许可。条款 UNSPECIFIED。\n"
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "method-hazard__judge.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "method-hazard__judge_hazard"})
        ran.append("method-hazard__judge_hazard")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出判定讨论卡。不是签发件，submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "finance-tax":
        md = (
            f"# 税务日历/检查表（AI 草稿）\n\n{DISCLAIMER}\n\n"
            "| 税种 | 申报期 | 税额 |\n| --- | --- | --- |\n"
            "| GST（SG） | （空栏，待按 IRAS F5 当期） | 待填 |\n"
            "| 企业所得税 | （空栏） | 待填 |\n\n"
            "IRAS Current GST rates 页述现行标准税率 **9%**。税额待持证办税人员算。"
            "禁止把 7%/8% 写成现行税率。不是税务意见书。\n"
        )
        path = out_dir / "finance-tax__calendar.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "finance-tax__calendar"})
        ran.append("finance-tax__calendar")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出税务日历草稿。页述 9%。税额待填。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "survey":
        md = _survey_record_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "survey__record.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "survey__record"})
        ran.append("survey__record")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出测量记录草稿。只抄已给点号。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "dispatch":
        md = _dispatch_daily_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "dispatch__daily.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "dispatch__daily"})
        ran.append("dispatch__daily")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出调度日报草稿。敏感作业交 method-hazard。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "variation":
        md = _variation_form_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "variation__form.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "variation__form"})
        ran.append("variation__form")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出变更签证草稿。金额 TBD。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "claim":
        md = _claim_notice_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "claim__notice.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "claim__notice"})
        ran.append("claim__notice")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出索赔意向草稿。条款原文待贴。工期金额 TBD。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "subcontract":
        md = _subcontract_sheet_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "subcontract__sheet.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "subcontract__sheet"})
        ran.append("subcontract__sheet")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出分包结算表头。无总包/业主确认金额 TBD。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "interim":
        md = _interim_measure_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "interim__measure.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "interim__measure"})
        ran.append("interim__measure")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出验工计价草稿。监理审/业主核空栏。不编应付合价。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "plan-master":
        md = _plan_master_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "plan-master__network.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "plan-master__network"})
        ran.append("plan-master__network")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出总控计划草稿。关键线路=待计算。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "plan-lookahead":
        md = _plan_lookahead_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "plan-lookahead__week.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "plan-lookahead__week"})
        ran.append("plan-lookahead__week")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出四周滚动草稿。制约未清不得写入本周承诺。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "plan-resource":
        md = _plan_resource_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "plan-resource__peak.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "plan-resource__peak"})
        ran.append("plan-resource__peak")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出资源负荷三表。数量待填。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "lab-mix":
        md = _lab_mix_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "lab-mix__report.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "lab-mix__report"})
        ran.append("lab-mix__report")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出配比报告提纲。无试验数据不给施工配合比。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "lab-sample":
        md = _lab_sample_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "lab-sample__list.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "lab-sample__list"})
        ran.append("lab-sample__list")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出取样送检清单。见证人空栏。组数 [A001]。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "lab-record":
        md = _lab_record_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "lab-record__ledger.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "lab-record__ledger"})
        ran.append("lab-record__ledger")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出试验台账骨架。报告编号待核。结论待填。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "supervision":
        md = _supervision_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "supervision__reply.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "supervision__reply"})
        ran.append("supervision__reply")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出监理通知回复草稿。暂停/复工只出目录。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "safety-brief":
        md = _safety_brief_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "safety-brief__talk.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "safety-brief__talk"})
        ran.append("safety-brief__talk")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出安全交底草稿。毫米/电话 [A001]。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "quality":
        md = _quality_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "quality__lot.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "quality__lot"})
        ran.append("quality__lot")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出质量检查表。主控/一般/隐蔽结果=未检。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "env":
        md = _env_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "env__list.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "env__list"})
        ran.append("env__list")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出环保文明清单。五行限值 UNSPECIFIED。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "emergency":
        md = _emergency_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "emergency__plan.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "emergency__plan"})
        ran.append("emergency__plan")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出应急预案提纲。电话医院待填。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "equip":
        md = _equip_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "equip__ledger.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "equip__ledger"})
        ran.append("equip__ledger")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出设备台账。只抄用户设备名与已给证件。无证件不编进场结论。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "warehouse":
        md = _warehouse_md(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
            }
        path = out_dir / "warehouse__log.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "warehouse__log"})
        ran.append("warehouse__log")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出收发存台账。有数只抄。无盘点不编盈亏。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "cost":
        md = (
            f"# 工程量拆分表（AI 草稿）\n\n{DISCLAIMER}\n\n"
            "| 分项 | 单位 | 数量 | 综合单价 | 合价 | 来源 |\n| --- | --- | --- | --- | --- | --- |\n"
            f"| {text.strip()[:80] or '未提供分项 [A001]'} | TBD | TBD | UNSPECIFIED | UNSPECIFIED | 用户表 |\n\n"
            "无清单/报价不编单价。条款 UNSPECIFIED。\n"
        )
        path = out_dir / "cost__takeoff.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "cost__takeoff"})
        ran.append("cost__takeoff")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出工程量拆分表。单价 UNSPECIFIED。submit_blocked=true。",
            "submit_blocked": True,
        }

    if expert.id == "construction":
        md = _construction_eleven(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
                "p0_reject_scan": {"hits": hits},
            }
        path = out_dir / "construction__scheme_draft.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "construction__scheme_draft"})
        ran.append("construction__scheme_draft")
        fill = _try_fill_scheme_docx(out_dir, (text or "").strip()[:40] or "未命名工程")
        pending = bool(fill.get("docx_pending", True))
        if fill.get("docx"):
            dp = Path(str(fill["docx"]))
            files.append({"name": dp.name, "path": str(dp), "tool": "construction__fill_scheme_docx"})
            ran.append("construction__fill_scheme_docx")
        reply = (
            "已出十一章讨论提纲并填 docx。不是法定专项，submit_blocked=true。"
            if not pending
            else "已出十一章讨论提纲（docx_pending）。不是法定专项，submit_blocked=true。"
        )
        out: Dict[str, Any] = {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": reply,
            "submit_blocked": True,
            "docx_pending": pending,
        }
        if fill.get("p0_reject_scan"):
            out["p0_reject_scan"] = fill["p0_reject_scan"]
        return out

    if not tools:
        tools = [f"{expert.id}__draft"]
    for tool in tools:
        md = _draft_markdown(expert, tool, text)
        path = out_dir / f"{tool}.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": tool})
        ran.append(tool)
    return {
        "wrote": True,
        "hitl_pending": False,
        "files": files,
        "tools_run": ran,
        "reply": f"{expert.name} 已出内部讨论草稿（{', '.join(ran)}）。不可递交。",
        "submit_blocked": True,
    }


def run_named_exclusive(name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ToolEngine entry: exclusive name → that expert's writer. HITL stays here."""
    from packing_assistant.expert_roster import exclusive_owner, get_expert

    args = args or {}
    owner = exclusive_owner(name)
    exp = get_expert(owner or "")
    if not exp:
        return {
            "ok": False,
            "wrote": False,
            "error_code": "invalid_args",
            "reply": f"未知独有工具 {name}",
            "submit_blocked": True,
            "files": [],
            "tools_run": [],
        }
    bits = [str(args.get("text") or args.get("task") or "").strip()]
    for k in (
        "window",
        "constraints",
        "works",
        "jobs",
        "milestones",
        "trades",
        "labor",
        "plant",
        "equipment",
        "material",
        "materials",
        "items",
        "package",
        "samples",
        "notice",
        "reply_points",
        "work_item",
        "hazards",
        "controls",
        "inspection_lot",
        "site",
        "issues",
        "scenario",
        "certs",
        "item",
        "note",
    ):
        v = args.get(k)
        if v:
            bits.append(str(v).strip())
    if args.get("has_trial_data") is True:
        bits.append("已有试验数据")
    elif args.get("has_trial_data") is False:
        bits.append("无试验数据")
    return _run_exclusive(
        exp,
        "\n".join(b for b in bits if b),
        confirm_ok=bool(args.get("confirm_ok") or args.get("p0_confirmed")),
        session_id=str(args.get("session_id") or "tool"),
        packing_summary=args.get("packing_summary") if isinstance(args.get("packing_summary"), dict) else None,
    )


def run_expert_turn(
    text: str,
    expert_id: str,
    *,
    confirm_ok: bool = False,
    session_id: str = "",
    force_intent: Optional[str] = None,
    packing_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    exp = get_expert(expert_id)
    if not exp:
        return {
            "ok": False,
            "schema": "civil.expert_turn.v1",
            "error": f"unknown expert: {expert_id}",
            "intent": "chat",
            "wrote": False,
        }
    intent = force_intent if force_intent in {"chat", "run", "both"} else understand(text)
    from packing_assistant.runtime.scheduler import get_scheduler

    sid = session_id or f"turn-{uuid4().hex[:8]}"
    from packing_assistant.runtime.memory import assemble_context, prompt_prefix

    ctx = assemble_context(sid, text=text, p0_confirmed=confirm_ok)
    confirm_ok = bool(confirm_ok) or bool(ctx.get("p0_confirmed"))
    ctx_prefix = prompt_prefix(ctx)
    sched = get_scheduler()
    run = sched.create_run(sid, expert_id=exp.id, intent=intent)
    sched.transition(run, "planning")
    base: Dict[str, Any] = {
        "ok": True,
        "schema": "civil.expert_turn.v1",
        "intent": intent,
        "expert_id": exp.id,
        "expert_name": exp.name,
        "category": exp.category,
        "exclusive": list(exp.exclusive),
        "risk": exp.risk,
        "wrote": False,
        "hitl_pending": False,
        "files": [],
        "tools_run": [],
        "reply": "",
        "submit_blocked": True,
        "n_experts": len(list_experts()),
        "run_id": run.run_id,
        "state": run.state,
        "session_id": sid,
        "context": {
            "jurisdiction": ctx.get("jurisdiction"),
            "project": ctx.get("project"),
            "p0_confirmed": ctx.get("p0_confirmed"),
            "compressed": ctx.get("compressed"),
            "has_handoff": ctx.get("has_handoff"),
            "has_packing": ctx.get("has_packing"),
        },
    }
    if intent == "chat":
        sched.transition(run, "done")
        sched.release(sid)
        body = explain_expert(exp, text)
        base["reply"] = f"{ctx_prefix}\n{body}".strip() if ctx_prefix else body
        base["state"] = run.state
        return base
    ran = _run_exclusive(
        exp, text, confirm_ok=confirm_ok, session_id=sid, packing_summary=packing_summary
    )
    if ran.get("hitl_pending"):
        sched.transition(run, "waiting_hitl")
    else:
        sched.transition(run, "acting")
        if run.cancelled:
            ran["wrote"] = False
            ran["files"] = []
            ran["reply"] = "run cancelled"
        else:
            sched.transition(run, "done")
    sched.release(sid)
    if intent == "both" and not ran.get("hitl_pending"):
        explained = explain_expert(exp, text)
        if ctx_prefix:
            explained = f"{ctx_prefix}\n{explained}"
        ran["reply"] = explained + "\n\n" + str(ran.get("reply") or "")
    base.update(ran)
    base["session_id"] = sid
    base["run_id"] = run.run_id
    base["state"] = run.state
    return base
