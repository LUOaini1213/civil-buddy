#!/usr/bin/env python3
"""Track 1: policy engine + failure recovery. Locked 4-beat live script."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.middleware import CHAIN, live_script, run_turn
    from packing_assistant.runtime.tool_engine import ERR_CIRCUIT, ERR_DENIED, get_engine

    gst = run_turn("什么是 GST", session_id="mw-t-gst")
    mw = gst.get("middleware") or {}
    assert mw.get("schema") == "civil.middleware.v1", mw
    assert mw.get("layer") == "runtime"
    assert list(mw.get("chain") or []) == list(CHAIN)
    assert gst.get("wrote") is False
    assert "9%" in (gst.get("reply") or "")

    script = live_script()
    assert script["chain"] == list(CHAIN)
    beats = {b["id"]: b for b in script["beats"]}
    assert set(beats) == {"order", "unauthorized", "recover", "fuse"}

    order = beats["order"]
    assert order["wrote"] is True, order
    assert order["gst9"] is True, order
    assert order["files"] >= 1, order
    assert order["policy"] == "ALLOW"

    unauth = beats["unauthorized"]
    assert unauth["policy"] == "DENY"
    assert "pack-ship__plan" in (unauth["reason"] or "")
    assert "bid-parse" in (unauth["reason"] or "")
    assert unauth["error_code"] == ERR_DENIED
    assert "secret" in (unauth["secret_reason"] or "").lower() or ".env" in (unauth["secret_reason"] or "")
    assert unauth["files"] == 0

    rec = beats["recover"]
    assert rec["can_fit"] == "UNSPECIFIED", rec
    assert rec["action"] == "degrade", rec
    assert "timeout" in rec["audit"] or "retry" in rec["audit"], rec["audit"]
    assert "degrade" in rec["audit"], rec["audit"]
    assert rec["attempts"] >= 1

    fuse = beats["fuse"]
    assert fuse["policy"] == "CIRCUIT"
    assert fuse["executed"] is False
    assert fuse["error_code"] == ERR_CIRCUIT
    assert "超限" in (fuse["reason"] or "") or "熔断" in (fuse["reason"] or "")

    sib = get_engine().execute(
        "pack-ship__plan",
        {"connected": False},
        expert_id="bid-parse",
        intent="run",
    )
    assert sib.get("ok") is False
    assert sib.get("reason")

    print(
        "PASS agent_middleware",
        "order",
        order.get("run_id"),
        "deny",
        unauth.get("error_code"),
        "degrade",
        rec.get("action"),
        "fuse",
        fuse.get("error_code"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
