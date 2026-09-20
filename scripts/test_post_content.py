#!/usr/bin/env python3
"""Gate check: the posts still put the user's facts where they belong.

scripts/eval_post_content.py measures it; this turns the measurement into a check, against a floor
recorded in test/benchmarks/post_content/floor.json. Raising the floor is a deliberate edit with the
new number in the commit message - a silent regression is what this exists to catch.

Three things fail the gate:
  - the placed rate falling below the floor (overall, or for one post by more than its own slack);
  - a forbidden conclusion appearing in a draft;
  - a fact landing in the wrong object's row ("misplaced"), which is worse than leaving it out.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = ROOT / "test" / "benchmarks" / "post_content" / "floor.json"


def measure(case_set: str, target: Path) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1"}
    for key in list(env):
        if key.endswith("_API_KEY"):
            env.pop(key)
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "eval_post_content.py"), "--set", case_set,
                           "--json", str(target)], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)
    if not target.exists():
        raise SystemExit(f"eval_post_content.py produced nothing (exit {done.returncode}):\n{done.stdout[-2000:]}{done.stderr[-2000:]}")
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> int:
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="post-content-gate-") as tmp:
        for case_set, expected in floor["sets"].items():
            result = measure(case_set, Path(tmp) / f"{case_set}.json")
            total, micro = result["total"], result["micro"]
            print(f"[{case_set}] facts {total['facts']} placed {total['placed']} ({micro:.3f} micro, "
                  f"{result['macro']:.3f} macro) misplaced {total['misplaced']} dumped {total['dumped']} "
                  f"echo_only {total['echo_only']} missing {total['missing']} forbidden {total['forbidden']}")
            if micro < expected["micro"] - 1e-9:
                failures.append(f"{case_set}: placed rate {micro:.3f} below the floor {expected['micro']:.3f}")
            if total["forbidden"] > expected.get("forbidden", 0):
                failures.append(f"{case_set}: {total['forbidden']} forbidden conclusion(s) in the drafts")
            if total["misplaced"] > expected.get("misplaced", 0):
                worst = sorted(((row["misplaced"], post) for post, row in result["posts"].items() if row["misplaced"]), reverse=True)
                failures.append(f"{case_set}: {total['misplaced']} fact(s) in the wrong field, "
                                f"at most {expected.get('misplaced', 0)} allowed; worst: "
                                + ", ".join(f"{post} {count}" for count, post in worst[:5]))
            for post, row in sorted(result["posts"].items()):
                rate = row["placed"] / max(1, row["facts"])
                if rate < expected["per_post"].get(post, expected["per_post_default"]) - 1e-9:
                    failures.append(f"{case_set}: {post} {rate:.2f} below its floor "
                                    f"{expected['per_post'].get(post, expected['per_post_default']):.2f}")
    for line in failures:
        print("FAIL " + line)
    print(("FAIL post-content" if failures else "PASS post-content") + f" ({len(floor['sets'])} case set(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
