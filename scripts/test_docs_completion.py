#!/usr/bin/env python3
"""D1: five completion docs exist, lock 66 and submit_blocked, no 可以投标 as capability."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "civil-buddy"
FILES = (
    "GETTING-STARTED.md",
    "PROTOCOL.md",
    "MCP.md",
    "SKILLS.md",
    "KB.md",
    "product-plan.md",
)


def main() -> int:
    blob = ""
    for name in FILES:
        p = DOCS / name
        assert p.is_file(), p
        text = p.read_text(encoding="utf-8")
        blob += text + "\n"
        assert "可以投标" not in text or "不判定可投标" in text or "不判定可以投标" in text or "禁止" in text, name
        if "中标率" in text:
            assert "禁止" in text or "不当" in text or "不是" in text, name
    assert "66" in blob
    assert "submit_blocked" in blob
    plan = (DOCS / "product-plan.md").read_text(encoding="utf-8")
    assert "全量产品规划书" in plan
    assert "lane-bid" in plan and "lane-people" in plan
    assert "不准空转" in plan
    assert "T001" in plan and "T047" in plan
    assert "APPBCA-2026-12" in plan
    assert "The current GST rate in Singapore is 9%" in plan or "9%" in plan
    assert (DOCS / "mcp-host.example.toml").is_file()
    assert (DOCS / "product-completion-plan.md").is_file()
    print("PASS docs_completion", " ".join(FILES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
