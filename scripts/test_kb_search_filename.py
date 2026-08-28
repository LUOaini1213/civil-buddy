#!/usr/bin/env python3
"""Drive shipped demo rag.search_kb — filename tokens should surface web-knowledge."""

from __future__ import annotations

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "demo"
sys.path.insert(0, str(DEMO))

from rag import search_kb  # noqa: E402


def main() -> int:
    hits = search_kb("bid-parse", "bid", "web-knowledge handoff P0", limit=8)
    paths = [h.path.replace("\\", "/") for h in hits]
    assert any("bid-parse/web-knowledge.md" in p for p in paths), paths
    # still scoped: no other expert private lib
    assert not any("/bid-tech/" in p for p in paths), paths
    body = next(h for h in hits if "bid-parse/web-knowledge.md" in h.path.replace("\\", "/"))
    assert body.score > 0

    labor = search_kb("hr-labor", "hr", "Employment Act KETs TADM 劳动合同", limit=8)
    lpaths = [h.path.replace("\\", "/") for h in labor]
    assert any("hr-labor/web-knowledge.md" in p for p in lpaths), lpaths
    assert not any("/hr-recruit/" in p for p in lpaths), lpaths
    kb = DEMO / "kb" / "hr" / "hr-labor"
    web = (kb / "web-knowledge.md").read_text(encoding="utf-8")
    assert "Employment Act" in web
    assert "Key employment terms" in web or "KETs" in web
    assert "TADM" in web
    assert "劳动合同法" in web
    assert "保障农民工工资支付条例" in web
    assert "可以开工" not in web
    assert "一定能赢" not in web
    faq = (kb / "faq.md").read_text(encoding="utf-8")
    assert faq.count("问：") >= 5
    assert "合同 of service" in faq or "contract of service" in faq
    readme = (kb / "README.md").read_text(encoding="utf-8")
    assert "| 栏 |" in readme
    outline = (kb / "outline.md").read_text(encoding="utf-8")
    assert "KETs" in outline
    assert "TADM" in outline
    print("PASS kb_search_filename", paths[:4], "hr-labor", lpaths[:3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
