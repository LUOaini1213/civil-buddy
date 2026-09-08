#!/usr/bin/env python3
"""Render the fan-out evaluation archive as a markdown table, or check that
the numbers README quotes are the numbers the archive contains.

    python scripts/render_eval_table.py                      # print the table
    python scripts/render_eval_table.py --check README.md    # exit 1 on any drift

The archive is docs/eval/<run>/rollup.json as written by
scripts/fanout16x8_online_cargo.py; every figure below is read from it, none
is typed in. No API key, no network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "docs" / "eval" / "fanout16x8-2026-09-02" / "rollup.json"


def load(path: Path = DEFAULT_RUN) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summary(r: dict) -> dict:
    lanes = r.get("lanes_detail") or []
    rounds = [rd for lane in lanes for rd in lane.get("rounds", [])]
    dts = sorted(float(rd["dt_s"]) for rd in rounds if rd.get("dt_s") is not None)
    phases: dict[str, int] = {}
    for rd in rounds:
        phases[str(rd.get("phase"))] = phases.get(str(rd.get("phase")), 0) + 1
    return {
        "lanes": int(r["lanes"]),
        "rounds_per_lane": int(r["rounds_per_lane"]),
        "expected": int(r["total_runs_expected"]),
        "attempts": int(r["total_attempts"]),
        "pass": int(r["total_pass"]),
        "fail": int(r["total_fail"]),
        "all_green": bool(r["all_green"]),
        "records": len(rounds),
        "wall_s": float(r["wall_s"]),
        "workers": int(r.get("workers", 0)),
        "dt_median_s": dts[len(dts) // 2] if dts else None,
        "dt_max_s": dts[-1] if dts else None,
        "phases": phases,
        "finished_at": r.get("finished_at"),
        "entry": r.get("entry"),
    }


def table(s: dict) -> str:
    lines = [
        "| 指标 | 值 |",
        "|---|---|",
        f"| lanes × rounds | {s['lanes']} × {s['rounds_per_lane']} = {s['expected']} |",
        f"| attempts / pass / fail | {s['attempts']} / **{s['pass']}** / {s['fail']} |",
        f"| all_green | {s['all_green']} |",
        f"| per-run records in the archive | {s['records']} |",
        f"| wall time ({s['workers']} workers) | {s['wall_s']:.1f} s |",
        f"| per-run time, median / max | {s['dt_median_s']:.1f} s / {s['dt_max_s']:.1f} s |",
        f"| terminal phases | {', '.join(f'{k}: {v}' for k, v in sorted(s['phases'].items()))} |",
        f"| entry | `{s['entry']}` |",
        f"| finished | {s['finished_at']} |",
    ]
    return "\n".join(lines)


def check_readme(readme: Path, s: dict) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    problems = []
    # The evidence row: "**128** 次（16 并发 × 8 轮），2026-09-02 复跑 **128/128 PASS**"
    m = re.search(r"\*\*(\d+)\*\* 次（(\d+) 并发 × (\d+) 轮）.*?复跑 \*\*(\d+)/(\d+) PASS\*\*", text)
    if not m:
        problems.append("README evidence row for the fan-out evaluation not found")
    else:
        total, lanes, rounds, npass, nexp = (int(x) for x in m.groups())
        if (total, lanes, rounds) != (s["expected"], s["lanes"], s["rounds_per_lane"]):
            problems.append(f"README says {lanes}×{rounds}={total}; archive has {s['lanes']}×{s['rounds_per_lane']}={s['expected']}")
        if (npass, nexp) != (s["pass"], s["expected"]):
            problems.append(f"README says {npass}/{nexp} PASS; archive has {s['pass']}/{s['expected']}")
        if not s["all_green"] or s["attempts"] != s["expected"]:
            problems.append("archive is not all-green or attempts != expected")
    if s["records"] != s["expected"]:
        problems.append(f"archive holds {s['records']} per-run records, expected {s['expected']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN, help="rollup.json of an archived run")
    ap.add_argument("--check", type=Path, metavar="README", help="verify the numbers quoted in this file")
    args = ap.parse_args()
    s = summary(load(args.run))
    if args.check:
        problems = check_readme(args.check, s)
        for p in problems:
            print("MISMATCH:", p)
        print(f"{args.check}: the fan-out numbers match {args.run.relative_to(ROOT)}" if not problems else
              f"{len(problems)} mismatch(es)")
        return 1 if problems else 0
    print(table(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
