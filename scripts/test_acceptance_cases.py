#!/usr/bin/env python3
"""Run every representative acceptance case, so CI does.

The acceptance scripts (one post each: what a representative input must produce and must not) were
green for a while only because nothing ran them. This runs each one the way a person would —
`python scripts/<case>.py`, in its own process — and fails if any of them does, or if there are
suddenly none to run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(p.name for p in (ROOT / "scripts").glob("test_*_acceptance.py")) + [
    "test_pack_ship_weight_validation.py",
    "run_dongyufei_tender_case.py",
]
MINIMUM = 12


def main() -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1"}
    failed = []
    for name in CASES:
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / name)], cwd=ROOT, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=300)
        last = (done.stdout.strip().splitlines() or ["(no output)"])[-1][:100]
        print(f"[{'PASS' if done.returncode == 0 else 'FAIL'}] {name}: {last}")
        if done.returncode != 0:
            failed.append(name)
            print((done.stderr or done.stdout)[-1200:])
    if len(CASES) < MINIMUM:
        print(f"only {len(CASES)} acceptance cases found, expected at least {MINIMUM}")
        return 1
    print(f"{len(CASES) - len(failed)}/{len(CASES)} acceptance cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
