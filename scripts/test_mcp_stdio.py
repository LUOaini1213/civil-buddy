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

    con_pack = _names(pack="construction")
    assert "construction__scheme_draft" in con_pack, con_pack
    assert any(n.endswith("__scan_forbidden") or n == "construction__scan_forbidden" for n in con_pack), con_pack
    assert "tender.parse" not in con_pack, con_pack
    assert "bid-parse__extract" not in con_pack, con_pack
    assert "pack-ship__plan" not in con_pack, con_pack
    assert "method-hazard__judge_hazard" not in con_pack, con_pack
    prompts = handle({"jsonrpc": "2.0", "id": 2, "method": "prompts/list"}, pack="construction")
    pnames = [p["name"] for p in (prompts or {}).get("result", {}).get("prompts") or []]
    assert "civil.construction.scheme" in pnames, pnames
    assert "civil.method-hazard.judge" not in pnames, pnames
    assert "civil.bid.parse" not in pnames, pnames

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

    proc_c = subprocess.run(
        [sys.executable, str(ROOT / "demo" / "mcp_stdio.py"), "--pack", "construction"],
        input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n{"jsonrpc":"2.0","id":2,"method":"prompts/list"}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc_c.returncode == 0, proc_c.stderr
    lines = [ln for ln in (proc_c.stdout or "").strip().splitlines() if ln.strip()]
    assert len(lines) >= 2, proc_c.stdout
    tools_c = json.loads(lines[0])
    prompts_c = json.loads(lines[1])
    cnames = [t["name"] for t in tools_c["result"]["tools"]]
    assert "construction__scheme_draft" in cnames, cnames
    assert "construction__scan_forbidden" in cnames, cnames
    assert "tender.parse" not in cnames and "pack-ship__plan" not in cnames, cnames
    assert "bid-parse__extract" not in cnames, cnames
    assert "method-hazard__judge_hazard" not in cnames, cnames
    cprom = [p["name"] for p in prompts_c["result"]["prompts"]]
    assert "civil.construction.scheme" in cprom, cprom
    assert "civil.method-hazard.judge" not in cprom, cprom
    print("PASS mcp_stdio bid_tools", len(pnames), "construction_tools", len(cnames))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
