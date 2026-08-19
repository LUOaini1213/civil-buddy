#!/usr/bin/env python3
"""M1: Python stdio MCP. pack=bid lists KB+tender, not pack-ship__plan."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))
sys.path.insert(0, str(ROOT))

from mcp_stdio import handle  # noqa: E402
from mcp_surface import list_tools  # noqa: E402


def _names(pack: str | None = None, expert: str | None = None) -> list[str]:
    return [t["name"] for t in list_tools(expert_id=expert, pack=pack)]


def main() -> int:
    bid = _names(pack="bid")
    assert "search_kb" in bid and "tender.parse" in bid, bid
    assert "pack-ship__plan" not in bid, bid
    parse = _names(expert="bid-parse")
    assert "bid-parse__extract" in parse
    assert "pack-ship__plan" not in parse
    con = _names(expert="construction")
    assert "construction__scheme_draft" in con
    assert "bid-parse__extract" not in con
    pack = _names(expert="pack-ship")
    assert "pack-ship__plan" in pack

    listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, pack="bid")
    assert listed and listed.get("result")
    names = [t["name"] for t in listed["result"]["tools"]]
    assert "tender.parse" in names and "pack-ship__plan" not in names, names

    proc = subprocess.run(
        [sys.executable, str(ROOT / "demo" / "mcp_stdio.py"), "--pack", "bid"],
        input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    line = (proc.stdout or "").strip().splitlines()[-1]
    payload = json.loads(line)
    pnames = [t["name"] for t in payload["result"]["tools"]]
    assert "search_kb" in pnames and "tender.parse" in pnames
    assert "pack-ship__plan" not in pnames
    print("PASS mcp_stdio bid_tools", len(pnames))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
