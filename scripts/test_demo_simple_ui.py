#!/usr/bin/env python3
"""Structural + shipped-path checks for frontend demo-simple first-glance mode.

Drives the real frontend/workbench.html artifact (no re-implementation of UI
logic). The packing workbench UI moved from index.html to workbench.html when
index.html became the tender-delivery mainline entry.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "frontend" / "workbench.html"


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

    # Simple mode must display:none sidebar (width:0 still stacks in 1-col grid)
    if "display: none !important" not in text or ".shell.demo-simple .sidebar" not in text:
        fails.append("missing CSS rule to display:none sidebar in demo-simple")
    if re.search(
        r"\.shell\.demo-simple\s+\.sidebar\s*\{[^}]*width:\s*0",
        text,
        re.S,
    ) and "display: none !important" not in text[
        text.find(".shell.demo-simple .sidebar") : text.find(".shell.demo-simple .sidebar") + 200
    ]:
        fails.append("sidebar still width:0 only (causes empty middle)")

    # Toggle control present
    if "简洁演示" not in text:
        fails.append("missing 简洁演示 toggle label")

    # Advanced actions gated when simple (v-show !demoSimpleMode)
    if "v-show=\"!demoSimpleMode\"" not in text and "v-show='!demoSimpleMode'" not in text:
        fails.append("advanced controls not gated by !demoSimpleMode")

    # Essential pills still visible in simple: 网关 + 待 HITL path
    if "网关" not in text:
        fails.append("gateway pill missing")

    # Simple mode is a guided 3-step script (meaningful, not just hide sidebar)
    if 'data-demo-script="true"' not in text and "demo-script" not in text:
        fails.append("missing demo-script guided strip")
    if "demoScriptStep" not in text or "goDemoStep" not in text:
        fails.append("missing demoScriptStep / goDemoStep wiring")
    if "三步" not in text and "第 1 步" not in text:
        fails.append("missing 3-step script copy")
    if "满载成箱" not in text or "人确认" not in text:
        fails.append("missing step labels 满载成箱 / 人确认")
    if "is-landing" not in text:
        fails.append("missing is-landing full-middle landing class")
    if "ds-features" not in text:
        fails.append("missing ds-features inside demo-script landing")
    # grid must not leave permanent 320px empty column by default
    if "has-drawer" not in text:
        fails.append("missing has-drawer grid switch (avoids empty middle column)")
    if "grid-template-columns: 1fr 320px" in text and "has-drawer" in text:
        # ok if only under .has-drawer
        import re as _re
        if not _re.search(r"\.workspace-split\.has-drawer\s*\{[^}]*1fr 320px", text, _re.S):
            # still accept if default is 1fr
            if "/* 默认单列" not in text and "grid-template-columns: 1fr;" not in text:
                fails.append("workspace-split still always two-column")

    # Empty-middle fix: absolute fill landing (not center-in-tall-void)
    if "position: absolute" not in text or "inset: 12px" not in text:
        fails.append("missing absolute inset landing fill for simple no-result")
    if "min-height: min(72vh, 680px)" in text:
        fails.append("legacy workspace-inner min(72vh) hole still present")
    if "justify-content: center" in text and "is-landing" in text:
        # disallow center-only landing that parks card mid/low
        if re.search(
            r"is-landing[^{]*\{[^}]*justify-content:\s*center",
            text,
            re.S,
        ):
            fails.append("is-landing still uses justify-content:center (causes upper void)")
    if ".shell.demo-simple.no-result .workspace" not in text:
        fails.append("missing no-result workspace fill selectors")
    if "开始第 1 步" not in text and "满载演示" not in text:
        fails.append("missing first-step CTA copy")


    # Simple tag copy for first glance
    if "tools 定柜" not in text and "人确认成箱" not in text:
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
