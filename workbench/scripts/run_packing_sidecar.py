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
    user = ""
    if raw.strip().startswith("{"):
        try:
            user = str(json.loads(raw).get("user_input") or "")
        except json.JSONDecodeError:
            user = raw
    else:
        user = raw
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
