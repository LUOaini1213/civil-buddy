#!/usr/bin/env python3
"""Gate: an English tender read by its structure - through the real entry point, as a Word file.

    python scripts/test_english_itt.py

Two made-up documents of test/benchmarks/real_tender: en_itt (SECTION n, an "Appendix to the Instructions to Tenderers"
as the front table, weights in per cent) and en_bds (the multilateral-bank shape: "Section II. Bid Data Sheet" as a
two-column table of sentences, criteria in points). en_bds was written after the rules were frozen on en_itt and run
once: fields 0/12, rejections 1/5, scores 0/4, forms 0/4 - "Section I." with a full stop was no chapter, and with no
chapters nothing else was found. What is asserted here are the development floors after that.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_real_document as erd  # noqa: E402

BENCH = ROOT / "test" / "benchmarks" / "real_tender"


def main() -> int:
    failed = []
    for name in ("en_itt", "en_bds"):
        out_dir = ROOT / "output" / f"gate_{name}"
        erd.deliver(BENCH / f"{name}.md", out_dir, as_word=True)
        md = (out_dir / "tender.parse.md").read_text(encoding="utf-8")
        got = erd.score(md, json.loads((BENCH / f"{name}.gold.json").read_text(encoding="utf-8")), verbose=False)
        print(f"[{name}] {got}")
        if got.get("fields_wrong"):
            failed.append(f"{name}: {got['fields_wrong']} field(s) WRONG")
        for key in ("fields", "rejections", "scores", "forms"):
            have, want = (int(x) for x in str(got.get(key, "0/0")).split("/"))
            if have < want:
                failed.append(f"{name}: {key} {have}/{want}")
    for line in failed:
        print("FAIL", line)
    print(("FAIL" if failed else "PASS") + " english-itt (2 documents)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
