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
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_CN = "一二三四五六七八九十百"
_CHAPTER = re.compile(r"^#*\s*(第[" + _CN + r"\d]+章)\s*(.*)$")
_TABLE_ROW = re.compile(r"^\|.*\|$")
_RULER = re.compile(r":?-{2,}:?")
#: "3.4 投标保证金" / "1. 总则" / "2.4 计划工期：540日历天。" at the start of a paragraph
_UNIT = "米天日年月万元个份名人次分项级倍吨时号％%页条款章"
_LEAD_NUMBER = re.compile(r"^#*\s*(\d+(?:\.\d+){0,3})[.．、]?\s+(?=\S)|^#*\s*(\d+)[.．、]\s*(?=[^\d\s])"
                          r"|^#*\s*(\d+(?:\.\d+){1,3})(?=[一-鿿])(?![" + _UNIT + r"])")   # "1.1.1根据…": a scan's reading drops the space
#: "… 。3.4.2 投标人不按 …" inside a paragraph: a clause number at the start of a sentence
_INLINE_NUMBER = re.compile(r"(?:(?<=[。；;])|(?<=[。；;]\s))(\d+(?:\.\d+){1,3})(?:\s+(?=\S)|(?=[一-鿿])(?![" + _UNIT + r"]))")
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
    page: int = 0           # the PDF page it stands on; 0 when the source has no pages (Word, text)

    @property
    def chapter_no(self) -> str:
        found = _CHAPTER.match(self.chapter)
        return found.group(1) if found else ""

    @property
    def ref(self) -> str:
        where = "前附表 " if (self.kind == "row" and "前附表" in self.table) else ""
        parts = [self.chapter_no, (where + self.number).strip() or ""]
        shown = " ".join(p for p in parts if p)
        where_page = f"第{self.page}页" if self.page else ""
        return (f"{shown}（{where_page}）" if (shown and where_page) else shown or where_page) or f"L{self.line}"


@dataclass
class Document:
    pieces: List[Piece] = field(default_factory=list)
    chars: int = 0
    lines: int = 0
    ocr: bool = False   # the text is an OCR reading of a scan (office_job marks it): every number needs the original

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
    page = 0
    first = len(doc.pieces)
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            header = None
            continue
        if line.startswith("〔OCR〕"):
            doc.ocr = True
            continue
        marker = _PAGE_MARK.match(line)
        if marker:
            # a PDF read by office_job.pdf_document_text: what follows stands on this page
            for index in range(first, len(doc.pieces)):
                if not doc.pieces[index].page and page:
                    doc.pieces[index] = _on_page(doc.pieces[index], page)
            first, page = len(doc.pieces), int(marker.group(1))
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
            number = (lead.group(1) or lead.group(2) or lead.group(3)) if lead else ""
            doc.pieces.append(Piece(chapter, number, heading, "", (), body, line_no, "heading"))
            continue
        if lead:
            number = lead.group(1) or lead.group(2) or lead.group(3)
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
    if page:
        for index in range(first, len(doc.pieces)):
            doc.pieces[index] = _on_page(doc.pieces[index], page)
    doc.lines = line_no
    return doc


_PAGE_MARK = re.compile(r"^〔第(\d+)页〕$")


def _on_page(piece: Piece, page: int) -> Piece:
    return replace(piece, page=page)


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


_SUBLABEL = re.compile(r"[：:]\s*(?=(?:\d+(?:\.\d+)+\s*)?([^：:；;，,。\s]{2,12})[：:])")
_SUBLABEL_END = re.compile(r"(?:要求|条件|资格|形式|金额|时间|日期|地点|方式|比例|期限|年份|名称|地址|联系人|电话)$")


def _split_parts(content: str) -> List[str]:
    """The parts of a front-table cell: at every "；" - and at a "：" that is followed by another label
    ("…施工业绩：项目经理资格：建筑…"). A scan read by OCR gives "；" back as "：" more often than not; a label is
    known by what it names (a field) or by how it ends (…要求 / …资格 / …金额)."""
    from packing_assistant.tools import tender_facts as tf

    parts: List[str] = []
    for chunk in re.split(r"[；;]", content):
        cursor = 0
        for found in _SUBLABEL.finditer(chunk):
            label = found.group(1)
            # only after a part that already has its own label and value: "形式：银行保函：履约担保的金额：…"
            if re.search(r"[：:]", chunk[cursor:found.start()]) and (tf.document_topic(label) or _SUBLABEL_END.search(label)):
                parts.append(chunk[cursor:found.start()])
                cursor = found.end()
        parts.append(chunk[cursor:])
    return parts


def _parts(content: str) -> List[Tuple[str, str, str]]:
    """"金额：80万元；形式：银行转账…；10.3 缺陷责任期：24个月" as [(label, body, number)]; "" where a part has none."""
    out: List[Tuple[str, str, str]] = []
    for part in _split_parts(content):
        part = part.strip()
        if not part:
            continue
        lead = re.match(r"(\d+(?:\.\d+)+)\s*", part)
        number = lead.group(1) if lead else ""
        rest = part[lead.end():] if lead else part
        found = re.match(r"(?!\d)((?:(?!\d{2})[^：:；;，,。\s]){2,18})\s*[：:]\s*(.+)$", rest)   # "应于2026-10-2709：00" holds a time, not a label
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
                piece = p if (p.kind == "text" and sentence == p.text) else replace(p, text=sentence)
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
                        out.append(Rejection(replace(item, number=number), (), False))
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
                out.append(replace(row.piece, number=row.number, heading=row.name, text=part))
    # the notice lays down who may bid at all: "本次招标不接受联合体投标", "拟派项目经理须具备…"
    said = {_flat(p.text) for p in out}
    for p in doc.chapter("第一章"):
        about_bidders = "资格" in p.heading or re.search(r"投标人|联合体|项目经理|项目负责人", p.text)
        if p.kind == "text" and about_bidders and _OBLIGES.search(p.text) and _flat(p.text) not in rejected | said:
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


#: fields whose value in OUR documents can be set against the tender's and against one another
_OUR_TOPICS = ("duration", "validity", "warranty", "bond", "our_price", "quality", "pm", "tech_lead", "project", "tender_no")
_OUR_PRICE = re.compile(r"(?:投标总报价|投标报价|投标总价|总报价|报价)[^，,；;。]{0,24}?(?:[¥￥]\s*)?(\d[\d,，]*(?:\.\d+)?\s*(?:万元|亿元|元))")
_OUR_PRICE_BEFORE = re.compile(r"[¥￥]\s*(\d[\d,，]*(?:\.\d+)?\s*(?:万元|亿元|元)?)[）)]?\s*的?(?:投标总报价|投标报价|投标总价|总报价)")
_STAGE = re.compile(r"阶段|节点|其中|里程碑|分部|单体|楼栋|每层|标准层")
_QUALITY_WORD = re.compile(r"(?:工程)?质量(?:标准|目标|等级|要求)?\s*(?:达到|为|：|:|承诺)?\s*(合格|优良|优质工程|优质)")
_CONTINUES = re.compile(r"^(?:金额|总额|数额|额度|期限|时间)?\s*(?:为|即|共计?|计|：|:)")


def response_values(text: str, title: str):
    """What one of our own documents says about the fields a tender lays down: [Mention(side="ours", origin=title)].

    A bid document is ours from its first word to its last, so no cue is looked for. It is also long and full
    of numbers, so a value counts only when it stands in the same clause as its field word - "其中基础阶段120日历天"
    is a stage, not the 工期 - and nothing is carried from one clause to the next."""
    from packing_assistant.tools import tender_facts as tf

    found = []
    seen: set = set()
    line_no = 0
    header: List[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            header = []
            continue
        line_no += 1
        if _TABLE_ROW.match(line):
            cells = _cells(line)
            if all(_RULER.fullmatch(c) for c in cells if c):
                continue
            if not header:
                header = cells   # 报价一览表: the field words are the column names, the values stand under them
                continue
            pairs = [(cells[i], cells[i + 1]) for i in range(len(cells) - 1)]          # 项目经理 | 周建华
            pairs += [(header[i], cells[i]) for i in range(min(len(header), len(cells)))]  # 工期（日历天） over 200
            for label, body in pairs:
                topic = tf.document_topic(re.sub(r"[（(][^）)]*[)）]", "", label)) if label and body and "____" not in body else ""
                if topic not in _OUR_TOPICS:
                    continue
                if topic in ("pm", "tech_lead"):
                    value = tf._person(body) if len(body) <= 12 else ""
                elif topic == "our_price":
                    money = tf._MONEY.search(body)
                    bare = re.fullmatch(r"[¥￥]?\s*\d[\d,]*(?:\.\d+)?", body)
                    unit = re.search(r"[（(]\s*(万元|亿元|元)\s*[)）]", label)
                    # "投标总报价（元）" over "33,000,000.00": the unit stands in the column name
                    value = money.group(0).strip() if money else f"{body}{unit.group(1)}" if (bare and unit) else body if bare else ""
                elif topic == "quality":
                    value = body if len(body) <= 12 else ""
                else:
                    kind = tf._TOPIC[topic].kind
                    match = tf._KIND_RE[kind].search(body) if kind in tf._KIND_RE else None
                    unit = re.search(r"[（(]([^）)]+)[)）]", label)
                    value = (match.group(0).strip() if match else
                             f"{body}{unit.group(1)}" if (unit and re.fullmatch(r"\d+(?:\.\d+)?", body)) else "")
                if value:
                    _keep(found, seen, tf.Mention(topic, "ours", "", value, line[:160], line_no, origin=title))
            continue
        header = []
        for sentence in re.split(r"[。；;]", line):
            price = _OUR_PRICE_BEFORE.search(sentence) or _OUR_PRICE.search(sentence)
            if price and "____" not in sentence:
                _keep(found, seen, tf.Mention("our_price", "ours", "", price.group(1).replace("，", ",").strip(), sentence.strip()[:160], line_no, origin=title))
            quality = _QUALITY_WORD.search(sentence)
            if quality and "____" not in sentence:
                _keep(found, seen, tf.Mention("quality", "ours", "", quality.group(1), sentence.strip()[:160], line_no, origin=title))
            clauses = [c.strip() for c in re.split(r"，|,(?!\d)", sentence)]   # "¥200,000.00": that comma ends no clause
            for index, clause in enumerate(clauses):
                if not clause or "____" in clause:
                    continue
                following = clauses[index + 1] if index + 1 < len(clauses) else ""
                for start, end, topic in tf._topic_hits(clause):
                    if topic not in _OUR_TOPICS or topic in ("our_price", "quality"):
                        continue
                    rest = clause[end:]
                    if topic in ("pm", "tech_lead"):
                        value = tf._person_adjacent(rest)
                    elif topic == "duration" and _STAGE.search(clause):
                        continue
                    else:
                        kind = tf._TOPIC[topic].kind
                        match = tf._KIND_RE[kind].search(rest) if kind in tf._KIND_RE else None
                        value = match.group(0).strip() if (match and match.start() <= 12) else ""
                        if not value and kind in tf._KIND_RE and _CONTINUES.match(following):
                            # "提交投标保证金一份，金额为人民币80万元": the clause right after says how much
                            after = tf._KIND_RE[kind].search(following)
                            value = after.group(0).strip() if (after and after.start() <= 12) else ""
                        if not value and kind == "text" and topic == "quality":
                            grade = re.search(r"合格|优良|优质", rest[:16])
                            value = grade.group(0) if grade else ""
                        if not value and kind == "code":
                            code = tf._DOC_CODE.search(rest[:40])
                            value = code.group(0) if code else ""
                    if value:
                        _keep(found, seen, tf.Mention(topic, "ours", "", value, sentence.strip()[:160], line_no, origin=title))
    return found


def _keep(found: list, seen: set, mention) -> None:
    key = (mention.topic, _flat(mention.value), mention.origin)
    if key not in seen:
        seen.add(key)
        found.append(mention)


def consistency(mentions: Sequence) -> List[Dict[str, object]]:
    """Fields our own files do not agree on: [{topic, label, values: [(value, file)], same}]. Only fields that
    at least two files speak of, or one file speaks of twice with different values."""
    from packing_assistant.tools import tender_facts as tf

    by_topic: Dict[str, List] = {}
    for m in mentions:
        by_topic.setdefault(m.topic, []).append(m)
    rows: List[Dict[str, object]] = []
    for topic, items in by_topic.items():
        values = list(dict.fromkeys((_flat(m.value), m.value, m.origin) for m in items))
        distinct = {_amount(v[1]) or v[0] for v in values}   # 3,300.00万元 and 33,000,000.00元 are one amount
        if len(values) < 2:
            continue
        rows.append({"topic": topic, "label": tf._TOPIC[topic].label, "values": [(v[1], v[2]) for v in values], "same": len(distinct) == 1})
    return rows


_AMOUNT = re.compile(r"[¥￥]?\s*(\d[\d,]*(?:\.\d+)?)\s*(亿元|万元|元|日历天|天|日|个月|月|年)?")
_SCALE = {"亿元": ("元", 100_000_000), "万元": ("元", 10_000), "元": ("元", 1), "日历天": ("天", 1), "天": ("天", 1), "日": ("天", 1),
          "个月": ("月", 1), "月": ("月", 1), "年": ("年", 1)}


def _amount(value: str) -> str:
    """"3,300.00万元" -> "元:33000000"; "" when the value is not a number with a unit. For telling whether two
    writings are the same quantity - never for showing."""
    found = _AMOUNT.fullmatch((value or "").strip())
    if not found or not found.group(2):
        return ""
    unit, scale = _SCALE[found.group(2)]
    number = float(found.group(1).replace(",", "")) * scale
    return f"{unit}:{number:.4f}".rstrip("0").rstrip(".")


def found_in(texts: Sequence[Tuple[str, str]], words: Sequence[str]) -> List[str]:
    """The titles of the files in which any of ``words`` occurs, letter for letter after folding whitespace."""
    return [title for title, text in texts if any(_flat(w) and _flat(w) in _flat(text) for w in words)]


def summary(doc: Document) -> Dict[str, int]:
    return {"chars": doc.chars, "lines": doc.lines, "ocr": doc.ocr, "pages": max((p.page for p in doc.pieces), default=0),
            "chapters": len({p.chapter for p in doc.pieces if p.chapter}),
            "front_rows": len(front_rows(doc)), "rejections": len(rejections(doc)), "obligations": len(obligations(doc)),
            "scores": len(scores(doc)), "specials": len(specials(doc)), "forms": len(forms(doc))}
