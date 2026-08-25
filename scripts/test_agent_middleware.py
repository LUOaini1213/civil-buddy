#!/usr/bin/env python3
"""Track 1: runtime middleware — happy path + reject + recovery. No API key."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.middleware import CHAIN, demo_bundle, run_turn

    gst = run_turn("什么是 GST", session_id="mw-t-gst")
    mw = gst.get("middleware") or {}
    assert mw.get("schema") == "civil.middleware.v1", mw
    assert mw.get("layer") == "runtime"
    assert list(mw.get("chain") or []) == list(CHAIN)
    assert gst.get("wrote") is False
    assert "9%" in (gst.get("reply") or "")
    assert gst.get("run_id")
    assert gst.get("submit_blocked") is True

    bundle = demo_bundle()
    happy = bundle["happy"]
    reject = bundle["reject"]
    recover = bundle["recover"]
    secret = bundle["secret"]

    assert happy["intent"] == "chat" and happy["wrote"] is False and happy["gst9"] is True
    assert happy["middleware"]["chain"] == list(CHAIN)

    assert reject["hitl_pending"] is True
    assert reject["wrote"] is False
    assert reject["files"] == 0
    assert reject["confirm_sentence"] is True

    for key in ("utilization", "can_fit", "mid50"):
        assert recover.get(key) == "UNSPECIFIED", (key, recover)

    assert secret.get("ok") is False
    assert secret.get("error_code") == "permission_denied"
    assert secret.get("exists") is False

    print(
        "PASS agent_middleware",
        "gst",
        gst.get("run_id"),
        "hitl",
        reject.get("run_id"),
        "pack",
        recover.get("run_id"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
