#!/usr/bin/env python3
"""Single-process supervisor: run autonomy loop in-process, restart on crash, for N hours."""
from __future__ import annotations

import os
import runpy
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "autonomy"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "supervisor.log"
LOCK = OUT / "loop.lock"
PIDF = OUT / "loop.pid"
HOURS = float(os.environ.get("AUTONOMY_HOURS", "12"))
LOOP = str(ROOT / "scripts" / "autonomy_12h_loop.py")


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    end = time.time() + HOURS * 3600
    os.environ["AUTONOMY_SUPERVISED"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ.setdefault("AUTONOMY_BASELINE_AVG", "0.9485")
    log(f"SUPERVISOR START in-process hours={HOURS} root={ROOT} pid={os.getpid()}")
    # clear locks
    for p in (LOCK, PIDF):
        try:
            p.unlink()
        except Exception:
            pass
    n = 0
    while time.time() < end:
        n += 1
        remaining = max(0.05, (end - time.time()) / 3600)
        os.environ["AUTONOMY_HOURS"] = f"{remaining:.4f}"
        log(f"run loop#{n} remaining_h={remaining:.3f}")
        try:
            runpy.run_path(LOOP, run_name="__main__")
            log(f"loop#{n} returned normally")
        except SystemExit as e:
            log(f"loop#{n} SystemExit {e.code}")
        except Exception:
            log(f"loop#{n} CRASH:\n{traceback.format_exc()[-2000:]}")
        # stop if DONE
        try:
            t = (OUT / "loop.log").read_text(encoding="utf-8", errors="replace")
            if "AUTONOMY DONE" in t[-8000:]:
                log("AUTONOMY DONE seen — stop")
                break
        except Exception:
            pass
        if time.time() >= end:
            break
        time.sleep(3)
    log("SUPERVISOR DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
