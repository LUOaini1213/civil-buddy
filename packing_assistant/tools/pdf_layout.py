"""What a PDF's text layer gives back, put together again: pages, paragraphs, tables.

pypdf returns the text of a page the way it was drawn: every line of a paragraph cut at the page width
("…本招标项目已具备招标\\n条件…"), every table cell on lines of its own -

    1.3.2
    计划工期
    计划工期：540日历天；计划开工日期：2026年12月1日；计划竣工日
    期：2028年5月23日

- the table's header repeated on every page a table runs over, and a page number somewhere on each page.
A sentence cut in two matches no rejection clause, and a front table that is a run of loose lines is no table.

    pages_text(reader)   the pages, each under a marker line "〔第N页〕", rebuilt by rebuild()
    rebuild(text)        lines joined into paragraphs again (a line that fills the page width continues on the
                         next, also across a page break); a table whose header cells came one to a line becomes
                         "| 1.3.2 | 计划工期 | 计划工期：540日历天；… |" rows under one header; page numbers dropped

Nothing is added, corrected or guessed at: every character of the output is a character of the input. What
the rebuild cannot know - where a cell ends when both halves are short - it decides by rules written down
below, and tools/tender_document.py still says where each value stands, now with its page.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

PAGE = re.compile(r"^〔第(\d+)页〕$")
_FOOTER = re.compile(r"^(?:第\s*\d+\s*页(?:\s*[，,/]?\s*共\s*\d+\s*页)?|[-—–]\s*\d+\s*[-—–]|\d+\s*/\s*\d+|Page\s+\d+(?:\s+of\s+\d+)?)$", re.I)
_NUMBER_ONLY = re.compile(r"^\d+(?:\.\d+)*(?:\s*[（(]\s*\d+\s*[)）])?$")
_CHAPTER = re.compile(r"^第[一二三四五六七八九十百\d]+章\s*\S*")
_BLOCK_START = re.compile(r"^(?:第[一二三四五六七八九十百\d]+[章节条]|\d+(?:\.\d+)*[.．、]?\s+\S|\d+[.．、]\s*[一-鿿]"
                          r"|\d+(?:\.\d+)+(?=[一-鿿])(?![米天日年月万元个份名人次分项级倍吨时号％%页])"
                          r"|[（(]\s*[\d一二三四五六七八九十]+\s*[)）]|[一二三四五六七八九十]+\s*、|[★☆＊])")
#: "1. 总则", "1.1 项目概况" - and what a scan's reading makes of them: "1．总则", "1.1项目概况" (no space). Not "3.5米以上".
_CLAUSE_HEADING = re.compile(r"^\d+(?:\.\d+)*[.．、]?\s+\S|^\d+[.．、]\s*[一-鿿]|^\d+(?:\.\d+)+(?=[一-鿿])(?![米天日年月万元个份名人次分项级倍吨时号％%页])")
_POINTS = re.compile(r"^\d+(?:\.\d+)?\s*分?$")
_HEADER_WORDS = ("条款号", "条款名称", "编列内容", "序号", "编号", "项号", "内容及要求", "说明与要求", "说明和要求", "评审因素", "评审标准", "评分因素",
                 "评分项", "评分标准", "评审项目", "评审内容", "分值", "项目", "技术要求", "备注", "项目编码", "项目名称", "计量单位", "单位", "工程量",
                 "合同条款号", "约定内容", "内容", "要求", "评分内容", "评分细则", "权重", "满分")
_NUMBERED_FIRST = ("条款号", "序号", "编号", "项号")


def width(text: str) -> int:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)


def pages_text(pages: Iterable[str]) -> str:
    """Page texts as one text: a marker line before each page, then rebuilt."""
    chunks: List[str] = []
    for number, text in enumerate(pages, 1):
        chunks.append(f"〔第{number}页〕")
        chunks.append(text or "")
    return rebuild("\n".join(chunks))


def is_paged(text: str) -> bool:
    return bool(re.search(r"^〔第\d+页〕$", text or "", re.M))


def _header_run(lines: Sequence[str], at: int) -> int:
    """How many consecutive lines from ``at`` are header cells of a table (0 when fewer than three)."""
    count = 0
    while at + count < len(lines) and lines[at + count] in _HEADER_WORDS and count < 8:
        count += 1
    return count if count >= 3 else 0


def rebuild(text: str) -> str:
    raw = [line.strip() for line in (text or "").splitlines()]
    lines = [line for line in raw if line and not _FOOTER.match(line)]
    body_widths = sorted(width(line) for line in lines if not PAGE.match(line))
    full = body_widths[int(len(body_widths) * 0.9)] if body_widths else 0
    out: List[str] = []
    paragraph: List[str] = []
    pending_pages: List[str] = []
    header: Optional[List[str]] = None
    cells: List[str] = []       # the lines of the row being collected

    def flush_paragraph() -> None:
        if paragraph:
            out.extend(["".join(paragraph), ""])
            paragraph.clear()
        out.extend(pending_pages)
        pending_pages.clear()

    def flush_row() -> None:
        if header is None or not cells:
            cells.clear()
            return
        row = _row(header, cells)
        if row:
            out.append("| " + " | ".join(cell.replace("|", "／") for cell in row) + " |")
        cells.clear()
        out.extend(pending_pages)               # a row cut by a page break stands where it began
        pending_pages.clear()

    def end_table() -> None:
        nonlocal header
        flush_row()
        if header is not None:
            out.append("")
        header = None

    index = 0
    while index < len(lines):
        line = lines[index]
        if PAGE.match(line):
            if header is not None or (paragraph and full and width(paragraph[-1]) >= full * 0.9):
                pending_pages.append(line)      # a row or a paragraph runs over the page break: the marker waits
                if header is not None and not cells:
                    out.extend(pending_pages)   # between two rows the marker is a line of its own
                    pending_pages.clear()
            else:
                flush_paragraph()
                out.extend([line, ""])
            index += 1
            continue
        run = _header_run(lines, index)
        if run:
            found = list(lines[index:index + run])
            if header is not None and found == header:
                index += run                    # the header repeated at the top of the next page: same table
                continue
            flush_paragraph()
            end_table()
            header = found
            out.extend(["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"])
            index += run
            continue
        if header is not None:
            numbered = header[0] in _NUMBERED_FIRST
            # "10.1 本项目采用…" inside row 10 is the row's own content; "1. 总则" after it is the text going on
            inside = bool(cells) and _NUMBER_ONLY.match(cells[0]) and line.startswith(cells[0].split("(")[0].split("（")[0].strip() + ".")
            # "二、技术要求" after a table's last row is the next heading, whatever the table is numbered by
            if _CHAPTER.match(line) or (numbered and _CLAUSE_HEADING.match(line) and not _NUMBER_ONLY.match(line) and not inside) or (
                    re.match(r"^[一二三四五六七八九十]+\s*、", line)):
                end_table()
                continue                        # re-read this line as running text
            if numbered and _NUMBER_ONLY.match(line) and (not cells or len(cells) >= 2):
                flush_row()
            elif not numbered and cells and _ends_row(header, cells) and not _POINTS.match(line):
                flush_row()
            cells.append(line)
            index += 1
            continue
        # running text
        if paragraph and (_BLOCK_START.match(line) or not full or width(paragraph[-1]) < full * 0.9):
            flush_paragraph()
        paragraph.append(line)
        index += 1
    end_table()
    flush_paragraph()
    return "\n".join(out).strip() + "\n"


def _ends_row(header: Sequence[str], cells: Sequence[str]) -> bool:
    """A table with no number column: a row is over once it holds its points and whatever standard text followed
    them fills no further line - the next short line starts the next row."""
    if "分值" not in header and "满分" not in header and "权重" not in header:
        return len(cells) >= len(header)
    points = next((i for i, cell in enumerate(cells) if _POINTS.match(cell)), None)
    return points is not None and len(cells) > points and width(cells[-1]) < 40


def _row(header: Sequence[str], cells: Sequence[str]) -> List[str]:
    """The cells of one row from the lines it was drawn as."""
    columns = len(header)
    lines = list(cells)
    if header[0] in _NUMBERED_FIRST and lines and _NUMBER_ONLY.match(lines[0]):
        number, rest = lines[0], lines[1:]
        if not rest:
            return [number] + [""] * (columns - 1)
        if columns >= 4 and _POINTS.match(rest[-1]) and len(rest) >= 2:
            # 条款号 | 评分因素 | 评分项 | 分值: the points end the row, the line before them is the item
            return [number, "".join(rest[:-2]) if len(rest) > 2 else "", rest[-2], rest[-1]][:columns] + [""] * max(0, columns - 4)
        name = rest[0]
        body = rest[1:]
        # a name that filled its column runs on: "投标人提出问题的截止" / "时间". A short name does not wrap.
        while len(body) >= 2 and width(name) >= 16 and width(body[0]) <= 24 and not re.search(r"[：:；;，,。\d]", body[0]):
            name += body.pop(0)
        last = ""
        if columns >= 4 and header[-1] in ("备注", "说明") and len(body) >= 2:
            last = body.pop()                   # 序号 | 项目 | 技术要求 | 备注: the remark is the row's last line
        return ([number, name, "".join(body)] + [""] * max(0, columns - 3))[:columns - 1] + [last] if last else (
            [number, name, "".join(body)] + [""] * max(0, columns - 3))
    points = next((i for i, cell in enumerate(lines) if _POINTS.match(cell)), None)
    if points is not None and points >= 1 and any(word in header for word in ("分值", "满分", "权重")):
        at = next(i for i, word in enumerate(header) if word in ("分值", "满分", "权重"))
        before = lines[:points]
        named = before[-(at):] if at and len(before) >= at else before
        row = [""] * columns
        for offset, value in enumerate(named[-at:] if at else []):
            row[at - len(named[-at:]) + offset] = value
        if len(before) > at and at:
            row[0] = "".join(before[:len(before) - at + 1])
        row[at] = lines[points]
        if at + 1 < columns:
            row[at + 1] = "".join(lines[points + 1:])
        return row
    if len(lines) >= columns:
        return lines[:columns - 1] + ["".join(lines[columns - 1:])]
    return lines + [""] * (columns - len(lines))
