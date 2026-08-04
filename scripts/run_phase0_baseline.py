#!/usr/bin/env python3
"""Phase 0 基线：评测集 + 加权分 + 一页报告。

用法:
  python scripts/run_phase0_baseline.py --quick
  python scripts/run_phase0_baseline.py
  python scripts/run_phase0_baseline.py --mode llm_toolcall --quick
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.phase0_benchmark import (  # noqa: E402
    build_phase0_cases,
    load_success_criteria,
    render_baseline_md,
    run_baseline,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 0 baseline")
    ap.add_argument("--quick", action="store_true", help="约 12 个 case")
    ap.add_argument(
        "--mode",
        default="steps",
        choices=["steps", "llm_toolcall", "auto"],
        help="agent_mode",
    )
    ap.add_argument(
        "--list-only",
        action="store_true",
        help="只列出 case 数量与 id",
    )
    ap.add_argument(
        "--from-json",
        default="",
        help="从已有 baseline json 重生成 MD",
    )
    ap.add_argument(
        "--t80-sample",
        type=int,
        default=None,
        help="full 时只跑前 N 张 t80（加速；默认全部）。例: --t80-sample 2",
    )
    ap.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="并行 case 数（线程池，默认 1）",
    )
    ap.add_argument(
        "--fast-full",
        action="store_true",
        help="快捷 full：t80 抽 2 张 + jobs=2（日常冲刺预览）",
    )
    args = ap.parse_args()

    if args.from_json:
        p = Path(args.from_json)
        report = json.loads(p.read_text(encoding="utf-8"))
        md = render_baseline_md(report)
        out = ROOT / "output" / "phase0" / "BASELINE_REPORT.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print("MD", out)
        return 0

    t80_sample = args.t80_sample
    jobs = max(1, int(args.jobs or 1))
    if args.fast_full:
        if args.quick:
            print("NOTE --fast-full 与 --quick 互斥，已按 full 加速")
        args.quick = False
        if t80_sample is None:
            t80_sample = 2
        if jobs < 2:
            jobs = 2

    cases = build_phase0_cases(include_heavy=not args.quick)
    print("CASES", len(cases), "t80_sample=", t80_sample, "jobs=", jobs)
    if args.list_only:
        for c in cases:
            print(c.id, c.tags)
        print("CRITERIA", json.dumps(load_success_criteria().get("weights"), ensure_ascii=False))
        return 0 if len(cases) >= 20 else 1

    report = run_baseline(
        cases,
        agent_mode=args.mode,
        quick=args.quick,
        t80_sample=t80_sample,
        jobs=jobs,
    )
    print(
        "BASELINE",
        "n=",
        report.get("n"),
        "pass_rate=",
        report.get("pass_rate"),
        "avg_score=",
        report.get("avg_score"),
        "paths=",
        report.get("paths"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
