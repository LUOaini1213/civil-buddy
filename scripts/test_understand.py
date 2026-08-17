#!/usr/bin/env python3
"""Default surface: understand first. Questions do not write drafts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.product_turn import run_turn
    from packing_assistant.understand import understand

    assert understand("什么是 GST") == "chat"
    assert understand("临边防护算不算危大？要不要专家论证？") == "chat"
    assert understand("写临边防护方案讨论提纲") == "run"
    assert understand("先解释 GST 再出一份税务日历") == "both"

    chat = run_turn("什么是 GST")
    assert chat["intent"] == "chat"
    assert chat["wrote"] is False
    assert chat.get("matrix") is None
    assert "9%" in chat["reply"]
    assert "可以开工" not in chat["reply"]
    assert "可以投标" not in chat["reply"]
    assert "中标率" not in chat["reply"]

    hazard = run_turn("临边防护算不算危大？要不要专家论证？")
    assert hazard["intent"] == "chat" and hazard["wrote"] is False
    assert hazard.get("matrix") is None

    draft = run_turn("写临边防护方案讨论提纲。招标：未实质性响应作废标。交货期 90 个日历天。须铁架包装。")
    assert draft["intent"] == "run"
    assert draft["wrote"] is True
    rows = (draft.get("matrix") or {}).get("rows") or []
    assert rows and all(r.get("exact_text") for r in rows)
    assert draft.get("submit_blocked") is True

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    q = client.post("/api/turn", json={"text": "新加坡现在 GST 税率多少？"})
    assert q.status_code == 200, q.text
    jq = q.json()
    assert jq.get("intent") == "chat"
    assert jq.get("wrote") is False
    assert jq.get("matrix") is None
    assert "9%" in (jq.get("reply") or "")

    u = client.post("/api/understand", json={"text": "写临边防护方案讨论提纲"})
    assert u.status_code == 200
    assert u.json().get("intent") == "run"
    assert u.json().get("wrote") is False

    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "/api/turn" in index
    assert "先理解再处理" in index
    print("PASS understand", f"chat={chat['intent']} run={draft['intent']} http_chat={jq['intent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
