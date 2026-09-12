#!/usr/bin/env python3
"""Recorded trace exports retain their protocol and events in every backend."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import run_artifacts, storage, trace_events


class TraceArtifactsTest(unittest.TestCase):
    def test_sqlite_export_recovers_failed_insert_without_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            st = storage.Storage(root / "trace.db")
            try:
                with patch.dict(os.environ, {"CB_STORAGE": "sqlite", "CIVIL_SANDBOX_ROOTS": td}), \
                     patch.object(storage, "get_storage", return_value=st), \
                     patch.object(trace_events, "RUNS_DIR", root / "runs"), \
                     patch.object(trace_events, "TRACE_DIR", str(root / "traces")):
                    first = trace_events.append_trace_event("fallback", {"type": "run_start", "seq": 1})
                    with patch.object(st, "insert_event", side_effect=RuntimeError("temporary write failure")), \
                         self.assertLogs("civil.trace_events", level="WARNING"):
                        recovered = trace_events.append_trace_event("fallback", {"type": "tool_end", "seq": 2})
                    final = trace_events.append_trace_event("fallback", {"type": "done", "seq": 3})
                    expected = [first, recovered, final]
                    self.assertEqual(trace_events.read_trace_jsonl("fallback"), expected)
                    self.assertEqual(st.read_trace_events("fallback"), [first, final])
                    for _ in range(2):
                        path = trace_events.export_trace_jsonl("fallback")
                        actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                        self.assertEqual(actual, expected)
                    self.assertEqual(trace_events.read_trace_jsonl("fallback"), expected)
            finally:
                st.read_conn().close()
                st.close()

    def test_sqlite_export_keeps_real_events_and_orders_unsequenced_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            st = storage.Storage(root / "trace.db")
            try:
                with patch.dict(os.environ, {"CB_STORAGE": "sqlite", "CIVIL_SANDBOX_ROOTS": td}), \
                     patch.object(storage, "get_storage", return_value=st), \
                     patch.object(trace_events, "RUNS_DIR", root / "runs"):
                    trace_events.export_trace_jsonl("summary", steps=[{"node": "old"}])
                    late = trace_events.normalize_event("summary", {"type": "tool_end", "t_ms": 30})
                    early = trace_events.normalize_event("summary", {"type": "tool_start", "t_ms": 10})
                    middle = trace_events.normalize_event("summary", {"type": "agent_start", "t_ms": 20})
                    st.insert_events([late, early])
                    path = root / "runs" / "summary" / "trace.jsonl"
                    with path.open("a", encoding="utf-8") as stream:
                        # Different object key order still identifies the same event.
                        stream.write(json.dumps(dict(reversed(list(early.items())))) + "\n")
                        stream.write(json.dumps(middle) + "\n")
                    trace_events.export_trace_jsonl("summary")
                    actual = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                    self.assertEqual(actual, [early, middle, late])
            finally:
                st.read_conn().close()
                st.close()

    def test_database_outage_does_not_replace_existing_export(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"CB_STORAGE": "json", "CIVIL_SANDBOX_ROOTS": td}), \
             patch.object(trace_events, "RUNS_DIR", Path(td)):
            path = trace_events.export_trace_jsonl("old-run", steps=[{"node": "loader"}])
            before = path.read_bytes()
            with patch.dict(os.environ, {"CB_STORAGE": "sqlite"}), \
                 patch.object(storage, "get_storage", side_effect=RuntimeError("database unavailable")):
                with self.assertLogs("civil.trace_events", level="WARNING"), self.assertRaises(RuntimeError):
                    trace_events.export_trace_jsonl("old-run", steps=[{"node": "replacement"}])
                with self.assertLogs("civil.trace_events", level="WARNING"):
                    self.assertEqual(trace_events.read_trace_jsonl("old-run"), [json.loads(before)])
            self.assertEqual(path.read_bytes(), before)

    def test_failed_export_replace_preserves_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"CB_STORAGE": "json", "CIVIL_SANDBOX_ROOTS": td}), \
             patch.object(trace_events, "RUNS_DIR", Path(td)):
            path = trace_events.export_trace_jsonl("old-run", steps=[{"node": "loader"}])
            before = path.read_bytes()
            with patch.object(Path, "replace", side_effect=PermissionError("replace failed")):
                with self.assertRaises(PermissionError):
                    trace_events.export_trace_jsonl("old-run")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_reading_unknown_run_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"CB_STORAGE": "json"}), \
             patch.object(trace_events, "RUNS_DIR", Path(td) / "runs"):
            self.assertEqual(trace_events.read_trace_jsonl("missing"), [])
            self.assertFalse((Path(td) / "runs").exists())

    def test_export_preserves_events_and_completion_in_all_modes(self):
        for mode in ("json", "dual", "sqlite"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                st = storage.Storage(root / "trace.db")
                try:
                    with patch.dict(os.environ, {"CB_STORAGE": mode, "CIVIL_SANDBOX_ROOTS": td}), \
                         patch.object(storage, "get_storage", return_value=st), \
                         patch.object(trace_events, "RUNS_DIR", root / "runs"), \
                         patch.object(trace_events, "TRACE_DIR", str(root / "traces")), \
                         patch.object(run_artifacts, "RUNS_DIR", root / "runs"):
                        recorded = [trace_events.append_trace_event("case", ev) for ev in (
                            {"type": "run_start", "session_id": "session"},
                            {"type": "tool_start", "tool": "packing"},
                            {"type": "tool_end", "tool": "packing", "result": {"can_fit": False}},
                        )]
                        state = {"run_id": "case", "container_plan": {"can_fit": "UNSPECIFIED"},
                                 "agent_steps": [{"node": "loader"}]}
                        paths = run_artifacts.save_run_artifacts(state)
                        path = Path(paths["trace_jsonl"])
                        self.assertEqual([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()], recorded)
                        self.assertFalse(json.loads(Path(paths["goal"]).read_text(encoding="utf-8"))["ship_ok"])
                        done = trace_events.append_trace_event("case", {"type": "done"})
                        self.assertEqual(json.loads(path.read_text(encoding="utf-8").splitlines()[-1]), done)
                        # Export is repeatable without duplicating tool events.
                        trace_events.export_trace_jsonl("case")
                        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 4)
                finally:
                    st.read_conn().close()
                    st.close()

    def test_step_only_export_is_normalized_and_labeled(self):
        with tempfile.TemporaryDirectory() as td, \
             patch.dict(os.environ, {"CB_STORAGE": "json", "CIVIL_SANDBOX_ROOTS": td}), \
             patch.object(trace_events, "RUNS_DIR", Path(td)):
            path = trace_events.export_trace_jsonl("old-run", steps=[{"node": "loader"}])
            event = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(event["schema"], "packing.stream.v1")
            self.assertEqual(event["source"], "step_summary")
            self.assertEqual(event["agent_id"], "loader")
            self.assertEqual(event["type"], "agent_end")

    def test_export_does_not_use_replay_limit(self):
        with tempfile.TemporaryDirectory() as td:
            st = storage.Storage(Path(td) / "trace.db")
            try:
                st.insert_events([trace_events.normalize_event("long", {"type": "tool_end", "seq": i})
                                  for i in range(5002)])
                with patch.dict(os.environ, {"CB_STORAGE": "sqlite", "CIVIL_SANDBOX_ROOTS": td}), \
                     patch.object(storage, "get_storage", return_value=st), \
                     patch.object(trace_events, "RUNS_DIR", Path(td) / "runs"):
                    self.assertEqual(len(trace_events.read_trace_jsonl("long")), 5000)
                    path = trace_events.export_trace_jsonl("long")
                    self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 5002)
            finally:
                st.read_conn().close()
                st.close()


if __name__ == "__main__":
    unittest.main()
