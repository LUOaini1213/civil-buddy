"""Mark a clause verified only if the token appears in extracted PDF text."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _extract(pdf: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass
    try:
        import pdfplumber  # type: ignore

        chunks: list[str] = []
        with pdfplumber.open(str(pdf)) as doc:
            for page in doc.pages:
                chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
    except Exception as exc:
        sys.stderr.write(f"cannot extract pdf text: {exc}\n")
        return ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--clause", required=True)
    p.add_argument("--name", default="")
    args = p.parse_args()
    if not args.pdf.is_file():
        sys.stderr.write(f"missing pdf: {args.pdf}\n")
        print("unspecified_clause")
        return 1
    text = _extract(args.pdf)
    if not text.strip():
        print("unspecified_clause")
        return 1
    if args.clause and args.clause in text:
        print("verified")
        return 0
    print("unverified")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
