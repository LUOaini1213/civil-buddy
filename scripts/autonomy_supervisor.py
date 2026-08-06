#!/usr/bin/env python3
"""In-process supervisor until AUTONOMY_END_TS (default overnight 08:30 +08)."""
from __future__ import annotations

import os
import runpy
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "autonomy"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "supervisor.log"
LOCK = OUT / "loop.lock"
PIDF = OUT / "loop.pid"
LOOP = str(ROOT / "scripts" / "autonomy_12h_loop.py")

DEFAULT_END = "2026-08-06T08:30:00+08:00"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_end() -> float:
    end_ts = (os.environ.get("AUTONOMY_END_TS") or DEFAULT_END).strip()
    os.environ["AUTONOMY_END_TS"] = end_ts
    s = end_ts.replace("Z", "+00:00")
    target = datetime.fromisoformat(s)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone(timedelta(hours=8)))
    return target.timestamp()


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    end = parse_end()
    os.environ["AUTONOMY_SUPERVISED"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ.setdefault("AUTONOMY_BASELINE_AVG", "0.9485")
    remaining_h = max(0.05, (end - time.time()) / 3600)
    os.environ["AUTONOMY_HOURS"] = f"{remaining_h:.4f}"
    log(f"SUPERVISOR START end={os.environ['AUTONOMY_END_TS']} rem_h={remaining_h:.3f} pid={os.getpid()} root={ROOT}")
    for p in (LOCK, PIDF):
        try:
            p.unlink()
        except Exception:
            pass
    n = 0
    while time.time() < end:
        n += 1
        remaining_h = max(0.05, (end - time.time()) / 3600)
        os.environ["AUTONOMY_HOURS"] = f"{remaining_h:.4f}"
        log(f"run loop#{n} remaining_h={remaining_h:.3f}")
        try:
            runpy.run_path(LOOP, run_name="__main__")
            log(f"loop#{n} returned normally")
        except SystemExit as e:
            log(f"loop#{n} SystemExit {e.code}")
        except Exception:
            log(f"loop#{n} CRASH:\n{traceback.format_exc()[-2000:]}")
        try:
            t = (OUT / "loop.log").read_text(encoding="utf-8", errors="replace")
            if "OVERNIGHT_DEADLINE_DONE" in t[-12000:]:
                log("OVERNIGHT_DEADLINE_DONE seen — stop")
                break
        except Exception:
            pass
        if time.time() >= end:
            break
        # if loop exited early without deadline, restart until clock
        time.sleep(5)
    log("SUPERVISOR DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
