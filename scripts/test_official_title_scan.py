#!/usr/bin/env python3
"""T007/T008: GST 9% if a post writes GST; CORENET anti-example not current."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "demo" / "kb"
COMPANY = KB / "company" / "web-portals.md"
_URL = re.compile(r"https?://\S+", re.I)


def _body(text: str) -> str:
    return _URL.sub(" ", text)


def _gst_ok(text: str) -> bool:
    blob = _body(text)
    if "GST" not in blob and "gst" not in blob:
        return True
    if "9%" not in blob:
        return False
    for line in blob.splitlines():
        if "7%" in line or "8%" in line:
            if not any(k in line for k in ("背景", "历史", "升档", "2023", "2024", "曾", "旧")):
                return False
    return True


def _corenet_ok(text: str) -> bool:
    bad = "全部新项目不论 GFA"
    if bad not in text:
        return True
    # allowed only as historical, next to 曾写 / 已被 / 收窄 / 取代 / 不得再
    for line in text.splitlines():
        if bad not in line and "全部新项目不论 GFA" not in line:
            continue
        if not any(k in line for k in ("曾写", "已被", "收窄", "取代", "不得再", "不再")):
            return False
    return True


def main() -> int:
    company = COMPANY.read_text(encoding="utf-8")
    assert "9%" in company and "APPBCA-2026-12" in company
    fails: list[str] = []
    for path in KB.rglob("web-knowledge.md"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if not _gst_ok(text):
            fails.append(f"T007 {rel}")
        if not _corenet_ok(text):
            fails.append(f"T008 {rel}")
    portals = COMPANY.read_text(encoding="utf-8")
    if not _corenet_ok(portals):
        fails.append("T008 company/web-portals.md")
    assert not fails, "\n".join(fails)
    print("PASS official_title_scan gst=9 corenet=appbca")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
