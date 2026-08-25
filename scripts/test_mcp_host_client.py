#!/usr/bin/env python3
"""H3: fake MCP host like Cursor — initialize / tools/list / tools/call over stdio."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rpc(pack: str, messages: list[dict]) -> list[dict]:
    blob = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages)
    proc = subprocess.run(
        [sys.executable, "-m", "packing_assistant.civil", "mcp", "--pack", pack],
        input=blob,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        timeout=45,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    out = []
    for ln in lines:
        row = json.loads(ln)
        if isinstance(row, dict) and "id" in row:
            out.append(row)
    return out


def main() -> int:
    msgs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "civil-host-test"}},
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "search_kb", "arguments": {"query": "专项方案"}},
        },
    ]
    rows = _rpc("construction", msgs)
    by_id = {r.get("id"): r for r in rows}
    assert 1 in by_id and 2 in by_id and 3 in by_id, rows
    init = by_id[1]["result"]
    assert init["serverInfo"]["name"] == "civil-buddy"
    names = [t["name"] for t in by_id[2]["result"]["tools"]]
    assert "construction__scheme_draft" in names, names
    assert "search_kb" in names, names
    assert "tender.parse" not in names, names
    assert "bid-parse__extract" not in names, names
    assert "pack-ship__plan" not in names, names
    called = by_id[3]
    assert "error" not in called, called
    body = called["result"]
    assert body.get("isError") is False, body
    text = (body.get("content") or [{}])[0].get("text") or ""
    payload = json.loads(text)
    assert payload.get("ok") is True, payload
    assert payload.get("name") == "search_kb"
    print("PASS test_mcp_host_client construction", len(names), "tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
