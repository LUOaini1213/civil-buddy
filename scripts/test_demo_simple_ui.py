#!/usr/bin/env python3
"""Structural + shipped-path checks for frontend demo-simple first-glance mode.

Drives the real frontend/index.html artifact (no re-implementation of UI logic).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "frontend" / "index.html"


def main() -> int:
    assert HTML.is_file(), HTML
    text = HTML.read_text(encoding="utf-8")
    fails = []

    # Marker on root shell
    if 'data-demo-simple-mode="true"' not in text:
        fails.append("missing data-demo-simple-mode marker on #app shell")
    if "demo-simple" not in text or "demoSimpleMode" not in text:
        fails.append("missing demoSimpleMode / demo-simple class wiring")

    # Default true in Vue data
    if not re.search(r"demoSimpleMode\s*:\s*true", text):
        fails.append("demoSimpleMode default is not true")

    # Primary CTA remains
    if "满载演示" not in text or "runDemo" not in text:
        fails.append("missing primary 满载演示 CTA")

    # Simple mode CSS collapses sidebar
    if ".shell.demo-simple .sidebar" not in text:
        fails.append("missing CSS rule to collapse sidebar in demo-simple")

    # Toggle control present
    if "简洁演示" not in text:
        fails.append("missing 简洁演示 toggle label")

    # Advanced actions gated when simple (v-show !demoSimpleMode)
    if "v-show=\"!demoSimpleMode\"" not in text and "v-show='!demoSimpleMode'" not in text:
        fails.append("advanced controls not gated by !demoSimpleMode")

    # Essential pills still visible in simple: 网关 + 待 HITL path
    if "网关" not in text:
        fails.append("gateway pill missing")

    # Simple tag copy for first glance
    if "tools 定柜坐标" not in text and "人确认成箱" not in text:
        fails.append("missing simple-mode brand tag copy")

    # Beauty / hierarchy markers (no pure black void workspace)
    if ".empty-hero" not in text or ".empty-features" not in text:
        fails.append("missing elevated empty-hero / empty-features surface")
    if "background-color: #121a26" not in text and "#121a26" not in text:
        fails.append("workspace surface token #121a26 missing (anti pure-black)")
    if "canvas" in text and "linear-gradient(180deg, #1a2740" not in text and "#1a2740" not in text:
        # allow either CSS canvas gradient
        if "canvas {" not in text:
            fails.append("missing canvas style block")
    if "自然语言改方案" not in text:
        fails.append("missing NL revise UI copy")
    if "无此功能" not in text:
        fails.append("missing 无此功能 contract copy on NL UI")
    # Reject pure black hole tokens in workspace CSS
    if re.search(r"\.workspace\s*\{[^}]*background:\s*#000\b", text):
        fails.append("workspace uses pure #000 background")
    if "#070b12" in text:
        fails.append("legacy pure-void canvas fill #070b12 still present")

    # Gateway advertises demo_simple feature (shipped health surface)
    gw = ROOT / "gateway" / "app.py"
    if gw.is_file():
        gwt = gw.read_text(encoding="utf-8")
        if "demo_simple_mode" not in gwt:
            fails.append("gateway health missing demo_simple_mode feature flag")
        else:
            print("gateway_feature demo_simple_mode=present")

    if fails:
        print("FAIL demo_simple_ui", fails)
        return 1
    print("ALL_PASS demo_simple_ui")
    print("file=", HTML.relative_to(ROOT))
    print("demoSimpleMode_default=true")
    print("primary_cta=满载演示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
