#!/usr/bin/env python3
"""ux(round14) 符号纪律门禁：浏览器资产不得出现装饰性状态符号（emoji/dingbats）。

规则（spec 附录 L）：
- 禁用：状态符号 ✓ ⚠ ⛔ ✅ ✗ ✕ ✅ 类 dingbats 与 emoji（🗺🔧📦☰ 等）——一律改纯文字或 CSS 圆点；
- 豁免：★（评分点业务排版，标书语境真实用法）与 →（流程箭头，正文排版）；
- 范围：前端浏览器资产（html/js/css，含 vendored 副本）。

用法：python scripts/test_ux_no_emoji.py   （退出码 0=干净，1=有残留并列出）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# U+2600–U+27BF（杂项符号+dingbats）、U+2B00–U+2BFF（箭头符号）、U+1F300–U+1FAFF（emoji）、U+FE0F（变体选择符）
FORBIDDEN = (
    [chr(c) for c in range(0x2600, 0x27C0)]
    + [chr(c) for c in range(0x2B00, 0x2C00)]
    + [chr(c) for c in range(0x1F300, 0x1FB00)]
    + ["\ufe0f"]
)
# 业务排版豁免：★ 评分点（标书语境）、→ 流程箭头
ALLOWED = {"\u2605", "\u2192", "\u00d7"}  # ★ → ×
TARGETS = [
    "frontend/index.html",
    "frontend/workbench.html",
    "demo/static/index.html",
    "demo/static/app.js",
    "demo/static/styles.css",
    "demo/static/docpreview.js",
    "demo/static/fixcard.js",
    "frontend/vendor/cb-doc.js",
    "frontend/vendor/cb-fix.js",
]


def main() -> int:
    bad: list[str] = []
    for rel in TARGETS:
        p = ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        for ch in FORBIDDEN:
            if ch in ALLOWED:
                continue
            idx = text.find(ch)
            while idx != -1:
                line = text.count("\n", 0, idx) + 1
                ctx = text[max(0, idx - 24) : idx + 24].replace("\n", " ")
                bad.append(f"{rel}:{line} {ch!r} …{ctx}…")
                idx = text.find(ch, idx + 1)
    if bad:
        print(f"FAIL 符号残留 {len(bad)} 处（规则见 docs/ux/ux-design-spec.md 附录 L）：")
        for b in bad[:30]:
            print("  " + b)
        return 1
    print("PASS 符号纪律：浏览器资产 0 装饰符号（★评分点/→箭头/×关闭 豁免）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
