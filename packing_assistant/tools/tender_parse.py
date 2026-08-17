"""投标文件要点抽取（MVP）：规则+关键词，不做幻觉写标。

schema: tender.parse.v1 / checklist.v1 / response_matrix.v1
合规矩阵字段对齐业界实践：requirement_ref · owner · risk · status · evidence
（DeepRFP / AutoRFP / 知乎「响应矩阵中枢」等公开材料）
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# (id, category, patterns, title, default_owner, risk)
_RULES: List[tuple] = [
    (
        "pkg_standard",
        "packaging",
        [r"包装", r"木箱", r"铁架", r"装箱", r"防护", r"防潮", r"packing", r"crate"],
        "包装/装箱要求",
        "delivery",
        "medium",
    ),
    (
        "transport_container",
        "transport",
        [r"集装箱", r"柜型", r"40HQ", r"40GP", r"20GP", r"整柜", r"拼柜", r"海运", r"container"],
        "集装箱/运输方式",
        "delivery",
        "high",
    ),
    (
        "weight_limit",
        "transport",
        [r"货载", r"限重", r"吨位", r"payload", r"超重", r"最大重量"],
        "重量/货载限制",
        "delivery",
        "high",
    ),
    (
        "overlength",
        "transport",
        [r"超长", r"超限", r"异形", r"框架柜", r"开顶", r"OT\b"],
        "超长/异形运输",
        "delivery",
        "high",
    ),
    (
        "cog_lashing",
        "transport",
        [r"重心", r"绑扎", r"加固", r"系固", r"CTU", r"lashing"],
        "重心/绑扎/系固",
        "delivery",
        "high",
    ),
    (
        "delivery_time",
        "schedule",
        [r"交货期", r"工期", r"到货", r"交货时间", r"calendar day", r"工作日", r"日历天"],
        "交货期/工期",
        "pm",
        "medium",
    ),
    (
        "qualification",
        "qualification",
        [r"资质", r"业绩", r"类似项目", r"注册资金", r"许可证", r"ISO"],
        "资格/业绩",
        "commercial",
        "critical",
    ),
    (
        "reject_item",
        "reject",
        [r"废标", r"否决", r"无效投标", r"实质性响应", r"重大偏差"],
        "废标/实质性响应",
        "legal",
        "critical",
    ),
    (
        "insurance_vgm",
        "compliance",
        [r"保险", r"VGM", r"提单", r"报关", r"原产地"],
        "保险/单证/VGM",
        "commercial",
        "medium",
    ),
    (
        "scoring",
        "scoring",
        [r"评分", r"分值", r"技术分", r"商务分", r"评标办法"],
        "评分办法",
        "proposal",
        "medium",
    ),
]


def _line_ref(idx: int) -> str:
    return f"L{idx + 1}"


def parse_tender_text(text: str, *, source: str = "text") -> Dict[str, Any]:
    """从纯文本招标节选抽取 requirements 列表（含 ref/owner/risk）。"""
    raw = (text or "").strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    blob = "\n".join(lines)
    requirements: List[Dict[str, Any]] = []
    seen = set()

    for rid, cat, patterns, title, owner, risk in _RULES:
        hits: List[str] = []
        refs: List[str] = []
        for i, ln in enumerate(lines):
            for pat in patterns:
                if re.search(pat, ln, flags=re.I):
                    hits.append(ln)
                    refs.append(_line_ref(i))
                    break
        if not hits:
            continue
        if rid in seen:
            continue
        seen.add(rid)
        must = cat in (
            "reject",
            "qualification",
            "transport",
            "packaging",
            "schedule",
        )
        # Inventive/AutoRFP: requirement type = mandatory | evaluated | administrative | informational
        if cat in ("reject", "qualification"):
            req_type = "mandatory"
        elif cat in ("transport", "packaging", "schedule", "compliance"):
            req_type = "mandatory" if must else "evaluated"
        elif cat == "scoring":
            req_type = "evaluated"
        else:
            req_type = "informational"
        requirements.append(
            {
                "id": rid,
                "category": cat,
                "title": title,
                "snippets": hits[:5],
                "requirement_ref": ",".join(refs[:5]),
                "owner": owner,
                "risk": risk,
                "requirement_type": req_type,
                "priority": (
                    "high"
                    if cat in ("reject", "qualification", "transport", "packaging")
                    or risk == "critical"
                    else "medium"
                ),
                "must_respond": must,
            }
        )

    return {
        "schema": "tender.parse.v1",
        "tool": "tender.parse",
        "source": source,
        "n_lines": len(lines),
        "n_chars": len(blob),
        "requirements": requirements,
        "summary": {
            "n_requirements": len(requirements),
            "categories": sorted({r["category"] for r in requirements}),
            "must_respond_n": sum(1 for r in requirements if r.get("must_respond")),
            "critical_n": sum(1 for r in requirements if r.get("risk") == "critical"),
            "owners": sorted({str(r.get("owner")) for r in requirements if r.get("owner")}),
        },
    }


def build_checklist(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成人工勾选清单（owner/risk 透传）。"""
    items = []
    for r in requirements or []:
        items.append(
            {
                "req_id": r.get("id"),
                "title": r.get("title"),
                "category": r.get("category"),
                "requirement_ref": r.get("requirement_ref"),
                "owner": r.get("owner") or "unassigned",
                "risk": r.get("risk") or "medium",
                "requirement_type": r.get("requirement_type") or "informational",
                "must_respond": bool(r.get("must_respond")),
                "status": "pending",
                "evidence": None,
            }
        )
    return {
        "schema": "tender.checklist.v1",
        "tool": "tender.checklist",
        "items": items,
        "n_pending": len(items),
        "n_must": sum(1 for i in items if i.get("must_respond")),
        "n_critical": sum(1 for i in items if i.get("risk") == "critical"),
    }


def build_response_matrix(
    requirements: List[Dict[str, Any]],
    *,
    packing_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """条款 × 证据矩阵（装柜结果可覆盖运输/包装/重心类）。"""
    pack = packing_summary or {}
    can_fit = pack.get("can_fit")
    used = pack.get("containers_used")
    n0 = pack.get("n0")
    ship_ok = pack.get("ship_ok")
    mid50 = pack.get("mid50")

    rows = []
    for r in requirements or []:
        cat = r.get("category")
        rid = r.get("id")
        status = "pending"
        evidence = None
        if cat in ("transport", "packaging") and can_fit is not None:
            status = "covered" if can_fit is True else "gap"
            evidence = {
                "type": "packing",
                "can_fit": can_fit,
                "containers_used": used,
                "n0": n0,
                "ship_ok": ship_ok,
                "mid50": mid50,
            }
            # 重心条款：需要 mid50 证据
            if rid == "cog_lashing":
                if mid50 is not None and float(mid50) >= 0.55 and can_fit is True:
                    status = "covered"
                elif can_fit is True:
                    status = "partial"
                    evidence = {
                        **(evidence or {}),
                        "note": "装柜可 fit，但 mid50 未达标或未提供",
                    }
        elif cat == "qualification":
            status = "human_required"
            evidence = {"type": "manual", "note": "资质/业绩须人工提供"}
        elif cat == "reject":
            status = "review"
            evidence = {"type": "manual", "note": "废标项须人工核对"}
        elif cat == "scoring":
            status = "human_required"
            evidence = {"type": "manual", "note": "评分策略由标书负责人确认"}
        elif cat == "schedule":
            status = "human_required"
            evidence = {"type": "manual", "note": "交货期须项目经理确认"}
        elif cat == "compliance":
            status = "human_required"
            evidence = {"type": "manual", "note": "VGM/保险/单证须商务确认"}
        rows.append(
            {
                "req_id": rid,
                "title": r.get("title"),
                "category": cat,
                "requirement_ref": r.get("requirement_ref"),
                "owner": r.get("owner") or "unassigned",
                "risk": r.get("risk") or "medium",
                "requirement_type": r.get("requirement_type") or "informational",
                "status": status,
                # 业界合规矩阵：应答落点（提案章节），便于评审对照
                "proposal_location": _proposal_location(cat, rid),
                "compliance_label": _compliance_label(status),
                "knowledge_ref": _knowledge_ref(cat, rid),
                "evidence": evidence,
                "snippets": r.get("snippets") or [],
            }
        )

    summary = {
        "n": len(rows),
        "covered": sum(1 for x in rows if x["status"] == "covered"),
        "partial": sum(1 for x in rows if x["status"] == "partial"),
        "pending": sum(1 for x in rows if x["status"] == "pending"),
        "human_required": sum(1 for x in rows if x["status"] == "human_required"),
        "gap": sum(1 for x in rows if x["status"] == "gap"),
        "review": sum(1 for x in rows if x["status"] == "review"),
        "by_owner": _count_by(rows, "owner"),
        "by_risk": _count_by(rows, "risk"),
    }
    summary["readiness_score"] = _readiness_score(summary)
    return {
        "schema": "tender.response_matrix.v1",
        "tool": "tender.response_matrix",
        "rows": rows,
        "summary": summary,
    }


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "unknown")
        out[k] = out.get(k, 0) + 1
    return out


def _proposal_location(category: Optional[str], req_id: Optional[str]) -> str:
    """默认应答落点（可被人工改写）。"""
    m = {
        "packaging": "技术标 · 包装与装箱方案",
        "transport": "技术标 · 运输与装柜方案",
        "qualification": "商务标 · 资格与业绩附件",
        "reject": "标书响应声明 / 偏离表",
        "schedule": "技术标 · 工期与交付计划",
        "compliance": "商务标 · 单证与合规附件",
        "scoring": "标书编制说明 / 评分对照表",
    }
    if req_id == "cog_lashing":
        return "技术标 · 装柜重心与系固说明（CTU）"
    return m.get(str(category or ""), "技术标 · 通用响应")


def _compliance_label(status: Optional[str]) -> str:
    """AutoRFP-style compliance wording for matrix export / UI."""
    m = {
        "covered": "compliant",
        "partial": "partially_compliant",
        "gap": "non_compliant",
        "human_required": "needs_sme",
        "review": "pending_review",
        "pending": "not_started",
    }
    return m.get(str(status or ""), "not_started")


def _knowledge_ref(category: Optional[str], req_id: Optional[str]) -> Optional[str]:
    """Map clause to in-repo tender-delivery knowledge (M4 light binding)."""
    cat = str(category or "")
    rid = str(req_id or "")
    if rid == "cog_lashing" or cat in ("transport", "packaging"):
        return "knowledge_base/08_tender_delivery/rules/transport_packaging_redlines.md"
    if cat in ("qualification", "reject", "scoring"):
        return "knowledge_base/08_tender_delivery/strategies/facade_bid_response.md"
    if cat in ("schedule", "compliance"):
        return "knowledge_base/08_tender_delivery/trajectories/TD1_tender_to_pack.md"
    return "knowledge_base/08_tender_delivery/README.md"


def _readiness_score(summary: Dict[str, Any]) -> float:
    """0–1：covered 加权，gap/review 重罚（非官方分，仅内部就绪度）。"""
    n = int(summary.get("n") or 0)
    if n <= 0:
        return 0.0
    covered = int(summary.get("covered") or 0)
    partial = int(summary.get("partial") or 0)
    gap = int(summary.get("gap") or 0)
    review = int(summary.get("review") or 0)
    human = int(summary.get("human_required") or 0)
    raw = (covered + 0.5 * partial + 0.25 * human - 0.75 * gap - 0.35 * review) / n
    return float(max(0.0, min(1.0, round(raw, 3))))


def matrix_to_markdown(matrix: Dict[str, Any]) -> str:
    """导出合规矩阵 Markdown（评委/客户可读，非原始 JSON）。"""
    rows = list((matrix or {}).get("rows") or [])
    sm = (matrix or {}).get("summary") or {}
    lines = [
        "# 合规响应矩阵",
        "",
        f"- 条款数: {sm.get('n', len(rows))}",
        f"- covered: {sm.get('covered', 0)} · partial: {sm.get('partial', 0)} · gap: {sm.get('gap', 0)}",
        f"- readiness: {sm.get('readiness_score', '—')}",
        "",
        "| 条款 | 类型 | 状态 | 合规 | 负责人 | 风险 | 应答落点 | 引用 |",
        "|------|------|------|------|--------|------|----------|------|",
    ]
    for r in rows:
        title = str(r.get("title") or r.get("req_id") or "").replace("|", "/")
        loc = str(r.get("proposal_location") or "").replace("|", "/")
        ref = str(r.get("requirement_ref") or "—").replace("|", "/")
        rtype = str(r.get("requirement_type") or "—").replace("|", "/")
        clabel = str(r.get("compliance_label") or _compliance_label(r.get("status"))).replace(
            "|", "/"
        )
        lines.append(
            f"| {title} | {rtype} | {r.get('status')} | {clabel} | {r.get('owner')} | {r.get('risk')} | {loc} | {ref} |"
        )
    return "\n".join(lines) + "\n"


def open_actions(matrix: Dict[str, Any]) -> List[Dict[str, Any]]:
    """人仍须处理的条款（HITL 待办，非自动盖章）。"""
    actions: List[Dict[str, Any]] = []
    for r in list((matrix or {}).get("rows") or []):
        st = str(r.get("status") or "")
        if st in ("covered",):
            continue
        actions.append(
            {
                "req_id": r.get("req_id"),
                "title": r.get("title"),
                "status": st,
                "owner": r.get("owner") or "unassigned",
                "risk": r.get("risk") or "medium",
                "proposal_location": r.get("proposal_location"),
                "action": _action_hint(st, r.get("category"), r.get("risk")),
            }
        )
    # critical / gap first
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: (order.get(str(a.get("risk")), 9), str(a.get("status"))))
    return actions


def _action_hint(status: str, category: Optional[str], risk: Optional[str]) -> str:
    if status == "gap":
        return "装柜证据未覆盖：调整方案或写偏离/澄清"
    if status == "partial":
        return "部分证据已有：补齐 mid50/系固说明或人工复核"
    if status == "review":
        return "废标/实质性响应：法务/标书负责人逐条核对"
    if status == "human_required":
        if category == "qualification":
            return "附资质与类似业绩扫描件（人工）"
        if category == "schedule":
            return "项目经理确认交货期与到港节点"
        if category == "compliance":
            return "商务准备 VGM/保险/单证"
        if category == "scoring":
            return "标书编制对照评分点"
        return "人工补充证据后改状态"
    return "待处理"


def build_response_package(
    *,
    matrix: Dict[str, Any],
    packing_summary: Optional[Dict[str, Any]] = None,
    parse_summary: Optional[Dict[str, Any]] = None,
    project_name: str = "幕墙项目投标应答（草稿）",
) -> Dict[str, Any]:
    """一页应答摘要：交付证据 + 矩阵就绪度 + 人工待办（可导出 Markdown）。"""
    sm = (matrix or {}).get("summary") or {}
    pack = packing_summary or {}
    actions = open_actions(matrix)
    md = _compose_package_markdown(
        project_name=project_name,
        pack=pack,
        sm=sm,
        actions=actions,
        matrix=matrix,
        parse_summary=parse_summary,
    )
    return {
        "schema": "tender.response_package.v1",
        "project_name": project_name,
        "open_actions": actions,
        "n_open": len(actions),
        "readiness_score": sm.get("readiness_score"),
        "packing_summary": pack or None,
        "markdown": md,
    }


def _compose_package_markdown(
    *,
    project_name: str,
    pack: Dict[str, Any],
    sm: Dict[str, Any],
    actions: List[Dict[str, Any]],
    matrix: Dict[str, Any],
    parse_summary: Optional[Dict[str, Any]] = None,
) -> str:
    mid = pack.get("mid50") if pack else None
    mid_s = "—"
    if mid is not None:
        try:
            mf = float(mid)
            mid_s = f"{mf * 100:.0f}%" if mf <= 1.0 else f"{mf:.0f}%"
        except (TypeError, ValueError):
            mid_s = str(mid)
    lines = [
        f"# {project_name}",
        "",
        "> 自动生成草稿 · **非**盖章投标文件 · 柜数/坐标/重心来自 tools；资质/价格/授权仅人工。",
        "",
        "## 1. 交付证据（装柜）",
        "",
    ]
    if pack:
        lines += [
            f"- can_fit: **{pack.get('can_fit')}**",
            f"- 柜型 / 使用: {pack.get('container_type') or '—'} · used={pack.get('containers_used')} · N0={pack.get('n0')}",
            f"- ship_ok: **{pack.get('ship_ok')}** · phase: {pack.get('phase') or '—'}",
            f"- mid50（CTU 中段质量）: **{mid_s}**",
            "",
        ]
    else:
        lines += ["- （未跑交付装柜）", ""]
    if parse_summary:
        lines += [
            "## 2. 招标要点摘要",
            "",
            f"- 抽取条款: {parse_summary.get('n_requirements', '—')}",
            f"- 类别: {', '.join(parse_summary.get('categories') or []) or '—'}",
            f"- 必应 / 关键: must={parse_summary.get('must_respond_n', '—')} · critical={parse_summary.get('critical_n', '—')}",
            "",
        ]
        sec_ready = "3"
        sec_todo = "4"
        sec_mx = "5"
    else:
        sec_ready, sec_todo, sec_mx = "2", "3", "4"
    lines += [
        f"## {sec_ready}. 响应就绪度",
        "",
        f"- 条款: {sm.get('n', 0)} · covered: {sm.get('covered', 0)} · partial: {sm.get('partial', 0)}",
        f"- human_required: {sm.get('human_required', 0)} · gap: {sm.get('gap', 0)} · review: {sm.get('review', 0)}",
        f"- readiness_score: **{sm.get('readiness_score', '—')}**",
        "",
        f"## {sec_todo}. 人工待办（按风险）",
        "",
    ]
    if not actions:
        lines.append("- 无未覆盖项（仍须人签商务）")
    else:
        for a in actions:
            lines.append(
                f"- **[{a.get('risk')}]** {a.get('title')} · {a.get('owner')} · `{a.get('status')}` — {a.get('action')}"
            )
    lines += ["", f"## {sec_mx}. 合规矩阵", ""]
    lines.append(matrix_to_markdown(matrix).rstrip())
    lines.append("")
    return "\n".join(lines)


def run_tender_pipeline(
    text: str,
    *,
    packing_summary: Optional[Dict[str, Any]] = None,
    source: str = "text",
    project_name: str = "幕墙项目投标应答（草稿）",
) -> Dict[str, Any]:
    """投标解析 → 清单 → 响应矩阵 → 应答包一站式（可接装柜 summary）。"""
    parsed = parse_tender_text(text, source=source)
    reqs = list(parsed.get("requirements") or [])
    checklist = build_checklist(reqs)
    matrix = build_response_matrix(reqs, packing_summary=packing_summary)
    package = build_response_package(
        matrix=matrix,
        packing_summary=packing_summary,
        parse_summary=parsed.get("summary"),
        project_name=project_name,
    )
    from packing_assistant.bidbook.sg_facade import build_sg_facade_bidbook

    bidbook = build_sg_facade_bidbook(
        tender_text=text,
        parsed=parsed,
        matrix=matrix,
        packing_summary=packing_summary,
        open_actions=package["open_actions"],
    )
    return {
        "schema": "tender.pipeline.v1",
        "product_mainline": "C_tender_delivery",
        "parse": parsed,
        "checklist": checklist,
        "matrix": matrix,
        "matrix_markdown": matrix_to_markdown(matrix),
        "open_actions": package["open_actions"],
        "response_package": package,
        "export_markdown": package["markdown"],
        "bidbook": bidbook,
        "bidbook_markdown": bidbook.get("markdown"),
        "ok": bool(reqs),
    }
