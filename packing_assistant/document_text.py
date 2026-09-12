"""Preserve Office and delimited-text tables at the draft input boundary."""
from __future__ import annotations

import csv
import html
from io import StringIO
from itertools import islice
from typing import Iterable
from xml.etree import ElementTree


def table_markdown(rows: Iterable[Iterable[object]], limit: int) -> str:
    """Keep column positions and literal content; the first nonempty row is the header."""
    lines: list[str] = []
    used = 0
    width = 0
    for row in islice(rows, 20_000):
        values = ["" if value is None else str(value) for value in islice(row, 256)]
        if not any(value.strip() for value in values):
            continue
        if not width:
            width = len(values)
        values += [""] * max(0, width - len(values))
        cells = [html.escape(value.replace("\r", " ").replace("\n", "；"), quote=False).replace("|", "&#124;") for value in values]
        line = "| " + " | ".join(cells) + " |"
        if not lines:
            line += "\n| " + " | ".join("---" for _ in values) + " |"
        if used + len(line) + 1 > limit:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def csv_text(text: str, limit: int) -> str:
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return table_markdown(csv.reader(StringIO(text), dialect), limit)


def docx_document_text(document: ElementTree.Element, limit: int) -> str:
    """Read paragraphs and tables in document order without flattening table cells."""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tag = "{" + ns["w"] + "}"
    body = document.find("w:body", ns)
    if body is None:
        return ""
    blocks: list[str] = []
    used = 0

    def paragraph_text(element: ElementTree.Element) -> str:
        return "".join(node.text or "" for node in element.findall(".//w:t", ns))

    for element in body:
        if used >= limit:
            break
        if element.tag == tag + "tbl":
            rows = (["；".join(paragraph_text(p) for p in cell.findall("w:p", ns))
                     for cell in row.findall("w:tc", ns)] for row in element.findall("w:tr", ns))
            block = table_markdown(rows, limit - used)
        else:
            block = paragraph_text(element)[:limit - used]
        if block:
            blocks.append(block)
            used += len(block) + 2
    return "\n\n".join(blocks)[:limit]
