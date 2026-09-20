"""The three bid deliverables as Markdown, in the sections each post's SKILL.md declares.

  bid-parse       招标解析表          9 sections, table 事项｜要求原文｜来源页段｜是否检出｜澄清建议
  bid-tech        技术标目录草稿      9 sections, table 评分点原文｜拟写章节｜已有证据｜缺项｜专项接口
  bid-compliance  响应缺口对照        7 sections, table 事项｜招标要求｜响应原文或证据｜三态｜缺口｜责任人

Input is what tools/tender_facts.py took out of the text (as the dict that travels in the parse and
in tender.handoff.json) plus the document parser's requirement rows. Nothing here reads a model,
computes a value or states a verdict: a cell holds a literal stretch of the source, a fixed label, or
a placeholder - "未在原文检出", "招标未写", "[A001] 待填". The one piece of arithmetic is the numeric
comparison the response benchmark already scores (tools/tender_response_match._compare_quantities),
and what it finds is worded "待人工核验", never 合格 / 不合格.

A row's first cell says what the row is about, with its lot in brackets when the text named lots
("工期（一标段）"), so one lot's number cannot be read as another's.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from packing_assistant.post_facts import table_cell

CELL = 40  # a cell longer than this is a sentence, not a field
MISSING = "未在原文检出"
NOT_WRITTEN = "招标未写"
TBD = "[A001] 待填"

Facts = Mapping[str, Any]
Row = Dict[str, Any]


# ---------------------------------------------------------------------------
# files that were pointed at and gave no text
# ---------------------------------------------------------------------------
_ROLE_WORD = {"tender": "招标侧", "response": "响应侧", "reference": "用途未标"}


def _unread(ho: Optional[Mapping[str, Any]], extra: Optional[Sequence[Mapping[str, Any]]] = None) -> List[Row]:
    """The handoff's unreadable files plus this turn's, one entry per title."""
    seen: Dict[str, Row] = {}
    for item in list((ho or {}).get("unreadable") or []) + list(extra or []):
        if isinstance(item, Mapping) and str(item.get("title") or "").strip():
            seen.setdefault(str(item["title"]).strip(), dict(item))
    return list(seen.values())


def _unread_names(items: Sequence[Mapping[str, Any]], roles: Optional[Tuple[str, ...]] = None) -> str:
    return "、".join(str(i["title"]).strip() for i in items if roles is None or str(i.get("role") or "reference") in roles)


def _unread_cell(item: Mapping[str, Any]) -> str:
    return f"{str(item['title']).strip()}（{_ROLE_WORD.get(str(item.get('role') or 'reference'), '用途未标')}）：{item.get('reason') or '未读出'}"


def _unread_warning(items: Sequence[Mapping[str, Any]]) -> List[str]:
    if not items:
        return []
    return [f"> 点名的文件有 {len(items)} 份没读出来：{'；'.join(_unread_cell(i) for i in items)}。"
            f"本稿的「{MISSING}」只对读到的部分成立——没读到的文件里有没有，本稿不知道。", ""]


# ---------------------------------------------------------------------------
# reading the facts dict
# ---------------------------------------------------------------------------


def _mentions(facts: Optional[Facts], topic: str, side: Optional[str] = None) -> List[Row]:
    return [m for m in (facts or {}).get("mentions") or []
            if m.get("topic") == topic and (side is None or m.get("side") == side)]


def _lots(facts: Optional[Facts]) -> List[str]:
    lots = list((facts or {}).get("lots") or [])
    return lots if len(lots) > 1 else []


def _with_lot(label: str, lot: str) -> str:
    return f"{label}（{lot}）" if lot else label


def _source(item: Mapping[str, Any]) -> str:
    origin = str(item.get("origin") or "")
    line = f"L{item.get('line')}" if item.get("line") else "—"
    return f"{origin} {line}".strip() if origin else line


def _clip(text: str, limit: int = CELL) -> str:
    """A literal stretch no longer than a cell; what is cut off is marked, never rewritten."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _value_cell(item: Mapping[str, Any]) -> str:
    """The value, with the clause it came from when both fit in one cell."""
    value, note = str(item.get("value") or ""), str(item.get("note") or "")
    if value and note and note != value and len(value) + len(note) + 2 <= CELL:
        return f"{value}（{note}）"
    return value or _clip(note)


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> List[str]:
    rows = [list(r) for r in rows]
    if not rows:
        return []
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(table_cell(c) or "—" for c in row) + " |" for row in rows]
    return out + [""]


# ---------------------------------------------------------------------------
# bid-parse
# ---------------------------------------------------------------------------

PARSE_HEADER = ("事项", "要求原文", "来源页段", "是否检出", "澄清建议")

#: (topic, label, asked for even when absent, what to do when absent)
_PARSE_SECTIONS: Tuple[Tuple[str, Tuple[Tuple[str, str, bool, str], ...]], ...] = (
    ("1 项目与公告", (
        ("project", "项目名称", True, "对照招标公告首页核对全称"),
        ("owner", "招标人", True, "对照招标公告核对招标人/代理机构"),
        ("tender_no", "招标编号", True, "对照招标公告核对编号"),
        ("scope", "招标范围", False, ""),
        ("area", "建筑面积", False, ""),
        ("structure", "结构形式", False, ""),
    )),
    ("2 时间轴", (
        ("deadline_query", "答疑/澄清截止", False, ""),
        ("deadline_visit", "踏勘", False, ""),
        ("deadline_bid", "投标截止", True, "查投标人须知前附表；口头传闻不算"),
        ("deadline_open", "开标", False, ""),
    )),
    ("3 资格与业绩", (
        ("qualification", "资质", True, "查资格审查条件原文，注意「及以上」和专业类别"),
        ("track_record", "类似业绩", True, "查业绩的年限、金额、数量口径"),
        ("pm", "项目经理", True, "查注册专业、等级、B证及在建限制"),
        ("tech_lead", "技术负责人", False, ""),
        ("registration", "注册资格/工作类别", False, ""),
    )),
    ("4 实质性响应", (
        ("duration", "工期", True, "查前附表工期及是否含节点工期"),
        ("delivery", "交货期", False, ""),
        ("quality", "质量标准", True, "查质量要求及创优条款"),
        ("validity", "投标有效期", True, "查前附表；保函有效期须与之匹配"),
        ("warranty", "缺陷责任期/质保期", False, ""),
    )),
    ("5 评分点", (
        ("eval_method", "评标办法", True, "查评标办法章节（综合评估/最低价）"),
    )),
    ("6 清单限价", (
        ("price_cap", "最高限价", True, "查招标公告/清单编制说明；未公布则书面提请澄清"),
    )),
    ("7 专项触发", ()),
    ("8 保证金", (
        ("bond", "投标保证金", True, "查金额、形式、到账截止"),
        ("bond_validity", "保函有效期", False, ""),
    )),
)


def _parse_rows(facts: Optional[Facts], topic: str, label: str, always: bool, advice: str) -> List[List[str]]:
    rows: List[List[str]] = []
    found = [m for m in _mentions(facts, topic, "tender") if m.get("value") or m.get("not_given")]
    seen: set = set()
    for m in found:
        name = _with_lot(label, str(m.get("lot") or ""))
        if m.get("not_given"):
            if m.get("origin"):
                continue  # "补遗没提保证金": the addendum left it alone, the original row stands
            key = (name, "absent")
            if key in seen or any(x.get("value") and x.get("lot") == m.get("lot") for x in found):
                continue
            seen.add(key)
            rows.append([name, NOT_WRITTEN, _source(m), f"用户称招标未载：{_clip(m.get('note'), 22)}", advice or "书面提请澄清"])
            continue
        key = (name, m.get("value"), m.get("origin"))
        if key in seen:
            continue
        seen.add(key)
        amended = "以补遗为准，对照补遗原文" if m.get("origin") else "—"
        rows.append([name, _clip(m.get("value")), _source(m), "已检出", amended])
    if always:
        lots = _lots(facts)
        have = {str(m.get("lot") or "") for m in found}
        if not found:
            rows.append([label, MISSING, "—", "未检出", advice])
        elif lots and "" not in have:
            for lot in lots:
                if lot not in have:
                    rows.append([_with_lot(label, lot), MISSING, "—", "未检出", advice])
    return rows


def extract_table(parsed: Optional[Mapping[str, Any]], *, project_name: str = "未命名招标") -> str:
    p = parsed or {}
    ho = p.get("handoff") or {}
    facts = p.get("facts") or ho.get("facts") or {}
    project = next((m["value"] for m in _mentions(facts, "project") if m.get("value")), "") or project_name
    lines = [
        f"# {project} · 招标解析表",
        "",
        "> AI 草稿 · 内部讨论。只抄原文：缺项写「未在原文检出」，用户说招标没写的记「招标未写」。不编造天数、分值、workhead。",
        "",
    ]
    unread = _unread(ho)
    lines += _unread_warning(unread)
    lots = _lots(facts)
    scopes = facts.get("lot_scopes") or {}
    day_line = ""
    for title, topics in _PARSE_SECTIONS:
        rows: List[List[str]] = []
        for topic, label, always, advice in topics:
            rows += _parse_rows(facts, topic, label, always, advice)
        if title.startswith("1 "):
            zone = _zone(facts)
            rows.append(["辖区", zone, "—", "已检出" if zone != "UNSPECIFIED" else "未检出", _ZONE_ADVICE])
            only = list(facts.get("lots") or [])
            if only:
                rows.append(["标段", "、".join(only), "—", "已检出", "各标段的工期、限价、保证金分行列出，不互相借用" if lots else "—"])
            rows += [[_with_lot("标段内容", lot), _clip(scope), "—", "已检出", "—"] for lot, scope in scopes.items()]
            rows += [["未读出的文件" + (f" {n}" if len(unread) > 1 else ""), str(u["title"]).strip(), "—", "未读出", str(u.get("reason") or "—")]
                     for n, u in enumerate(unread, 1)]
        if title.startswith("3 "):
            rows += _requirement_rows(p, {"qualification"}, facts)
        if title.startswith("4 "):
            days = p.get("duration_days")
            if days is not None and not any(r[0].startswith("工期") or r[0].startswith("交货期") for r in rows if r[3] == "已检出"):
                rows.insert(0, ["工期", f"{days} 日历天", "—", "已检出", "—"])
            day_line = f"工期（招标方的日历天数，只抄原文）：{days} 日历天" if days is not None else ""
            rows += _requirement_rows(p, {"reject", "validity", "quality", "warranty", "payment"}, facts, stars=True)
        if title.startswith("5 "):
            rows += _score_rows(p, facts)
        if title.startswith("6 "):
            rows += _requirement_rows(p, {"price"}, facts)
        if title.startswith("7 "):
            rows += _special_rows(p, facts)
        lines += [f"## {title}", ""]
        lines += _table(PARSE_HEADER, rows) or [f"{MISSING}。", ""]
        if title.startswith("4 ") and day_line:
            lines += [day_line, ""]
    lines += ["## 9 书面澄清与交接", ""]
    gaps = [ln for ln in lines if ln.startswith("|") and ("| 未检出 |" in ln or NOT_WRITTEN in ln)]
    lines.append(f"- 上表 {len(gaps)} 项未检出或招标未写：逐项按「澄清建议」核对原文，需要时在澄清截止前书面提问。")
    wh = ", ".join(ho.get("workheads") or [])
    lines.append(f"- workhead: {wh or MISSING} · envelope: {ho.get('envelope') or MISSING} · eval_method: {ho.get('eval_method') or MISSING}")
    ours = [m for m in facts.get("mentions") or [] if m.get("side") == "ours" and (m.get("value") or m.get("note"))]
    if ours:
        lines += ["", "用户同时说了我方的情况，不属于招标要求，未写入上表（交 bid-compliance 对照）：", ""]
        lines += [f"- {m.get('label')}{'（' + m['lot'] + '）' if m.get('lot') else ''}：{_clip(_value_cell(m))}" for m in ours]
    lines += _unplaced(facts)
    lines += ["", f"- 下一岗：{', '.join(ho.get('next_experts') or []) or '—'}", "",
              "P0 资格/废标/★须人工确认。系统不判定可投标。", ""]
    return "\n".join(lines)


#: which fields say what a parser rule is about; a rule with no field of its own is always listed
_RULE_TOPICS = {
    "qualification": ("qualification", "track_record"), "personnel": ("pm", "tech_lead"), "bid_validity": ("validity",),
    "price_cap": ("price_cap",), "quality_standard": ("quality",), "warranty": ("warranty",),
    "delivery_time": ("duration", "delivery"), "scoring": ("eval_method",),
}


def _covered(text: str, facts: Optional[Facts], rule: str = "") -> bool:
    """A requirement line whose content already stands in a field row is not listed twice.

    The parser quotes whole lines. For a typed request the line is the whole run-on sentence, and
    listing it under 资格, again under 质量 and again under 限价 is the pasted blob this table
    replaces. So: if the field the rule is about was taken from this very text, the row is covered.
    A clause no field speaks for ("须具备有效的安全生产许可证") is never covered.
    """
    flat = re.sub(r"\s+", "", text)
    topics = _RULE_TOPICS.get(rule)
    inside = [re.sub(r"\s+", "", str(m.get("value") or "")) for m in (facts or {}).get("mentions") or []
              if m.get("side") == "tender" and m.get("value")]
    inside = [v for v in inside if v in flat]
    if topics is not None:
        return any(m.get("topic") in topics and re.sub(r"\s+", "", str(m.get("value") or "")) in flat
                   for m in (facts or {}).get("mentions") or [] if m.get("side") == "tender" and m.get("value"))
    if not inside:
        return False
    # no rule to go by (a row of the response comparison): the sentence is covered when the fields
    # took every number out of it, or when it is hardly longer than the one value it holds
    numbers = re.findall(r"\d+(?:\.\d+)?", re.sub(r"[A-Za-z]{2,}[-_/][A-Za-z0-9\-_/]+", " ", flat))
    if numbers:
        return all(any(n in v for v in inside) for n in numbers)
    return any(len(flat) <= len(v) + 24 for v in inside)


def _clauses(text: str) -> List[str]:
    return [c.strip(" \t，,;；。、:：") for c in re.split(r"[，,；;。]", text) if c.strip(" \t，,;；。、:：")]


def _quote(text: str, facts: Optional[Facts], rule: str = "") -> str:
    """What to print for a requirement the parser quoted as a whole line.

    A clause of a document is printed as it stands. A typed request is one long line, and the parser
    quotes it whole under every rule it touches - the pasted blob. Of such a sentence only the
    clauses are printed that the rule is about and that no field row already speaks for; "" when
    none is left. Each is still a literal stretch of the source.
    """
    from packing_assistant.tools.tender_facts import is_task_talk
    from packing_assistant.tools.tender_parse import _RULES, rule_patterns_for_line

    flat = re.sub(r"\s+", " ", str(text or "")).strip()
    parts = _clauses(flat)
    if len(flat) <= 60 or len(parts) < 3:
        return flat
    patterns = next((list(pats) for rid, _cat, pats, _t, _o, _r in _RULES if rid == rule), None)
    if patterns is None:
        patterns = [r"[★☆＊]"] if rule == "star" else rule_patterns_for_line(flat)
    spoken = {re.sub(r"\s+", "", str(m.get("note") or "")) for m in (facts or {}).get("mentions") or [] if m.get("value")}
    spoken |= {re.sub(r"\s+", "", str(s.get("note") or "")) for s in ((facts or {}).get("scores") or []) + ((facts or {}).get("specials") or [])}
    keep = [c for c in parts if any(re.search(p, c, re.I) for p in patterns) and not is_task_talk(c)
            and re.sub(r"\s+", "", c) not in spoken]
    return "；".join(dict.fromkeys(keep))


def _requirement_rows(parsed: Mapping[str, Any], categories: set, facts: Optional[Facts], *, stars: bool = False) -> List[List[str]]:
    rows: List[List[str]] = []
    seen: set = set()
    for r in parsed.get("requirements") or []:
        is_star = r.get("item_kind") == "star"
        if not ((r.get("category") in categories and r.get("item_kind") == "theme") or (stars and is_star)):
            continue
        refs = [x for x in str(r.get("requirement_ref") or "").split(",") if x]
        texts = [str(t) for t in (r.get("snippets") or [r.get("exact_text")]) if t]
        for index, text in enumerate(texts):
            if text in seen or _covered(text, facts, str(r.get("id") or "")):
                continue
            seen.add(text)
            quote = _quote(text, facts, "star" if is_star else str(r.get("id") or ""))
            if not quote:
                continue
            ref = refs[index] if index < len(refs) else (refs[0] if refs else "—")
            label = "★/必须满足项" if is_star else str(r.get("title") or "要求")
            rows.append([f"{label} {ref}", _clip(quote, 120), ref, "已检出", "逐条响应，须人工确认" if is_star else "—"])
    return rows


def _score_rows(parsed: Mapping[str, Any], facts: Optional[Facts]) -> List[List[str]]:
    rows: List[List[str]] = []
    noted: List[str] = []
    method = str((parsed.get("handoff") or {}).get("eval_method") or "")
    if method and not any(m.get("value") for m in _mentions(facts, "eval_method")):
        rows.append(["评标办法（原文出现）", method, "—", "已检出", "对照评标办法章节确认"])
    for s in (facts or {}).get("scores") or []:
        name = str(s.get("name") or "")
        rows.append([_with_lot(f"评分点：{name}" if name else "评分点（未写名称）", str(s.get("lot") or "")),
                     f"{name} {s.get('score')}".strip(), _source(s), "已检出", "分值以评标办法原文为准"])
        noted.append(re.sub(r"\s+", "", str(s.get("note") or "")))
    for p in (parsed.get("handoff") or {}).get("scoring_points") or []:
        flat = re.sub(r"\s+", "", str(p.get("text") or ""))
        if flat and not any(n and (n in flat or flat in n) for n in noted):
            rows.append([f"评分点 {p.get('requirement_ref')}", _clip(p.get("text"), 120), str(p.get("requirement_ref") or "—"), "已检出", "—"])
    if not any(r[0].startswith("评分点") for r in rows):
        rows.append(["评分点", MISSING, "—", "未检出", "查评标办法的评分表；没有评分点就不排技术标目录"])
    return rows


def _special_rows(parsed: Mapping[str, Any], facts: Optional[Facts]) -> List[List[str]]:
    rows: List[List[str]] = []
    noted: List[str] = []
    for s in (facts or {}).get("specials") or []:
        lot = str(s.get("lot") or "")
        if s.get("not_given"):
            rows.append([_with_lot("点名专项", lot), NOT_WRITTEN, _source(s), f"用户称招标未载：{_clip(s.get('note'), 22)}", "对照招标文件确认确无点名专项"])
            continue
        detail = f"；{s['detail']}" if s.get("detail") else ""
        rows.append([_with_lot(f"专项：{s.get('name')}", lot), _clip(f"{s.get('name')}{detail}"), _source(s), "已检出",
                     "专项正文交施工方案岗；本表不判定是否危大"])
        noted.append(re.sub(r"\s+", "", str(s.get("note") or "")))
    for p in (parsed.get("handoff") or {}).get("specials") or []:
        flat = re.sub(r"\s+", "", str(p.get("text") or ""))
        if flat and not any(n and (n in flat or flat in n) for n in noted):
            rows.append([f"专项 {p.get('requirement_ref')}", _clip(p.get("text"), 120), str(p.get("requirement_ref") or "—"), "已检出", "专项正文交施工方案岗"])
    return rows or [["点名专项", MISSING, "—", "未检出", "查技术要求与评分表是否点名专项方案"]]


_ZONE_ADVICE = "未写明则不默认国家；CN / SG / EU 的依据不得混用"


def _zone(facts: Optional[Facts]) -> str:
    return str((facts or {}).get("jurisdiction") or "UNSPECIFIED")


def _unplaced(facts: Optional[Facts]) -> List[str]:
    left = [str(c) for c in (facts or {}).get("unplaced") or [] if str(c).strip()]
    if not left:
        return []
    return ["", "原话里带数字、但没有对应栏位的句子（原样列出，未丢弃）：", ""] + [f"- {_clip(c, 60)}" for c in left]


# ---------------------------------------------------------------------------
# bid-tech
# ---------------------------------------------------------------------------

TECH_HEADER = ("评分点原文", "拟写章节", "已有证据", "缺项", "专项接口")


def tech_outline(handoff: Optional[Mapping[str, Any]], *, project_name: str = "未命名项目") -> Dict[str, Any]:
    ho = handoff or {}
    facts = ho.get("facts") or {}
    project = next((m["value"] for m in _mentions(facts, "project") if m.get("value")), "") or project_name
    evidence = [m for m in _mentions(facts, "evidence") if m.get("value")]
    specials = [s for s in facts.get("specials") or [] if not s.get("not_given")]
    doc_specials = list(ho.get("specials") or [])

    # ---- chapters: one per scoring point, then one per named special
    chapters: List[Dict[str, Any]] = []
    score_rows: List[List[str]] = []
    noted: List[str] = []
    interface = "见 7 点名专项" if (specials or doc_specials) else "—"
    proof = "见 9 已有证据（未核验原件）" if evidence else f"{TBD}：未提供企业证据"
    for s in facts.get("scores") or []:
        name = str(s.get("name") or "")
        original = f"{name} {s.get('score')}".strip()
        n = len(chapters) + 1
        title = _with_lot(name or f"评分点 {s.get('score')}", str(s.get("lot") or ""))
        chapters.append({"n": n, "title": title, "source_ref": _source(s), "note": "要点：待按招标原文扩写 · 条款 [UNSPECIFIED]"})
        score_rows.append([original, f"第{n}章 {title}", proof, "正文待按评分细则扩写；分值未核验", interface])
        noted.append(re.sub(r"\s+", "", str(s.get("note") or "")))
    for p in ho.get("scoring_points") or []:
        flat = re.sub(r"\s+", "", str(p.get("text") or ""))
        if not flat or any(x and (x in flat or flat in x) for x in noted):
            continue
        n = len(chapters) + 1
        title = str(p.get("text") or "评分点").strip()[:160]
        chapters.append({"n": n, "title": title, "source_ref": p.get("requirement_ref"), "note": "要点：待按招标原文扩写 · 条款 [UNSPECIFIED]"})
        score_rows.append([_clip(title, 120), f"第{n}章", proof, "正文待按评分细则扩写；分值未核验", interface])
    from_scores = bool(chapters)
    if not chapters:
        chapters.append({"n": 1, "title": "通用骨架 + 待对照前附表", "source_ref": None, "note": "原文未检出评分点。禁止套上个中标项目目录。"})
    special_rows: List[List[str]] = []
    special_notes: List[str] = []
    for s in specials:
        lot = str(s.get("lot") or "")
        n = len(chapters) + 1
        chapters.append({"n": n, "title": f"专项：{_with_lot(str(s.get('name')), lot)}", "source_ref": _source(s),
                         "note": "招标点名专项：目录须有章；数值待填。禁止写已论证/可开工。"})
        special_rows.append([_with_lot(str(s.get("name")), lot), str(s.get("detail") or TBD), _source(s), f"第{n}章；专项正文交施工方案岗"])
        special_notes.append(re.sub(r"\s+", "", str(s.get("note") or "")))
    for p in doc_specials:
        flat = re.sub(r"\s+", "", str(p.get("text") or ""))
        if not flat or any(x and (x in flat or flat in x) for x in special_notes):
            continue
        n = len(chapters) + 1
        chapters.append({"n": n, "title": f"专项：{str(p.get('text') or '').strip()[:140]}", "source_ref": p.get("requirement_ref"),
                         "note": "招标点名专项：目录须有章；数值待填。禁止写已论证/可开工。"})
        special_rows.append([_clip(p.get("text"), 120), TBD, str(p.get("requirement_ref") or "—"), f"第{n}章；专项正文交施工方案岗"])
    for s in facts.get("specials") or []:
        if s.get("not_given"):
            special_rows.append([_with_lot("点名专项", str(s.get("lot") or "")), NOT_WRITTEN, _source(s), f"用户称招标未点名：{_clip(s.get('note'), 22)}"])

    md = [f"# {project} · 技术标目录草稿", "",
          "> AI 草稿 · 内部讨论。按评分点排目录，分数未核验则标未核实。不承诺得分或中标；专项只列目录，不是已论证方案。", ""]
    unread = _unread(ho)
    md += _unread_warning(unread)
    md += ["## 1 评分目录映射", ""]
    if from_scores:
        md += _table(TECH_HEADER, score_rows)
    else:
        md += ["原文未检出评分点。禁止套上个中标项目目录；先补评标办法的评分表。", ""]
    md += ["## 2 依据概况", ""]
    md += _table(("项目", "内容", "来源"), _kv_rows(facts, (
        ("project", "工程名称", None, True), ("scope", "招标范围", None, True), ("area", "建筑面积", None, True),
        ("structure", "结构形式", None, True), ("owner", "招标人", None, False), ("tender_no", "招标编号", None, False)),
        extra=[["辖区", _zone(facts), "—"]] + [[_with_lot("标段内容", lot), _clip(scope), "—"]
                                              for lot, scope in (facts.get("lot_scopes") or {}).items()]))
    md += ["## 3 部署工艺", "", f"{TBD}：待按评分点、图纸和现场条件扩写；本稿不写未给的工艺参数。", ""]
    md += ["## 4 工期资源", ""]
    md += _table(("项目", "内容", "来源"), _kv_rows(facts, (
        ("duration", "招标工期", "tender", True), ("duration", "工期承诺（我方）", "ours", False),
        ("delivery", "交货期", "tender", False))))
    md += ["## 5 质量", ""]
    md += _table(("项目", "内容", "来源"), _kv_rows(facts, (("quality", "质量标准/目标", None, True), ("warranty", "缺陷责任期/质保期", None, False))))
    md += ["## 6 安全环保", "", f"{TBD}：待按评分点与现场条件扩写。", ""]
    md += ["## 7 点名专项", ""]
    md += _table(("专项名称", "参数原文", "来源", "接口"), special_rows) or [f"{MISSING}点名专项。", ""]
    md += ["## 8 组织机构", ""]
    md += _table(("岗位", "姓名或要求", "来源"), _people_rows(facts))
    md += ["## 9 缺项与自检", ""]
    check_rows = [["已有证据", _clip(m.get("value")), _source(m)] for m in evidence]
    if not evidence:
        check_rows.append(["已有证据", f"{TBD}：未提供业绩/证书；不得编造项目名", "—"])
    track = [m for m in _mentions(facts, "track_record", "tender") if m.get("value")]
    check_rows += [["类似业绩（招标要求）", _clip(m.get("value")), _source(m)] for m in track]
    check_rows += [["未读出的文件" + (f" {n}" if len(unread) > 1 else ""), _unread_cell(u), "—"] for n, u in enumerate(unread, 1)]
    md += _table(("事项", "内容", "来源"), check_rows)
    n_points = len(score_rows)
    md.append(f"- 自检：评分点 {n_points} 个，均已对应章节；点名专项 {len([r for r in special_rows if r[1] != NOT_WRITTEN])} 个，均已单列章节。"
              if from_scores else "- 自检：原文未检出评分点，目录未展开。")
    md += _unplaced(facts)
    md.append("")
    # the chapter list, as headings, for whoever continues from this outline
    md += ["## 章节清单", ""]
    for ch in chapters:
        md.append(f"### {ch['n']}. {ch['title']}")
        if ch.get("source_ref"):
            md.append(f"- 原文：{ch['source_ref']}")
        md.append(f"- {ch['note']}")
        md.append("")
    return {
        "schema": "tender.tech_outline.v1",
        "project_name": project,
        "n_chapters": len(chapters),
        "from_extracted_scores": from_scores,
        "chapters": chapters,
        "markdown": "\n".join(md),
    }


def _kv_rows(facts: Optional[Facts], spec: Sequence[Tuple[str, str, Optional[str], bool]], *, extra: Sequence[Sequence[str]] = ()) -> List[List[str]]:
    rows: List[List[str]] = []
    lots = _lots(facts)
    for topic, label, side, always in spec:
        found = [m for m in _mentions(facts, topic, side) if m.get("value") or m.get("not_given")]
        seen: set = set()
        for m in found:
            name = _with_lot(label, str(m.get("lot") or ""))
            if m.get("not_given"):
                if not m.get("origin") and not any(x.get("value") and x.get("lot") == m.get("lot") for x in found):
                    rows.append([name, f"{TBD}（用户称未提供：{_clip(m.get('note'), 20)}）", _source(m)])
                continue
            key = (name, m.get("value"))
            if key not in seen:
                seen.add(key)
                rows.append([name, _clip(m.get("value")), _source(m)])
        if always:
            have = {str(m.get("lot") or "") for m in found}
            if not found:
                rows.append([label, TBD, "—"])
            elif lots and "" not in have:
                rows += [[_with_lot(label, lot), TBD, "—"] for lot in lots if lot not in have]
    return rows + [list(r) for r in extra]


def _people_rows(facts: Optional[Facts]) -> List[List[str]]:
    rows: List[List[str]] = []
    lots = _lots(facts)
    for topic, label in (("pm", "项目经理"), ("tech_lead", "技术负责人")):
        for m in _mentions(facts, topic, "tender"):
            if m.get("value"):
                rows.append([_with_lot(f"{label}资格要求（招标）", str(m.get("lot") or "")), _clip(m.get("value")), _source(m)])
        named = [m for m in _mentions(facts, topic, "ours")]
        for m in named:
            name = _with_lot(f"{label}·拟派", str(m.get("lot") or ""))
            rows.append([name, str(m.get("value") or "") or f"{TBD}（{_clip(m.get('note'), 24)}）", _source(m)])
        absent = [m for m in _mentions(facts, topic) if m.get("not_given")]
        for m in absent:
            if not any(x.get("lot") == m.get("lot") for x in named):
                rows.append([_with_lot(f"{label}·拟派", str(m.get("lot") or "")), f"{TBD}（用户称未提供：{_clip(m.get('note'), 20)}）", _source(m)])
        if topic == "pm" and not named and not absent:
            rows += [[_with_lot("项目经理·拟派", lot), TBD, "—"] for lot in (lots or [""])]
    # anybody else the user named with a post: the row is called by the post as it was written
    rows += [[_with_lot(f"{m.get('role') or '其他人员'}·拟派", str(m.get("lot") or "")), str(m.get("value")), _source(m)]
             for m in _mentions(facts, "staff") if m.get("value")]
    return rows


# ---------------------------------------------------------------------------
# bid-compliance
# ---------------------------------------------------------------------------

GAP_HEADER = ("事项", "招标要求", "响应原文或证据", "三态", "缺口", "责任人")
RESPONDED, NOT_RESPONDED, NO_TENDER_TEXT = "已响应·待核验", "未响应", "招标未提供正文"
#: a file that may hold the answer was given and could not be read: neither 已响应 nor 未响应 can be said
UNKNOWN = "未能判断·文件未读出"
EVIDENCE_HEADER = ("事项", "我方写的", "证据文件", "字样", "说明")
#: rows an evidence file can say something about: who, which certificate, which guarantee. A promised
#: number of days is the bid letter's own content - no certificate carries it.
_EVIDENCE_TOPICS = ("poa", "qualification", "registration", "track_record", "pm", "tech_lead", "bond", "bond_validity")

_GAP_SECTIONS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("2 形式签章", ("poa", "seal")),
    ("3 资格证据", ("qualification", "registration", "track_record", "pm", "tech_lead")),
    ("4 保证金", ("bond", "bond_validity")),
    ("5 实质性与价格响应", ("duration", "delivery", "quality", "validity", "warranty", "price_cap")),
)
_LABELS = {"poa": "授权委托书", "seal": "签章", "qualification": "资质", "registration": "注册资格/工作类别", "track_record": "类似业绩", "pm": "项目经理",
           "tech_lead": "技术负责人", "bond": "投标保证金", "bond_validity": "保函有效期", "duration": "工期", "delivery": "交货期",
           "quality": "质量标准", "validity": "投标有效期", "warranty": "缺陷责任期/质保期", "price_cap": "最高限价 / 我方报价"}
#: what to say the numbers mean when both sides gave one, in the words the response matcher compares on
_COMPARE = {"duration": "工期", "delivery": "交货期", "validity": "投标有效期", "warranty": "质保期", "bond": "保证金"}
_PENDING = re.compile(r"还没|尚未|没拿到|没定|没盖|没开|没交|没办|没编|未盖|未开|未交|未办|待补|后补|明天补|还差|只转")


def _owner_for(facts: Optional[Facts], lot: str) -> str:
    people = _mentions(facts, "owner_person")
    for m in people:
        if m.get("value") and str(m.get("lot") or "") == lot:
            return str(m["value"])
    for m in people:
        if m.get("not_given") and str(m.get("lot") or "") == lot:
            return f"{TBD}（{_clip(m.get('note'), 16)}）"
    for m in people:
        if m.get("value") and not m.get("lot"):
            return str(m["value"])
    return TBD


_GRADE = re.compile(r"(?:特|[一二三四五]|[甲乙丙])级(?:及以上|以上)?")


def _grade_note(need: str, have: str) -> str:
    """"一级" asked, "二级" offered. Said as what it is - the words differ - and left to a person:
    "二级及以上" against "一级" differs too and is fine."""
    asked, offered = _GRADE.findall(need or ""), _GRADE.findall(have or "")
    if asked and offered and not set(asked) & set(offered):
        return f"等级字样不同（招标：{'、'.join(dict.fromkeys(asked))}；响应：{'、'.join(dict.fromkeys(offered))}），待人工核验"
    return ""


#: which conflict topics of the response matcher belong to which field row
_MATCHER_TOPICS = {"duration": ("duration", "delivery"), "delivery": ("delivery", "duration"), "validity": ("validity",),
                   "warranty": ("warranty",), "bond": ("bond",), "price_cap": ("price",), "quality": ("quality",),
                   "track_record": ("track_record",)}


def _answer_from_documents(topic: str, need_value: str, comparison: Optional[Sequence[Mapping[str, Any]]],
                           tender: Optional[Facts] = None) -> Dict[str, Any]:
    """What the response documents say to this requirement: the quotes and the numeric conflicts that are
    about this field. The comparison row may be a whole sentence holding several requirements - a conflict
    about 工期 found in it says nothing about 投标有效期."""
    from packing_assistant.tools.tender_facts import _TOPIC

    flat = re.sub(r"\s+", "", need_value or "")
    aliases = _TOPIC[topic].aliases if topic in _TOPIC else ()
    mine = _MATCHER_TOPICS.get(topic, ())
    for row in comparison or []:
        text = re.sub(r"\s+", "", str(row.get("requirement") or ""))
        if not flat or flat not in text:
            continue
        others = [re.sub(r"\s+", "", str(m.get("value") or "")) for m in (tender or {}).get("mentions") or []
                  if m.get("side") == "tender" and m.get("topic") != topic and m.get("value")]
        alone = not any(v and v in text for v in others)  # the sentence is this one requirement and nothing else
        conflicts = [c for c in row.get("conflicts") or [] if c.get("topic") in mine]
        quotes = [str(e.get("quote")) for e in row.get("response_evidence") or []
                  if alone or any(a in str(e.get("quote")) for a in aliases)]
        quotes += [str(c.get("response_quote")) for c in conflicts if c.get("response_quote") and str(c.get("response_quote")) not in quotes]
        if quotes or conflicts:
            return {"quotes": list(dict.fromkeys(quotes)), "conflicts": conflicts}
    return {"quotes": [], "conflicts": []}


def _numeric_gap(topic: str, need: str, have: str) -> str:
    from packing_assistant.tools.tender_response_match import _compare_quantities

    word = _COMPARE.get(topic)
    if not (word and need and have):
        return ""
    notes = [c["note"] for c in _compare_quantities(f"{word}{need}", f"{word}{have}")]
    return "；".join(notes)


def _price_gap(need: str, have: str) -> str:
    from packing_assistant.tools.tender_response_match import _compare_quantities

    if not (need and have):
        return ""
    return "；".join(c["note"] for c in _compare_quantities(f"最高限价{need}", f"投标报价{have}"))


def compliance_gaps(handoff: Optional[Mapping[str, Any]], matrix: Optional[Mapping[str, Any]], *,
                    ours: Optional[Facts] = None, comparison: Optional[Sequence[Mapping[str, Any]]] = None,
                    disclaimer: str = "", unreadable: Optional[Sequence[Mapping[str, Any]]] = None,
                    evidence: Optional[Sequence[Mapping[str, Any]]] = None,
                    checked: Optional[Sequence[Mapping[str, Any]]] = None) -> str:
    """``handoff`` carries what the tender asks (its ``facts``); ``ours`` is what this turn said of our side.

    When the same text held both, the two are the same dict. ``comparison`` is
    tender_response_match.compare_responses() over the parser's requirement rows, for clauses that are
    not one of the fields below (★ items, pasted document lines).

    ``unreadable`` - ``[{title, role, reason}]``, files that were pointed at and gave no text (the
    handoff's own list is merged in). A row nothing answers is then 未能判断, not 未响应.
    ``evidence`` - ``[{title, text}]``, files given as evidence (certificates, the guarantee, contracts).
    They are searched for our side's own wording, letter for letter; what is found is that the wording
    occurs, never that the document is genuine or in force.
    ``checked`` - ``[{title, sha256}]``, the texts this check read (tools/bid_check_record.py). The draft
    names them, so that whoever reads it later can tell which version it is about.
    """
    ho = handoff or {}
    unread = _unread(ho, unreadable)
    may_answer = _unread_names(unread, ("response", "reference"))
    evidence = [e for e in evidence or [] if isinstance(e, Mapping) and str(e.get("text") or "").strip()]
    checks: List[Row] = []
    tender = ho.get("facts") or {}
    ours = ours if ours is not None else tender
    lots = _lots(tender) or _lots(ours)
    project = next((m["value"] for m in _mentions(tender, "project") + _mentions(ours, "project") if m.get("value")), "")
    number = next((m["value"] for m in _mentions(tender, "tender_no") + _mentions(ours, "tender_no") if m.get("value")), "")
    has_response = any(m.get("side") == "ours" for m in ours.get("mentions") or []) or any(
        r.get("response_evidence") for r in comparison or [])

    md = ["# 废标检查岗 · 响应缺口对照", ""]
    if disclaimer:
        md += [disclaimer, ""]
    md += ["不代判废标。须持证人员按招标文件确认。submit_blocked=true。", "",
           f"三态：**{RESPONDED}** = 用户给了对应的响应原文（证据原件未核验）；**{NOT_RESPONDED}** = 没给，或明说还没办、数值与要求不符；"
           f"**{NO_TENDER_TEXT}** = 只有我方说法，没有招标要求原文。", ""]
    if unread:
        md += [f"另有 **{UNKNOWN}**：点名的文件没读出来（见 1 节）。答案可能就在那份文件里，所以既不能认定未响应，也不能认定已响应。", ""]
    md += ["## 1 来源与范围", ""]
    zone = _zone(tender) if _zone(tender) != "UNSPECIFIED" else _zone(ours)
    scope_rows = [["项目名称", project or MISSING, "—"], ["招标编号", number or MISSING, "—"], ["辖区", zone, "—"]]
    if tender.get("lots") or ours.get("lots"):
        scope_rows.append(["标段", "、".join(tender.get("lots") or ours.get("lots") or []), "—"])
    if may_answer:
        given = (f"已提供（原件未核验；以下只是原文对照）；另有未读出：{may_answer}" if has_response
                 else f"给了但未读出（{may_answer}）：不能认定未响应，也不能认定已响应")
    else:
        given = "已提供（原件未核验；以下只是原文对照）" if has_response else "用户未提供投标响应资料，不能认定已响应"
    scope_rows.append(["响应资料", given, "—"])
    scope_rows += [["未读出的文件" + (f" {n}" if len(unread) > 1 else ""), _unread_cell(u), "—"] for n, u in enumerate(unread, 1)]
    if evidence:
        scope_rows.append(["证据文件", "、".join(str(e.get("title") or "未命名") for e in evidence) + "（只核对字样是否出现，见 8 节）", "—"])
    if checked:
        # the hashes go under 来源: a content cell holds nothing the user did not write
        scope_rows.append(["核对对象", "；".join(str(c.get("title")) for c in checked) + "（文字一改，本表即过期）",
                           "sha256 " + "；".join(str(c.get("sha256") or "")[:12] for c in checked)])
    md += _table(("事项", "内容", "来源"), scope_rows)

    open_items: List[str] = []
    lost_tender = _unread_names(unread, ("tender",))
    if lost_tender:
        open_items.append(f"招标侧文件未读出（{lost_tender}）：下表的招标要求可能不全，或已被它修改；读出后重新解析")
    for title, topics in _GAP_SECTIONS:
        rows: List[List[str]] = []
        for topic in topics:
            rows += _gap_rows(topic, tender, ours, lots, open_items, comparison, unread=may_answer,
                              evidence=evidence, checks=checks, unread_evidence=_unread_names(unread, ("reference",)))
        if title.startswith("3 "):
            for m in _mentions(ours, "staff"):
                if m.get("value"):
                    lot = str(m.get("lot") or "")
                    rows.append([_with_lot(str(m.get("role") or "其他人员"), lot), NO_TENDER_TEXT, _clip(_value_cell(m)), NO_TENDER_TEXT,
                                 "补招标文件对该岗位的要求原文（证书、专职、在岗）后再对照", _owner_for(ours, lot)])
        if title.startswith("5 "):
            rows += _comparison_rows(comparison, tender, open_items, unread=may_answer)
        md += [f"## {title}", ""]
        md += _table(GAP_HEADER, rows) or ["本节无招标要求原文，也无我方说法。", ""]

    md += ["## 6 技术目录缺口", ""]
    tech_rows: List[List[str]] = []
    for s in tender.get("scores") or []:
        name = f"{s.get('name') or ''} {s.get('score')}".strip()
        tech_rows.append([_with_lot("评分点", str(s.get("lot") or "")), name, "未提供技术标目录", NOT_RESPONDED, "交 bid-tech 排章节后回查", _owner_for(ours, str(s.get("lot") or ""))])
    for s in tender.get("specials") or []:
        if not s.get("not_given"):
            tech_rows.append([_with_lot("点名专项", str(s.get("lot") or "")), _clip(f"{s.get('name')} {s.get('detail') or ''}".strip()),
                              "未提供专项目录", NOT_RESPONDED, "技术标须单列专项章节", _owner_for(ours, str(s.get("lot") or ""))])
    noted = [re.sub(r"\s+", "", str(s.get("note") or "")) for s in (tender.get("scores") or []) + (tender.get("specials") or [])]
    for key, label in (("scoring_points", "评分点"), ("specials", "专项")):
        for p in ho.get(key) or []:
            flat = re.sub(r"\s+", "", str(p.get("text") or ""))
            if flat and not any(x and (x in flat or flat in x) for x in noted):
                tech_rows.append([f"{label} {p.get('requirement_ref')}", _clip(p.get("text"), 120), "未提供技术标目录", NOT_RESPONDED, "交 bid-tech 排章节后回查", TBD])
    if may_answer:
        # the technical proposal may be the file that was not read
        for row in tech_rows:
            row[2], row[3], row[4] = f"未读出：{_clip(may_answer, 30)}", UNKNOWN, "技术标可能就在未读出的文件里；" + row[4]
    md += _table(GAP_HEADER, tech_rows) or ["招标要求里未检出评分点或点名专项。", ""]

    md += ["## 7 澄清与补证", ""]
    md += [f"- {item}" for item in open_items] or ["- （本轮没有可列的缺口：要么资料不足，要么要求与响应逐项对上，仍须人工核验原件）"]
    p0 = (ho.get("p0_reject_scan") or {}).get("items") or []
    if p0:
        # no count here: every number in this draft is one the user wrote, and `civil review` holds it to that
        md += ["", "未解决 P0（资格/废标/★，须人工确认，系统不关闭），逐项如下：", ""]
        quotes = [_quote(str(item.get("exact_text") or item.get("title") or ""), tender, str(item.get("req_id") or "")) for item in p0[:12]]
        md += [f"- {_clip(q, 80)}" for q in dict.fromkeys(quotes) if q] or ["- （均已在上表逐项列出）"]
    summary = (matrix or {}).get("summary") or {}
    if summary:
        md += ["", f"- 解析矩阵：{summary.get('n', 0)} 条要求，其中须人工 {summary.get('human_required', 0)}、待核 {summary.get('review', 0)}。"]
    md += _unplaced(ours)
    if evidence:
        md += ["", "## 8 证据文件字样核对", "",
               "只查我方写的字样在所给证据文件里出现没有。出现不代表证件真实、在有效期内或属于本人；没出现也可能只是文件是扫描件。", ""]
        md += _table(EVIDENCE_HEADER, [[c["label"], c["token"], c["files"], c["state"], c["note"]] for c in checks]) or [
            "本轮没有可核对的字样：证据类事项（授权、资质、人员、业绩、保证金）我方都还没写。", ""]
    md += ["", "条款号 UNSPECIFIED。不判定可投标。", ""]
    return "\n".join(md)


def _flat(text: Any) -> str:
    """For a letter-for-letter search in extracted text: PDF text layers break a name with spaces, a
    certificate prints "注册编号：京…" where a sentence says "注册编号京…"."""
    return re.sub(r"[\s：:]+", "", str(text or ""))


def _evidence_tokens(topic: str, haves: Sequence[Mapping[str, Any]], quotes: Sequence[str]) -> List[str]:
    """What of our side's answer to a row can be looked for in an evidence file: the values we stated -
    a name, a certificate class, a number of a document, an amount. Never a paraphrase."""
    values = [str(m["value"]) for m in haves if m.get("value")]
    if not values and quotes:
        from packing_assistant.tools.tender_facts import extract

        for quote in quotes:
            values += [m.value for m in extract(quote, sides="none").mentions if m.topic == topic and m.value]
    return [v for v in dict.fromkeys(values) if len(_flat(v)) >= 2][:3]


def _check_evidence(label: str, tokens: Sequence[str], evidence: Sequence[Mapping[str, Any]], unread_evidence: str,
                    checks: List[Row], *, about: str = "") -> List[str]:
    """One row of section 8 per token; returns the tokens no evidence file holds.

    ``about`` is the row's own name (项目经理). A file called 项目经理证书.pdf that was read and does not
    hold the name we wrote is the most telling thing this check can find - it is said as 未检出 even
    when some other file could not be read and might, in principle, hold the word."""
    absent: List[str] = []
    named = [str(e.get("title")) for e in evidence if about and about in str(e.get("title") or "")]
    for token in tokens:
        holders = [str(e.get("title") or "未命名") for e in evidence if _flat(token) in _flat(e.get("text"))]
        if holders:
            checks.append({"label": label, "token": token, "files": "、".join(holders), "state": "检出",
                           "note": "只说明字样出现；真伪、有效期、是否本人须核原件"})
        elif named:
            absent.append(token)
            checks.append({"label": label, "token": token, "files": "、".join(named) + " 读到了，里面没有", "state": "未检出",
                           "note": "文件名说的就是这一项，却没有这个字样：核对是不是拿错了人，或拿错了文件"})
        elif unread_evidence:
            checks.append({"label": label, "token": token, "files": f"读到的 {len(evidence)} 份均无；未读出：{_clip(unread_evidence, 30)}",
                           "state": "未能判断", "note": "可能就在未读出的文件里：让它可读后重查"})
        else:
            absent.append(token)
            checks.append({"label": label, "token": token, "files": f"所给 {len(evidence)} 份均无", "state": "未检出",
                           "note": "补该项证据，或核对文件是否给对"})
    return absent


def _gap_rows(topic: str, tender: Facts, ours: Facts, lots: List[str], open_items: List[str],
              comparison: Optional[Sequence[Mapping[str, Any]]] = None, *, unread: str = "",
              evidence: Sequence[Mapping[str, Any]] = (), checks: Optional[List[Row]] = None,
              unread_evidence: str = "") -> List[List[str]]:
    need_all = [m for m in _mentions(tender, topic, "tender") if m.get("value") or m.get("not_given") or topic in ("poa", "seal")]
    have_all = _mentions(ours, topic, "ours")
    if topic == "price_cap":
        have_all = _mentions(ours, "our_price", "ours")
    keys = list(dict.fromkeys([str(m.get("lot") or "") for m in need_all + have_all]))
    rows: List[List[str]] = []
    for lot in keys:
        needs = [m for m in need_all if str(m.get("lot") or "") == lot]
        amended = [m for m in needs if m.get("origin") and m.get("value")]
        need = (amended or [m for m in needs if m.get("value")] or [None])[0]
        haves = [m for m in have_all if str(m.get("lot") or "") == lot]
        if not needs and not haves:
            continue
        label = _with_lot(_LABELS[topic], lot)
        need_cell = (f"{need['value']}（{need['origin']}）" if need.get("origin") else str(need["value"])) if need else (
            NOT_WRITTEN if any(m.get("not_given") for m in needs) else (_clip(needs[0].get("note")) if needs else NO_TENDER_TEXT))
        have_value = next((str(m["value"]) for m in haves if m.get("value")), "")
        have_cell = "；".join(dict.fromkeys(_clip(_value_cell(m)) for m in haves)) if haves else "未提供"
        if len(have_cell) > CELL and have_value:
            # too long with the clauses: keep every value, drop the clauses - never a value for room
            have_cell = "；".join(dict.fromkeys(str(m["value"]) for m in haves if m.get("value")))
        pending = any(_PENDING.search(str(m.get("note") or "")) for m in haves)
        mismatch = _price_gap(str(need["value"]), have_value) if (topic == "price_cap" and need) else _numeric_gap(topic, str(need["value"]) if need else "", have_value)
        # response documents (the workflow's role-tagged sources) answer a field row as well
        answered = _answer_from_documents(topic, str(need["value"]), comparison, tender) if (need and not haves) else {"quotes": [], "conflicts": []}
        quotes = answered["quotes"]
        if quotes:
            have_cell = _clip("；".join(quotes), 120)
            mismatch = "；".join(str(c.get("note")) for c in answered["conflicts"])
        grade = _grade_note(str(need["value"]) if need else "", have_cell if (haves or quotes) else "")
        waiting = next((str(m.get("note")) for m in haves if _PENDING.search(str(m.get("note") or ""))), "")
        if not needs or (not need and not any(m.get("not_given") for m in needs) and topic not in ("poa", "seal")):
            state = NO_TENDER_TEXT
            gap = ("用户称未办结（见响应栏）；" if waiting else "") + "补招标文件对应条款原文后再对照"
        elif not haves and not quotes and unread:
            state, gap = UNKNOWN, f"响应可能就在未读出的文件里（{_clip(unread, 30)}）：让它可读后再对照"
        elif not haves and not quotes:
            state, gap = NOT_RESPONDED, "未见响应内容：补响应原文或证据"
        elif mismatch:
            state, gap = f"{NOT_RESPONDED}·数值不符", mismatch
        elif pending:
            state, gap = NOT_RESPONDED, "用户称未办结（见响应栏）：办结并取得证据后回填"
        else:
            state, gap = RESPONDED, "核对原件：" + ("证书/社保/注册专业" if topic in ("pm", "tech_lead") else "金额、形式、有效期" if topic.startswith("bond") else "与投标函、附件逐字一致")
            if quotes:
                gap = "候选响应原文，出现相同词不代表已实质响应；" + gap
        if grade:
            gap = grade + "；" + gap
        missing_words: List[str] = []
        if evidence and checks is not None and topic in _EVIDENCE_TOPICS and (haves or quotes):
            missing_words = _check_evidence(label, _evidence_tokens(topic, haves, quotes), evidence, unread_evidence, checks,
                                            about=_LABELS[topic])
            if missing_words:
                gap = f"证据文件里未检出「{'」「'.join(missing_words)}」字样（见 8 节）；" + gap
        owner = _owner_for(ours, lot)
        rows.append([label, need_cell, have_cell, state, gap, owner])
        if state != RESPONDED or grade or missing_words:
            open_items.append(f"{label}：{gap}（责任人 {owner}）")
    return rows


def _field_speaks_for(text: str, tender: Facts) -> bool:
    """A requirement line one of the field rows above is about (it holds that field's value)."""
    flat = re.sub(r"\s+", "", text)
    topics = {t for _title, ts in _GAP_SECTIONS for t in ts}
    return any(m.get("side") == "tender" and m.get("topic") in topics and m.get("value")
               and re.sub(r"\s+", "", str(m["value"])) in flat for m in tender.get("mentions") or [])


def _comparison_rows(comparison: Optional[Sequence[Mapping[str, Any]]], tender: Facts, open_items: List[str],
                     *, unread: str = "") -> List[List[str]]:
    rows: List[List[str]] = []
    for row in comparison or []:
        text = str(row.get("requirement") or "")
        if not text or _covered(text, tender) or _field_speaks_for(text, tender):
            continue
        text = _quote(text, tender, "star" if "star" in (row.get("kinds") or []) else "")
        if not text:
            continue
        quotes = "；".join(str(e.get("quote")) for e in row.get("response_evidence") or [])
        notes = "；".join(str(c.get("note")) for c in row.get("conflicts") or [])
        if notes:
            state, gap = f"{NOT_RESPONDED}·数值不符", notes
        elif quotes:
            state, gap = RESPONDED, "候选响应原文，出现相同词不代表已实质响应"
        elif unread:
            state, gap = UNKNOWN, f"响应可能就在未读出的文件里（{_clip(unread, 30)}）：让它可读后再对照"
        else:
            state, gap = NOT_RESPONDED, "未检出对应响应原文"
        label = "★/必须满足项" if "star" in (row.get("kinds") or []) else "招标条款"
        rows.append([f"{label} {row.get('requirement_ref')}", _clip(text, 120), _clip(quotes, 120) or "未提供", state, gap, TBD])
        if state != RESPONDED:
            open_items.append(f"{label} {row.get('requirement_ref')}：{gap}")
    return rows
