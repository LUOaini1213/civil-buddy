"""投标文件要点抽取（MVP）：规则+关键词，不做幻觉写标。

schema: tender.parse.v1 / checklist.v1 / response_matrix.v1 / handoff.v1
合规矩阵字段对齐业界实践：requirement_ref · owner · risk · status · evidence
（DeepRFP / AutoRFP / 知乎「响应矩阵中枢」等公开材料）

v1.1：条款级行项目（★ / 评分点 / 专项）+ 经营岗交接 handoff + P0 废标扫描。
不编造分值、资质、BCA、天数；只抄原文。
"""

from __future__ import annotations

import re
from pathlib import Path
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


_STAR_RE = re.compile(r"[★☆＊]|不满足即废标|必须满足项")
_SCORE_RE = re.compile(
    r"评分点|评标办法|技术分|商务分|分值|施工组织设计|"
    r"(?:Quality|Price)\s+\d+\s*%|"
    r"\d+\s*分(?!公司)",
    re.I,
)
_SPECIAL_RE = re.compile(
    r"专项(?:方案|施工)?|危大|临边|method statement|working at height",
    re.I,
)
_DAYS_RE = re.compile(
    r"(\d+)\s*(?:个)?\s*(日历天|calendar\s*days?|工作日)",
    re.I,
)
_WORKHEAD_RE = re.compile(r"\bCW0[0-9]\b", re.I)
_ENVELOPE_RE = re.compile(
    r"双信封|两信封|三信封|two[\s-]*envelope|technical and (?:financial|price)|"
    r"技术标与报价分投|暗标",
    re.I,
)
_EBID_RE = re.compile(r"电子标|电子投标|CA\s*锁|投标文件加密|加密递交")
_BOND_RE = re.compile(r"投标保证金|履约保证金|投标保函")
_BOND_AMT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万|万元|元|%|％)")
_EVAL_RE = re.compile(
    r"综合评估法|经评审的最低投标价法|合理低价(?:法)?|Price Quality Method|PQM|QFM|"
    r"Quality Fee Method",
    re.I,
)
_DEADLINE_RE = re.compile(
    r"(提问截止|异议截止|澄清截止|答疑截止|投标截止|递交截止|开标)"
    r"[^\n]{0,48}?"
    r"(\d{4}\s*[-./年]\s*\d{1,2}\s*[-./月]\s*\d{1,2}(?:\s*[日号])?"
    r"(?:\s+\d{1,2}:\d{2})?)",
    re.I,
)


def _is_star_line(ln: str) -> bool:
    return bool(_STAR_RE.search(ln or ""))


def _is_score_line(ln: str) -> bool:
    t = ln or ""
    if "不合格" in t and "分" not in t:
        return False
    return bool(_SCORE_RE.search(t))


def _is_special_line(ln: str) -> bool:
    return bool(_SPECIAL_RE.search(ln or ""))


def _duration_days_from_lines(lines: List[str]) -> Optional[int]:
    """Copy calendar-day counts already in the text. Never invent a period."""
    for ln in lines:
        m = _DAYS_RE.search(ln)
        if m:
            try:
                n = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if 1 <= n <= 3650:
                return n
    return None


def _line_item(
    *,
    rid: str,
    kind: str,
    cat: str,
    title: str,
    line: str,
    idx: int,
    owner: str,
    risk: str,
    req_type: str,
    must: bool,
) -> Dict[str, Any]:
    return {
        "id": rid,
        "item_kind": kind,
        "category": cat,
        "title": title,
        "snippets": [line],
        "exact_text": line,
        "requirement_ref": _line_ref(idx),
        "owner": owner,
        "risk": risk,
        "requirement_type": req_type,
        "priority": "high" if risk in ("critical", "high") else "medium",
        "must_respond": must,
    }


def _extract_line_items(lines: List[str]) -> List[Dict[str, Any]]:
    """One row per ★ / scoring-point / special line (AutoRFP item-level matrix)."""
    items: List[Dict[str, Any]] = []
    seen: set = set()
    units: List[tuple] = []
    for i, ln in enumerate(lines):
        pieces = [p.strip() for p in re.split(r"[。；;]", ln) if p.strip()]
        if not pieces:
            continue
        for p in pieces:
            units.append((i, p))
    for i, ln in units:
        kinds: List[str] = []
        if _is_star_line(ln):
            kinds.append("star")
        if _is_score_line(ln):
            kinds.append("scoring_point")
        if _is_special_line(ln):
            kinds.append("special")
        if _EBID_RE.search(ln or ""):
            kinds.append("ebid")
        if _BOND_RE.search(ln or ""):
            kinds.append("bond")
        # ★ line that is also a special stays one star row; still listed in handoff.specials
        if "star" in kinds and "special" in kinds:
            kinds = [k for k in kinds if k != "special"]
        if "star" in kinds and "scoring_point" in kinds:
            kinds = [k for k in kinds if k != "scoring_point"]
        for kind in kinds:
            key = (kind, ln)
            if key in seen:
                continue
            seen.add(key)
            if kind == "star":
                items.append(
                    _line_item(
                        rid=f"star_{_line_ref(i)}",
                        kind="star",
                        cat="reject",
                        title="★/必须满足项",
                        line=ln,
                        idx=i,
                        owner="legal",
                        risk="critical",
                        req_type="mandatory",
                        must=True,
                    )
                )
            elif kind == "scoring_point":
                items.append(
                    _line_item(
                        rid=f"score_{_line_ref(i)}",
                        kind="scoring_point",
                        cat="scoring",
                        title="评分点",
                        line=ln,
                        idx=i,
                        owner="proposal",
                        risk="medium",
                        req_type="evaluated",
                        must=False,
                    )
                )
            elif kind == "bond":
                items.append(
                    _line_item(
                        rid=f"bond_{_line_ref(i)}",
                        kind="bond",
                        cat="qualification",
                        title="保证金/保函",
                        line=ln,
                        idx=i,
                        owner="commercial",
                        risk="critical",
                        req_type="mandatory",
                        must=True,
                    )
                )
            elif kind == "ebid":
                items.append(
                    _line_item(
                        rid=f"ebid_{_line_ref(i)}",
                        kind="ebid",
                        cat="reject",
                        title="电子标/加密/CA锁",
                        line=ln,
                        idx=i,
                        owner="legal",
                        risk="high",
                        req_type="mandatory",
                        must=True,
                    )
                )
            else:
                items.append(
                    _line_item(
                        rid=f"special_{_line_ref(i)}",
                        kind="special",
                        cat="scoring",
                        title="必须专项/危大",
                        line=ln,
                        idx=i,
                        owner="proposal",
                        risk="high",
                        req_type="mandatory",
                        must=True,
                    )
                )
    return items


def _detect_eval_method(blob: str) -> Optional[str]:
    m = _EVAL_RE.search(blob or "")
    return m.group(0) if m else None


def _detect_envelope(blob: str) -> Optional[str]:
    """Copy envelope scheme from text. None = 招标未写. Never invent 两信封."""
    t = blob or ""
    if re.search(r"三信封|three[\s-]*envelope", t, re.I):
        return "three"
    if re.search(
        r"双信封|两信封|two[\s-]*envelope|技术标与报价分投",
        t,
        re.I,
    ):
        return "two"
    if "暗标" in t:
        return "blind_tech"
    return None


def _extract_deadlines(blob: str) -> List[Dict[str, str]]:
    """Only dated milestones already in the text."""
    out: List[Dict[str, str]] = []
    seen = set()
    for m in _DEADLINE_RE.finditer(blob or ""):
        label = m.group(1)
        when = re.sub(r"\s+", " ", m.group(2)).strip()
        key = (label, when)
        if key in seen:
            continue
        seen.add(key)
        out.append({"label": label, "when": when, "source": "verbatim"})
    return out


def _bond_from_requirements(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Copy bond wording only. Never invent 2% or an account number."""
    bonds = [r for r in requirements if r.get("item_kind") == "bond"]
    amount = None
    account = None
    for r in bonds:
        text = str(r.get("exact_text") or "")
        m = _BOND_AMT_RE.search(text)
        if m and amount is None:
            amount = f"{m.group(1)}{m.group(2)}"
        if re.search(r"账户|账号", text) and account is None:
            account = "见原文（本工具不抄账号数字）" if re.search(r"\d{6,}", text) else "招标提到账户但未写账号"
    return {
        "mentioned": bool(bonds),
        "amount_verbatim": amount,
        "account": account,
        "n": len(bonds),
    }


def build_handoff(
    requirements: List[Dict[str, Any]],
    *,
    duration_days: Optional[int] = None,
    envelope: Optional[str] = None,
    deadlines: Optional[List[Dict[str, str]]] = None,
    eval_method: Optional[str] = None,
) -> Dict[str, Any]:
    """经营岗交接：评分点 → bid-tech；★/废标 → bid-compliance。不判定可投标。"""
    scoring = [r for r in requirements if r.get("item_kind") == "scoring_point"]
    stars = [r for r in requirements if r.get("item_kind") == "star"]
    specials = [
        r
        for r in requirements
        if r.get("item_kind") == "special"
        or (r.get("item_kind") == "star" and _is_special_line(str((r.get("exact_text") or ""))))
    ]
    workheads: List[str] = []
    for r in requirements:
        blob = " ".join([str(r.get("exact_text") or "")] + [str(s) for s in (r.get("snippets") or [])])
        for m in _WORKHEAD_RE.finditer(blob):
            wh = m.group(0).upper()
            if wh not in workheads:
                workheads.append(wh)
    next_experts: List[str] = []
    if scoring or specials:
        next_experts.append("bid-tech")
    if stars or any(r.get("category") == "reject" for r in requirements):
        next_experts.append("bid-compliance")
    if specials:
        next_experts.append("construction")
    p0_src = [
        r
        for r in requirements
        if r.get("item_kind") == "star" or r.get("category") in ("reject", "qualification")
    ]
    p0_items = []
    if envelope == "blind_tech":
        p0_items.append(
            {
                "req_id": "blind_identity",
                "title": "暗标露名风险",
                "exact_text": "原文检出暗标：封面/页眉/可识别业绩地名须人工核对，系统不保证看不出来。",
                "requirement_ref": "envelope",
                "risk": "high",
                "owner": "legal",
            }
        )
    for r in p0_src:
        p0_items.append(
            {
                "req_id": r.get("id"),
                "title": r.get("title"),
                "exact_text": r.get("exact_text") or ((r.get("snippets") or [None])[0]),
                "requirement_ref": r.get("requirement_ref"),
                "risk": r.get("risk"),
                "owner": r.get("owner"),
            }
        )
    def _brief(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.get("id"),
                    "text": r.get("exact_text") or ((r.get("snippets") or [""])[0]),
                    "requirement_ref": r.get("requirement_ref"),
                }
            )
        return out

    return {
        "schema": "tender.handoff.v1",
        "scoring_points": _brief(scoring),
        "star_items": _brief(stars),
        "specials": _brief(specials),
        "workheads": workheads,
        "duration_days": duration_days,
        "envelope": envelope,
        "eval_method": eval_method,
        "deadlines": list(deadlines or []),
        "bid_bond": _bond_from_requirements(requirements),
        "bid_decision": "human_required",
        "next_experts": next_experts,
        "p0_reject_scan": {
            "schema": "tender.p0_reject_scan.v1",
            "human_confirm_required": True,
            "n": len(p0_items),
            "items": p0_items,
            "note": "P0 废标/资格/★项须人工确认。系统不判定可投标、不编造否决结论。",
        },
    }


def build_tech_outline_from_handoff(
    handoff: Optional[Dict[str, Any]] = None,
    *,
    project_name: str = "未命名项目",
) -> Dict[str, Any]:
    """按抽出的评分点出技术标目录骨架。无评分点则只给待对照前附表，不套模板冒充本标。"""
    ho = handoff or {}
    points = list(ho.get("scoring_points") or [])
    specials = list(ho.get("specials") or [])
    chapters: List[Dict[str, Any]] = []
    if not points:
        chapters.append(
            {
                "n": 1,
                "title": "通用骨架 + 待对照前附表",
                "source_ref": None,
                "note": "原文未检出评分点。禁止套上个中标项目目录。",
            }
        )
    else:
        for i, p in enumerate(points, 1):
            chapters.append(
                {
                    "n": i,
                    "title": str(p.get("text") or "评分点").strip()[:160],
                    "source_ref": p.get("requirement_ref"),
                    "note": "要点：待按招标原文扩写 · 条款 [UNSPECIFIED]",
                }
            )
    extra_n = len(chapters)
    for j, s in enumerate(specials, 1):
        chapters.append(
            {
                "n": extra_n + j,
                "title": f"专项：{str(s.get('text') or '').strip()[:140]}",
                "source_ref": s.get("requirement_ref"),
                "note": "招标点名专项：目录须有章；数值待填。禁止写已论证/可开工。",
            }
        )
    md_lines = [
        f"# {project_name} · 技术标目录草稿",
        "",
        "> AI 草稿 · 内部讨论。按评分点排目录，分数未核验则标未核实。",
        "",
    ]
    for ch in chapters:
        md_lines.append(f"## {ch['n']}. {ch['title']}")
        if ch.get("source_ref"):
            md_lines.append(f"- 原文：{ch['source_ref']}")
        md_lines.append(f"- {ch['note']}")
        md_lines.append("")
    return {
        "schema": "tender.tech_outline.v1",
        "project_name": project_name,
        "n_chapters": len(chapters),
        "from_extracted_scores": bool(points),
        "chapters": chapters,
        "markdown": "\n".join(md_lines),
    }


def build_workbench_extract_table(
    parsed: Optional[Dict[str, Any]] = None,
    *,
    project_name: str = "未命名招标",
) -> str:
    """同一张招标解析表：主线 C 与 workbench sidecar 共用，禁止编造空栏。"""
    p = parsed or {}
    ho = p.get("handoff") or {}
    days = p.get("duration_days")
    days_s = f"{days} 日历天" if days is not None else "未在原文检出"
    scores = ho.get("scoring_points") or []
    stars = ho.get("star_items") or []
    specials = ho.get("specials") or []
    quals = [
        r
        for r in (p.get("requirements") or [])
        if r.get("category") == "qualification" and r.get("item_kind") == "theme"
    ]
    score_md = "\n".join(f"- {s.get('requirement_ref')}: {s.get('text')}" for s in scores) or "未在原文检出评分点"
    star_md = "\n".join(f"- {s.get('requirement_ref')}: {s.get('text')}" for s in stars) or "未在原文检出★项"
    spec_md = "\n".join(f"- {s.get('requirement_ref')}: {s.get('text')}" for s in specials) or "未在原文检出专项要求"
    qual_md = "\n".join(f"- {q.get('requirement_ref')}: {q.get('exact_text')}" for q in quals) or "未在原文检出资质要求"
    wh = ", ".join(ho.get("workheads") or []) or "未在原文检出"
    env = ho.get("envelope") or "未在原文检出"
    dls = ho.get("deadlines") or []
    dl_md = "\n".join(f"- {d.get('label')}: {d.get('when')}" for d in dls) or "未在原文检出（口头传闻不算）"
    return "\n".join(
        [
            f"# {project_name} · 招标解析表",
            "",
            "> AI 草稿 · 内部讨论。缺项写「未在原文检出」。不编造天数、分值、workhead。",
            "",
            "## 工程",
            project_name,
            "",
            "## 评标 / 评分点摘录",
            score_md,
            "",
            "## ★ / 必须满足项",
            star_md,
            "",
            f"## Workhead / 信封",
            f"- workhead: {wh}",
            f"- envelope: {env}",
            f"- eval_method: {ho.get('eval_method') or '未在原文检出'}",
            "",
            "## 资质/证书",
            qual_md,
            "",
            "## 工期",
            days_s,
            "",
            "## 时间轴（仅原文日期）",
            dl_md,
            "",
            "## 必须编制的专项",
            spec_md,
            "",
            f"## 下一岗",
            ", ".join(ho.get("next_experts") or []) or "—",
            "",
            "P0 资格/废标/★须人工确认。系统不判定可投标。",
            "",
        ]
    )


def workbench_bid_extract(text: str, *, project_name: str = "未命名招标") -> Dict[str, Any]:
    """Workbench bid-parse extract entry. Same transform as packing tender-handoff."""
    parsed = parse_tender_text(text, source="workbench-bid-parse")
    ho = parsed.get("handoff") or {}
    return {
        "ok": bool(parsed.get("requirements")),
        "schema": "tender.workbench_extract.v1",
        "duration_days": parsed.get("duration_days"),
        "star_items": list(ho.get("star_items") or []),
        "scoring_points": list(ho.get("scoring_points") or []),
        "handoff": ho,
        "submit_blocked": True,
        "submit_block_reason": "P0 资格/废标/★项须人工确认；成果仍是 AI 草稿，不可递交。",
        "extract_table_markdown": build_workbench_extract_table(
            parsed, project_name=project_name
        ),
    }


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
                "item_kind": "theme",
                "category": cat,
                "title": title,
                "snippets": hits[:5],
                "exact_text": hits[0],
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

    theme_ids = {r["id"] for r in requirements}
    for item in _extract_line_items(lines):
        if item["id"] in theme_ids:
            continue
        requirements.append(item)
        theme_ids.add(item["id"])

    duration_days = _duration_days_from_lines(lines)
    envelope = _detect_envelope(blob)
    eval_method = _detect_eval_method(blob)
    deadlines = _extract_deadlines(blob)
    handoff = build_handoff(
        requirements,
        duration_days=duration_days,
        envelope=envelope,
        deadlines=deadlines,
        eval_method=eval_method,
    )

    return {
        "schema": "tender.parse.v1",
        "tool": "tender.parse",
        "source": source,
        "n_lines": len(lines),
        "n_chars": len(blob),
        "requirements": requirements,
        "duration_days": duration_days,
        "handoff": handoff,
        "summary": {
            "n_requirements": len(requirements),
            "n_line_items": sum(1 for r in requirements if r.get("item_kind") != "theme"),
            "categories": sorted({r["category"] for r in requirements}),
            "must_respond_n": sum(1 for r in requirements if r.get("must_respond")),
            "critical_n": sum(1 for r in requirements if r.get("risk") == "critical"),
            "owners": sorted({str(r.get("owner")) for r in requirements if r.get("owner")}),
            "duration_days": duration_days,
            "n_scoring_points": len(handoff.get("scoring_points") or []),
            "n_star_items": len(handoff.get("star_items") or []),
            "envelope": envelope,
            "eval_method": eval_method,
            "n_deadlines": len(deadlines),
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
                "item_kind": r.get("item_kind") or "theme",
                "requirement_ref": r.get("requirement_ref"),
                "owner": r.get("owner") or "unassigned",
                "risk": r.get("risk") or "medium",
                "requirement_type": r.get("requirement_type") or "informational",
                "status": status,
                # 业界合规矩阵：应答落点（提案章节），便于评审对照
                "proposal_location": _proposal_location(cat, rid, r.get("item_kind")),
                "compliance_label": _compliance_label(status),
                "knowledge_ref": _knowledge_ref(cat, rid),
                "public_ref": _public_ref(cat, rid),
                "evidence": evidence,
                "snippets": r.get("snippets") or [],
                "exact_text": r.get("exact_text") or ((r.get("snippets") or [None])[0]),
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
    _attach_knowledge_excerpts(rows)
    return {
        "schema": "tender.response_matrix.v1",
        "tool": "tender.response_matrix",
        "rows": rows,
        "summary": summary,
    }


def _attach_knowledge_excerpts(rows: List[Dict[str, Any]]) -> None:
    """Bind in-repo tender-delivery notes onto matrix rows. No invented clauses."""
    root = Path(__file__).resolve().parents[2]
    cache: Dict[str, str] = {}
    for row in rows:
        rel = str(row.get("knowledge_ref") or "")
        if not rel:
            continue
        if rel not in cache:
            path = root / rel
            if not path.is_file():
                cache[rel] = ""
            else:
                body = path.read_text(encoding="utf-8")
                if body.startswith("---"):
                    parts = body.split("---", 2)
                    body = parts[2] if len(parts) >= 3 else body
                cache[rel] = " ".join(body.split())[:400]
        excerpt = cache[rel]
        if excerpt:
            row["knowledge_excerpt"] = excerpt


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "unknown")
        out[k] = out.get(k, 0) + 1
    return out


def _proposal_location(
    category: Optional[str], req_id: Optional[str], item_kind: Optional[str] = None
) -> str:
    """默认应答落点（可被人工改写）。"""
    kind = str(item_kind or "")
    if kind == "star":
        return "标书响应声明 / 偏离表（★项须逐条响应）"
    if kind == "scoring_point":
        return "技术标 · 对应评分点章节"
    if kind == "special":
        return "技术标 · 危大及招标点名专项"
    if kind == "ebid":
        return "形式评审 · 电子标加密/CA锁（截止后补传无效）"
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


def _public_ref(category: Optional[str], req_id: Optional[str]) -> Optional[str]:
    """Official portal titles only. No invented clause numbers."""
    if req_id == "cog_lashing" or str(category or "") in ("transport", "packaging"):
        return (
            "IMO/ILO/UNECE CTU Code (non-mandatory) · "
            "https://unece.org/transport/intermodal-transport/"
            "imoilounece-code-practice-packing-cargo-transport-units-ctu-code"
        )
    if str(category or "") in ("qualification", "scoring"):
        return (
            "BCA Price Quality Method (PQM) Framework (portal, 26 Jan 2026) · "
            "https://www1.bca.gov.sg/growth-and-transformation/procurement/"
            "procurement-and-legal-frameworks/price-quality-method-pqm-framework/"
        )
    return None


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


def matrix_to_csv(matrix: Dict[str, Any]) -> str:
    """Compliance-matrix CSV for bid leads (owner / status / evidence). No invented cells."""
    rows = list((matrix or {}).get("rows") or [])
    headers = [
        "req_id",
        "title",
        "exact_text",
        "requirement_type",
        "status",
        "compliance_label",
        "owner",
        "risk",
        "proposal_location",
        "requirement_ref",
        "item_kind",
    ]

    def _cell(v: Any) -> str:
        s = "" if v is None else str(v)
        s = s.replace("\r", " ").replace("\n", " ").replace('"', "'")
        if "," in s or "'" in s:
            return f'"{s}"'
        return s

    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(_cell(r.get(h)) for h in headers))
    return "\n".join(lines) + "\n"


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
    handoff: Optional[Dict[str, Any]] = None,
    tech_outline: Optional[Dict[str, Any]] = None,
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
        handoff=handoff,
        tech_outline=tech_outline,
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
    handoff: Optional[Dict[str, Any]] = None,
    tech_outline: Optional[Dict[str, Any]] = None,
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
        days = parse_summary.get("duration_days")
        days_s = f"{days} 日历天" if days is not None else "招标未写"
        lines += [
            "## 2. 招标要点摘要",
            "",
            f"- 抽取条款: {parse_summary.get('n_requirements', '—')}",
            f"- 行项目: {parse_summary.get('n_line_items', '—')} · 评分点 {parse_summary.get('n_scoring_points', '—')} · ★项 {parse_summary.get('n_star_items', '—')}",
            f"- 类别: {', '.join(parse_summary.get('categories') or []) or '—'}",
            f"- 必应 / 关键: must={parse_summary.get('must_respond_n', '—')} · critical={parse_summary.get('critical_n', '—')}",
            f"- 工期（只抄原文）: {days_s}",
            f"- 信封: {parse_summary.get('envelope') or '招标未写'}",
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
    ho = handoff or {}
    p0 = ho.get("p0_reject_scan") or {}
    nxt = ho.get("next_experts") or []
    if p0 or nxt:
        lines += [
            "",
            "## 经营岗交接 / P0",
            "",
            f"- 下一岗: {', '.join(nxt) or '—'}",
            f"- P0 人工确认: **{p0.get('human_confirm_required', True)}** · {p0.get('n', 0)} 项",
            f"- {p0.get('note') or '资格/废标/★项不自动关闭'}",
            "",
        ]
    outline = tech_outline or {}
    if outline.get("markdown"):
        lines += ["", "## 技术标目录（按抽出评分点）", "", outline["markdown"].rstrip(), ""]
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
    p0_confirmed: bool = False,
    ingest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """投标解析 → 清单 → 响应矩阵 → 应答包一站式（可接装柜 summary）。"""
    parsed = parse_tender_text(text, source=source)
    reqs = list(parsed.get("requirements") or [])
    checklist = build_checklist(reqs)
    matrix = build_response_matrix(reqs, packing_summary=packing_summary)
    handoff = parsed.get("handoff") or build_handoff(reqs, duration_days=parsed.get("duration_days"))
    outline = build_tech_outline_from_handoff(handoff, project_name=project_name)
    extract_table = build_workbench_extract_table(parsed, project_name=project_name)
    package = build_response_package(
        matrix=matrix,
        packing_summary=packing_summary,
        parse_summary=parsed.get("summary"),
        project_name=project_name,
        handoff=handoff,
        tech_outline=outline,
    )
    from packing_assistant.bidbook.sg_facade import build_sg_facade_bidbook

    bidbook = build_sg_facade_bidbook(
        tender_text=text,
        parsed=parsed,
        matrix=matrix,
        packing_summary=packing_summary,
        open_actions=package["open_actions"],
        p0_confirmed=p0_confirmed,
    )
    return {
        "schema": "tender.pipeline.v1",
        "product_mainline": "C_tender_delivery",
        "parse": parsed,
        "handoff": handoff,
        "extract_table_markdown": extract_table,
        "tech_outline": outline,
        "tech_outline_markdown": outline.get("markdown"),
        "p0_reject_scan": (handoff or {}).get("p0_reject_scan"),
        "checklist": checklist,
        "matrix": matrix,
        "matrix_markdown": matrix_to_markdown(matrix),
        "matrix_csv": matrix_to_csv(matrix),
        "open_actions": package["open_actions"],
        "response_package": package,
        "export_markdown": package["markdown"],
        "bidbook": bidbook,
        "bidbook_markdown": bidbook.get("markdown"),
        "p0_confirmed": bool(p0_confirmed),
        "submit_blocked": True,
        "submit_block_reason": (
            "P0 资格/废标/★项尚未人工确认；成果仍是 AI 草稿，不可递交。"
            if not p0_confirmed
            else "已记录 P0 核对，仍是 AI 草稿：无盖章、无业绩附件、不可递交。"
        ),
        "ingest": ingest,
        "ok": bool(reqs),
    }
