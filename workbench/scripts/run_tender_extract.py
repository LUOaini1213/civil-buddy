#!/usr/bin/env python3
"""Workbench bid-parse extract sidecar. Prints one JSON object (handoff fields).

Stdin: JSON {"tender_text": "...", "project_name": "...", "files": [{"path": "...", "name": "招标文件.pdf"}]} or raw text.
Uses packing_assistant.tools.tender_parse.workbench_bid_extract — same transform as packing handoff.

``files`` are the ORIGINAL uploads of the session (the workbench keeps them as <id>.bin beside the text it extracted
itself). They are read here, whole, by the readers the command line uses - a PDF by what its pages draw
(tools/pdf_grid.py), a Word file with its list numbers - and handed to the parser under the file marks it knows
("### 招标文件.pdf"). The workbench's own extractor keeps a prefix of twenty thousand characters for the prompt; a tender
is five times that, and a draft made from a fifth of it reads exactly like one made from all of it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MAX_FILES = 8


def _whole_text(path: Path, name: str) -> str:
    """One original upload as text; "" when it cannot be read here (the caller falls back to its own reading)."""
    from packing_assistant import office_job

    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".pdf":
            with path.open("rb") as stream:
                return office_job.pdf_document_text(stream)
        if suffix == ".docx":
            return office_job._read_docx_text(path, office_job.DOCUMENT_FILE_CHARS)
        if suffix in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")[: office_job.DOCUMENT_FILE_CHARS]
    except Exception:  # noqa: BLE001 - an unreadable file is reported by its absence; the caller keeps its own text
        return ""
    return ""


def main() -> int:
    root = Path(os.environ.get("PACKING_AGENT_ROOT") or "").expanduser()
    if not root.is_dir() or not (root / "packing_assistant").is_dir():
        here = Path(__file__).resolve()
        for cand in (here.parents[2], here.parents[1], Path.cwd()):
            if (cand / "packing_assistant").is_dir():
                root = cand
                break
    if not root.is_dir() or not (root / "packing_assistant").is_dir():
        print(json.dumps({"ok": False, "error": "PACKING_AGENT_ROOT missing"}))
        return 2
    sys.path.insert(0, str(root))

    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace") if not sys.stdin.isatty() else ""
    payload: dict = {}
    text = ""
    if raw.strip().startswith("{"):
        try:
            payload = json.loads(raw)
            text = str(payload.get("tender_text") or payload.get("text") or "")
        except json.JSONDecodeError:
            text = raw
    else:
        text = raw
    read = []
    for item in list(payload.get("files") or [])[:MAX_FILES]:
        if not isinstance(item, dict):
            continue
        path, name = Path(str(item.get("path") or "")), str(item.get("name") or "")
        if not name or not path.is_file():
            continue
        body = _whole_text(path, name)
        if body.strip():
            read.append(name)
            text = (text.rstrip() + "\n\n" if text.strip() else "") + f"### {name}\n{body}"
    if not text.strip():
        text = " ".join(sys.argv[1:])
    from packing_assistant.tools.tender_parse import workbench_bid_extract

    out = workbench_bid_extract(
        text, project_name=str(payload.get("project_name") or "工作台招标解析")
    )
    out["files_read"] = read
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
