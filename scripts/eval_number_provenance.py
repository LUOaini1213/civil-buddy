#!/usr/bin/env python3
"""Ground-truth benchmark for the number-provenance guard (packing_assistant/tools/number_provenance.py).

The guard must flag every quantity or clause number in a draft that the turn's evidence does not
support — and nothing else. Cases: test/benchmarks/number_provenance/cases.json.

    python scripts/eval_number_provenance.py --variant all   # what each mechanism contributes
    python scripts/eval_number_provenance.py --show          # missed and wrongly flagged items
    python scripts/eval_number_provenance.py --check         # CI floors for the shipped configuration
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.number_provenance import ABLATIONS, untraced  # noqa: E402

CASES = ROOT / "test" / "benchmarks" / "number_provenance" / "cases.json"


def _key(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).replace("％", "%").replace("：", ":").lower()


def evaluate(options, cases):
    tp = fp = fn = 0
    missed, extra = [], []
    for case in cases:
        gold = {_key(t) for t in case["untraced"]} | {_key(t) for t in case["clauses"]}
        got = {_key(item["text"]) for item in untraced(case["draft"], case["evidence"], **options)}
        tp += len(gold & got); fp += len(got - gold); fn += len(gold - got)
        missed += [(case["id"], t) for t in sorted(gold - got)]
        extra += [(case["id"], t) for t in sorted(got - gold)]
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "missed": missed, "extra": extra}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="shipped", help="a key of number_provenance.ABLATIONS, or 'all'")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    gold = sum(len(c["untraced"]) + len(c["clauses"]) for c in cases)
    clean = sum(1 for c in cases if not c["untraced"] and not c["clauses"])
    print(f"cases={len(cases)} must_flag={gold} clean_drafts={clean}")
    print(f"{'variant':30s} {'P':>6s} {'R':>6s} {'F1':>6s}   tp/fp/fn")
    names = [n for n in ABLATIONS if n != "shipped"] if args.variant == "all" else [args.variant]
    results = {}
    for name in names:
        r = results[name] = evaluate(ABLATIONS[name], cases)
        print(f"{name:30s} {r['precision']:6.3f} {r['recall']:6.3f} {r['f1']:6.3f}   {r['tp']}/{r['fp']}/{r['fn']}")
        if args.show:
            for cid, text in r["missed"]:
                print(f"    missed  [{cid}] {text}")
            for cid, text in r["extra"]:
                print(f"    extra   [{cid}] {text}")
    if args.check:
        r = results["shipped"]
        assert r["recall"] >= 0.95, r      # an invented number that gets through is the failure that matters
        assert r["precision"] >= 0.95, r   # a guard that cries wolf gets switched off
        print("PASS number_provenance floors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
