"""Small, dependency-free Markdown to editable WordprocessingML conversion.

Only document content is emitted: no macros, fields, external relationships,
embedded files or signature objects. Source strings never become executable code.
"""

from __future__ import annotations

import html
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("w", W)

_INVALID_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.+?)\s*$")
_LIST = re.compile(r"^(\s*)([-+*]|\d+[.)])\s+(.+)$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_INLINE = re.compile(
    r"(`+)([^`]*?)\1|\*\*(.+?)\*\*|(?<!\w)__(.+?)__(?!\w)|"
    r"(?<!\*)\*([^*]+?)\*(?!\*)|(?<!\w)_([^_]+?)_(?!\w)|"
    r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)"
)


def _w(parent: ET.Element, tag: str, text: str | None = None, **attrs: object) -> ET.Element:
    node = ET.SubElement(parent, f"{{{W}}}{tag}", {f"{{{W}}}{name}": str(value) for name, value in attrs.items()})
    node.text = text
    return node


def _xml(node: ET.Element) -> bytes:
    return ET.tostring(node, encoding="utf-8", xml_declaration=True)


def _run(paragraph: ET.Element, text: str, *, bold: bool = False, italic: bool = False, code: bool = False) -> None:
    if _INVALID_XML.search(text):
        raise ValueError("Markdown 含 Word/XML 不支持的控制字符")
    run = _w(paragraph, "r")
    if bold or italic or code:
        props = _w(run, "rPr")
        if bold:
            _w(props, "b")
        if italic:
            _w(props, "i")
        if code:
            _w(props, "rFonts", ascii="Consolas", hAnsi="Consolas", eastAsia="宋体")
    for piece in re.split(r"([\n\t])", text):
        if piece == "\n":
            _w(run, "br")
        elif piece == "\t":
            _w(run, "tab")
        elif piece:
            node = _w(run, "t", piece)
            node.set(f"{{{XML}}}space", "preserve")


def _inline(paragraph: ET.Element, text: str, *, decode: bool = True, bold: bool = False) -> None:
    """Render supported inline syntax; keep malformed or unsupported text intact."""
    def value(raw: str) -> str:
        return html.unescape(raw) if decode else raw

    offset = 0
    for match in _INLINE.finditer(text):
        _run(paragraph, value(text[offset:match.start()]), bold=bold)
        if match.group(1):
            _run(paragraph, match.group(2), bold=bold, code=True)
        elif match.group(3) is not None or match.group(4) is not None:
            _run(paragraph, value(match.group(3) or match.group(4)), bold=True)
        elif match.group(5) is not None or match.group(6) is not None:
            _run(paragraph, value(match.group(5) or match.group(6)), bold=bold, italic=True)
        else:
            # Preserve link destinations as editable text, without external rels.
            _run(paragraph, value(match.group(7) + " (" + match.group(8) + ")"), bold=bold)
        offset = match.end()
    _run(paragraph, value(text[offset:]), bold=bold)


def _paragraph(parent: ET.Element, text: str, *, style: str = "", literal: bool = False,
               number: int | None = None, level: int = 0) -> ET.Element:
    paragraph = _w(parent, "p")
    if style or number is not None:
        props = _w(paragraph, "pPr")
        if style:
            _w(props, "pStyle", val=style)
        if number is not None:
            numbering = _w(props, "numPr")
            _w(numbering, "ilvl", val=level)
            _w(numbering, "numId", val=number)
    if literal:
        _run(paragraph, text, code=True)
    else:
        _inline(paragraph, text)
    return paragraph


def _table_cells(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith(r"\|"):
        row = row[:-1]
    # Split outside inline code and escaped pipes; decode entities exactly once
    # later, so an encoded literal pipe is never mistaken for a column boundary.
    cells, part = [], []
    code_ticks = 0
    index = 0
    while index < len(row):
        char = row[index]
        if char == "\\" and index + 1 < len(row) and row[index + 1] == "|":
            part.append("|")
            index += 2
            continue
        if char == "`":
            end = index + 1
            while end < len(row) and row[end] == "`":
                end += 1
            count = end - index
            if not code_ticks:
                code_ticks = count
            elif code_ticks == count:
                code_ticks = 0
            part.append(row[index:end])
            index = end
            continue
        if char == "|" and not code_ticks:
            cells.append("".join(part).strip())
            part = []
        else:
            part.append(char)
        index += 1
    cells.append("".join(part).strip())
    return cells


def _is_table(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    header, separator = _table_cells(lines[index]), _table_cells(lines[index + 1])
    return bool(header) and len(header) == len(separator) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator)


def _table(body: ET.Element, rows: list[list[str]]) -> None:
    columns = max(map(len, rows))
    if columns > 63:
        raise ValueError("Word 表格最多支持 63 列，请先拆分表格")
    table = _w(body, "tbl")
    props = _w(table, "tblPr")
    _w(props, "tblStyle", val="TableGrid")
    _w(props, "tblW", w=0, type="auto")
    borders = _w(props, "tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        _w(borders, edge, val="single", sz=4, color="B8C1CC")
    grid = _w(table, "tblGrid")
    width = max(1, 9600 // columns)
    for _ in range(columns):
        _w(grid, "gridCol", w=width)
    for index, row in enumerate(rows):
        tr = _w(table, "tr")
        if index == 0:
            _w(_w(tr, "trPr"), "tblHeader")
        for value in row + [""] * (columns - len(row)):
            cell = _w(tr, "tc")
            _w(_w(cell, "tcPr"), "tcW", w=width, type="dxa")
            paragraph = _w(cell, "p")
            _inline(paragraph, value, bold=index == 0)


class _Numbering:
    def __init__(self) -> None:
        self.root = ET.Element(f"{{{W}}}numbering")
        for identifier, kind in ((0, "bullet"), (1, "decimal")):
            abstract = _w(self.root, "abstractNum", abstractNumId=identifier)
            _w(abstract, "multiLevelType", val="multilevel")
            for level in range(9):
                item = _w(abstract, "lvl", ilvl=level)
                _w(item, "start", val=1)
                _w(item, "numFmt", val=kind)
                _w(item, "lvlText", val="•" if kind == "bullet" else f"%{level + 1}.")
                _w(item, "lvlJc", val="left")
                _w(_w(item, "pPr"), "ind", left=360 * (level + 1), hanging=240)
        _w(_w(self.root, "num", numId=1), "abstractNumId", val=0)
        self.next_id = 2
        self.ordered: dict[int, tuple[int, int]] = {}

    def reset(self) -> None:
        self.ordered.clear()

    def item(self, marker: str, level: int) -> int:
        if marker in "-+*":
            self.ordered.pop(level, None)
            return 1
        value = int(marker[:-1])
        if value > 2_147_483_647:
            raise ValueError("Word 有序列表编号超出支持范围")
        previous = self.ordered.get(level)
        if previous and previous[1] + 1 == value:
            identifier = previous[0]
        else:
            identifier = self.next_id
            self.next_id += 1
            number = _w(self.root, "num", numId=identifier)
            _w(number, "abstractNumId", val=1)
            _w(_w(number, "lvlOverride", ilvl=level), "startOverride", val=value)
        self.ordered[level] = (identifier, value)
        for depth in list(self.ordered):
            if depth > level:
                self.ordered.pop(depth)
        return identifier


def _styles() -> ET.Element:
    styles = ET.Element(f"{{{W}}}styles")
    defaults = _w(styles, "docDefaults")
    run = _w(_w(defaults, "rPrDefault"), "rPr")
    _w(run, "rFonts", ascii="Calibri", hAnsi="Calibri", eastAsia="宋体")
    _w(run, "sz", val=22)
    _w(run, "lang", val="zh-CN", eastAsia="zh-CN")
    paragraph = _w(_w(defaults, "pPrDefault"), "pPr")
    _w(paragraph, "spacing", after=100, line=300, lineRule="auto")
    normal = _w(styles, "style", type="paragraph", default=1, styleId="Normal")
    _w(normal, "name", val="Normal")
    for level, size in enumerate((36, 30, 26, 24, 22, 22), 1):
        style = _w(styles, "style", type="paragraph", styleId=f"Heading{level}")
        _w(style, "name", val=f"heading {level}")
        _w(style, "basedOn", val="Normal")
        _w(style, "next", val="Normal")
        _w(style, "qFormat")
        props = _w(style, "pPr")
        _w(props, "keepNext")
        _w(props, "spacing", before=220, after=100)
        _w(props, "outlineLvl", val=level - 1)
        run = _w(style, "rPr")
        _w(run, "b")
        _w(run, "sz", val=size)
    quote = _w(styles, "style", type="paragraph", styleId="Quote")
    _w(quote, "name", val="Quote")
    _w(quote, "basedOn", val="Normal")
    _w(_w(quote, "pPr"), "ind", left=360)
    code = _w(styles, "style", type="paragraph", styleId="Code")
    _w(code, "name", val="Code")
    _w(code, "basedOn", val="Normal")
    _w(_w(code, "pPr"), "spacing", before=0, after=0)
    table = _w(styles, "style", type="table", styleId="TableGrid")
    _w(table, "name", val="Table Grid")
    return styles


def markdown_docx_bytes(markdown: str) -> bytes:
    """Return a real .docx package, raising on content that cannot be preserved."""
    if not markdown.strip():
        raise ValueError("Markdown 内容为空，无法生成 Word 文档")
    if _INVALID_XML.search(markdown):
        raise ValueError("Markdown 含 Word/XML 不支持的控制字符")
    document = ET.Element(f"{{{W}}}document")
    body = _w(document, "body")
    numbering = _Numbering()
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            numbering.reset()
            continue
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            index += 1
            while index < len(lines):
                close = _FENCE.match(lines[index])
                if close and close.group(1)[0] == marker[0] and len(close.group(1)) >= len(marker) and not close.group(2).strip():
                    index += 1
                    break
                _paragraph(body, lines[index], style="Code", literal=True)
                index += 1
            numbering.reset()
            continue
        heading = _HEADING.match(line)
        if heading:
            title = re.sub(r"\s+#+\s*$", "", heading.group(2))
            _paragraph(body, title, style=f"Heading{len(heading.group(1))}")
            index += 1
            numbering.reset()
            continue
        if _is_table(lines, index):
            rows = [_table_cells(line)]
            index += 2
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(_table_cells(lines[index]))
                index += 1
            _table(body, rows)
            numbering.reset()
            continue
        item = _LIST.match(line)
        if item:
            level = min(8, len(item.group(1).expandtabs(4)) // 2)
            _paragraph(body, item.group(3), number=numbering.item(item.group(2), level), level=level)
            index += 1
            continue
        if line.lstrip().startswith(">"):
            _paragraph(body, re.sub(r"^\s*>\s?", "", line), style="Quote")
            index += 1
            numbering.reset()
            continue
        # Soft-wrapped source lines stay in one editable paragraph. Explicit
        # line boundaries are retained as breaks, preserving user record text.
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not (
            _HEADING.match(lines[index]) or _LIST.match(lines[index]) or _FENCE.match(lines[index])
            or lines[index].lstrip().startswith(">") or _is_table(lines, index)
        ):
            paragraph.append(lines[index])
            index += 1
        _paragraph(body, "\n".join(paragraph))
        numbering.reset()
    # Word requires a paragraph after a final table in some editing contexts.
    if len(body) and body[-1].tag == f"{{{W}}}tbl":
        _paragraph(body, "")
    section = _w(body, "sectPr")
    _w(section, "pgSz", w=11906, h=16838)
    _w(section, "pgMar", top=1134, right=1134, bottom=1134, left=1134, header=708, footer=708, gutter=0)
    content_types = ET.Element(f"{{{CONTENT}}}Types")
    ET.SubElement(content_types, f"{{{CONTENT}}}Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    ET.SubElement(content_types, f"{{{CONTENT}}}Default", Extension="xml", ContentType="application/xml")
    for name, kind in (("document", "document.main"), ("styles", "styles"), ("numbering", "numbering")):
        ET.SubElement(content_types, f"{{{CONTENT}}}Override", PartName=f"/word/{name}.xml",
                      ContentType=f"application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml")
    package_rels = ET.Element(f"{{{REL}}}Relationships")
    ET.SubElement(package_rels, f"{{{REL}}}Relationship", Id="rId1", Type=OFFICE_REL + "/officeDocument", Target="word/document.xml")
    document_rels = ET.Element(f"{{{REL}}}Relationships")
    for index, name in enumerate(("styles", "numbering"), 1):
        ET.SubElement(document_rels, f"{{{REL}}}Relationship", Id=f"rId{index}", Type=OFFICE_REL + "/" + name, Target=name + ".xml")
    with BytesIO() as buffer:
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as package:
            for name, node in (("[Content_Types].xml", content_types), ("_rels/.rels", package_rels),
                               ("word/document.xml", document), ("word/_rels/document.xml.rels", document_rels),
                               ("word/styles.xml", _styles()), ("word/numbering.xml", numbering.root)):
                package.writestr(name, _xml(node))
        return buffer.getvalue()
