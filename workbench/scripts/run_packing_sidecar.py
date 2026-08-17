#!/usr/bin/env python3
"""Civil Buddy sidecar: run local packing-agent, print one JSON object.

Env:
  PACKING_AGENT_ROOT  checkout that contains packing_assistant/
Stdin: JSON {\"user_input\": \"...\"} or raw text.
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
        print(json.dumps({"ok": False, "error": "PACKING_AGENT_ROOT missing; expected monorepo root with packing_assistant/"}))
        return 2
    sys.path.insert(0, str(root))
    os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
    os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    payload: dict = {}
    user = ""
    if raw.strip().startswith("{"):
        try:
            payload = json.loads(raw)
            user = str(payload.get("user_input") or "")
        except json.JSONDecodeError:
            user = raw
    else:
        user = raw
    mode = str(payload.get("mode") or "").strip().lower()
    tender_text = str(payload.get("tender_text") or payload.get("text") or "")
    if mode in {"tender_parse", "tender", "bid-parse"} or (tender_text.strip() and not user.strip()):
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        out = run_tender_pipeline(
            tender_text or user,
            source="civil-buddy-sidecar",
            project_name=str(payload.get("project_name") or "Civil Buddy 招标解析"),
            p0_confirmed=bool(payload.get("p0_confirmed")),
        )
        print(
            json.dumps(
                {
                    "ok": bool(out.get("ok")),
                    "mode": "tender_parse",
                    "handoff": out.get("handoff"),
                    "p0_reject_scan": out.get("p0_reject_scan"),
                    "submit_blocked": out.get("submit_blocked"),
                    "tech_outline": out.get("tech_outline"),
                    "extract_table_markdown": out.get("extract_table_markdown"),
                    "n_requirements": len((out.get("parse") or {}).get("requirements") or []),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if not user.strip():
        user = " ".join(sys.argv[1:]) or "civil-buddy packing sidecar"

    from packing_assistant.harness import run_agent_pipeline

    st = run_agent_pipeline(
        user,
        enable_auto_confirm=True,
        save_artifacts=False,
        session_id="civil-buddy-sidecar",
        agent_mode="steps",
    )
    plan = st.get("container_plan") or {}
    book = st.get("booking") or plan.get("booking") or {}
    out = {
        "ok": True,
        "summary": {
            "boxes": len(st.get("boxes") or []),
            "n0": book.get("n0") or plan.get("n0"),
            "containers_used": plan.get("containers_used"),
            "can_fit": plan.get("can_fit"),
            "ship_ok": st.get("ship_ok"),
            "phase": st.get("phase"),
        },
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
