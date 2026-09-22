#!/usr/bin/env python3
"""Gate check: the bid posts still get out of a real-shaped tender what they got out of it, and the bid check
still finds the planted defects without flagging what is right.

scripts/eval_real_tender.py and scripts/eval_real_bid_check.py measure; this turns the measurements into a check
against test/benchmarks/real_tender/floor.json. Every document and bid set there has been seen by the rules
(a held-out document's first-run numbers are in the README, and they are the ones to quote) - here they only
guard against a regression. Lowering a floor is a deliberate edit with the new number in the commit message.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = ROOT / "test" / "benchmarks" / "real_tender" / "floor.json"


def run(script: str, *args: str) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1"}
    for key in list(env):
        if key.endswith("_API_KEY"):
            env.pop(key)
    with tempfile.TemporaryDirectory(prefix="real-tender-gate-") as tmp:
        target = Path(tmp) / "out.json"
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args, "--json", str(target)], cwd=ROOT, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if not target.exists():
            raise SystemExit(f"{script} produced nothing (exit {done.returncode}):\n{done.stdout[-1500:]}{done.stderr[-1500:]}")
        return json.loads(target.read_text(encoding="utf-8"))


def main() -> int:
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))
    failures: list[str] = []
    for key, expected in floor["documents"].items():
        name, _, fmt = key.partition(":")   # "cn_municipal:pdf" - the same document as a PDF; ":ocr" - as a saved OCR reading
        total = run("eval_real_tender.py", "--doc", name, "--format", fmt or "docx")["total"]
        name = key
        print(f"[{name}] fields right {total['fields_right']}/{total['fields']} wrong {total['fields_wrong']} ambiguous {total['fields_ambiguous']} "
              f"clause refs {total['clause_refs']} rejections {total['rejections']}/{total['rejections_total']} scores {total['scores']} "
              f"specials {total['specials']} forms {total['forms']}")
        for key in ("fields_right", "clause_refs", "rejections", "scores", "specials", "forms"):
            if total[key] < expected[key]:
                failures.append(f"{name}: {key} {total[key]}, the floor is {expected[key]}")
        for key in ("fields_wrong", "fields_ambiguous"):
            if total[key] > expected.get(key, 0):
                failures.append(f"{name}: {key} {total[key]}, at most {expected.get(key, 0)} allowed - a wrong value in a field row is worse than an empty one")
    for name, expected in floor["bids"].items():
        result = run("eval_real_bid_check.py", "--set", name)
        print(f"[{name}] defects caught {result['caught']}/{result['defects']} false alarms {result['false_alarms']}/{result['rights']}")
        if result["caught"] < expected["caught"]:
            failures.append(f"{name}: {result['caught']} planted defects caught, the floor is {expected['caught']}")
        if result["false_alarms"] > expected.get("false_alarms", 0):
            failures.append(f"{name}: {result['false_alarms']} false alarm(s), at most {expected.get('false_alarms', 0)} allowed")
    for line in failures:
        print("FAIL " + line)
    print(("FAIL real-tender" if failures else "PASS real-tender") + f" ({len(floor['documents'])} document(s), {len(floor['bids'])} bid set(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
