#!/usr/bin/env python3
"""Lock the industry-eval observations on shipped parse + pack-ship (not a live portal)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SAMPLE = """一、投标人须具备建筑工程施工资质及类似幕墙业绩。
二、货物须妥善包装，采用铁架防护。
三、采用海运整柜 40HQ。
四、未实质性响应招标文件的作废标处理。
五、交货期：合同签订后 90 个日历天内到港。
"""


def main() -> int:
    from packing_assistant.tools.pack_ship_mcp import call_tool
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    pipe = run_tender_pipeline(SAMPLE, source="industry-eval", p0_confirmed=False)
    assert pipe.get("submit_blocked") is True
    rows = (pipe.get("matrix") or {}).get("rows") or []
    assert rows and all(r.get("exact_text") for r in rows), rows
    assert (pipe.get("p0_reject_scan") or {}).get("human_confirm_required") is True
    assert (pipe.get("review") or {}).get("业绩") == []
    hist = (ROOT / "docs" / "civil-buddy" / "industry-agent-eval-2026-08-17.md").read_text(encoding="utf-8")
    assert "**总判：部分合格。**" in hist
    now = (ROOT / "docs" / "civil-buddy" / "industry-agent-eval-2026-08-25.md").read_text(encoding="utf-8")
    assert "合格" in now and "内部起草搭子" in now
    assert "完全合格" in now
    assert "可以投标" not in now.split("禁止")[0] or "禁止" in now
    track = (ROOT / "docs" / "civil-buddy" / "track1-qualified.md").read_text(encoding="utf-8")
    assert "完全合格" in track
    assert "可以开工" not in track or "禁止" in track
    kb = (ROOT / "demo" / "kb" / "finance" / "finance-tax" / "web-knowledge.md").read_text(encoding="utf-8")
    assert "9%" in kb and "Current GST rates" in kb
    bid = (ROOT / "demo" / "kb" / "bid" / "bid-parse" / "web-knowledge.md").read_text(encoding="utf-8")
    assert "GeBIZ" in bid
    assert "评分办法" not in bid or "只抄" in bid or "PQM" in bid

    off = call_tool("pack-ship__plan", {"connected": False})
    for key in ("utilization", "can_fit", "mid50", "系固待办"):
        assert off.get(key) == "UNSPECIFIED", (key, off)

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    r = client.post("/api/tender/parse", json={"text": SAMPLE})
    assert r.status_code == 200, r.text
    assert r.json().get("submit_blocked") is True
    print("PASS industry_agent_eval blocked=1 exact=1 unspecified=1 hist=部分合格 now=合格-内部起草搭子 track1=完全合格")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
