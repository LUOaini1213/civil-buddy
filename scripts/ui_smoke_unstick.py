#!/usr/bin/env python3
"""UI 卡死回归：health / team-a / confirm / demo 限时必须完成。"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"


def post(path: str, body: dict, timeout: float = 60.0) -> tuple[float, dict]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    dt = time.time() - t0
    return dt, json.loads(raw) if raw else {}


def get(path: str, timeout: float = 5.0) -> tuple[float, dict]:
    t0 = time.time()
    with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return time.time() - t0, json.loads(raw)


def main() -> int:
    fails = []
    print("== UI unstick smoke ==")

    try:
        dt, h = get("/api/health", 3)
        print(f"health {dt*1000:.0f}ms gateway={h.get('gateway')} skjolber={h.get('skjolber')}")
        if dt > 1.0:
            fails.append(f"health too slow {dt:.2f}s")
    except Exception as e:
        print("health FAIL", e)
        return 1

    sid = f"smoke-{int(time.time())}"
    try:
        dt, a = post(
            "/api/team-a",
            {"user_input": "smoke", "session_id": sid},
            timeout=30,
        )
        print(f"team-a {dt:.2f}s phase={a.get('phase')}")
        if dt > 15:
            fails.append(f"team-a slow {dt:.2f}s")
        if a.get("phase") not in ("await_user_confirm", "done", "team_a_done"):
            # still ok if has boxes
            if not (a.get("boxes") or a.get("n_boxes")):
                fails.append(f"team-a unexpected phase {a.get('phase')}")
    except Exception as e:
        print("team-a FAIL", e)
        fails.append(f"team-a {e}")

    try:
        dt, c = post(
            "/api/confirm",
            {
                "session_id": sid,
                "action": "confirm",
                "container_type": "40HQ",
                "max_containers": 0,
            },
            timeout=60,
        )
        cf = (c.get("container_plan") or {}).get("can_fit")
        print(f"confirm {dt:.2f}s can_fit={cf} phase={c.get('phase')}")
        if dt > 45:
            fails.append(f"confirm slow {dt:.2f}s")
        if cf is None and not c.get("error"):
            fails.append("confirm missing can_fit")
    except Exception as e:
        print("confirm FAIL", e)
        fails.append(f"confirm {e}")

    try:
        dt, d = post(
            "/api/demo",
            {
                "user_input": "高利用率",
                "session_id": sid + "-demo",
                "preset": "high_util",
                "container_type": "40HQ",
            },
            timeout=90,
        )
        pub = d.get("public") or d
        cf = (pub.get("container_plan") or d.get("container_plan") or {}).get("can_fit")
        print(f"demo {dt:.2f}s can_fit={cf} phase={pub.get('phase') or d.get('phase')}")
        if dt > 60:
            fails.append(f"demo slow {dt:.2f}s")
    except Exception as e:
        print("demo FAIL", e)
        fails.append(f"demo {e}")

    # concurrent health while confirm-like load
    try:
        t0 = time.time()
        dt_h, _ = get("/api/health", 3)
        print(f"post-load health {dt_h*1000:.0f}ms (after {time.time()-t0:.2f}s)")
        if dt_h > 1.0:
            fails.append("health after load slow")
    except Exception as e:
        fails.append(f"health after {e}")

    if fails:
        print("FAIL:", fails)
        return 1
    print("PASS all under budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
