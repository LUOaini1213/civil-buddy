#!/usr/bin/env python3
"""Drive shipped demo.mcp_surface (same kb:// and prompt names as civil-mcp)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))

from mcp_surface import (  # noqa: E402
    get_prompt,
    initialize_capabilities,
    list_prompts,
    list_resources,
    read_resource,
)


def main() -> int:
    caps = initialize_capabilities()
    assert "tools" in caps and "resources" in caps and "prompts" in caps

    res = list_resources("bid-parse", "bid")
    uris = [r["uri"] for r in res]
    assert "kb://bid/bid-parse/web-knowledge.md" in uris, uris[:8]
    assert not any("bid-tech/" in u for u in uris), uris

    ok = read_resource("bid-parse", "bid", "kb://bid/bid-parse/web-knowledge.md")
    text = ok["contents"][0]["text"]
    assert "招标解析" in text
    assert "可以投标" not in text or "不报" in text

    denied = read_resource("bid-parse", "bid", "kb://bid/bid-tech/outline.md")
    assert denied["contents"][0]["text"].startswith("拒绝")

    names = [p["name"] for p in list_prompts(expert_id="bid-parse")]
    assert names == ["civil.bid.parse"], names
    got = get_prompt(
        "civil.bid.parse",
        {"tender_text": "工期 90 个日历天", "jurisdiction": "SG"},
        expert_id="bid-parse",
    )
    body = got["messages"][0]["content"]["text"]
    assert "90" in body
    assert "不要判定可投标" in body
    sneak = get_prompt("civil.pack-ship.plan", expert_id="bid-parse")
    assert sneak.get("messages") == []

    # HTTP surface on shipped demo app
    from fastapi.testclient import TestClient

    from app import app

    client = TestClient(app)
    cap = client.get("/api/mcp/capabilities")
    assert cap.status_code == 200
    assert cap.json()["capabilities"].get("resources") is not None
    listed = client.get("/api/mcp/resources", params={"expert_id": "bid-parse"})
    assert listed.status_code == 200
    uris2 = [r["uri"] for r in listed.json()["resources"]]
    assert "kb://bid/bid-parse/web-knowledge.md" in uris2
    sib = next((u for u in uris2 if "bid-tech/" in u), None)
    assert sib is None
    got = client.post(
        "/api/mcp/prompts/get",
        json={
            "name": "civil.bid.parse",
            "expert_id": "bid-parse",
            "arguments": {"tender_text": "工期 90 个日历天", "jurisdiction": "SG"},
        },
    )
    assert got.status_code == 200, got.text
    body = got.json()["messages"][0]["content"]["text"]
    assert "90 个日历天" in body
    assert "不要判定可投标" in body
    pack_txt = get_prompt(
        "civil.pack-ship.plan", {"materials": "铁架"}, expert_id="pack-ship"
    )["messages"][0]["content"]["text"]
    assert "UNSPECIFIED" in pack_txt
    assert "xyz" in pack_txt
    print("PASS mcp_surface resources+prompts scoped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
