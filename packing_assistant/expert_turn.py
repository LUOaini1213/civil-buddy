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
    return _run_exclusive(
        exp,
        str(args.get("text") or args.get("task") or ""),
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
    }
    if intent == "chat":
        sched.transition(run, "done")
        sched.release(sid)
        base["reply"] = explain_expert(exp, text)
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
        ran["reply"] = explain_expert(exp, text) + "\n\n" + str(ran.get("reply") or "")
    base.update(ran)
    base["session_id"] = sid
    base["run_id"] = run.run_id
    base["state"] = run.state
    return base
