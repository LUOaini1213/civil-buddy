#!/usr/bin/env python3
"""SQLite snapshots must retain real events across persistence failures."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import run_artifacts, storage, trace_events


class TraceArtifactExport(unittest.TestCase):
    def setUp(self):
        output = ROOT / "output"
        output.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="trace-export-", dir=output)
        self.base = Path(self.temp.name)
        self.db = storage.Storage(db_path=self.base / "trace.db")
        self.patches = ExitStack()
        for owner, name, value in (
            (storage, "storage_mode", lambda: "sqlite"),
            (storage, "get_storage", lambda: self.db),
            (trace_events, "RUNS_DIR", self.base / "runs"),
            (trace_events, "TRACE_DIR", self.base / "global"),
            (run_artifacts, "RUNS_DIR", self.base / "runs"),
        ):
            self.patches.enter_context(patch.object(owner, name, value))

    def tearDown(self):
        self.patches.close()
        self.db.read_conn().close()
        self.db.close()
        self.temp.cleanup()

    def emit(self, kind, seq, **fields):
        return trace_events.append_trace_event(
            "fixture", {"type": kind, "seq": seq, **fields}, also_global=False)

    def snapshot(self):
        return trace_events.run_trace_path("fixture")

    def file_events(self):
        return [json.loads(line) for line in self.snapshot().read_text(encoding="utf-8").splitlines()]

    def save(self):
        return run_artifacts.save_run_artifacts(
            {"run_id": "fixture", "agent_steps": [{"node": "summary"}]})

    def test_finalize_before_done_exports_the_complete_real_stream(self):
        for seq, kind in enumerate(("run_start", "tool_start", "tool_end"), 1):
            self.emit(kind, seq, node="test_tool")
        paths = self.save()
        self.assertEqual(Path(paths["trace_jsonl"]), self.snapshot())
        self.assertEqual([ev["type"] for ev in self.file_events()], ["run_start", "tool_start", "tool_end"])
        self.emit("done", 4)
        self.assertEqual([ev["type"] for ev in self.file_events()], ["run_start", "tool_start", "tool_end", "done"])
        self.assertEqual(self.file_events(), self.db.read_trace_events("fixture", limit=100))
        self.assertTrue(all(ev["schema"] == "packing.stream.v1" for ev in self.file_events()))

    def test_db_failure_recovery_retains_fallback_and_deduplicates_snapshots(self):
        self.emit("run_start", 1)
        with patch.object(self.db, "insert_event", side_effect=OSError("temporary DB failure")):
            with self.assertLogs("civil.trace_events", level="WARNING"):
                lost_before_fix = self.emit("tool_start", 2, tool="packing")
        self.emit("tool_end", 3, tool="packing")
        self.assertEqual([ev["seq"] for ev in trace_events.read_trace_jsonl("fixture")], [1, 2, 3])
        self.save()
        self.emit("done", 4)
        self.assertEqual([ev["seq"] for ev in self.file_events()], [1, 2, 3, 4])
        self.assertEqual(self.file_events()[1], lost_before_fix)
        self.assertEqual([ev["seq"] for ev in self.db.read_trace_events("fixture")], [1, 3, 4])
        before = self.file_events()
        trace_events.export_trace_jsonl("fixture")
        self.assertEqual(self.file_events(), before)
        self.assertEqual([ev["seq"] for ev in trace_events.read_trace_jsonl("fixture", limit=2)], [1, 2])

    def test_refresh_failure_does_not_retry_an_already_committed_done(self):
        self.emit("run_start", 1)
        self.save()
        old = self.snapshot().read_bytes()
        with patch.object(trace_events, "export_trace_jsonl", side_effect=OSError("snapshot unavailable")):
            with self.assertLogs("civil.trace_events", level="WARNING") as logs:
                event = trace_events.append_trace_event("fixture", {"type": "done", "seq": 2})
        self.assertIn("snapshot refresh failed", logs.output[0])
        self.assertEqual(event["seq"], 2)
        self.assertEqual(self.snapshot().read_bytes(), old)
        self.assertFalse((self.base / "global" / "stream.jsonl").exists())
        self.assertEqual([ev["seq"] for ev in self.db.read_trace_events("fixture")], [1, 2])
        trace_events.export_trace_jsonl("fixture")
        self.assertEqual([ev["seq"] for ev in self.file_events()], [1, 2])

    def test_read_and_replace_failures_preserve_the_old_snapshot_for_retry(self):
        self.emit("run_start", 1)
        self.save()
        old = self.snapshot().read_bytes()
        with patch.object(self.db, "read_trace_events", side_effect=OSError("read failure")):
            with self.assertLogs("civil.trace_events", level="WARNING"):
                self.emit("done", 2)
        self.assertEqual(self.snapshot().read_bytes(), old)
        with patch.object(Path, "replace", side_effect=OSError("replace failure")):
            with self.assertRaises(OSError):
                trace_events.export_trace_jsonl("fixture")
        self.assertEqual(self.snapshot().read_bytes(), old)
        self.assertEqual(list(self.snapshot().parent.glob(".trace-*.tmp")), [])
        trace_events.export_trace_jsonl("fixture")
        self.assertEqual([ev["seq"] for ev in self.file_events()], [1, 2])

    def test_legacy_events_keep_payload_multiplicity_and_stable_order(self):
        self.emit("run_start", 1, t_ms=1000)
        repeated = {"type": "legacy", "seq": None, "ts": "2026-09-12T00:00:00Z", "t_ms": 1500}
        for _ in range(2):
            trace_events.append_trace_event("fixture", repeated, also_global=False)
        self.emit("tool_end", 2, t_ms=2000)
        self.save()
        old_without_clock = {"type": "old", "payload": "unsequenced history"}
        with self.snapshot().open("a", encoding="utf-8") as f:
            f.write(json.dumps(old_without_clock) + "\n")
        first = trace_events.read_trace_jsonl("fixture")
        self.assertEqual([ev["type"] for ev in first], ["run_start", "legacy", "legacy", "tool_end", "old"])
        self.assertEqual(first[-1], old_without_clock)
        for _ in range(2):
            trace_events.export_trace_jsonl("fixture")
            self.assertEqual(self.file_events(), first)

    def test_sqlite_is_authoritative_for_duplicate_sequence_ids(self):
        canonical = self.emit("run_start", 1, note="canonical")
        self.save()
        with self.snapshot().open("a", encoding="utf-8") as f:
            f.write(json.dumps({**canonical, "note": "stale file copy"}) + "\n")
        trace_events.export_trace_jsonl("fixture")
        self.assertEqual(self.file_events(), [canonical])

    def test_steps_only_snapshot_is_labelled_and_superseded_by_real_events(self):
        self.save()
        self.assertEqual(self.file_events()[0]["source"], "agent_steps_snapshot")
        self.assertEqual(self.file_events()[0]["schema"], "packing.stream.v1")
        self.emit("run_start", 1)
        self.emit("done", 2)
        self.assertEqual([ev["type"] for ev in self.file_events()], ["run_start", "done"])
        self.assertTrue(all(ev.get("source") != "agent_steps_snapshot" for ev in self.file_events()))

    def test_json_and_dual_keep_appending_terminal_events(self):
        for mode in ("json", "dual"):
            with self.subTest(mode=mode), patch.object(storage, "storage_mode", return_value=mode):
                for seq, kind in enumerate(("run_start", "tool_end", "done"), 1):
                    trace_events.append_trace_event(mode, {"type": kind, "seq": seq}, also_global=False)
                self.assertEqual([ev["seq"] for ev in trace_events.read_trace_jsonl(mode)], [1, 2, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
