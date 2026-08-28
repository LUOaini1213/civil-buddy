#!/usr/bin/env python3
"""constraints-* files must have exactly one YAML frontmatter block; INDEX priority high.

2026-08-28 起 06_competition 拆分两赛口径：
- constraints-nus-iss.md（NUS-ISS 新加坡赛道，原 constraints.md 改名保留）
- constraints-hzzb.md（海之子杯，中建国际 AI 智能体挑战）
两文件都必须单 frontmatter、priority high，且 INDEX.yaml 各有 high 条目。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = ("constraints-nus-iss.md", "constraints-hzzb.md")


def check_frontmatter(path: Path) -> None:
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


def main() -> int:
    for name in FILES:
        path = ROOT / "knowledge_base" / "06_competition" / name
        assert path.is_file(), f"missing {path}"
        check_frontmatter(path)

    idx = (ROOT / "knowledge_base" / "INDEX.yaml").read_text(encoding="utf-8")
    for name in FILES:
        m = re.search(
            r"- path: 06_competition/" + re.escape(name) + r"\n((?:  .+\n)+)",
            idx,
        )
        assert m, f"INDEX missing {name}"
        block = m.group(0)
        assert "priority: high" in block, block
    # 旧名不得再被 INDEX 引用（口径拆分后防回窜）
    assert "06_competition/constraints.md\n" not in idx, "stale INDEX entry"
    print("PASS constraints single frontmatter + INDEX high (nus-iss + hzzb)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
