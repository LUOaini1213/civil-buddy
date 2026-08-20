"""Authorized job folder + Office interchange (WorkBuddy local-file slice).

NL run writes real .xlsx next to table drafts so Excel can open them.
Not a desktop shell. Not D:\\layout. Not in-place COM into Word/Excel windows.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple

FORBIDDEN_LAYOUT = ("d:\\layout", "d:/layout")


def is_forbidden_layout(path: Path) -> bool:
    n = str(path).replace("/", "\\").rstrip("\\").lower()
    return n == "d:\\layout" or n.startswith("d:\\layout\\")


def job_root() -> Path:
    raw = (os.getenv("CIVIL_JOB_ROOT") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not is_forbidden_layout(p):
            return p
    return Path.cwd() / ".civil-buddy" / "out"


def _sheet_name(title: str, used: set) -> str:
    t = re.sub(r'[:\\/?*\[\]]', " ", title or "表").strip() or "表"
    t = t[:31]
    base = t
    i = 2
    while t in used:
        suffix = f"_{i}"
        t = (base[: 31 - len(suffix)] + suffix)
        i += 1
    used.add(t)
    return t


def tables_from_md(md: str) -> List[Tuple[str, List[List[str]]]]:
    """Return (sheet_name, rows) for each markdown table. Caption from last heading."""
    lines = (md or "").splitlines()
    heading = "表"
    used: set = set()
    out: List[Tuple[str, List[List[str]]]] = []
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        hs = raw.lstrip()
        if hs.startswith("#"):
            heading = hs.lstrip("#").strip() or heading
            i += 1
            continue
        if hs.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            rows: List[List[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if cells and not all(re.match(r"^:?-{3,}:?$", c or "") for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                out.append((_sheet_name(heading, used), rows))
            continue
        i += 1
    return out


def write_xlsx(path: Path, sheets: List[Tuple[str, List[List[str]]]]) -> Path:
    from io import BytesIO

    from packing_assistant.sandbox import guarded_write_bytes

    import openpyxl

    wb = openpyxl.Workbook()
    first = True
    for name, rows in sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = name[:31] or "表"
        for r_i, row in enumerate(rows, 1):
            for c_i, val in enumerate(row, 1):
                ws.cell(r_i, c_i, val)
    bio = BytesIO()
    wb.save(bio)
    return guarded_write_bytes(Path(path), bio.getvalue())


def export_md_to_xlsx(md_path: Path) -> List[Path]:
    """Write sibling xlsx in the md folder and a copy in the job root. Skip if no tables."""
    p = Path(md_path)
    if not p.is_file() or p.suffix.lower() != ".md":
        return []
    sheets = tables_from_md(p.read_text(encoding="utf-8", errors="ignore"))
    if not sheets:
        return []
    written: List[Path] = []
    sibling = p.with_suffix(".xlsx")
    written.append(write_xlsx(sibling, sheets))
    if not (os.getenv("CIVIL_JOB_ROOT") or "").strip():
        return written
    root = job_root()
    if is_forbidden_layout(root):
        return written
    dest = root / sibling.name
    try:
        if dest.resolve() != sibling.resolve():
            written.append(write_xlsx(dest, sheets))
    except OSError:
        pass
    return written
