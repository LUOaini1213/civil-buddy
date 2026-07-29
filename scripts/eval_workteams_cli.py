#!/usr/bin/env python3
"""Workteams 影子评测 CLI：steps vs llm_toolcall + 路由/选工具 KPI。

用法:
  python scripts/eval_workteams_cli.py
  python scripts/eval_workteams_cli.py --tiny-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.eval_harness import case_tiny  # noqa: E402
from packing_assistant.eval_workteams import run_workteam_shadow_eval  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiny-only", action="store_true", help="仅 tiny（CI 快速）")
    ap.add_argument(
        "--out",
        default=str(ROOT / "output" / "eval_workteams_last.json"),
        help="报告输出路径",
    )
    args = ap.parse_args()
    cases = [case_tiny] if args.tiny_only else None
    report = run_workteam_shadow_eval(
        cases=cases,
        out_path=Path(args.out),
    )
    agg = report.get("aggregate") or {}
    print(
        "WORKTEAM_SHADOW",
        "ok=",
        report.get("ok"),
        "agree=",
        agg.get("agree_core_rate"),
        "illegal=",
        agg.get("illegal_tool_calls_total"),
        "ms=",
        report.get("ms"),
        "out=",
        report.get("out_path"),
    )
    # CI：核心一致率达标即可（无 LLM Key 时 policy 仍应一致）
    if not agg.get("pass_agree_core"):
        return 1
    if not agg.get("pass_illegal_zero"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
