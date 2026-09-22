#!/usr/bin/env python3
"""The benchmark tenders as PDF files - a text layer, real tables, page breaks - and as scans (images only).

Published tenders are PDF more often than Word. This script needs reportlab (and, for the scans, pypdfium2),
which are NOT dependencies of Civil Buddy: run it with a Python that has them, from the repo root -

    python test/benchmarks/real_tender/build_pdf.py            # cn_construction.pdf, cn_municipal.pdf
    python test/benchmarks/real_tender/build_pdf.py --scan     # + *.scan.pdf, every page an image at 150 dpi

The PDFs are committed as fixtures so that the evaluation itself needs nothing beyond pypdf.
A CJK TrueType font is required (Windows: simsun.ttc / msyh.ttc; Linux: Noto Sans CJK).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = [("C:/Windows/Fonts/simsun.ttc", 0), ("C:/Windows/Fonts/msyh.ttc", 0), ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
         ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0)]


def blocks_of(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"build_{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.document()


def build(name: str) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = next(((path, index) for path, index in FONTS if Path(path).is_file()), None)
    if font is None:
        raise SystemExit("no CJK font found: " + ", ".join(path for path, _ in FONTS))
    pdfmetrics.registerFont(TTFont("CJK", font[0], subfontIndex=font[1]))
    body = ParagraphStyle("body", fontName="CJK", fontSize=10.5, leading=16, wordWrap="CJK")
    cell = ParagraphStyle("cell", fontName="CJK", fontSize=9.5, leading=13, wordWrap="CJK")
    h1 = ParagraphStyle("h1", fontName="CJK", fontSize=16, leading=24, spaceBefore=6, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="CJK", fontSize=12.5, leading=19, spaceBefore=6, spaceAfter=4)
    story = []
    first = True
    for block in blocks_of(name):
        kind = block[0]
        if kind == "h1":
            if not first:
                story.append(PageBreak())
            first = False
            story.append(Paragraph(block[1], h1))
        elif kind == "h2":
            story.append(Paragraph(block[1], h2))
        elif kind == "p":
            story.append(Paragraph(block[1].replace("&", "&amp;").replace("<", "&lt;"), body))
            story.append(Spacer(1, 3))
        else:
            _kind, header, rows = block
            widths = {3: (22, 40, 108), 4: (22, 45, 70, 33), 5: (40, 36, 30, 30, 34)}.get(len(header))
            data = [[Paragraph(str(c).replace("&", "&amp;").replace("<", "&lt;"), cell) for c in row] for row in [header, *rows]]
            grid = Table(data, colWidths=[w * mm for w in widths] if widths else None, repeatRows=1)
            grid.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
            story += [grid, Spacer(1, 6)]
    target = HERE / f"{name}.pdf"

    def footer(canvas, doc):
        canvas.setFont("CJK", 9)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, f"第 {doc.page} 页")

    SimpleDocTemplate(str(target), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=22 * mm,
                      title=name, invariant=1).build(story, onFirstPage=footer, onLaterPages=footer)
    return target


def scan(source: Path, dpi: int = 150) -> Path:
    """The same pages as images only - what a scanner makes. No text layer survives."""
    import io

    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdfcanvas

    target = source.with_suffix(".scan.pdf")
    pages = pdfium.PdfDocument(str(source))
    out = pdfcanvas.Canvas(str(target), invariant=1)
    for page in pages:
        width, height = page.get_size()
        image = page.render(scale=dpi / 72).to_pil().convert("L")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)
        out.setPageSize((width, height))
        out.drawImage(ImageReader(buffer), 0, 0, width=width, height=height)
        out.showPage()
    out.save()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("names", nargs="*", default=["cn_construction", "cn_municipal"])
    args = parser.parse_args()
    for name in args.names:
        target = build(name)
        print(f"{target.name}: {target.stat().st_size // 1024} KB")
        if args.scan:
            scanned = scan(target)
            print(f"{scanned.name}: {scanned.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
