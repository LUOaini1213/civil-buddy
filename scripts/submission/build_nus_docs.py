# -*- coding: utf-8 -*-
"""Build the two NUS-ISS "Show Me Your Agents" PDFs: the Technical Document and the Business Proposal.

    docs/submission/nus-iss-technical.md  -->  output/submission/nus-iss/Technical-Document.pdf
    docs/submission/nus-iss-business.md   -->  output/submission/nus-iss/Business-Proposal.pdf

For each document:

    Markdown  --mark placeholders-->  --pandoc-->  standalone HTML (CSS and diagram embedded; title block, contents)
              --headless Chrome-->  A4 PDF  --pypdf-->  running header naming the document + "Page N of M"

Both use docs/submission/nus-iss-doc.css. Every [TEAM TO FILL ...] and [TEAM TO VERIFY ...] outside code is wrapped in
a pandoc span with the class "placeholder", which the stylesheet prints as a yellow, red-bordered highlight, so an
unfinished PDF cannot pass for a finished one. After building, the script prints how many placeholders each document
still has. Placeholders do not fail the build: the exit code is 0 unless a tool is missing or a step fails (then 2).

Output goes to output/submission/nus-iss/ (gitignored), with each PDF's HTML next to it.

Needs pandoc (2.19+ for --embed-resources; older falls back to --self-contained), Google Chrome (run only as
--headless=new, with a throwaway profile) and pypdf (in requirements.txt). Tools are looked up in this order:
--pandoc/--chrome, the PANDOC/CHROME environment variables, PATH, then the usual Windows install folders.

    python scripts/submission/build_nus_docs.py
    python scripts/submission/build_nus_docs.py --only business
    python scripts/submission/build_nus_docs.py --pandoc D:/tools/pandoc.exe --chrome "C:/.../chrome.exe"

The header and page numbers are stamped with pypdf because @page margin boxes only print from Chrome 131 on.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "docs" / "submission"
STYLESHEET = "nus-iss-doc.css"
DIAGRAM = "nus-iss-architecture.svg"
OUT_DIR = ROOT / "output" / "submission" / "nus-iss"
PDF_AUTHOR = "Team Mintang (PJ2U63AF)"


@dataclass(frozen=True)
class Doc:
    key: str  # --only name, and the body class doc-<key>
    source: str  # Markdown file in docs/submission
    pdf_name: str
    label: str  # the running header ends with this
    subject: str
    figure: bool = False  # carries the architecture diagram on its own landscape page
    flow: bool = False  # sections run on instead of each starting a new page

    @property
    def header(self) -> str:
        return f"civil-buddy \u00b7 {PDF_AUTHOR} \u00b7 {self.label}"

    @property
    def title(self) -> str:
        return f"civil-buddy: {self.label}"


DOCS = [
    Doc("technical", "nus-iss-technical.md", "Technical-Document.pdf", "Technical Document",
        "NUS-ISS Show Me Your Agents Hackathon 2026: architecture, safety, evaluation and deployment", figure=True),
    Doc("business", "nus-iss-business.md", "Business-Proposal.pdf", "Business Proposal",
        "NUS-ISS Show Me Your Agents Hackathon 2026: problem, value, market, business model and go-to-market",
        flow=True),
]

PANDOC_CANDIDATES = [
    "D:/ProgramData/anaconda3/Library/bin/pandoc.exe",
    "C:/Program Files/Pandoc/pandoc.exe",
    os.path.expandvars("%LOCALAPPDATA%/Pandoc/pandoc.exe"),
]
CHROME_CANDIDATES = [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    os.path.expandvars("%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe"),
]
CHROME_ON_PATH = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]

# Status tags in the text are inline code; they get the diagram's colours.
TAGS = ["LIVE", "OPT-IN", "BEFORE DEMO", "ROADMAP", "NOT NEEDED"]

# [TEAM TO FILL], [TEAM TO FILL: ...], [TEAM TO VERIFY with BCA: ...] and so on.
PLACEHOLDER = re.compile(r"\[TEAM TO (FILL|VERIFY)\b")
# The SME partner is named only in the PDFs sent to the organisers, never in the public repo:
# {{SME_NAME}} and friends come from this untracked file; a missing value becomes a TEAM TO FILL.
PRIVATE = Path(__file__).resolve().parents[2] / "docs" / "submission" / "sme.local.json"
TOKEN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def fill_private(text: str) -> str:
    values = json.loads(PRIVATE.read_text(encoding="utf-8")) if PRIVATE.is_file() else {}
    return TOKEN.sub(lambda m: str(values.get(m[1]) or "").strip()
                     or f"[TEAM TO FILL: {m[1]} in docs/submission/sme.local.json]", text)

MM = 72 / 25.4
# Helvetica advance widths (1/1000 em) for the characters of "Page N of M".
_HELV = {" ": 278, "P": 667, "a": 556, "g": 556, "e": 556, "o": 556, "f": 278, **{d: 556 for d in "0123456789"}}


def fail(msg: str) -> None:
    print(f"build_nus_docs: {msg}", file=sys.stderr)
    sys.exit(2)


def find_tool(explicit: str | None, env: str, on_path: list[str], candidates: list[str], what: str, hint: str) -> str:
    if explicit:
        if Path(explicit).is_file():
            return explicit
        fail(f"{what} not found at {explicit!r} (given with --{env.lower()}).")
    if os.environ.get(env):
        if Path(os.environ[env]).is_file():
            return os.environ[env]
        fail(f"{what} not found at {os.environ[env]!r} (from the {env} environment variable).")
    for name in on_path:
        hit = shutil.which(name)
        if hit:
            return hit
    for cand in candidates:
        if cand and Path(cand).is_file():
            return cand
    fail(f"{what} is missing. {hint}")
    return ""


def pandoc_version(pandoc: str) -> tuple[int, ...]:
    try:
        out = subprocess.run([pandoc, "--version"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"could not run pandoc at {pandoc!r}: {exc}")
    m = re.search(r"pandoc(?:\.exe)?\s+(\d+(?:\.\d+)*)", out)
    if not m:
        fail(f"could not read the pandoc version from {pandoc!r}")
    return tuple(int(x) for x in m.group(1).split("."))


# ---------------------------------------------------------------- placeholders

def _code_span_end(line: str, i: int) -> int | None:
    """line[i] starts a backtick run; the index just past the matching closing run, or None if it is unclosed."""
    run = re.match(r"`+", line[i:]).group(0)
    j = i + len(run)
    while True:
        j = line.find(run, j)
        if j < 0:
            return None
        k = j + len(run)
        if k < len(line) and line[k] == "`":  # a longer run does not close this one
            j = k + len(re.match(r"`+", line[k:]).group(0))
            continue
        return k


def _bracket_end(line: str, i: int) -> int | None:
    """line[i] is '['; the index of its matching ']' on the same line (escapes and code spans skipped)."""
    depth, j = 0, i
    while j < len(line):
        c = line[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            end = _code_span_end(line, j)
            if end is None:
                return None
            j = end
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _mark_line(line: str, counts: Counter, problems: list[str], where: str) -> str:
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == "`":  # a code span only mentions a placeholder; leave it as written
            end = _code_span_end(line, i)
            if end is None:
                out.append(line[i:])
                break
            out.append(line[i:end])
            i = end
            continue
        if c == "\\" and i + 1 < n:
            out.append(line[i:i + 2])
            i += 2
            continue
        m = PLACEHOLDER.match(line, i)
        if m:
            end = _bracket_end(line, i)
            if end is None:
                problems.append(f"{where}: placeholder without a closing ']' on the same line")
                out.append(line[i:])
                break
            counts[m.group(1)] += 1
            out.append("[\\[" + line[i + 1:end] + "\\]]{.placeholder}")
            i = end + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def mark_placeholders(text: str, source: str) -> tuple[str, Counter, list[str]]:
    """Wrap every placeholder outside code in a pandoc span `[...]{.placeholder}`; count them by kind."""
    counts: Counter = Counter()
    problems: list[str] = []
    lines = text.split("\n")
    in_yaml = bool(lines) and lines[0].strip() == "---"
    fence = ""
    for no, line in enumerate(lines):
        if in_yaml:
            if no > 0 and line.strip() in ("---", "..."):
                in_yaml = False
            continue
        stripped = line.lstrip()
        if fence:
            if stripped.startswith(fence):
                fence = ""
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            continue
        if "[TEAM TO" in line:
            lines[no] = _mark_line(line, counts, problems, f"{source}:{no + 1}")
    return "\n".join(lines), counts, problems


# ---------------------------------------------------------------- HTML and PDF

def build_html(pandoc: str, doc: Doc, html_out: Path) -> Counter:
    text = fill_private((SRC_DIR / doc.source).read_text(encoding="utf-8"))
    marked, counts, problems = mark_placeholders(text, doc.source)
    for p in problems:
        print(f"  warning: {p}", file=sys.stderr)

    embed = "--embed-resources" if pandoc_version(pandoc) >= (2, 19) else "--self-contained"
    cmd = [
        pandoc, "-",
        "--from", "markdown-implicit_figures",  # the Markdown carries its own caption line under the figure
        "--to", "html5",
        "--standalone", embed,
        "--toc", "--toc-depth=3",  # sections are h2 (the title is the h1), subsections h3
        "--columns=4000",  # no fixed column widths from the dash counts of pipe tables
        "--css", STYLESHEET,
        "--resource-path", ".",
        "--metadata", "toc-title=Contents",
        "--metadata", "lang=en",
        "--output", str(html_out),
    ]
    # Run from docs/submission so the stylesheet and the SVG resolve as plain relative paths; the marked-up
    # Markdown goes in on stdin, so nothing is written next to the sources.
    res = subprocess.run(cmd, cwd=SRC_DIR, input=marked, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=300)
    if res.returncode != 0 or not html_out.is_file():
        fail(f"pandoc failed on {doc.source} (exit {res.returncode}):\n{res.stderr.strip()}")
    for line in res.stderr.splitlines():
        print(f"  pandoc: {line}")

    html = html_out.read_text(encoding="utf-8")
    body_cls = f"doc-{doc.key}" + (" flow" if doc.flow else "")
    html = html.replace("<body>", f'<body class="{body_cls}">', 1)
    for tag in TAGS:
        cls = "tag tag-" + tag.lower().replace(" ", "-")
        html = html.replace(f"<code>{tag}</code>", f'<code class="{cls}">{tag}</code>')
    # A note to the team at the top ("Draft for the team: ...") prints as a warning box, like a placeholder.
    html = re.sub(r"<blockquote>(\s*<p><strong>Draft\b)", r'<blockquote class="draft-note">\1', html)
    if doc.figure:
        if 'src="data:image/svg+xml' not in html and "<svg" not in html:
            fail(f"the architecture diagram was not embedded in the HTML ({DIAGRAM} missing?)")
        # Mark the figure paragraph and its caption so the stylesheet can give them a landscape page.
        html, n = re.subn(r'<p>(<img[^>]*src="data:image/svg\+xml[^"]*"[^>]*>)</p>(\s*)<p>',
                          r'<p class="figure-image">\1</p>\2<p class="figure-caption">', html, count=1)
        if n != 1:
            print("  warning: could not mark the figure paragraph; it will print at text width", file=sys.stderr)
    spans = html.count('<span class="placeholder">')
    if spans != sum(counts.values()):
        print(f"  warning: {sum(counts.values())} placeholders marked in {doc.source}, "
              f"but {spans} highlighted spans in the HTML", file=sys.stderr)
    html_out.write_text(html, encoding="utf-8", newline="\n")
    return counts


def print_pdf(chrome: str, html: Path, pdf_out: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="nus-docs-chrome-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome,
            "--headless=new",  # never a visible window
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",  # never touch the user's own Chrome profile or a running Chrome
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_out}",
            html.resolve().as_uri(),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        except subprocess.TimeoutExpired:
            fail("headless Chrome did not finish printing within 300 s")
        except OSError as exc:
            fail(f"could not start Chrome at {chrome!r}: {exc}")
    if not pdf_out.is_file() or pdf_out.stat().st_size == 0:
        fail(f"Chrome did not write {pdf_out} (exit {res.returncode}):\n{res.stderr.strip()[-2000:]}")


def _text_width(text: str, size: float) -> float:
    return sum(_HELV.get(ch, 556) for ch in text) * size / 1000


def _pdf_string(text: str) -> bytes:
    raw = text.encode("cp1252")  # WinAnsiEncoding: covers the middle dot of the header
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _pypdf():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        fail("pypdf is missing: run `pip install -r requirements.txt` (it lists pypdf>=5.0).")
    import pypdf
    return pypdf


def stamp(doc: Doc, pdf_in: Path, pdf_out: Path) -> int:
    pypdf = _pypdf()
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    reader = pypdf.PdfReader(str(pdf_in))
    writer = pypdf.PdfWriter(clone_from=reader)
    total = len(writer.pages)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    for i, page in enumerate(writer.pages, start=1):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        landscape = w > h
        side = (10 if landscape else 20) * MM
        head_y = h - (6 if landscape else 12) * MM
        foot_y = (4 if landscape else 11) * MM
        size = 7.5 if landscape else 8
        label = f"Page {i} of {total}"
        ops = [b"q 0.45 0.49 0.55 rg"]
        if i > 1:  # the first page carries the title block itself
            ops.append(b"BT /FHdr %.1f Tf 1 0 0 1 %.2f %.2f Tm %s Tj ET" % (size, side, head_y, _pdf_string(doc.header)))
            if not landscape:
                ops.append(b"0.78 0.81 0.86 RG 0.4 w %.2f %.2f m %.2f %.2f l S" % (side, head_y - 4, w - side, head_y - 4))
        lx = (w - _text_width(label, size)) / 2
        ops.append(b"BT /FHdr %.1f Tf 1 0 0 1 %.2f %.2f Tm %s Tj ET" % (size, lx, foot_y, _pdf_string(label)))
        ops.append(b"Q")
        overlay = pypdf.PageObject.create_blank_page(width=w, height=h)
        overlay[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/FHdr"): font}),
        })
        content = DecodedStreamObject()
        content.set_data(b"\n".join(ops))
        overlay[NameObject("/Contents")] = writer._add_object(content)
        page.merge_page(overlay)
    writer.add_metadata({"/Title": doc.title, "/Author": PDF_AUTHOR, "/Subject": doc.subject})
    with open(pdf_out, "wb") as fh:
        writer.write(fh)
    return total


def placeholders_in_pdf(pdf: Path) -> int:
    """Placeholders still readable in the PDF text (a cross-check of the count taken from the Markdown)."""
    reader = _pypdf().PdfReader(str(pdf))
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in reader.pages)
    return len(PLACEHOLDER.findall(text))


def build(doc: Doc, pandoc: str, chrome: str, out_dir: Path) -> dict:
    pdf = out_dir / doc.pdf_name
    html = pdf.with_suffix(".html")
    print(f"\n{doc.label}: docs/submission/{doc.source}")
    counts = build_html(pandoc, doc, html)
    with tempfile.TemporaryDirectory(prefix="nus-docs-") as tmp:
        raw = Path(tmp) / "raw.pdf"
        print_pdf(chrome, html, raw)
        pages = stamp(doc, raw, pdf)
    print(f"  html: {html}")
    print(f"  pdf:  {pdf} ({pages} pages, {pdf.stat().st_size / 1024:.0f} KB)")
    return {"doc": doc, "pdf": pdf, "pages": pages, "counts": counts, "in_pdf": placeholders_in_pdf(pdf)}


def report(results: list[dict]) -> None:
    print("\nPlaceholders left ([TEAM TO FILL] / [TEAM TO VERIFY], highlighted in the PDF):")
    for r in results:
        doc, counts = r["doc"], r["counts"]
        total = sum(counts.values())
        detail = f" ({counts['FILL']} TEAM TO FILL, {counts['VERIFY']} TEAM TO VERIFY)" if total else ""
        print(f"  {doc.label:<20} {total:>3}{detail}   {r['pdf'].name}, {r['pages']} pages")
        if r["in_pdf"] < total:
            print(f"    warning: only {r['in_pdf']} of them were found in the PDF text", file=sys.stderr)
        if "Draft for the team" in (SRC_DIR / doc.source).read_text(encoding="utf-8"):
            print(f"    the 'Draft for the team' box is still at the top of {doc.source}; "
                  "delete it before the final export")
    if any(sum(r["counts"].values()) for r in results):
        print("Resolve or delete every placeholder, then rebuild before submitting.")
    else:
        print("None left.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pandoc", help="path to pandoc (default: $PANDOC, PATH, then known install folders)")
    ap.add_argument("--chrome", help="path to Chrome (default: $CHROME, PATH, then known install folders)")
    ap.add_argument("--only", choices=[d.key for d in DOCS], action="append",
                    help="build only this document (repeatable; default: both)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR,
                    help=f"output folder (default: {OUT_DIR.relative_to(ROOT).as_posix()})")
    args = ap.parse_args()

    docs = [d for d in DOCS if not args.only or d.key in args.only]
    if not args.only:  # a draft kept off main (the business proposal) is skipped, not an error
        for d in [d for d in docs if not (SRC_DIR / d.source).is_file()]:
            print(f"skip {d.key}: docs/submission/{d.source} is not in this checkout")
        docs = [d for d in docs if (SRC_DIR / d.source).is_file()]
    needed = {STYLESHEET, *(d.source for d in docs)} | ({DIAGRAM} if any(d.figure for d in docs) else set())
    for name in sorted(needed):
        if not (SRC_DIR / name).is_file():
            fail(f"missing input docs/submission/{name}")
    pandoc = find_tool(args.pandoc, "PANDOC", ["pandoc"], PANDOC_CANDIDATES, "pandoc",
                       "Install it from https://pandoc.org/installing.html, or pass --pandoc PATH.")
    chrome = find_tool(args.chrome, "CHROME", CHROME_ON_PATH, CHROME_CANDIDATES, "Google Chrome",
                       "Install Chrome, or pass --chrome PATH (any Chromium browser with --headless=new).")
    _pypdf()
    print(f"pandoc: {pandoc}\nchrome: {chrome}")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [build(doc, pandoc, chrome, out_dir) for doc in docs]
    report(results)
    return 0  # placeholders are reported, not fatal


if __name__ == "__main__":
    raise SystemExit(main())
