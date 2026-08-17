#!/usr/bin/env python3
"""Drive shipped demo.mcp_surface (same kb:// and prompt names as civil-mcp)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))

from mcp_surface import (  # noqa: E402
    call_tool,
    get_prompt,
    initialize_capabilities,
    list_prompts,
    list_resources,
    list_tools,
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

    # Discoverable pack-ship list / plan / export (cold import + HTTP)
    names = [t["name"] for t in list_tools(expert_id="pack-ship")]
    assert "pack-ship__list" in names and "pack-ship__plan" in names and "pack-ship__export" in names, names
    listed = call_tool("pack-ship__list", {}, expert_id="pack-ship")
    assert set(listed.get("names") or []) >= {"pack-ship__list", "pack-ship__plan", "pack-ship__export"}
    off = call_tool("pack-ship__plan", {"connected": False}, expert_id="pack-ship")
    for key in ("utilization", "can_fit", "mid50", "系固待办"):
        assert off.get(key) == "UNSPECIFIED", (key, off)
    exp_off = call_tool("pack-ship__export", {"connected": False}, expert_id="pack-ship")
    for key in ("utilization", "can_fit", "mid50", "系固待办"):
        assert exp_off.get(key) == "UNSPECIFIED", (key, exp_off)
    solver = {
        "utilization": 0.71,
        "can_fit": True,
        "mid50": 0.62,
        "系固待办": ["绑扎未确认"],
    }
    on = call_tool("pack-ship__plan", {"solver": solver, "connected": True}, expert_id="pack-ship")
    assert on.get("utilization") == 0.71 and on.get("can_fit") is True
    assert on.get("mid50") == 0.62 and on.get("系固待办") == ["绑扎未确认"]
    exp_on = call_tool("pack-ship__export", {"solver": solver, "connected": True}, expert_id="pack-ship")
    assert exp_on.get("utilization") == 0.71
    assert exp_on.get("can_fit") is True
    assert exp_on.get("mid50") == 0.62
    assert exp_on.get("系固待办") == ["绑扎未确认"]

    hl = client.get("/api/mcp/tools", params={"expert_id": "pack-ship"})
    assert hl.status_code == 200, hl.text
    hnames = [t["name"] for t in hl.json()["tools"]]
    assert set(hnames) >= {"pack-ship__list", "pack-ship__plan", "pack-ship__export"}, hnames
    hp = client.post(
        "/api/mcp/tools/call",
        json={"name": "pack-ship__plan", "expert_id": "pack-ship", "arguments": {"connected": False}},
    )
    assert hp.status_code == 200, hp.text
    jp = hp.json()
    assert jp.get("can_fit") == "UNSPECIFIED" and jp.get("系固待办") == "UNSPECIFIED"
    hx = client.post(
        "/api/mcp/tools/call",
        json={
            "name": "pack-ship__export",
            "expert_id": "pack-ship",
            "arguments": {"solver": solver, "connected": True},
        },
    )
    assert hx.status_code == 200, hx.text
    assert hx.json().get("utilization") == 0.71
    sneak_tools = client.get("/api/mcp/tools", params={"expert_id": "bid-parse"})
    assert sneak_tools.status_code == 200
    assert sneak_tools.json()["tools"] == []

    print("PASS mcp_surface resources+prompts scoped pack-ship list/plan/export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
