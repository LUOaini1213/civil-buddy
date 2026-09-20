#!/usr/bin/env python3
"""Ground-truth benchmark for the tender-requirement ↔ bid-response comparison.

Measures, against hand-labelled cases (test/benchmarks/tender_response/cases.json):
  links      does the comparison show the reviewer the response lines that address a tender line
  conflicts  does it notice a stated quantity that does not meet the tender's number
  rows       how many comparison rows it emits per distinct tender line (1.0 = no duplicates)

No model, no network. `--variant all` prints the ablation table the design was chosen from;
`--check` asserts the floors that CI enforces for the shipped configuration.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.tender_parse import parse_tender_text  # noqa: E402

CASES = ROOT / "test" / "benchmarks" / "tender_response" / "cases.json"
_PUNCT = re.compile(r"[\s。；;．.，,：:！!？?]+$")


def _norm(text: str) -> str:
    return _PUNCT.sub("", str(text or "").strip())


def _variants():
    from packing_assistant.tools import tender_response_match as m

    return {name: (lambda req, src, _o=opts: m.compare_responses(req, src, **_o)) for name, opts in m.ABLATIONS.items()}


def evaluate(compare, cases):
    tp = fp = fn = ctp = cfp = cfn = rows_total = lines_with_rows = unreachable = 0
    misses, extras = [], []
    for case in cases:
        tender, response = case["tender"], case["response"]
        sources = [{"source_id": "tender", "role": "tender", "text": "\n".join(tender), "start": 0},
                   {"source_id": "response", "role": "response", "text": "\n".join(response), "start": 0}]
        requirements = parse_tender_text(sources[0]["text"])["requirements"]
        rows = compare(requirements, sources)
        rows_total += len(rows)
        response_index = {_norm(line): i for i, line in enumerate(response)}
        predicted, predicted_conflicts, covered = set(), set(), set()
        for row in rows:
            quote = _norm(row.get("requirement"))
            t_idx = next((i for i, line in enumerate(tender) if quote and quote in _norm(line)), None)
            if t_idx is None:
                continue
            covered.add(t_idx)
            for ev in row.get("response_evidence") or []:
                r_idx = response_index.get(_norm(ev.get("quote")))
                if r_idx is not None:
                    predicted.add((t_idx, r_idx))
            for conflict in row.get("conflicts") or []:
                r_idx = response_index.get(_norm(conflict.get("response_quote")))
                if r_idx is not None:
                    predicted_conflicts.add((t_idx, r_idx))
        lines_with_rows += len(covered)
        gold = {tuple(x) for x in case["links"]}
        gold_conflicts = {tuple(x) for x in case["conflicts"]}
        unreachable += sum(1 for t, _ in gold if t not in covered)
        tp += len(gold & predicted); fp += len(predicted - gold); fn += len(gold - predicted)
        ctp += len(gold_conflicts & predicted_conflicts)
        cfp += len(predicted_conflicts - gold_conflicts)
        cfn += len(gold_conflicts - predicted_conflicts)
        misses += [(case["id"], tender[t], response[r]) for t, r in sorted(gold - predicted)]
        extras += [(case["id"], tender[t], response[r]) for t, r in sorted(predicted - gold)]

    def prf(a, b, c):
        p = a / (a + b) if a + b else 1.0
        r = a / (a + c) if a + c else 1.0
        return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0.0

    lp, lr, lf = prf(tp, fp, fn)
    cp, cr, cf = prf(ctp, cfp, cfn)
    return {"links": {"tp": tp, "fp": fp, "fn": fn, "precision": lp, "recall": lr, "f1": lf,
                      "gold_on_lines_with_no_row": unreachable},
            "conflicts": {"tp": ctp, "fp": cfp, "fn": cfn, "precision": cp, "recall": cr, "f1": cf},
            "rows_per_tender_line": round(rows_total / max(lines_with_rows, 1), 3),
            "rows": rows_total, "misses": misses, "extras": extras}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="shipped", help="a key of tender_response_match.ABLATIONS, or 'all'")
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--show", action="store_true", help="list missed and extra links")
    ap.add_argument("--check", action="store_true", help="assert the CI floors for the shipped configuration")
    args = ap.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    variants = _variants()
    names = [n for n in variants if n != "shipped"] if args.variant == "all" else [args.variant]
    print(f"cases={len(cases)} gold_links={sum(len(c['links']) for c in cases)} gold_conflicts={sum(len(c['conflicts']) for c in cases)}")
    print(f"{'variant':26s} {'link P':>7s} {'link R':>7s} {'link F1':>8s} {'confl P':>8s} {'confl R':>8s} {'rows/line':>10s}")
    results = {}
    for name in names:
        r = evaluate(variants[name], cases)
        results[name] = r
        print(f"{name:26s} {r['links']['precision']:7.3f} {r['links']['recall']:7.3f} {r['links']['f1']:8.3f} "
              f"{r['conflicts']['precision']:8.3f} {r['conflicts']['recall']:8.3f} {r['rows_per_tender_line']:10.3f}")
        if args.variant != "all":
            print(f"    rows={r['rows']}  links tp/fp/fn={r['links']['tp']}/{r['links']['fp']}/{r['links']['fn']}  "
                  f"gold_on_lines_with_no_row={r['links']['gold_on_lines_with_no_row']}  "
                  f"conflicts tp/fp/fn={r['conflicts']['tp']}/{r['conflicts']['fp']}/{r['conflicts']['fn']}")
        if args.show:
            for kind in ("misses", "extras"):
                for cid, t, resp in r[kind]:
                    print(f"    {kind[:-2]:5s} [{cid}] {t}  <->  {resp}")
    if args.check:
        r = results["shipped"]
        floors = {"link precision": (r["links"]["precision"], 0.97), "link recall": (r["links"]["recall"], 0.95),
                  "conflict precision": (r["conflicts"]["precision"], 1.0), "conflict recall": (r["conflicts"]["recall"], 0.95)}
        bad = {k: v for k, v in floors.items() if v[0] < v[1]}
        assert not bad, bad
        assert r["rows_per_tender_line"] == 1.0, r["rows_per_tender_line"]
        print("PASS tender_response_match floors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
