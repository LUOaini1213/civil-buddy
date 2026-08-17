#!/usr/bin/env python3
"""Drive Singapore façade English bid-book (shipped assembler + optional API)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SAMPLE = """
Marina Bay Sample Façade Package
Tenderer shall have similar curtain-wall track record.
Goods shall be packed in crates; ocean freight 40HQ preferred.
Centre of gravity and lashing shall follow CTU.
Delivery within 90 calendar days.
Non-substantial response shall be rejected.
"""


def _assert_no_invented_money(md: str) -> None:
    # Allow "S$ [TO FILL]" only — reject S$ 1.2m / SGD 50000 etc.
    for m in re.finditer(r"(?:S\$|SGD)\s*([^\n|]*)", md, flags=re.I):
        tail = m.group(1).strip()
        assert "[TO FILL]" in tail, f"invented money near {m.group(0)!r}"
        assert not re.search(r"\d", tail.replace("[TO FILL]", "")), tail


def main() -> int:
    from packing_assistant.bidbook.sg_facade import (
        DEMO_BIDDER,
        REQUIRED_HEADINGS,
        build_sg_facade_bidbook,
    )
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    pipe = run_tender_pipeline(
        SAMPLE,
        packing_summary={
            "can_fit": True,
            "containers_used": 1,
            "n0": 1,
            "ship_ok": True,
            "mid50": 0.72,
            "container_type": "40HQ",
            "phase": "done",
        },
        source="bidbook-unit",
    )
    assert pipe.get("bidbook_markdown")
    md = pipe["bidbook_markdown"]
    book = pipe["bidbook"]
    assert book["schema"] == "tender.bidbook.sg_facade.v1"
    assert book["jurisdiction"] == "SG"
    assert book["language"] == "en"
    assert book["bidder"]["legal_name"] == DEMO_BIDDER["legal_name"]
    assert "REDACTED-CLIENT" not in md
    assert "DRAFT" in md and "NOT FOR" in md
    for h in REQUIRED_HEADINGS:
        assert h in md, h
    assert "[TO FILL]" in md
    assert "UEN" in md
    assert "can_fit" in md and "0.72" in md or "72" in md
    assert "No Deviation" in md or "Pending" in md
    _assert_no_invented_money(md)
    # title inferred from Latin first line
    assert "Marina Bay" in md or "Singapore" in md

    # no packing → logistics says not run
    empty = build_sg_facade_bidbook(tender_text=SAMPLE)
    assert "not run" in empty["markdown"].lower() or "No packing" in empty["markdown"]

    print(
        "PASS sg_facade_bidbook",
        f"chars={book['n_chars']}",
        f"title={book['project_title']!r}",
        f"open={len(pipe.get('open_actions') or [])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
