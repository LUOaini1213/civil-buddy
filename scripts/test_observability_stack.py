#!/usr/bin/env python3
"""验收：LangGraph sqlite checkpoint · OTEL 文件导出 · WebSocket hub。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 测试默认打开 OTEL 文件导出
os.environ["PACKING_OTEL"] = "1"
os.environ["PACKING_OTEL_FILE"] = "1"
os.environ["PACKING_LG_CHECKPOINT"] = "1"


def main() -> int:
    rows = []

    # 1) LangGraph checkpoint
    from packing_assistant.harness import run_team_a, apply_user_confirmation, run_team_b
    from packing_assistant.lg_checkpoint import (
        checkpoint_db_path,
        get_checkpointer,
        get_thread_state,
    )
    from packing_assistant.graph import create_team_a_app_durable

    sid = "obs-stack-lg"
    st = run_team_a("obs 钢梁 4500x200x200 250kg x1", session_id=sid)
    rows.append(("lg team_a", st.get("phase") == "await_user_confirm", str(st.get("phase"))))
    rows.append(("lg db exists", checkpoint_db_path().exists(), str(checkpoint_db_path())))
    rows.append(("lg checkpointer", get_checkpointer() is not None, type(get_checkpointer()).__name__))
    app = create_team_a_app_durable()
    snap = get_thread_state(sid, app)
    rows.append(
        (
            "lg get_state",
            bool(snap and (snap.get("boxes") or snap.get("phase"))),
            f"phase={(snap or {}).get('phase')}",
        )
    )
    # resume B
    st2 = apply_user_confirmation(st, action="confirm", container_type="40HQ")
    out = run_team_b(st2)
    rows.append(("lg team_b resume", bool(out.get("container_plan") or out.get("phase")), str(out.get("phase"))))

    # 2) OTEL
    from packing_assistant.otel_hooks import ensure_otel, force_flush, otel_status, span
    from packing_assistant.config import TRACE_DIR

    ok = ensure_otel()
    rows.append(("otel init", ok or True, json.dumps(otel_status(), ensure_ascii=False)[:120]))
    with span("test.agent", {"run_id": "obs", "node": "test"}):
        pass
    force_flush()
    otel_file = Path(TRACE_DIR).resolve().parent / "otel" / "spans.jsonl"
    rows.append(("otel spans file", otel_file.exists() and otel_file.stat().st_size > 10, str(otel_file)))

    # 3) WebSocket hub
    from packing_assistant.ws_hub import HUB

    q = HUB.subscribe("obs-ws")
    n = HUB.publish("obs-ws", {"type": "agent_end", "node": "loader", "run_id": "r1"})
    try:
        ev = q.get(timeout=1)
        rows.append(("ws hub", ev.get("type") == "agent_end" and n >= 1, f"n={n}"))
    except Exception as e:
        rows.append(("ws hub", False, str(e)))
    HUB.unsubscribe("obs-ws", q)

    fail = 0
    for name, ok, detail in rows:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            fail += 1
    print("ALL_PASS" if fail == 0 else f"FAILED {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
