#!/usr/bin/env python3
"""Offline regressions for thread admission, identity, and durable snapshots."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.runtime import threads


class ThreadRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="civil-runtime-threads-")
        self.root = Path(self.directory.name)
        self.workers = ThreadPoolExecutor(max_workers=2)
        self.callers = ThreadPoolExecutor(max_workers=2)
        self.releases: list[Event] = []
        self.patches = [
            patch.object(threads, "_DIR", self.root),
            patch.object(threads, "_POOL", self.workers),
            patch.object(threads, "_ACTIVE", set()),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for release in self.releases:
            release.set()
        self.callers.shutdown(wait=True)
        self.workers.shutdown(wait=True)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def release_event(self) -> Event:
        event = Event()
        self.releases.append(event)
        return event

    def test_unknown_or_alias_id_never_creates_or_runs_a_thread(self) -> None:
        th = threads.CivilThread("t_alias", "t_alias")
        threads.save_thread(th)
        with patch("packing_assistant.runtime.agent_loop.run_agent") as agent:
            for thread_id in ("missing", "t/alias", "", "x" * 41, "NUL", "CON"):
                for background in (False, True):
                    result = threads.run_on_thread(thread_id, "hello", background=background)
                    self.assertEqual(result["error_code"], "unknown_thread")
            agent.assert_not_called()
        self.assertIsNone(threads.load_thread("t/alias"))
        self.assertEqual([item.thread_id for item in threads.list_threads()], ["t_alias"])

    def test_active_foreground_turn_rejects_both_duplicate_modes(self) -> None:
        th = threads.new_thread()
        started, release = Event(), self.release_event()

        def agent(text: str, **kwargs: object) -> dict:
            started.set()
            self.assertTrue(release.wait(5), "test did not release the foreground turn")
            return {"ok": True, "reply": text, "wrote": False}

        with patch("packing_assistant.runtime.agent_loop.run_agent", side_effect=agent) as mocked:
            first = self.callers.submit(threads.run_on_thread, th.thread_id, "first")
            try:
                self.assertTrue(started.wait(3))
                self.assertTrue(threads.thread_status(th.thread_id)["running"])
                for background in (False, True):
                    duplicate = threads.run_on_thread(th.thread_id, "duplicate", background=background)
                    self.assertEqual(duplicate["error_code"], "thread_busy")
                self.assertEqual(threads.load_thread(th.thread_id).last_text, "first")
            finally:
                release.set()
            self.assertTrue(first.result(timeout=3)["ok"])
            self.assertEqual(mocked.call_count, 1)
        status = threads.thread_status(th.thread_id)
        self.assertFalse(status["running"])
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["last_reply"], "first")

    def test_distinct_background_threads_really_run_in_parallel(self) -> None:
        first, second = threads.new_thread(), threads.new_thread()
        both_started, release, guard = Event(), self.release_event(), Lock()
        sessions: set[str] = set()

        def agent(text: str, *, session_id: str, **kwargs: object) -> dict:
            with guard:
                sessions.add(session_id)
                if len(sessions) == 2:
                    both_started.set()
            self.assertTrue(release.wait(5), "test did not release background turns")
            return {"ok": True, "reply": text, "wrote": False}

        with patch("packing_assistant.runtime.agent_loop.run_agent", side_effect=agent):
            try:
                for th in (first, second):
                    result = threads.run_on_thread(th.thread_id, th.thread_id, background=True)
                    self.assertTrue(result["ok"])
                self.assertTrue(both_started.wait(3), "different threads did not run concurrently")
            finally:
                release.set()
            self.workers.shutdown(wait=True)
        self.assertEqual(sessions, {first.session_id, second.session_id})
        for th in (first, second):
            self.assertEqual(threads.thread_status(th.thread_id)["state"], "done")
        self.assertFalse(threads._ACTIVE)

    def test_queued_turn_is_reserved_before_worker_starts(self) -> None:
        first, second = threads.new_thread(), threads.new_thread()
        started, release = Event(), self.release_event()

        def agent(text: str, **kwargs: object) -> dict:
            if text == "first":
                started.set()
                self.assertTrue(release.wait(5))
            return {"ok": True, "reply": text}

        pool = ThreadPoolExecutor(max_workers=1)
        try:
            with patch.object(threads, "_POOL", pool), patch(
                "packing_assistant.runtime.agent_loop.run_agent", side_effect=agent
            ) as mocked:
                try:
                    threads.run_on_thread(first.thread_id, "first", background=True)
                    self.assertTrue(started.wait(3))
                    threads.run_on_thread(second.thread_id, "queued", background=True)
                    self.assertTrue(threads.thread_status(second.thread_id)["running"])
                    duplicate = threads.run_on_thread(second.thread_id, "duplicate", background=True)
                    self.assertEqual(duplicate["error_code"], "thread_busy")
                    self.assertEqual(mocked.call_count, 1)
                finally:
                    release.set()
                pool.shutdown(wait=True)
                self.assertEqual(mocked.call_count, 2)
            self.assertEqual(threads.thread_status(second.thread_id)["last_reply"], "queued")
        finally:
            release.set()
            pool.shutdown(wait=True)

    def test_execution_failure_releases_reservation_for_retry(self) -> None:
        th = threads.new_thread()
        with patch("packing_assistant.runtime.agent_loop.run_agent", side_effect=RuntimeError("engine failed")):
            result = threads.run_on_thread(th.thread_id, "first")
        self.assertEqual(result["error_code"], "thread_execution_failed")
        self.assertEqual(threads.thread_status(th.thread_id)["state"], "failed")
        self.assertFalse(threads._ACTIVE)
        with patch("packing_assistant.runtime.agent_loop.run_agent", return_value={"ok": True, "reply": "retry"}):
            self.assertTrue(threads.run_on_thread(th.thread_id, "retry")["ok"])
        self.assertEqual(threads.thread_status(th.thread_id)["error"], "")

    def test_submit_failure_does_not_leave_a_running_thread(self) -> None:
        th = threads.new_thread()
        with patch.object(self.workers, "submit", side_effect=RuntimeError("executor unavailable")):
            result = threads.run_on_thread(th.thread_id, "first", background=True)
        self.assertEqual(result["error_code"], "thread_start_failed")
        self.assertFalse(threads._ACTIVE)
        self.assertEqual(threads.thread_status(th.thread_id)["state"], "failed")

    def test_failed_atomic_replace_preserves_last_snapshot_and_removes_temp(self) -> None:
        th = threads.new_thread("before")
        path = self.root / f"{th.thread_id}.json"
        before = path.read_bytes()
        th.title = "after"
        with patch.object(Path, "replace", side_effect=PermissionError("disk unavailable")):
            with self.assertRaises(PermissionError):
                threads.save_thread(th)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_storage_failure_during_admission_never_runs_model(self) -> None:
        th = threads.new_thread()
        with patch.object(Path, "replace", side_effect=PermissionError("disk unavailable")), patch(
            "packing_assistant.runtime.agent_loop.run_agent"
        ) as agent:
            result = threads.run_on_thread(th.thread_id, "first")
        self.assertEqual(result["error_code"], "thread_start_failed")
        self.assertIn("storage_error", result)
        self.assertFalse(threads._ACTIVE)
        agent.assert_not_called()
        self.assertEqual(threads.load_thread(th.thread_id).state, "idle")

    def test_list_skips_corrupt_snapshots_and_sorts_valid_ones(self) -> None:
        first, second = threads.new_thread("first"), threads.new_thread("second")
        for th, updated_at in ((first, 10), (second, 20)):
            raw = {**th.to_dict(), "updated_at": updated_at}
            (self.root / f"{th.thread_id}.json").write_text(json.dumps(raw), encoding="utf-8")
        invalid = [
            {"thread_id": "other"},
            {"created_at": "bad timestamp"},
            {"updated_at": float("inf")},
            {"artifacts": 5},
            {"artifacts": [123]},
            {"confirm": "false"},
        ]
        for number, changes in enumerate(invalid):
            thread_id = f"bad-{number}"
            raw = {**first.to_dict(), "thread_id": thread_id, **changes}
            (self.root / f"{thread_id}.json").write_text(json.dumps(raw), encoding="utf-8")
        (self.root / "truncated.json").write_text('{"thread_id":', encoding="utf-8")
        (self.root / "invalid-utf8.json").write_bytes(b"\xff")
        self.assertEqual([th.thread_id for th in threads.list_threads()], [second.thread_id, first.thread_id])


if __name__ == "__main__":
    unittest.main()
