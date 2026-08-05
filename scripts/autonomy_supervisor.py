#!/usr/bin/env python3
"""Outer supervisor: keep autonomy_12h_loop alive for N hours (ASCII-safe)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "autonomy"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "supervisor.log"
LOCK = OUT / "loop.lock"
PIDF = OUT / "loop.pid"
HOURS = float(os.environ.get("AUTONOMY_HOURS", "12"))
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
if not Path(PY).exists():
    PY = sys.executable
LOOP = str(ROOT / "scripts" / "autonomy_12h_loop.py")


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def clear_stale_lock() -> None:
    for p in (LOCK, PIDF):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def kill_existing_loops() -> None:
    """Kill any autonomy_12h_loop processes (not this supervisor)."""
    if sys.platform != "win32":
        return
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/FORMAT:LIST"],
            text=True,
            errors="replace",
            timeout=30,
        )
    except Exception as e:
        log(f"wmic fail: {e}")
        return
    cur = {"pid": None, "cmd": ""}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("CommandLine="):
            cur["cmd"] = line.split("=", 1)[1]
        elif line.startswith("ProcessId="):
            try:
                cur["pid"] = int(line.split("=", 1)[1])
            except Exception:
                cur["pid"] = None
            cmd = cur["cmd"] or ""
            pid = cur["pid"]
            if pid and "autonomy_12h_loop" in cmd and "autonomy_supervisor" not in cmd:
                if pid != os.getpid():
                    log(f"kill existing loop pid={pid}")
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=15)
                    except Exception as e:
                        log(f"taskkill {pid}: {e}")
            cur = {"pid": None, "cmd": ""}


def main() -> int:
    end = time.time() + HOURS * 3600
    log(f"SUPERVISOR START hours={HOURS} py={PY} root={ROOT}")
    os.chdir(ROOT)
    n = 0
    while time.time() < end:
        n += 1
        remaining = max(0.1, (end - time.time()) / 3600)
        kill_existing_loops()
        clear_stale_lock()
        env = os.environ.copy()
        env["AUTONOMY_HOURS"] = f"{remaining:.4f}"
        env["AUTONOMY_BASELINE_AVG"] = env.get("AUTONOMY_BASELINE_AVG", "0.9485")
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = str(ROOT)
        env["AUTONOMY_SUPERVISED"] = "1"
        log(f"spawn loop#{n} remaining_h={remaining:.3f}")
        try:
            p = subprocess.Popen(
                [PY, LOOP],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log(f"spawn fail: {e}")
            time.sleep(10)
            continue
        log(f"child pid={p.pid}")
        # wait child or deadline
        while time.time() < end:
            rc = p.poll()
            if rc is not None:
                log(f"child exit code={rc}")
                break
            time.sleep(15)
        else:
            # time up
            log("deadline — terminate child")
            try:
                p.terminate()
                p.wait(timeout=30)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
            break
        # if loop wrote DONE, stop supervising
        try:
            ll = (OUT / "loop.log").read_text(encoding="utf-8", errors="replace")
            if "AUTONOMY DONE" in ll[-5000:]:
                log("detected AUTONOMY DONE — supervisor exit")
                break
        except Exception:
            pass
        time.sleep(5)
    log("SUPERVISOR DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
