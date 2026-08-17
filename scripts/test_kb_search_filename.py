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
    print("PASS kb_search_filename", paths[:4])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
