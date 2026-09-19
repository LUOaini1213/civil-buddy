#!/usr/bin/env python3
"""Score task_router's intent (chat / run / both) on test/benchmarks/task_intent/cases.json.

    python scripts/eval_task_intent.py --variant all     # what each verb group buys, and costs
    python scripts/eval_task_intent.py --show            # the misses of the shipped router
    python scripts/eval_task_intent.py --check           # CI floors

Reported per variant: accuracy overall, recall on `run`/`both` requests (a missed request is a
turn that answers with an explanation instead of the document), and the number of questions
or refusals wrongly executed (`false_run` — the expensive direction: it writes files).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.runtime import task_router  # noqa: E402

BENCH = ROOT / "test" / "benchmarks" / "task_intent"
CASES = BENCH / "cases.json"
FLOOR_ACCURACY, MAX_FALSE_RUN = 0.95, 0
HELDOUT_FLOOR = 0.90        # heldout2.json: the round the shipped rules had not seen when they were frozen


_NAMES = ("_QUESTION", "_READ_REQUEST", "_ACTION", "_FOLLOWUP_ACTION")


def score(groups, cases=None):
    saved = [getattr(task_router, name) for name in _NAMES]
    for name, pattern in zip(_NAMES, task_router.compile_intent(**groups)):
        setattr(task_router, name, pattern)
    try:
        rows = json.loads((cases or CASES).read_text(encoding="utf-8"))["cases"]
        misses = []
        for row in rows:
            got = task_router.route_task(row["text"])["intent"]
            if got != row["intent"]:
                misses.append({**row, "got": got})
    finally:
        for name, pattern in zip(_NAMES, saved):
            setattr(task_router, name, pattern)
    wanted = [r for r in rows if r["intent"] != "chat"]
    missed_requests = [m for m in misses if m["intent"] != "chat"]
    false_run = [m for m in misses if m["intent"] == "chat"]
    return {"n": len(rows), "accuracy": 1 - len(misses) / len(rows),
            "request_recall": 1 - len(missed_requests) / len(wanted), "false_run": len(false_run), "misses": misses}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="shipped")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--heldout", type=int, choices=(1, 2), default=0, help="score a held-out round instead of the development set")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    variants = task_router.ACTION_VARIANTS
    names = list(variants) if args.variant == "all" else [args.variant]
    print(f"{'variant':<28}{'acc':>7}{'req.recall':>12}{'false_run':>11}")
    result = {}
    for name in names:
        result = score(variants[name], BENCH / ("heldout.json" if args.heldout == 1 else "heldout2.json") if args.heldout else None)
        print(f"{name:<28}{result['accuracy']:>7.3f}{result['request_recall']:>12.3f}{result['false_run']:>11}")
        if args.show:
            for miss in result["misses"]:
                print(f"    want {miss['intent']:<5} got {miss['got']:<5} [{miss['kind']}] {miss['text']}")
    if args.check:
        shipped, unseen = score(variants["shipped"]), score(variants["shipped"], BENCH / "heldout2.json")
        ok = (shipped["accuracy"] >= FLOOR_ACCURACY and shipped["false_run"] <= MAX_FALSE_RUN
              and unseen["accuracy"] >= HELDOUT_FLOOR and unseen["false_run"] <= MAX_FALSE_RUN)
        print(f"dev {shipped['accuracy']:.3f}/{shipped['false_run']}  heldout2 {unseen['accuracy']:.3f}/{unseen['false_run']}")
        print(("PASS" if ok else "FAIL") + f" task_intent floors (dev accuracy >= {FLOOR_ACCURACY}, heldout2 >= {HELDOUT_FLOOR}, false_run <= {MAX_FALSE_RUN})")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
