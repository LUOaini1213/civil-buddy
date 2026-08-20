#!/usr/bin/env python3
"""T011: /api/tender/parse goes through ToolEngine; chat intent does not write."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    chat = client.post(
        "/api/tender/parse",
        json={"text": "交货期 90 个日历天。铁架包装。", "intent": "chat"},
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert body.get("ok") is False
    assert body.get("error_code") == "permission_denied"
    assert body.get("wrote") is False
    assert body.get("matrix") is None

    run = client.post(
        "/api/tender/parse",
        json={"text": "交货期 90 个日历天。铁架包装。未实质性响应作废标。", "intent": "run"},
    )
    assert run.status_code == 200, run.text
    jp = run.json()
    assert jp.get("ok") is True
    assert jp.get("submit_blocked") is True
    assert (jp.get("matrix") or {}).get("rows")
    print("PASS tender_parse_engine chat_denied run_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
