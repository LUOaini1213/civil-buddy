"""Reading a scan: pages rendered by pdfium, read by RapidOCR - both optional, both local.

A scanned tender or certificate has no text layer; office_job reports it as not read. With the optional
packages installed (`pip install -e .[ocr]`: rapidocr-onnxruntime and pypdfium2, models shipped in the wheel,
nothing fetched at run time) the pages are recognised here and handed on in the shape pdf_layout expects -
one table cell to a line - so that a scanned front table is rebuilt like a drawn one.

What OCR gives is a reading, not the text: 竣工 comes back as 峻工, "；" as "：", and a digit can be wrong
without looking wrong. So the text is marked ("〔OCR〕" on its first line), every draft made from it says so,
and nothing here corrects a character - a corrected character would be one nobody wrote.

    available()             are both packages importable
    pdf_page_lines(path)    per page, the recognised lines in reading order, table cells one to a line
    image_lines(image)      the same for one page image (a PIL image or an array)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

MARK = "〔OCR〕"
DPI = 200
_NUMBER_ONLY = re.compile(r"^\d+(?:\.\d+)*(?:\s*[（(]\s*\d+\s*[)）])?$")
_ENGINE: Any = None

Box = Tuple[float, float, float, float, str]  # left, top, right, bottom, text


def available() -> bool:
    try:
        import pypdfium2  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001 - any failure to import means: not available here
        return False
    return True


def _engine() -> Any:
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _ENGINE = RapidOCR()
    return _ENGINE


def _boxes(image: Any) -> List[Box]:
    import numpy as np

    result, _elapsed = _engine()(np.array(image))
    boxes: List[Box] = []
    for points, text, _score in result or []:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if str(text).strip():
            boxes.append((min(xs), min(ys), max(xs), max(ys), str(text).strip()))
    return boxes


def lines_from_boxes(boxes: Sequence[Box]) -> List[str]:
    """Recognised boxes as lines in the order a text layer would give them.

    Boxes on one visual line are one line, left to right - unless they stand in the columns of a table: a
    table is known by a visual line of three or more boxes (its header, or any row), whose left edges become
    the column anchors. Inside it a row starts at a box in the first column; its cells are put out one to a
    line, first column first, each cell's text joined top to bottom - the layout pdf_layout.rebuild() reads.
    """
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (b[1], b[0]))
    height = sorted(b[3] - b[1] for b in ordered)[len(ordered) // 2] or 1.0
    visual: List[List[Box]] = []
    for box in ordered:
        if visual and abs(box[1] - visual[-1][0][1]) <= height * 0.6:
            visual[-1].append(box)
        else:
            visual.append([box])
    out: List[str] = []
    anchors: List[float] = []
    numbered = False            # the table's first column holds numbers only (条款号 / 序号)
    row: List[List[str]] = []

    def flush_row() -> None:
        for cell in row:
            if cell:
                out.append("".join(cell))
        row.clear()

    def column(box: Box) -> Optional[int]:
        best = min(range(len(anchors)), key=lambda i: abs(anchors[i] - box[0]))
        return best if abs(anchors[best] - box[0]) <= height * 2.5 else None

    for line in visual:
        line.sort(key=lambda b: b[0])
        if len(line) >= 3 and not anchors:
            anchors = [b[0] for b in line]
            numbered = line[0][4] in ("条款号", "序号", "编号", "项号") or bool(_NUMBER_ONLY.match(line[0][4]))
            row.extend([[] for _ in anchors])
            for index, box in enumerate(line):
                row[index].append(box[4])
            flush_row()  # the header: each cell a line of its own
            row.extend([[] for _ in anchors])
            continue
        if anchors:
            placed = [column(b) for b in line]
            first = line[0]
            # "1.总则" under a front table stands in the first column's place and is no clause number: the table is over
            leaves = (any(p is None for p in placed)
                      or (placed[0] == 0 and not _NUMBER_ONLY.match(first[4])
                          and (numbered or (len(line) == 1 and (first[2] - first[0]) > (anchors[1] - anchors[0]) * 1.2))))
            if leaves:
                flush_row()
                anchors = []
            else:
                if placed[0] == 0 and (_NUMBER_ONLY.match(first[4]) or len(line) >= len(anchors)) and any(row):
                    flush_row()
                    row.extend([[] for _ in anchors])
                if not row:
                    row.extend([[] for _ in anchors])
                for box, index in zip(line, placed):
                    row[index].append(box[4])
                continue
        out.append("".join(b[4] for b in line) if all(_cjk(b[4]) for b in line) else " ".join(b[4] for b in line))
    flush_row()
    return out


def _cjk(text: str) -> bool:
    return any(ord(ch) > 0x2E7F for ch in text)


def image_lines(image: Any) -> List[str]:
    return lines_from_boxes(_boxes(image))


def pdf_page_lines(path: Path, *, on_page: Optional[Callable[[int, int], None]] = None, max_pages: int = 400) -> List[List[str]]:
    """Every page of a PDF recognised. ``on_page(done, total)`` is called after each page - a hundred pages take
    minutes on a CPU, and somebody is waiting."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    try:
        total = min(len(document), max_pages)
        pages: List[List[str]] = []
        for index in range(total):
            page = document[index]
            try:
                image = page.render(scale=DPI / 72).to_pil().convert("RGB")
            finally:
                page.close()
            pages.append(image_lines(image))
            if on_page is not None:
                on_page(index + 1, total)
        return pages
    finally:
        document.close()   # pdfium keeps the file open: on Windows the user could not move or delete their own PDF
