#!/usr/bin/env python3
"""3-minute live demo: happy path + one reject + recovery. No API key."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.middleware import demo_bundle

    bundle = demo_bundle()
    print("Civil Buddy · Agent Middleware")
    print("chain:", " → ".join(bundle["chain"]))
    print()
    print("1. 正常  问 GST")
    h = bundle["happy"]
    print("   intent", h["intent"], "wrote", h["wrote"], "GST 9%", h["gst9"], "run", h["run_id"])
    print()
    print("2. 拒绝  写专项方案、未打确认句")
    r = bundle["reject"]
    print(
        "   hitl",
        r["hitl_pending"],
        "wrote",
        r["wrote"],
        "files",
        r["files"],
        "确认句",
        r["confirm_sentence"],
        "run",
        r["run_id"],
    )
    print()
    print("3. 恢复  装箱无 solver → 字面 UNSPECIFIED，不编柜数")
    v = bundle["recover"]
    print("   can_fit", v["can_fit"], "mid50", v["mid50"], "run", v["run_id"])
    print()
    print("4. 密钥  写 .env")
    s = bundle["secret"]
    print("   ok", s["ok"], "error", s["error_code"], "exists", s["exists"])
    print()
    print(json.dumps({"submit_blocked": True, "secret_leak": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
