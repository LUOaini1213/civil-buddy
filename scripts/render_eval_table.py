#!/usr/bin/env python3
"""Render the fan-out evaluation archive as a markdown table, or check that
the numbers README quotes are the numbers the archive contains.

    python scripts/render_eval_table.py                      # print the table
    python scripts/render_eval_table.py --check README.md    # exit 1 on any drift

The archive is docs/eval/<run>/rollup.json as written by
scripts/fanout16x8_online_cargo.py; every figure below is read from it, none
is typed in. No API key, no network.

Input diversity (how many source instances, lane variants and distinct inputs
the 128 runs really cover) is recomputed from the archived fetch_meta.json and
the committed cargo cache under data/external/, with the same functions the
evaluation used (load_material_bank, round_materials, round_options). Distinct
outcomes are the distinct (boxes, can_fit, containers_used) triples in rollup.json.
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


def _canon(materials: list) -> tuple:
    """A cargo list as a value: ids and names (which carry the lane number) are left out."""
    return tuple(sorted(
        (int(m["qty"]), float(m["length_mm"]), float(m["width_mm"]), float(m["height_mm"]), float(m["weight_kg"]))
        for m in materials
    ))


def diversity(r: dict, fetch_meta_path: Path) -> dict:
    """Source instances, lane variants and distinct (materials, options) inputs behind the archived runs,
    plus the distinct outcomes the archive records."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import fanout16x8_online_cargo as fan

    meta = json.loads(fetch_meta_path.read_text(encoding="utf-8"))
    sources = {_canon(m) for m in fan.cargo_instances(meta)}
    lanes, rounds = int(r["lanes"]), int(r["rounds_per_lane"])
    bank = fan.load_material_bank(meta, n_lanes=lanes)
    inputs = {
        (_canon(fan.round_materials(bank[lane], rd)), json.dumps(fan.round_options(rd), sort_keys=True))
        for lane in range(lanes)
        for rd in range(1, rounds + 1)
    }
    outcomes = {
        (rd.get("n_boxes"), rd.get("can_fit"), rd.get("containers_used"))
        for lane in r.get("lanes_detail") or []
        for rd in lane.get("rounds", [])
    }
    return {
        "source_instances": len(sources),
        "lane_variants": len({_canon(b) for b in bank}),
        "distinct_inputs": len(inputs),
        "distinct_outcomes": len(outcomes),
    }


def summary(r: dict) -> dict:
    lanes = r.get("lanes_detail") or []
    rounds = [rd for lane in lanes for rd in lane.get("rounds", [])]
    dts = sorted(float(rd["dt_s"]) for rd in rounds if rd.get("dt_s") is not None)
    phases: dict[str, int] = {}
    for rd in rounds:
        phases[str(rd.get("phase"))] = phases.get(str(rd.get("phase")), 0) + 1
    # PASS in this archive means the pipeline completed and returned a plan
    # (scripts/fanout16x8_online_cargo.py::_pass_criteria). Whether that plan
    # fits is a separate number, and the one a reader actually wants.
    can_fit_true = sum(1 for rd in rounds if rd.get("can_fit") is True)
    can_fit_false = sum(1 for rd in rounds if rd.get("can_fit") is False)
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
        "can_fit_true": can_fit_true,
        "can_fit_false": can_fit_false,
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
        f"| can_fit True / False (PASS = the pipeline completed, not that the cargo fits) | {s['can_fit_true']} / {s['can_fit_false']} |",
    ]
    if "distinct_inputs" in s:
        lines += [
            f"| public source instances (D-Wave 3D-BPP samples that parse as cargo) | {s['source_instances']} |",
            f"| cargo variants derived from them (one per lane) | {s['lane_variants']} |",
            f"| distinct inputs among the {s['expected']} runs (materials + options) | {s['distinct_inputs']} |",
            f"| distinct outcomes (boxes, can_fit, containers_used) | {s['distinct_outcomes']} |",
        ]
    lines += [
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
    # The fit count must be quoted next to the PASS count, and must match.
    m2 = re.search(r"`can_fit=True` \*\*(\d+)/(\d+)\*\*", text)
    if not m2:
        problems.append("README does not state the can_fit=True count next to the PASS figure")
    else:
        fit, of = (int(x) for x in m2.groups())
        if (fit, of) != (s["can_fit_true"], s["expected"]):
            problems.append(f"README says can_fit=True {fit}/{of}; archive has {s['can_fit_true']}/{s['expected']}")
    if s["records"] != s["expected"]:
        problems.append(f"archive holds {s['records']} per-run records, expected {s['expected']}")
    # What the runs cover must be stated next to the run count, in both languages, and must match.
    if "distinct_inputs" in s:
        want = (s["source_instances"], s["lane_variants"], s["distinct_inputs"], s["distinct_outcomes"])
        m3 = re.search(
            r"\*\*(\d+)\*\* 个公开 D-Wave 3D-BPP 样本.*?\*\*(\d+)\*\* 个货物变体.*?\*\*(\d+)\*\* 种不同输入"
            r".*?\*\*(\d+)\*\* 种结果",
            text,
        )
        if not m3:
            problems.append("README evidence row does not state sources / variants / distinct inputs / outcomes")
        elif tuple(int(x) for x in m3.groups()) != want:
            problems.append(f"README (zh) says sources/variants/inputs/outcomes {tuple(int(x) for x in m3.groups())}; "
                            f"archive gives {want}")
        m4 = re.search(
            r"(\d+) cargo variants of (\d+) public D-Wave 3D-BPP samples, (\d+) distinct inputs, "
            r"(\d+) distinct outcomes",
            text,
        )
        if not m4:
            problems.append("README English summary does not state variants / sources / distinct inputs / outcomes")
        else:
            got = tuple(int(x) for x in m4.groups())
            if (got[1], got[0], got[2], got[3]) != want:
                problems.append(f"README (en) says variants/sources/inputs/outcomes {got}; archive gives "
                                f"{(want[1], want[0], want[2], want[3])}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN, help="rollup.json of an archived run")
    ap.add_argument("--check", type=Path, metavar="README", help="verify the numbers quoted in this file")
    ap.add_argument("--fetch-meta", type=Path, default=None,
                    help="fetch_meta.json of the same run (default: next to --run)")
    args = ap.parse_args()
    r = load(args.run)
    s = summary(r)
    fetch_meta = args.fetch_meta or args.run.with_name("fetch_meta.json")
    if fetch_meta.is_file():
        s.update(diversity(r, fetch_meta))
    elif args.check:
        print(f"MISMATCH: {fetch_meta} not found; input diversity cannot be checked")
        return 1
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
