#!/usr/bin/env python3
"""Issue #22: a run_start trace event may arrive before its session row exists
(parallel lanes, or a run that never checkpoints). With foreign keys on,
runs.session_id -> sessions.session_id made ensure_run() raise and every event
of that run fall back to JSONL. ensure_run must create the parent row itself.

Runs against a temporary database; no network, no key."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.storage import Storage

    tmp = tempfile.mkdtemp(prefix="cb-fk-")
    st = Storage(db_path=Path(tmp) / "t.db")
    try:
        # 1. run_start for a session nobody has saved yet
        st.ensure_run({"run_id": "run-a", "session_id": "lane-07", "started_at": "2026-09-03T00:00:00Z",
                       "phase": "planning", "container_type": "40HQ", "run_dir": tmp})
        st.insert_event({"run_id": "run-a", "session_id": "lane-07", "type": "run_start", "ts": "2026-09-03T00:00:00Z",
                         "status": "start", "schema": "packing.stream.v1"})
        conn = st.read_conn()
        rows = conn.execute("SELECT run_id, session_id FROM runs").fetchall()
        assert [tuple(r) for r in rows] == [("run-a", "lane-07")], rows
        placeholder = conn.execute(
            "SELECT session_id, status, state_json FROM sessions WHERE session_id='lane-07'").fetchone()
        assert placeholder is not None and placeholder[1] == "placeholder", placeholder
        # 2. a later real checkpoint replaces the placeholder, not the other way round
        st.save_session("lane-07", {"phase": "done", "run_id": "run-a"}, meta={"status": "done"})
        row = conn.execute("SELECT status FROM sessions WHERE session_id='lane-07'").fetchone()
        assert row[0] == "done", row
        # 3. a run without a session id still inserts
        st.ensure_run({"run_id": "run-b", "session_id": None})
        assert st.count("runs") == 2
        # 4. idempotent
        st.ensure_run({"run_id": "run-a", "session_id": "lane-07"})
        assert st.count("runs") == 2
    finally:
        try:
            st.read_conn().close()
        except Exception:
            pass
        st.close()
        shutil.rmtree(tmp, ignore_errors=True)  # Windows may still hold the WAL; best effort
    print("PASS storage.ensure_run creates the parent session row; no FK fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
