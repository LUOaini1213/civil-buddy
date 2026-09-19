"""Authorized job folder + Office interchange (WorkBuddy local-file slice).

NL run writes real .xlsx next to table drafts so Excel can open them.
If the user names an existing workbook in CIVIL_JOB_ROOT, patch only CB草稿-*
sheets and leave the owner's sheets alone.
Not a desktop shell. Not D:\\layout. Not COM into an open Excel window.
"""

from __future__ import annotations

import html

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zipfile import BadZipFile
from packing_assistant.document_text import csv_text, docx_document_text, table_markdown

JOB_EXTS = {".xlsx", ".csv", ".txt", ".md", ".json", ".docx", ".log"}
JOB_MAX_FILES = 12
JOB_FILE_CHARS = 8_000
JOB_TOTAL_CHARS = 48_000
DRAFT_PREFIX = "CB草稿"
_OFFICE_CONTENT_ERRORS = (BadZipFile, ValueError, KeyError, SyntaxError)

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
    while t.casefold() in {name.casefold() for name in used}:
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
                # Decode after splitting: encoded pipes are cell contents, not
                # Markdown column separators. Excel receives the original text.
                row = lines[i].strip()[1:]
                if row.endswith("|"):
                    row = row[:-1]
                cells = [html.unescape(c.strip()) for c in row.split("|")]
                if cells and not all(re.match(r"^:?-{3,}:?$", c or "") for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                out.append((_sheet_name(heading, used), rows))
            continue
        i += 1
    return out


def _write_rows(worksheet: Any, rows: List[List[str]]) -> None:
    """Draft tables contain text, including strings that look like formulas."""
    for r_i, row in enumerate(rows, 1):
        for c_i, value in enumerate(row, 1):
            cell = worksheet.cell(r_i, c_i, value)
            if isinstance(value, str):
                cell.data_type = "s"


def _save_workbook(workbook: Any, path: Path) -> Path:
    from io import BytesIO

    from packing_assistant.sandbox import guarded_write_bytes

    try:
        with BytesIO() as buffer:
            workbook.save(buffer)
            return guarded_write_bytes(path, buffer.getvalue())
    finally:
        workbook.close()


def write_xlsx(path: Path, sheets: List[Tuple[str, List[List[str]]]]) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    first = True
    used: set = set()
    for name, rows in sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = _sheet_name(name, used)
        _write_rows(ws, rows)
    return _save_workbook(wb, Path(path))


def _query_from_md(md: str) -> str:
    if "## 用户原文" in (md or ""):
        return (md or "").split("## 用户原文", 1)[1].split("##", 1)[0].strip()
    return (md or "")[:400]


def pick_job_xlsx(query: str) -> Path | None:
    """Existing job-root workbook the user named. Do not guess the first file."""
    q = (query or "").lower()
    if not q:
        return None
    for f in list_job_files():
        if f.get("suffix") != ".xlsx":
            continue
        name = str(f.get("name") or "")
        stem = Path(name).stem.lower()
        if name.lower() in q or (stem and stem in q):
            return Path(str(f["path"]))
    return None


def patch_xlsx(path: Path, sheets: List[Tuple[str, List[List[str]]]]) -> Path:
    """Replace only CB草稿-* sheets. Owner sheets stay."""
    import openpyxl

    resolved = _resolve_job_file(path)
    if not sheets:
        return resolved
    wb = openpyxl.load_workbook(resolved)
    for name in list(wb.sheetnames):
        if name.startswith(f"{DRAFT_PREFIX}-"):
            del wb[name]
    used = set(wb.sheetnames)
    for title, rows in sheets:
        ws = wb.create_sheet(_sheet_name(f"{DRAFT_PREFIX}-{title}", used))
        _write_rows(ws, rows)
    return _save_workbook(wb, resolved)


def _resolve_job_file(path: Path) -> Path:
    """Resolve every job-file read/patch through the same root and secret guard."""
    from packing_assistant.sandbox import assert_open

    root = job_root().resolve()
    try:
        resolved = Path(path).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as e:
        raise PermissionError("job file outside authorized root") from e
    if is_forbidden_layout(resolved):
        raise PermissionError("D:\\layout denied")
    return assert_open(resolved)


def export_md_to_xlsx(md_path: Path, query: str = "") -> List[Path]:
    """Sibling xlsx always. If the user named a job-root workbook, patch it too."""
    p = Path(md_path)
    if not p.is_file() or p.suffix.lower() != ".md":
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    sheets = tables_from_md(text)
    if not sheets:
        return []
    written: List[Path] = []
    sibling = p.with_suffix(".xlsx")
    written.append(write_xlsx(sibling, sheets))
    if not job_root_granted():
        return written
    q = query or _query_from_md(text)
    target = pick_job_xlsx(q)
    try:
        if target is not None:
            written.append(patch_xlsx(target, sheets))
        else:
            dest = job_root() / sibling.name
            if dest.resolve() != sibling.resolve():
                written.append(write_xlsx(dest, sheets))
    except (OSError, RuntimeError, *_OFFICE_CONTENT_ERRORS):
        pass
    return written


def export_md_to_docx(md_path: Path) -> Path | None:
    """Export a new editable Word sibling, never overwriting an existing file.

    Missing/non-Markdown input is not an export candidate. Content, permission
    and I/O failures propagate so callers cannot report an unsuccessful export
    as a completed deliverable.
    """
    from packing_assistant.sandbox import assert_open, assert_write
    from packing_assistant.runtime.civil_config import load_config
    from packing_assistant.word_export import markdown_docx_bytes

    source = Path(md_path)
    if source.suffix.lower() != ".md":
        return None
    source = assert_open(source)
    if not source.is_file():
        return None
    if not load_config().allow_write():
        raise PermissionError("read-only sandbox: Word export is not allowed")
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Markdown 超过 2 MB，请拆分后导出 Word")
    data = markdown_docx_bytes(source.read_text(encoding="utf-8-sig"))
    number = 1
    while True:
        suffix = "" if number == 1 else f"-{number}"
        candidate = source.with_name(source.stem + suffix + ".docx")
        number += 1
        if candidate.exists() or candidate.is_symlink():
            continue
        target = assert_write(candidate)
        try:
            stream = target.open("xb")
        except FileExistsError:
            continue  # A concurrent export won this name; preserve its document.
        try:
            with stream:
                if stream.write(data) != len(data):
                    raise OSError("Word 导出未完整写入")
        except Exception:
            # This invocation created this file exclusively; remove only its
            # incomplete output and propagate the actual failure to the caller.
            try:
                assert_write(target).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return target


def job_root_granted() -> bool:
    raw = (os.getenv("CIVIL_JOB_ROOT") or "").strip()
    if not raw:
        return False
    p = Path(raw).expanduser()
    return p.is_dir() and not is_forbidden_layout(p)


def list_job_files() -> List[Dict[str, Any]]:
    """Files in the authorized job folder. Empty if CIVIL_JOB_ROOT is unset."""
    if not job_root_granted():
        return []
    root = job_root()
    rows: List[Dict[str, Any]] = []
    try:
        names = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []
    for p in names:
        if p.suffix.lower() not in JOB_EXTS:
            continue
        # CIVIL.md 是给 Civil Buddy 的工程说明，不是待处理的业务资料：当资料读进去，
        # 整份模板（含 "CN / SG / EU / DUAL" 的填写提示）会被抄进成稿并把辖区带偏。
        if p.name == "CIVIL.md":
            continue
        try:
            resolved = _resolve_job_file(p)
            if not resolved.is_file():
                continue
            size = resolved.stat().st_size
        except (OSError, RuntimeError):
            continue
        rows.append(
            {
                "name": p.name,
                "path": str(p),
                "suffix": p.suffix.lower(),
                "bytes": size,
            }
        )
        if len(rows) >= JOB_MAX_FILES:
            break
    return rows


def _read_xlsx_text(path: Path, limit: int) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        lines: List[str] = []
        for ws in wb.worksheets:
            lines.append(f"# {ws.title}")
            rows = ws.iter_rows(max_row=min(ws.max_row or 0, 80), max_col=min(ws.max_column or 0, 16), values_only=True)
            lines.append(table_markdown(rows, max(0, limit - sum(len(x) + 1 for x in lines))))
            if sum(len(x) for x in lines) >= limit:
                break
        return "\n".join(lines)[:limit]
    finally:
        wb.close()


def _read_docx_text(path: Path, limit: int) -> str:
    import zipfile
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root_el = ET.fromstring(xml)
    return docx_document_text(root_el, limit)


def read_job_file(path: Path, limit: int = JOB_FILE_CHARS) -> str:
    p = _resolve_job_file(path)
    limit = max(0, int(limit))
    if not limit:
        return ""
    suf = p.suffix.lower()
    if suf not in JOB_EXTS:
        raise ValueError("unsupported job file type")
    if suf == ".xlsx":
        return _read_xlsx_text(p, limit)
    if suf == ".docx":
        return _read_docx_text(p, limit)
    with p.open(encoding="utf-8", errors="ignore") as stream:
        text = stream.read(limit)
    return csv_text(text.lstrip("\ufeff"), limit) if suf == ".csv" else text


_BLOB_HEADER = "## 作业根文件（授权文件夹，未再上传）"


def named_files_blob(paths: Sequence[Path], *, reader: Optional[Callable[[Path, int], str]] = None) -> str:
    """The same block ``job_files_blob`` builds, for files picked by name (sub-folders and PDFs included)."""
    chunks: List[str] = []
    used = 0
    for path in paths:
        room = JOB_TOTAL_CHARS - used
        if room < 80:
            chunks.append(f"（还有 {path.name} 未贴全文）")
            continue
        try:
            body = (reader or read_job_file)(path, min(JOB_FILE_CHARS, room))
        except (OSError, RuntimeError, *_OFFICE_CONTENT_ERRORS):
            chunks.append(f"### {path.name}\n（读失败）")
            continue
        block = f"### {path.name}\n{body}"
        chunks.append(block)
        used += len(block)
    return "\n\n".join([_BLOB_HEADER, *chunks]) if chunks else ""


def job_files_blob(query: str = "") -> str:
    """Text of job-root files to prepend on run. Prefer names mentioned in query."""
    if _BLOB_HEADER in (query or ""):
        return ""   # 资料已经由调用方点名贴进来了（named_files_blob），不再整夹重贴一遍
    files = list_job_files()
    if not files:
        return ""
    q = (query or "").lower()
    named = [f for f in files if f["name"].lower() in q or Path(f["name"]).stem.lower() in q]
    pick = named or files
    chunks: List[str] = [_BLOB_HEADER]
    used = 0
    for f in pick:
        room = JOB_TOTAL_CHARS - used
        if room < 80:
            chunks.append(f"（还有 {f['name']} 未贴全文）")
            continue
        try:
            body = read_job_file(Path(f["path"]), min(JOB_FILE_CHARS, room))
        except (OSError, RuntimeError, *_OFFICE_CONTENT_ERRORS):
            chunks.append(f"### {f['name']}\n（读失败）")
            continue
        block = f"### {f['name']}\n{body}"
        chunks.append(block)
        used += len(block)
    return "\n\n".join(chunks)
