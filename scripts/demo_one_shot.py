#!/usr/bin/env python3
"""One-shot demo for packing-agent (Agent Harness).

Default path needs **no API key**: deterministic ``steps`` runtime + tools.

Usage:
  python scripts/demo_one_shot.py
  python scripts/demo_one_shot.py --closed-loop
  python scripts/demo_one_shot.py --eval-tiny
  python scripts/demo_one_shot.py --all

Exit code 0 only if selected checks pass.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, argv: list[str]) -> int:
    print()
    print("=" * 64)
    print(f"[demo_one_shot] {label}")
    print(" ", " ".join(argv))
    print("=" * 64)
    proc = subprocess.run(argv, cwd=str(ROOT))
    if proc.returncode != 0:
        print(f"[demo_one_shot] FAIL: {label} (exit {proc.returncode})")
    else:
        print(f"[demo_one_shot] OK: {label}")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="packing-agent one-shot demo")
    ap.add_argument(
        "--closed-loop",
        action="store_true",
        help="also run demo_agent_closed_loop.py --tiny",
    )
    ap.add_argument(
        "--eval-tiny",
        action="store_true",
        help="also run eval_workteams_cli.py --tiny-only (shadow KPI)",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="smoke + closed-loop + tiny eval",
    )
    args = ap.parse_args()
    if args.all:
        args.closed_loop = True
        args.eval_tiny = True

    py = sys.executable
    print("packing-agent · one-shot demo")
    print(f"root: {ROOT}")
    print("docs: docs/architecture-as-harness.md")
    print("default: no DEEPSEEK_API_KEY required (steps / policy fallback)")

    code = _run("smoke (product harness)", [py, "scripts/smoke_agent_product.py"])
    if code != 0:
        return code

    if args.closed_loop:
        code = _run(
            "closed-loop (tiny materials)",
            [py, "scripts/demo_agent_closed_loop.py", "--tiny"],
        )
        if code != 0:
            return code

    if args.eval_tiny:
        code = _run(
            "shadow eval (tiny)",
            [py, "scripts/eval_workteams_cli.py", "--tiny-only"],
        )
        if code != 0:
            return code

    print()
    print("=" * 64)
    print("[demo_one_shot] ALL SELECTED CHECKS PASSED")
    print("Next:")
    print("  uvicorn gateway.app:app --reload --host 127.0.0.1 --port 8000")
    print("  open http://127.0.0.1:8000")
    print("  read docs/architecture-as-harness.md")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
