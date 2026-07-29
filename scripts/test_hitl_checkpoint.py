#!/usr/bin/env python3
"""HITL durable checkpoint：落盘 → 清空 RAM 语义 → resume。

用法:
  python scripts/test_hitl_checkpoint.py
  python scripts/test_hitl_checkpoint.py --http   # 需网关 8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_local() -> list[tuple[str, bool, str]]:
    rows = []
    from packing_assistant.harness import run_team_a, apply_user_confirmation, run_team_b
    from packing_assistant.session_store import (
        list_checkpoints,
        load_session,
        save_session,
        load_checkpoint_meta,
    )

    sid = "hitl-ckpt-test"
    state = run_team_a(
        "checkpoint 测试 钢梁 5000x200x300 350kg x2",
        session_id=sid,
    )
    phase = state.get("phase")
    rows.append(("team_a phase", phase == "await_user_confirm", str(phase)))

    paths = save_session(sid, state)
    rows.append(("save_session", bool(paths.get("path")), paths.get("status", "")))

    disk = load_session(sid)
    rows.append(
        (
            "load without RAM",
            disk is not None and len(disk.get("boxes") or []) >= 1,
            f"boxes={len((disk or {}).get('boxes') or [])}",
        )
    )
    meta = load_checkpoint_meta(sid)
    rows.append(
        (
            "meta interrupted",
            bool(meta and (meta.get("interrupt") or meta.get("status") == "interrupted")),
            str((meta or {}).get("status")),
        )
    )
    pending = list_checkpoints(pending_hitl_only=True, limit=20)
    rows.append(
        (
            "list pending",
            any(p.get("session_id") == sid or p.get("thread_id") == sid for p in pending),
            f"n={len(pending)}",
        )
    )

    # resume path without touching original RAM object
    resumed = apply_user_confirmation(
        disk or {},
        action="confirm",
        container_type=str((disk or {}).get("container_type") or "40HQ"),
        max_containers=0,
    )
    out = run_team_b(resumed)
    rows.append(
        (
            "resume team_b",
            bool(out.get("container_plan") or out.get("final_response")),
            f"phase={out.get('phase')} can_fit={(out.get('container_plan') or {}).get('can_fit')}",
        )
    )
    return rows


def test_http(base: str = "http://127.0.0.1:8000") -> list[tuple[str, bool, str]]:
    rows = []

    def post(path, body, timeout=180):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def get(path, timeout=30):
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return json.loads(r.read().decode())

    sid = "hitl-http-ckpt"
    try:
        j = post(
            "/api/team-a",
            {"user_input": "HTTP HITL 钢梁 4000x200x200 200kg x1", "session_id": sid},
        )
        rows.append(
            ("http team-a", j.get("phase") == "await_user_confirm", str(j.get("phase")))
        )
        # simulate process restart: only disk
        from packing_assistant.session_store import load_session

        # gateway RAM still has it — we still test endpoints
        ck = get(f"/api/checkpoints/{sid}")
        rows.append(("http get checkpoint", ck.get("ok") is True, str((ck.get("checkpoint") or {}).get("status"))))

        pending = get("/api/checkpoints?pending_hitl=true&limit=10")
        rows.append(
            (
                "http pending list",
                pending.get("ok") is True,
                f"n={pending.get('count')}",
            )
        )

        # resume via dedicated endpoint
        j2 = post(
            f"/api/checkpoints/{sid}/resume",
            {
                "session_id": sid,
                "action": "confirm",
                "container_type": j.get("container_type") or "40HQ",
                "max_containers": 0,
            },
            timeout=240,
        )
        rows.append(
            (
                "http resume",
                j2.get("phase") != "await_user_confirm",
                f"phase={j2.get('phase')} boxes={len(j2.get('boxes') or [])}",
            )
        )
    except urllib.error.URLError as e:
        rows.append(("http", False, f"gateway down: {e}"))
    except Exception as e:
        rows.append(("http", False, str(e)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    rows = test_local()
    if args.http:
        rows.extend(test_http(args.base))
    fail = 0
    for name, ok, detail in rows:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            fail += 1
    print("ALL_PASS" if fail == 0 else f"FAILED {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
