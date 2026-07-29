#!/usr/bin/env python3
"""CI 友好：合成 tiny + 20t 评测。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.eval_harness import run_eval_suite  # noqa: E402


def main() -> int:
    s = run_eval_suite(out_path=ROOT / "output" / "eval_harness_last.json")
    print("SUMMARY", s.get("passed"), "/", s.get("n"), "ms=", s.get("ms"))
    return 0 if s.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
