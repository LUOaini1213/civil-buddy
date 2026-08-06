#!/usr/bin/env python3
"""constraints.md must have exactly one YAML frontmatter block; INDEX priority high."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "knowledge_base" / "06_competition" / "constraints.md"
    raw = path.read_text(encoding="utf-8")
    assert not raw.startswith("\ufeff"), "BOM not allowed"
    assert raw.startswith("---\n"), "must open with frontmatter"
    lines = raw.splitlines()
    delim = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
    assert len(delim) >= 2, delim
    # first two delimiters form the only frontmatter
    body = "\n".join(lines[delim[1] + 1 :]).lstrip()
    assert body.startswith("# "), body[:60]
    assert not body.startswith("---"), "dual frontmatter"
    assert "subcategory: constraints" in "\n".join(lines[delim[0] + 1 : delim[1]])
    assert "priority: high" in "\n".join(lines[delim[0] + 1 : delim[1]])

    idx = (ROOT / "knowledge_base" / "INDEX.yaml").read_text(encoding="utf-8")
    m = re.search(
        r"- path: 06_competition/constraints\.md\n((?:  .+\n)+)",
        idx,
    )
    assert m, "INDEX missing constraints.md"
    block = m.group(0)
    assert "priority: high" in block, block
    print("PASS constraints single frontmatter + INDEX high")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
