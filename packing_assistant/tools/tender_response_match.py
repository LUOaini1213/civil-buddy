"""招标要求 ↔ 投标响应：候选对照与数值核对。

纯函数：不调模型、不读盘、不判定资格。输出的每一行都是「给人看的候选」，
`verified` 恒为 False；数值核对只做算术（招标写的数 vs 响应写的数），
结论一律写成「待人工核验」，不写「合格 / 不合格」。

设计取舍全部由基准决定：test/benchmarks/tender_response/cases.json，
`python scripts/eval_tender_response_match.py --variant all` 复现下表
（19 例，51 个应匹配对，14 个数值冲突；含三组干扰项）。

    variant                 link P  link R  link F1  confl R  rows/line
    baseline_4gram           0.816   0.608    0.697    0.000      1.327   ← 改动前的算法
    +dedupe                  0.816   0.608    0.697    0.000      1.000
    +snippets                0.833   0.686    0.753    0.000      1.000
    +words>=3                0.938   0.588    0.723    0.000      1.000
    +triggers                0.957   0.863    0.907    0.000      1.000
    +quantities              0.960   0.941    0.950    1.000      1.000
    +bigram>=4               0.962   0.980    0.971    1.000      1.000
    +phrase>=5 (shipped)     1.000   0.980    0.990    1.000      1.000

2026-09-20 加了 5 个土建施工招标的用例（人员资格、投标有效期、最高限价对报价、质量标准、
质保期、付款条件、BCA workhead，外加一组硬负例）。加进去的当时、解析规则还没动：
link R 0.765、confl R 0.714，51 对里有 11 对落在「解析器根本没抽出这一行」上——匹配算法
没有错，是没有东西可比。补的是 tender_parse._RULES 的七条主题和这里的 price / quality
两个主题，匹配机制一个没改；上表是补完之后的数。

唯一仍漏掉的一对是「须编制施工专项方案 ↔ 施工方案资料待补」：只共享「施工」「方案」
两个常见词，能救它的规则都会带来更多误连。被基准否决、保留为消融开关的机制
（及其数字）见 ABLATIONS 旁的注释。CI 用 `--check` 卡下限。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_TRAILING = re.compile(r"[\s。；;．.，,：:！!？?]+$")
_CLAUSE_SPLIT = re.compile(r"[，,；;。！!？?]")


def _norm(text: Any) -> str:
    return _TRAILING.sub("", str(text or "").strip())


# ---------------------------------------------------------------------------
# 1. 一条招标原文一行
# ---------------------------------------------------------------------------

def requirement_lines(requirements: Sequence[Dict[str, Any]], *, dedupe: bool, snippets: bool) -> List[Dict[str, Any]]:
    """解析器把同一句招标原文拆成 theme / 评分点 / 专项 多条要求；对照表按原文去重。

    theme 类要求只把第一句命中放进 exact_text，其余命中在 snippets 里——此前
    那些句子根本不进对照表。snippets=True 时逐句展开，ref 与命中顺序一一对应。
    """
    rows: List[Dict[str, Any]] = []
    index: Dict[str, Dict[str, Any]] = {}
    for req in requirements:
        refs = [r for r in str(req.get("requirement_ref") or "").split(",") if r]
        texts = [str(req.get("exact_text") or "")]
        if snippets:
            texts += [str(s) for s in (req.get("snippets") or []) if str(s) not in texts]
        for position, text in enumerate(texts):
            if not text.strip():
                continue
            ref = refs[position] if position < len(refs) else (refs[0] if refs else "")
            if position == 0 and len(texts) == 1:
                ref = str(req.get("requirement_ref") or ref)
            key = _norm(text)
            kind = str(req.get("item_kind") or "")
            if dedupe and key in index:
                row = index[key]
                if kind and kind not in row["kinds"]:
                    row["kinds"].append(kind)
                continue
            row = {"requirement_ref": ref, "requirement": text, "kinds": [kind] if kind else []}
            rows.append(row)
            index[key] = row
    return rows


# ---------------------------------------------------------------------------
# 2. 候选匹配
# ---------------------------------------------------------------------------

_CJK_RUN = re.compile(r"[一-鿿]+")
_ALNUM_RUN = re.compile(r"[A-Za-z0-9_-]{4,}")
_WORD = re.compile(r"[A-Za-z][A-Za-z-]{3,}")
_EN_STOP = frozenset(
    "shall will with within from that this have has been being must should their there which would could"
    " tenderer tenderers tender bidder bidders company calendar days day months month years year weeks week"
    " than less more least most not the and for are our your its into upon under over such each other".split()
)
# 标书里到处都是的二字组，不携带「是哪条要求」的信息
_CJK_STOP_BIGRAMS = frozenset(
    "投标 标人 人须 须提 提供 须具 具备 我司 公司 项目 工程 见附 附件 采用 使用 进行 以及 不得 不少 少于"
    " 应当 要求 文件 材料 资料 证明 有效 复印 印件 相关 负责 承诺 本项 目采 须在 须使 须采 须编 编制".split()
)


def _cjk_ngrams(text: str, n: int) -> set:
    grams = set()
    for run in _CJK_RUN.findall(text):
        grams.update(run[i:i + n] for i in range(len(run) - n + 1))
    return grams


def _short_runs(text: str) -> set:
    return {run for run in _CJK_RUN.findall(text) if 2 <= len(run) <= 3}


def _word_stems(text: str) -> set:
    stems = set()
    for word in _WORD.findall(text):
        low = word.lower()
        if low in _EN_STOP:
            continue
        stems.add(low[:6] if len(low) > 5 else low)
    return stems


def _legacy_anchors(quote: str) -> set:
    return {part[i:i + 4] for part in re.findall(r"[一-鿿]{4,}|[A-Za-z0-9_-]{4,}", quote)
            for i in range(len(part) - 3)}


def _trigger_patterns(line: str) -> List[str]:
    from packing_assistant.tools.tender_parse import rule_patterns_for_line

    return rule_patterns_for_line(line)


# ---------------------------------------------------------------------------
# 3. 数值
# ---------------------------------------------------------------------------

# (topic, 中文标签, 关键词, 单位类, 招标未写比较词时的默认方向)
_TOPICS: Tuple[Tuple[str, str, str, str, str], ...] = (
    ("validity", "投标有效期", r"投标有效期|报价有效期|bid validity|tender validity|validity period|tender remains? valid|remains? valid for", "time", "min"),
    ("warranty", "质保期", r"质保期|保修期|质量保证期|缺陷责任期|defects liability|warranty", "time", "min"),
    ("delivery", "交货期", r"交货期|交货时间|供货期|到货|交货|delivery|deliver", "time", "max"),
    ("duration", "工期", r"总工期|工期|竣工|完工|封顶|按期|如期|completion|completed|complete the works", "time", "max"),
    ("bond", "保证金", r"保证金|保函|bid bond|security deposit", "money", "equal"),
    ("payload", "货载/限重", r"货载|限重|最大重量|单件重|payload|weight limit", "mass", "max"),
    ("track_record", "业绩", r"业绩|类似项目|similar projects?|track record", "count", "min"),
    # 招标写「最高限价」，响应写「投标报价」：关键词不同，只有主题能把两句连上。报价超过限价才算数值不符。
    ("price", "报价/最高限价", r"最高投标限价|最高限价|招标控制价|控制价|拦标价|投标总报价|投标报价|投标总价|总报价", "money", "max"),
    # 质量标准没有可比的数；列为主题只为了让「质量标准：合格」能带到「质量目标：合格」那一句。
    ("quality", "质量标准", r"质量标准|质量目标|质量要求|质量等级|质量承诺", "grade", "equal"),
)
_TOPIC_RE = {tid: re.compile(pattern, re.I) for tid, _label, pattern, _cls, _default in _TOPICS}
_TOPIC_META = {tid: (label, cls, default) for tid, label, _pattern, cls, default in _TOPICS}

# 单位 → (可比组, 换算到组内基准的系数)
_UNITS: Tuple[Tuple[str, str, str, float], ...] = (
    ("time", r"个?工作日|working days?|business days?", "workdays", 1.0),
    ("time", r"日历天|日历日|calendar days?|天|日|days?", "days", 1.0),
    ("time", r"周|weeks?", "days", 7.0),
    ("time", r"个月|月|months?", "months", 1.0),
    ("time", r"年|years?", "months", 12.0),
    ("money", r"万元|万", "yuan", 10000.0),
    ("money", r"元", "yuan", 1.0),
    ("mass", r"吨|tonnes?|tons?|t\b", "kg", 1000.0),
    ("mass", r"公斤|千克|kg", "kg", 1.0),
    ("count", r"项|个|projects?", "items", 1.0),
)
# 日期不是数量：「2026年12月31日前完工」里的 2026年 / 12月 / 31日 不得被读成工期。
_DATE = re.compile(r"\d{4}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*[日号])?|\d{1,2}\s*月\s*\d{1,2}\s*[日号]"
                   r"|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}", re.I)
_MIN_WORDS = re.compile(r"不少于|不低于|不小于|不短于|至少|以上|≥|not less than|at least|minimum|no less than", re.I)
_MAX_WORDS = re.compile(r"不超过|不得超过|不大于|不多于|不长于|以内|之内|≤|within|not more than|not exceed|no more than|maximum|no later than", re.I)


def _quantities(line: str) -> List[Dict[str, Any]]:
    """一句话里「主题词 … 数 + 单位」。主题取同一分句里数值之前最近的主题词；
    分句里没有主题词、而整句只有一个主题时，归给那个主题。单位类必须与主题相符
    （保证金只认金额，工期只认时间），所以「9月1日汇出」「40HQ」「12 engineers」都不算。"""
    found: List[Dict[str, Any]] = []
    line = _DATE.sub(lambda m: " " * len(m.group(0)), line)  # 等长抹掉，span 仍对得上原句
    line_topics = [tid for tid, rx in _TOPIC_RE.items() if rx.search(line)]
    position = 0
    for clause in _CLAUSE_SPLIT.split(line):
        clause_start = position
        position += len(clause) + 1
        if not clause.strip():
            continue
        hits = sorted((m.start(), tid) for tid, rx in _TOPIC_RE.items() for m in rx.finditer(clause))
        for cls, unit_pattern, group, factor in _UNITS:
            for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:" + unit_pattern + r")", clause, re.I):
                before = [tid for start, tid in hits if start <= m.start() and _TOPIC_META[tid][1] == cls]
                candidates = before[-1:] or [tid for _s, tid in hits if _TOPIC_META[tid][1] == cls][:1]
                if not candidates and len(line_topics) == 1 and _TOPIC_META[line_topics[0]][1] == cls:
                    candidates = line_topics
                if not candidates:
                    continue
                span = (clause_start + m.start(), clause_start + m.end())
                if any(q["span"][0] <= span[0] < q["span"][1] for q in found):
                    continue  # 「日历天」已认领的数，不再让「天」「日」重复认领
                tail = clause[m.end():m.end() + 2]
                window = clause[max(0, m.start() - 12):m.start()] + " " + tail
                comparator = "min" if _MIN_WORDS.search(window) else "max" if _MAX_WORDS.search(window) or tail.startswith("内") else None
                found.append({"topic": candidates[0], "value": float(m.group(1)) * factor, "group": group,
                              "text": m.group(0).strip(), "comparator": comparator, "span": span})
    return sorted(found, key=lambda q: q["span"][0])


def _compare_quantities(requirement: str, response: str) -> List[Dict[str, Any]]:
    required, offered = _quantities(requirement), _quantities(response)
    conflicts: List[Dict[str, Any]] = []
    for tid in dict.fromkeys(q["topic"] for q in required):
        need = [q for q in required if q["topic"] == tid]
        have = [q for q in offered if q["topic"] == tid]
        if not have or len(need) != len(have):
            continue  # 个数对不上就不配对：宁可不说，也不把总工期和节点工期配错
        label, _cls, default = _TOPIC_META[tid]
        for n, h in zip(need, have):
            if n["group"] != h["group"]:
                continue  # 「90天」对「3个月」不做换算，留给人看
            direction = n["comparator"] or default
            ok = h["value"] >= n["value"] if direction == "min" else h["value"] <= n["value"] if direction == "max" else h["value"] == n["value"]
            if ok:
                continue
            relation = {"min": "低于", "max": "超过", "equal": "不同于"}[direction]
            conflicts.append({"topic": tid, "label": label, "required": n["text"], "offered": h["text"],
                              "direction": direction,
                              "note": f"{label}：响应 {h['text']} {relation}招标 {n['text']}，待人工核验"})
    return conflicts


# ---------------------------------------------------------------------------
# 4. 对照
# ---------------------------------------------------------------------------

_OFF = dict(dedupe=False, snippets=False, words=False, triggers=False, quantities=False, short_runs=False,
            bigram_min=0, words_min=3, phrase_len=4, special_trigger=False)
_SHIPPED = dict(dedupe=True, snippets=True, words=True, triggers=True, quantities=True, short_runs=False,
                bigram_min=4, words_min=3, phrase_len=5, special_trigger=False)

#: 消融表。前七行是逐项累加得到 shipped 的过程，其余是被基准否决、留作复测开关的机制。
#: 数字见模块 docstring，`python scripts/eval_tender_response_match.py --variant all` 复现。
ABLATIONS: Dict[str, Dict[str, Any]] = {
    "baseline_4gram": dict(_OFF),
    "+dedupe": dict(_OFF, dedupe=True),
    "+snippets": dict(_OFF, dedupe=True, snippets=True),
    "+words>=3": dict(_OFF, dedupe=True, snippets=True, words=True),
    "+triggers": dict(_OFF, dedupe=True, snippets=True, words=True, triggers=True),
    "+quantities": dict(_OFF, dedupe=True, snippets=True, words=True, triggers=True, quantities=True),
    "+bigram>=4": dict(_SHIPPED, phrase_len=4),
    "+phrase>=5 (shipped)": dict(_SHIPPED),
    # —— 否决 ——
    # 英文共享词 >=2：「last three years」这类套话就够两个词，多出误连；>=3 不丢召回。
    "rejected: words>=2": dict(_SHIPPED, words_min=2),
    # 短句时把 2–3 字整段当锚点：召回 +0。它能救的句子都已被触发词和数值主题救回。
    "rejected: short_runs": dict(_SHIPPED, short_runs=True),
    # 共享二字组 >=2：召回到 1.000，但「近三年」一个套话就是两个二字组，精确率掉到 0.91。
    "rejected: bigram>=2": dict(_SHIPPED, bigram_min=2),
    # 共享二字组 >=3：一个共同的四字短语恰好产生三个二字组，等于把 phrase>=5 挡掉的
    # 「货物运输」类套话又放回来。
    "rejected: bigram>=3": dict(_SHIPPED, bigram_min=3),
    # 不用二字组：丢掉「财务报表 ↔ 财务审计报告」这类换了说法的响应。
    "rejected: no bigrams": dict(_SHIPPED, bigram_min=0),
    # 专项要求 ↔ 任何含「方案」的响应：基准上召回 1.000、只多 1 个误连，F1 与 shipped 持平；
    # 但标书里「付款方案 / 实施方案 / 应急方案」遍地都是，基准只放了一个干扰项，
    # 低估了它的噪声。宁可让那一对（施工专项方案 ↔ 施工方案资料待补）显示为未匹配。
    "rejected: plan_keyword": dict(_SHIPPED, special_trigger=True),
}
ABLATIONS["shipped"] = dict(_SHIPPED)


def _reasons(requirement: str, line: str, *, words: bool, triggers: bool, quantities: bool,
             short_runs: bool, bigram_min: int, words_min: int, phrase_len: int, special_trigger: bool) -> List[str]:
    reasons: List[str] = []
    if words:
        if _cjk_ngrams(requirement, phrase_len) & _cjk_ngrams(line, phrase_len):
            reasons.append("same_phrase")
        shared = _word_stems(requirement) & _word_stems(line)
        if len(shared) >= words_min:
            reasons.append("same_words")
    elif any(anchor in line for anchor in _legacy_anchors(requirement)):
        reasons.append("same_phrase")
    if triggers and any(re.search(p, line, re.I) for p in _trigger_patterns(requirement)):
        reasons.append("same_keyword")
    if special_trigger and re.search(r"专项|危大|method statement", requirement, re.I) and re.search(r"方案|method statement", line, re.I):
        reasons.append("plan_keyword")
    if quantities:
        req_topics = {tid for tid, rx in _TOPIC_RE.items() if rx.search(requirement)}
        if any(_TOPIC_RE[tid].search(line) for tid in req_topics):
            reasons.append("same_quantity_topic")
    if short_runs and not _cjk_ngrams(requirement, 4) and any(run in line for run in _short_runs(requirement)):
        reasons.append("short_run")
    if bigram_min:
        shared_bigrams = (_cjk_ngrams(requirement, 2) & _cjk_ngrams(line, 2)) - _CJK_STOP_BIGRAMS
        if len(shared_bigrams) >= bigram_min:
            reasons.append("shared_bigrams")
    return reasons


def compare_responses(requirements: Sequence[Dict[str, Any]], sources: Sequence[Dict[str, Any]], *,
                      dedupe: bool = True, snippets: bool = True, words: bool = True, triggers: bool = True,
                      quantities: bool = True, short_runs: bool = False, bigram_min: int = 4,
                      words_min: int = 3, phrase_len: int = 5, special_trigger: bool = False) -> List[Dict[str, Any]]:
    """一条招标原文一行；每行列出候选响应原文、匹配理由和数值不符项。"""
    responses = [s for s in sources if s.get("role") == "response"]
    compared: List[Dict[str, Any]] = []
    for row in requirement_lines(requirements, dedupe=dedupe, snippets=snippets):
        quote = row["requirement"]
        matches: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        for source in responses:
            offset = 0
            for line in source["text"].splitlines(keepends=True):
                text = line.rstrip("\r\n")
                reasons = _reasons(quote, text, words=words, triggers=triggers, quantities=quantities,
                                   short_runs=short_runs, bigram_min=bigram_min, words_min=words_min,
                                   phrase_len=phrase_len, special_trigger=special_trigger) if text.strip() else []
                if reasons:
                    start = source.get("start", 0) + offset
                    matches.append({"source_id": source["source_id"], "quote": text, "start": start,
                                    "end": start + len(text), "matched_by": reasons})
                    if quantities:
                        for conflict in _compare_quantities(quote, text):
                            conflicts.append({**conflict, "source_id": source["source_id"], "response_quote": text})
                offset += len(line)
        status = ("conflict_requires_review" if conflicts else "candidate_requires_review" if matches
                  else "not_matched" if responses else "not_provided")
        compared.append({"requirement_ref": row["requirement_ref"], "requirement": quote, "kinds": row["kinds"],
                         "status": status, "response_evidence": matches, "conflicts": conflicts, "verified": False})
    return compared
