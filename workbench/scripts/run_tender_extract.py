#!/usr/bin/env python3
"""Workbench bid-parse extract sidecar. Prints one JSON object (handoff fields).

Stdin: JSON {"tender_text": "...", "project_name": "..."} or raw text.
Uses packing_assistant.tools.tender_parse.workbench_bid_extract — same transform as packing handoff.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
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
    if not text.strip():
        text = " ".join(sys.argv[1:])
    from packing_assistant.tools.tender_parse import workbench_bid_extract

    out = workbench_bid_extract(
        text, project_name=str(payload.get("project_name") or "工作台招标解析")
    )
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
