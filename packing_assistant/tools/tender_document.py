"""Reading a tender DOCUMENT - eight chapters and a hundred pages - not a typed request.

tools/tender_facts.py reads what somebody types: whose number, which lot, which field. Pointed at a real
招标文件 it goes wrong in a way of its own - every stretch of running text that stands next to the word
招标人 becomes a 招标人 ("将予以拒收", "在监理人收到后56天内将进度应付款支付给承包人"), and the sixty pages of
contract conditions are full of numbers of days that are nobody's 工期.

A tender document says where things are. The values are laid down in two tables - 投标人须知前附表 and
评标办法前附表 - row by row, each under its clause number; the notice in chapter one repeats some of them
as labelled lines. The clauses that get a bid rejected are sentences with a small vocabulary (否决, 不予受理,
拒收, 无效投标) scattered through chapters two, three and seven. So this module reads structure first:

    read(text)            chapters, numbered clauses, table rows - every piece knows where it stands
    is_document(text)     at least two chapters, or a front table
    front_rows(doc)       the rows of the two front tables: number, name, content
    field_mentions(doc)   fields from the front table first, the notice's labelled lines for what it lacks;
                          where the two disagree both are kept and the disagreement is said
    rejections(doc)       every sentence that gets a bid rejected or refused, the clause it cites beside it
    obligations(doc)      front-table rows that lay down a 须 / 不得 on form, sealing, delivery
    scores / specials / forms

Every value is a literal stretch of the document; every piece carries ``ref`` - "第二章 前附表 3.4.1",
"第三章 3.1.5" - which is what a person needs to find it again. Nothing is judged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_CN = "一二三四五六七八九十百"
_CHAPTER = re.compile(r"^#*\s*(第[" + _CN + r"\d]+章)\s*(.*)$")
_TABLE_ROW = re.compile(r"^\|.*\|$")
_RULER = re.compile(r":?-{2,}:?")
#: "3.4 投标保证金" / "1. 总则" / "2.4 计划工期：540日历天。" at the start of a paragraph
_LEAD_NUMBER = re.compile(r"^#*\s*(\d+(?:\.\d+){0,3})[.．、]?\s+(?=\S)|^#*\s*(\d+)[.．、]\s*(?=\S)")
#: "… 。3.4.2 投标人不按 …" inside a paragraph: a clause number at the start of a sentence
_INLINE_NUMBER = re.compile(r"(?:(?<=[。；;])|(?<=[。；;]\s))(\d+(?:\.\d+){1,3})\s+(?=\S)")
_SENTENCE_END = re.compile(r"(?<=。)")
_HEADING_MARK = re.compile(r"^#+\s*")
_FRONT_HEADER = ("条款号", "序号", "编号", "项号", "条款")   # local templates number the front table 1, 2, 3 …
_CONTRACT = re.compile(r"合同条款|合同条件|合同格式|Conditions of Contract", re.I)

_REJECT = re.compile(r"否决其?投标|否决投标|作否决|被否决|予以否决|不予受理|不予接[收受]|予以拒收|拒收|拒绝接收|拒绝受理|无效投标|投标无效|按无效|"
                     r"作无效|无效标|视为无效|废标|取消其?(?:投标|中标)资格|不予通过|不得参[加与](?:本项目|本次)?(?:的)?投标|"
                     r"shall be rejected|will be rejected|be disqualified|non-responsive", re.I)
#: "投标文件有下列情形之一的，按无效投标处理：" - what follows, one item to a paragraph, is the list it announces
_LIST_LEAD = re.compile(r"(?:下列|以下|如下)(?:情形|情况|行为|条件)?.{0,12}[：:]\s*$|[：:]\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[（(]\s*[\d" + _CN + r"]+\s*[)）]|\d+\s*[)）.、]|[" + _CN + r"]+\s*、)\s*")
_NOT_A_REJECTION = re.compile(r"否决所有投标|否决全部投标")
_CITES = re.compile(r"第?\s*(\d+(?:\.\d+){1,3})\s*[项款条]")
_OBLIGES = re.compile(r"须|必须|不得|应当|严禁|不允许|不接受")
_STAR = re.compile(r"[★☆＊]")
_FORM_LIST = re.compile(r"投标文件应包括下列内容|投标文件(?:由|应由)下列(?:部分|内容)(?:组成|构成)")
_FORM_ITEM = re.compile(r"[（(]\s*\d+\s*[)）]\s*([^；;。（(]+)")
_FORM_DIR = re.compile(r"(?:^|[；;：:])\s*[" + _CN + r"]+、\s*([^；;。]+)")
_POINTS = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*分\s*$")
_POINT_PART = re.compile(r"([^：:；;，,。\d][^：:；;，,。]{1,23}?)\s*[：:]\s*(\d+(?:\.\d+)?\s*分)")


@dataclass(frozen=True)
class Piece:
    """One sentence, heading or table row of the document, and where it stands."""

    chapter: str            # "第二章 投标人须知"
    number: str             # "3.4.2"; "" when it stands under no number
    heading: str            # the nearest heading above it
    table: str              # the heading a table stands under when this piece is one of its rows
    cells: Tuple[str, ...]  # the row's cells; () for running text
    text: str               # literal
    line: int               # n-th non-empty line of the source, from 1
    kind: str               # "heading" | "text" | "row" | "header"
    header: Tuple[str, ...] = ()  # a row's column names

    @property
    def chapter_no(self) -> str:
        found = _CHAPTER.match(self.chapter)
        return found.group(1) if found else ""

    @property
    def ref(self) -> str:
        where = "前附表 " if (self.kind == "row" and "前附表" in self.table) else ""
        parts = [self.chapter_no, (where + self.number).strip() or ""]
        shown = " ".join(p for p in parts if p)
        return shown or f"L{self.line}"


@dataclass
class Document:
    pieces: List[Piece] = field(default_factory=list)
    chars: int = 0
    lines: int = 0

    def chapter(self, *names: str) -> List[Piece]:
        return [p for p in self.pieces if any(n in p.chapter for n in names)]

    def numbered(self, number: str, chapter_no: str = "") -> List[Piece]:
        return [p for p in self.pieces if p.number == number and p.kind != "heading" and (not chapter_no or p.chapter_no == chapter_no)]


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_document(text: str) -> bool:
    """A document, not a request: two chapters, or a front table. A pasted page or two is neither - it is
    read the way it always was."""
    body = text or ""
    if len(body) < 1500:
        return False
    chapters = {m.group(1) for line in body.splitlines() for m in [_CHAPTER.match(line.strip())] if m}
    if len(chapters) >= 2:
        return True
    return any(_TABLE_ROW.match(line.strip()) and "条款号" in line and ("条款名称" in line or "编列内容" in line)
               for line in body.splitlines())


def read(text: str) -> Document:
    doc = Document(chars=len(text or ""))
    chapter = heading = number = table_heading = ""
    header: Optional[List[str]] = None
    line_no = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            header = None
            continue
        line_no += 1
        found = _CHAPTER.match(line)
        if found:
            chapter = f"{found.group(1)} {found.group(2).strip()}".strip()
            heading, number, header = chapter, "", None
            doc.pieces.append(Piece(chapter, "", heading, "", (), _HEADING_MARK.sub("", line), line_no, "heading"))
            continue
        if _TABLE_ROW.match(line):
            cells = _cells(line)
            if all(_RULER.fullmatch(c) for c in cells if c):
                continue
            if header is None:
                # what a table is follows from its own header row - a Word reader gives no "#", and the line
                # "投标人须知前附表" above the table is just one more paragraph
                joined = "".join(cells)
                front = cells[0].strip() in _FRONT_HEADER and "格式" not in chapter and (
                    cells[0].strip() == "条款号" or "前附表" in heading or re.search(r"条款名称|编列内容|内容及要求|说明[与和及]要求", joined))
                table_heading = ("投标人须知前附表" if (front and ("条款名称" in joined or "编列内容" in joined))
                                 else "评标办法前附表" if (front and re.search(r"评审因素|评审标准|评分因素|评分标准|分值", joined)) else heading)
                header = cells
                doc.pieces.append(Piece(chapter, "", heading, table_heading, tuple(cells), line, line_no, "header"))
                continue
            row_number = cells[0] if (header and header[0] in _FRONT_HEADER and re.fullmatch(r"[\d.()（）]+", cells[0] or "")) else ""
            doc.pieces.append(Piece(chapter, row_number, heading, table_heading, tuple(cells), line, line_no, "row", tuple(header)))
            continue
        header = None
        is_heading = line.startswith("#")
        body = _HEADING_MARK.sub("", line)
        lead = _LEAD_NUMBER.match(body)
        short_title = len(body) <= 24 and not re.search(r"[。；;：:，,]", body)   # "投标人须知前附表", "一、投标函"
        if is_heading or short_title or (lead and len(body) <= 30 and not re.search(r"[。；;：:]", body)):
            heading = body
            number = (lead.group(1) or lead.group(2)) if lead else ""
            doc.pieces.append(Piece(chapter, number, heading, "", (), body, line_no, "heading"))
            continue
        if lead:
            number = lead.group(1) or lead.group(2)
        # a paragraph may hold several numbered clauses: "3.4.1 …。3.4.2 …。"
        current = number
        cursor = 0
        stretches: List[Tuple[str, str]] = []
        for inner in _INLINE_NUMBER.finditer(body):
            if inner.start() > cursor:
                stretches.append((current, body[cursor:inner.start()]))
            current, cursor = inner.group(1), inner.start()
        stretches.append((current, body[cursor:]))
        for clause_number, stretch in stretches:
            for sentence in _SENTENCE_END.split(stretch):
                if sentence.strip():
                    doc.pieces.append(Piece(chapter, clause_number, heading, "", (), sentence.strip(), line_no, "text"))
        number = current
    doc.lines = line_no
    return doc


# ---------------------------------------------------------------------------
# the two front tables
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FrontRow:
    number: str
    name: str
    content: str
    piece: Piece


def front_rows(doc: Document) -> List[FrontRow]:
    rows: List[FrontRow] = []
    for p in doc.pieces:
        if p.kind == "row" and "前附表" in p.table and len(p.cells) >= 3:
            rows.append(FrontRow(p.cells[0], p.cells[1], "；".join(c for c in p.cells[2:] if c), p))
    return rows


def _parts(content: str) -> List[Tuple[str, str, str]]:
    """"金额：80万元；形式：银行转账…；10.3 缺陷责任期：24个月" as [(label, body, number)]; "" where a part has none."""
    out: List[Tuple[str, str, str]] = []
    for part in re.split(r"[；;]", content):
        part = part.strip()
        if not part:
            continue
        lead = re.match(r"(\d+(?:\.\d+)+)\s*", part)
        number = lead.group(1) if lead else ""
        rest = part[lead.end():] if lead else part
        found = re.match(r"([^：:；;，,。\s]{2,18})\s*[：:]\s*(.+)$", rest)
        out.append((found.group(1), found.group(2).strip(), number) if found else ("", rest, number))
    return out


def field_mentions(doc: Document):
    """Mentions for the facts layer: the front table first, the notice for what the table lacks."""
    from packing_assistant.tools import tender_facts as tf

    table: List[tf.Mention] = []
    for row in front_rows(doc):
        if "评标办法" in row.piece.table:
            continue  # its rows are review standards and scoring, read by scores() and rejections()
        row_topic = tf.document_topic(row.name)
        taken: set = set()
        for label, body, inner in _parts(row.content):
            own = tf.document_topic(label) if label else ""
            topic = own or row_topic
            if not topic and tf._EVAL_METHOD.search(body):
                topic = "eval_method"   # "10.1 本项目采用综合评估法评标"
            if not topic or topic in tf._ALWAYS_OURS or topic in tf._NO_SIDE or topic in tf._STATEMENT_ONLY:
                continue
            if not own and topic in taken:
                continue  # "地址：…" under 招标人 is not a second 招标人
            related = not row_topic or tf._TOPIC[topic].section == tf._TOPIC[row_topic].section
            value = _document_value(topic, body, same_as=related)
            if not value or any(m.topic == topic and _flat(m.value) == _flat(value) for m in table):
                continue  # "招标人名称：…" on the envelope row says nothing the 招标人 row did not
            taken.add(topic)
            ref = row.piece.ref if not inner else f"{row.piece.chapter_no} 前附表 {inner}".strip()
            # two parts of one row about the same field ("履约担保的形式：…；履约担保的金额：…") are told apart by their label
            part_name = re.sub(r"^" + re.escape(tf._TOPIC[topic].label) + r"的?", "", label) if (own and own == row_topic) else ""
            table.append(tf.Mention(topic, "tender", "", value, f"{row.name}：{body}"[:160], row.piece.line, role=part_name, ref=ref))
    if not any(m.topic == "eval_method" for m in table):
        for p in doc.pieces:
            found = tf._EVAL_METHOD.search(p.text) if (p.kind == "heading" and "评标办法" in p.text) else None
            if found:
                table.append(tf.Mention("eval_method", "tender", "", found.group(0), p.text[:160], p.line, ref=p.chapter_no or p.ref))
                break
    have = {m.topic for m in table}
    notice: List[tf.Mention] = []
    for p in doc.chapter("第一章"):
        if p.kind != "text":
            continue
        body = _LEAD_NUMBER.sub("", p.text)
        found = re.match(r"([^：:；;，,。\s]{2,14})\s*[：:]\s*(.+)$", body)
        if found:
            topic = tf.document_topic(found.group(1))
            if topic and topic not in tf._ALWAYS_OURS | tf._NO_SIDE | tf._STATEMENT_ONLY:
                value = _document_value(topic, found.group(2))
                if value:
                    notice.append(tf.Mention(topic, "tender", "", value, p.text[:160], p.line, ref=p.ref))
                continue
        for topic, value in _strict_in_sentence(body):
            notice.append(tf.Mention(topic, "tender", "", value, p.text[:160], p.line, ref=p.ref))
    mentions = list(table)
    for m in notice:
        if m.topic not in have:
            if not any(x.topic == m.topic and _same(x.value, m.value) for x in mentions):
                mentions.append(m)
            continue
        same = [x for x in table if x.topic == m.topic]
        if same and not any(_same(x.value, m.value) or _flat(m.value) in _flat(x.note) or _flat(x.value) in _flat(m.note) for x in same):
            # the notice and the front table disagree: both stand, and whoever reads the draft is told
            mentions.append(tf.Mention(m.topic, "tender", "", m.value, m.note, m.line, origin="招标公告，与前附表不一致", ref=m.ref))
    return mentions


def _flat(text: str) -> str:
    return re.sub(r"[\s,，]+", "", text or "")


def _same(a: str, b: str) -> bool:
    return _flat(a) == _flat(b) or _flat(a) in _flat(b) or _flat(b) in _flat(a)


def _balanced(value: str, source: str) -> str:
    """A value keeps the bracket it opened: "…合格证书（B证）"."""
    for opened, closed in (("（", "）"), ("(", ")")):
        if value.count(opened) > value.count(closed):
            at = source.find(value)
            if at >= 0 and source[at + len(value):at + len(value) + 1] == closed:
                value += closed
    return value


def _document_value(topic: str, body: str, *, same_as: bool = True) -> str:
    """The literal value of a field inside the content laid down for it. A document's text value may be a
    clause long; it is kept whole up to the sentence end and cut only by the table cell."""
    from packing_assistant.tools import tender_facts as tf

    kind = tf._TOPIC[topic].kind
    text = body.strip().rstrip("。；; ")
    if kind in tf._KIND_RE:
        found = tf._KIND_RE[kind].search(text)
        if not found:
            # "开标时间：同投标截止时间" - as written. Not under another field's row: the 递交截止时间 of the
            # 投标保证金 row is the bond's, not the bid's.
            said = re.match(r"同[^，,；;。]{2,12}(?:时间|日期)", text) if (kind == "date" and same_as) else None
            return said.group(0) if said else ""
        value = found.group(0).strip()
        if kind == "date":
            clock = tf._CLOCK.match(text[found.end():].lstrip("，, "))
            if clock:
                value = text[found.start():found.end() + (len(text[found.end():]) - len(text[found.end():].lstrip("，, "))) + clock.end()].strip()
        return value
    if kind == "method":
        found = tf._EVAL_METHOD.search(text)
        return found.group(0) if found else ""
    if kind == "code":
        found = tf._DOC_CODE.search(text)
        return found.group(0) if found else ""
    if kind == "person":
        return _balanced(tf._requirement_text(text), text) or text[:80]
    first = re.split(r"[。]", text)[0].strip()
    return first[:120]


_STRICT = (("tender_no", re.compile(r"(?:招标|项目|采购)编号\s*[：:]\s*([A-Za-z0-9][A-Za-z0-9\-_/〔〕\[\]（）()]{3,40})")),)


def _strict_in_sentence(sentence: str) -> List[Tuple[str, str]]:
    """Inside the notice's running text only what cannot be mistaken: "招标编号：LJZB-2026-SG-0418",
    "投标截止时间…为2026年11月3日9时30分"."""
    from packing_assistant.tools import tender_facts as tf

    out: List[Tuple[str, str]] = []
    for topic, pattern in _STRICT:
        found = pattern.search(sentence)
        if found:
            out.append((topic, found.group(1).rstrip("。，,；;")))
    for start, end, topic in tf._topic_hits(sentence):
        if tf._TOPIC[topic].kind == "date":
            value = _document_value(topic, sentence[end:])
            if value and sentence[end:].find(value) <= 24:
                out.append((topic, value))
    return out


# ---------------------------------------------------------------------------
# what gets a bid rejected
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rejection:
    piece: Piece
    cited: Tuple[Piece, ...]  # the clauses it points at ("第1.4.3项规定的任何一种情形")
    star: bool


def _rejecting_parts(sentence: str) -> List[str]:
    """A sentence, or - when it is a run of "；"-separated items of which one says 不得参加投标 - that item.
    A sentence that announces a list ("有下列情形之一的，否决其投标：（1）…；（2）…") stays whole: its items are
    what it is about."""
    parts = [part.strip() for part in re.split(r"[；;]", sentence) if part.strip()]
    if len(parts) < 3 or len(sentence) <= 160:
        return [sentence]
    lead = next((i for i, part in enumerate(parts) if _REJECT.search(part) or _STAR.search(part)), None)
    if lead is None or re.search(r"[：:]", parts[lead]) and lead + 1 < len(parts) and _LIST_ITEM.match(parts[lead + 1]):
        return [sentence]
    return [part for part in parts if _REJECT.search(part) or _STAR.search(part)]


def rejections(doc: Document) -> List[Rejection]:
    out: List[Rejection] = []
    seen: set = set()
    for p in doc.pieces:
        if p.kind not in ("text", "row") or _CONTRACT.search(p.chapter):
            continue
        texts = [p.text] if p.kind == "text" else [c for c in p.cells[2:] or p.cells]
        if p.kind == "row" and "前附表" not in p.table and any(_STAR.search(c) or _REJECT.search(c) for c in p.cells):
            # a row of a requirements table: "沥青混凝土面层：★上面层采用…；不满足的为无效投标" - the cells, not the bars
            cells = [c for c in p.cells if c and c != "—" and not re.fullmatch(r"[\d.]+", c)]
            texts = ["：".join(cells[:2]) + ("；" + "；".join(cells[2:]) if len(cells) > 2 else "")]
        for text in texts:
            whole_row = p.kind == "row" and "前附表" not in p.table
            for sentence in (_rejecting_parts(text) if p.kind == "text" else [text] if whole_row else re.split(r"[；;。]", text)):
                sentence = sentence.strip()
                star = bool(_STAR.search(sentence))
                if not sentence or not (star or (_REJECT.search(sentence) and not _NOT_A_REJECTION.search(sentence))):
                    continue
                key = _flat(sentence)
                if key in seen:
                    continue
                seen.add(key)
                cited: List[Piece] = []
                for number in _CITES.findall(sentence):
                    if number != p.number:
                        cited += [c for c in doc.pieces if c.number == number and c.kind == "text" and c is not p][:6]
                piece = p if (p.kind == "text" and sentence == p.text) else Piece(p.chapter, p.number, p.heading, p.table, p.cells, sentence, p.line, p.kind)
                out.append(Rejection(piece, tuple(cited), star))
                if p.kind == "text" and not star and _LIST_LEAD.search(sentence):
                    at = doc.pieces.index(p)
                    for item in doc.pieces[at + 1:at + 40]:
                        if item.kind != "text" or not _LIST_ITEM.match(item.text):
                            break
                        mark = _LIST_ITEM.match(item.text).group(0).strip()
                        if _flat(item.text) in seen:
                            continue
                        seen.add(_flat(item.text))
                        number = f"{p.number}{mark}" if p.number else mark
                        out.append(Rejection(Piece(item.chapter, number, item.heading, "", (), item.text, item.line, "text"), (), False))
    return out


def obligations(doc: Document) -> List[Piece]:
    """Front-table content that lays down a 须 / 不得 - binding, sealing, delivery, the account a transfer
    comes from. No rejection word stands in them; the formal review rejects for them all the same."""
    out: List[Piece] = []
    rejected = {_flat(r.piece.text) for r in rejections(doc)}
    for row in front_rows(doc):
        for part in re.split(r"[；;]", row.content):
            part = part.strip()
            if part and _OBLIGES.search(part) and _flat(part) not in rejected:
                out.append(Piece(row.piece.chapter, row.number, row.name, row.piece.table, row.piece.cells, part, row.piece.line, "row"))
    # the notice lays down who may bid at all: "本次招标不接受联合体投标", "拟派项目经理须具备…"
    said = {_flat(p.text) for p in out}
    for p in doc.chapter("第一章"):
        if p.kind == "text" and "资格" in p.heading and _OBLIGES.search(p.text) and _flat(p.text) not in rejected | said:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# scoring rows, named 危大 items, the documents a bid must contain
# ---------------------------------------------------------------------------
def scores(doc: Document) -> List[Tuple[str, str, Piece]]:
    out: List[Tuple[str, str, Piece]] = []
    seen: set = set()
    for p in doc.pieces:
        if p.kind != "row" or "评标" not in p.chapter and "评审" not in p.chapter and "评分" not in p.table:
            continue
        column = next((i for i, h in enumerate(p.header) if re.fullmatch(r"分值|分数|满分|权重|标准分|分值[（(]分[)）]", h.strip())), None)
        if column is not None and column < len(p.cells) and re.fullmatch(r"\d+(?:\.\d+)?(?:\s*分)?", p.cells[column].strip()) and column >= 1:
            name = p.cells[column - 1].strip()
            value = p.cells[column].strip()
            key = (_flat(name), _flat(value))
            if name and len(name) <= 30 and key not in seen:
                seen.add(key)
                out.append((name, value if value.endswith("分") else value + "分", p))
            continue
        points = next((c for c in reversed(p.cells) if _POINTS.match(c)), "")
        if points and len(p.cells) >= 3:
            item = p.cells[-2]
            factor = re.sub(r"评分标准|[（(][^）)]*[)）]", "", p.cells[-3] if len(p.cells) >= 4 else p.cells[1]).strip()
            name = item if len(item) <= 24 else factor
            key = (_flat(name), _flat(points))
            if name and key not in seen:
                seen.add(key)
                out.append((name, points.strip(), p))
            continue
        for text in p.cells[2:]:
            if "分值" in "".join(p.cells[:2]) or "分值构成" in text:
                for name, value in _POINT_PART.findall(text):
                    key = (_flat(name), _flat(value))
                    if key not in seen:
                        seen.add(key)
                        out.append((name.strip(), re.sub(r"\s+", "", value), p))
    return out


def specials(doc: Document):
    from packing_assistant.tools import tender_facts as tf

    out = []
    seen: set = set()
    for p in doc.pieces:
        if p.kind != "text" or _CONTRACT.search(p.chapter):
            continue
        for clause in re.split(r"[；;]", p.text):
            for found in tf._SPECIAL.finditer(clause):
                hazard = re.search(tf._HAZARD, found.group(0))
                name = found.group(0)[hazard.start():] if hazard else found.group(0)  # "深基坑专项施工方案", without 须编制
                # the figure may stand in the clause before: "基坑开挖深度6.8米，…，须编制深基坑专项施工方案"
                detail = tf._SPECIAL_DETAIL.search(clause) or tf._SPECIAL_DETAIL.search(p.text)
                key = hazard.group(0) if hazard else name
                if key in seen:
                    continue
                seen.add(key)
                out.append((name, detail.group(0).strip() if detail else "", p))
    return out


def forms(doc: Document) -> List[Tuple[str, Piece]]:
    out: List[Tuple[str, Piece]] = []
    seen: List[str] = []

    def add(name: str, piece: Piece) -> None:
        name = re.sub(r"^[\s、.．]+|[\s。；;]+$", "", name)
        if not (2 <= len(name) <= 30) or re.search(r"规定的其他材料|其他材料$", name) and any("其他材料" in s for s in seen):
            return
        flat_name = _flat(name)
        if any(flat_name == s or flat_name in s or s in flat_name for s in seen):
            return
        seen.append(flat_name)
        out.append((name, piece))

    composition = re.compile(r"投标文件的?(?:组成|构成)|投标文件由")
    announced = False   # "投标文件由资格证明文件、商务技术文件、报价文件三部分组成：" - the lists follow, paragraph by paragraph
    for p in doc.pieces:
        if p.kind == "heading":
            announced = bool(composition.search(p.text))
        elif p.kind == "text" and composition.search(p.text) and not _FORM_ITEM.search(p.text):
            announced = True
            continue
        if announced and p.kind == "text" and _FORM_ITEM.search(p.text) and not _FORM_LIST.search(p.text):
            for name in _FORM_ITEM.findall(p.text):
                add(name, p)
            continue
        if p.kind == "heading" and "格式" in p.chapter and re.match(r"[" + _CN + r"]+、", p.text):
            add(re.sub(r"^[" + _CN + r"]+、\s*", "", p.text), p)   # "一、投标函": a form of its own
            continue
        if p.kind != "text":
            continue
        if composition.search(p.heading) and not _FORM_LIST.search(p.text) and _FORM_ITEM.search(p.text):
            for name in _FORM_ITEM.findall(p.text):
                add(name, p)
            continue
        if _FORM_LIST.search(p.text):
            for name in _FORM_ITEM.findall(p.text):
                for single in re.split(r"及|和(?=投标函附录)", name) if "投标函及投标函附录" in name else [name]:
                    add(single, p)
        elif "投标文件格式" in p.chapter and p.text.startswith("目录"):
            for name in _FORM_DIR.findall(p.text):
                for single in re.split(r"及(?=投标函附录)", name):
                    add(single, p)
    return out


def summary(doc: Document) -> Dict[str, int]:
    return {"chars": doc.chars, "lines": doc.lines, "chapters": len({p.chapter for p in doc.pieces if p.chapter}),
            "front_rows": len(front_rows(doc)), "rejections": len(rejections(doc)), "obligations": len(obligations(doc)),
            "scores": len(scores(doc)), "specials": len(specials(doc)), "forms": len(forms(doc))}
