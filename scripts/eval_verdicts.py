#!/usr/bin/env python3
"""Score tools/verdict_guard on test/benchmarks/verdicts/cases.json.

    python scripts/eval_verdicts.py --variant all     # what the clause scope and each check buy
    python scripts/eval_verdicts.py --show            # misses and false flags of the shipped guard
    python scripts/eval_verdicts.py --check           # CI floors: P >= 0.95, R >= 0.95
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.verdict_guard import ABLATIONS, stated_verdicts  # noqa: E402

BENCH = ROOT / "test" / "benchmarks" / "verdicts"
FLOOR_P, FLOOR_R = 0.95, 0.95
HELDOUT_P, HELDOUT_R = 0.85, 0.90      # heldout2.json, unseen by the shipped rules (measured 0.900 / 1.000)


def score(flags, name="cases.json"):
    rows = json.loads((BENCH / name).read_text(encoding="utf-8"))["cases"]
    tp = fp = fn = 0
    notes = []
    for row in rows:
        got = [item["text"] for item in stated_verdicts(row["text"], **flags)]
        want = list(row["verdicts"])
        for phrase in got:
            if phrase in want:
                want.remove(phrase)
                tp += 1
            else:
                fp += 1
                notes.append(f"    extra   [{row['id']}] {phrase}")
        fn += len(want)
        notes += [f"    missed  [{row['id']}] {phrase}" for phrase in want]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {"p": precision, "r": recall, "tp": tp, "fp": fp, "fn": fn, "notes": notes, "n": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="shipped")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--heldout", type=int, choices=(1, 2), default=0, help="score a held-out round (2 = unseen by the shipped rules)")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    names = list(ABLATIONS) if args.variant == "all" else [args.variant]
    print(f"{'variant':<42}{'P':>7}{'R':>7}   tp/fp/fn")
    for name in names:
        result = score(ABLATIONS[name], {0: "cases.json", 1: "heldout.json", 2: "heldout2.json"}[args.heldout])
        print(f"{name:<42}{result['p']:>7.3f}{result['r']:>7.3f}   {result['tp']}/{result['fp']}/{result['fn']}")
        if args.show:
            print("\n".join(result["notes"]))
    if args.check:
        shipped, unseen = score(ABLATIONS["shipped"]), score(ABLATIONS["shipped"], "heldout2.json")
        ok = (shipped["p"] >= FLOOR_P and shipped["r"] >= FLOOR_R and unseen["p"] >= HELDOUT_P and unseen["r"] >= HELDOUT_R)
        print(f"dev {shipped['p']:.3f}/{shipped['r']:.3f}  heldout2 {unseen['p']:.3f}/{unseen['r']:.3f}")
        print(("PASS" if ok else "FAIL") + f" verdicts floors (dev P/R >= {FLOOR_P}, heldout2 P >= {HELDOUT_P}, R >= {HELDOUT_R})")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
