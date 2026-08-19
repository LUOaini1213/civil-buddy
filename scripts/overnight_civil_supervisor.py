#!/usr/bin/env python3
"""Restart overnight_civil_loop.py until AUTONOMY_END_TS (default 2026-08-20 08:30 +08)."""

from __future__ import annotations

import os
import runpy
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "overnight-civil"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "supervisor.log"
LOOP = str(ROOT / "scripts" / "overnight_civil_loop.py")
DEFAULT_END = "2026-08-20T08:30:00+08:00"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_end() -> float:
    raw = (os.environ.get("AUTONOMY_END_TS") or DEFAULT_END).strip()
    os.environ["AUTONOMY_END_TS"] = raw
    s = raw.replace("Z", "+00:00")
    target = datetime.fromisoformat(s)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone(timedelta(hours=8)))
    return target.timestamp()


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ.setdefault("OVERNIGHT_APPLY", "0")
    end = parse_end()
    log(f"SUPERVISOR START end={os.environ['AUTONOMY_END_TS']} rem_h={(end-time.time())/3600:.2f} pid={os.getpid()}")
    n = 0
    while time.time() < end:
        n += 1
        log(f"run loop#{n}")
        try:
            runpy.run_path(LOOP, run_name="__main__")
            log(f"loop#{n} returned")
        except SystemExit as e:
            log(f"loop#{n} SystemExit {e.code}")
        except Exception:
            log(f"loop#{n} CRASH:\n{traceback.format_exc()[-2000:]}")
        try:
            hb = (OUT / "heartbeat.log").read_text(encoding="utf-8", errors="replace")
            lg = (OUT / "loop.log").read_text(encoding="utf-8", errors="replace")
            near = (end - time.time()) < 180
            if near and ("DONE overnight-civil" in hb[-4000:] or "OVERNIGHT_DEADLINE_DONE" in lg[-4000:]):
                log("deadline marker — stop")
                break
        except OSError:
            pass
        if time.time() >= end:
            break
        time.sleep(8)
    log("SUPERVISOR DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
