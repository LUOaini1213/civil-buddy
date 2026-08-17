"""Fail on assertive statutory phrases; allowlist the fixed disclaimer and header."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from paths import DISCLAIMER, HEADER_STOCK

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ASSERTIVE = (
    "可交差",
    "可报审",
    "报审通过",
    "可提交专家论证",
    "请专家论证",
    "请监理审核后开工",
    "请监理审核",
    "可以开工",
    "已具备报审条件",
)

CLAUSE_RE = re.compile(r"第[\d.]+条")
ASSUMPTION_RE = re.compile(r"A00\d")
JURISDICTION_RE = re.compile(r"\b(CN|SG|EU|DUAL)\b")
TOKEN_RE = re.compile(r"\{\{")


def _docx_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = [
            n
            for n in zf.namelist()
            if n.startswith("word/")
            and n.endswith(".xml")
            and (
                n == "word/document.xml"
                or "header" in n
                or "footer" in n
            )
        ]
        for name in names:
            root = ET.fromstring(zf.read(name))
            for node in root.iter(f"{W_NS}t"):
                if node.text:
                    texts.append(node.text)
    return "\n".join(texts)


def _strip_allowlist(text: str) -> str:
    out = text
    for block in (DISCLAIMER, HEADER_STOCK):
        out = out.replace(block, "")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--docx", type=Path, required=True)
    p.add_argument("--citations", type=Path, required=True)
    p.add_argument("--jurisdiction", required=True)
    args = p.parse_args()

    draft = args.draft.read_text(encoding="utf-8")
    citations = args.citations.read_text(encoding="utf-8")
    docx_text = _docx_text(args.docx)
    combined = draft + "\n" + docx_text

    if HEADER_STOCK not in combined and DISCLAIMER not in combined:
        sys.stderr.write("missing header stock sentence or disclaimer\n")
        return 1
    if not ASSUMPTION_RE.search(combined):
        sys.stderr.write("missing A00x assumption id\n")
        return 1
    if args.jurisdiction not in combined and not JURISDICTION_RE.search(combined):
        sys.stderr.write("missing jurisdiction code\n")
        return 1

    scanned = _strip_allowlist(combined)
    for phrase in ASSERTIVE:
        if phrase in scanned:
            sys.stderr.write(f"assertive phrase: {phrase}\n")
            return 1

    if TOKEN_RE.search(docx_text):
        sys.stderr.write("residual {{ token in docx\n")
        return 1

    for clause in CLAUSE_RE.findall(draft):
        if clause not in citations:
            sys.stderr.write(f"clause not in citations.md: {clause}\n")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
