#!/usr/bin/env python3
"""Offline regressions for cancellation, worker leases and workspace isolation."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.runtime import agent_loop, cancel, threads, workspace_ctx
from packing_assistant.runtime.deadlock import get_watch, reset_watch
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import ToolEngine


class ConfinedCancellationTests(unittest.TestCase):
    def test_precancelled_turn_does_not_start_worker_or_steps(self):
        from packing_assistant.runtime.turn import run_turn
        event = Event()
        event.set()
        with patch("packing_assistant.runtime.os_sandbox.Worker") as worker, \
                patch("packing_assistant.runtime.agent_loop.run_agent") as steps:
            result = run_turn("写会务清单", mode="steps", cancel_event=event)
        self.assertTrue(result["cancelled"])
        worker.assert_not_called()
        steps.assert_not_called()

    def test_auto_unavailable_after_cancel_does_not_fallback(self):
        from packing_assistant.runtime.turn import run_turn
        event = Event()
        def unavailable(*args, **kwargs):
            event.set()
            return {"ok": False, "error_code": "model_unavailable", "tools_run": []}
        with patch("packing_assistant.runtime.turn.resolve_mode", return_value=("model", "")), \
                patch("packing_assistant.runtime.os_sandbox.resolve_backend", return_value=("app", "")), \
                patch("packing_assistant.runtime.model_loop.run_model_agent", side_effect=unavailable), \
                patch("packing_assistant.runtime.agent_loop.run_agent") as steps:
            result = run_turn("写会务清单", mode="auto", cancel_event=event)
        self.assertEqual(result["error_code"], "cancelled")
        steps.assert_not_called()

    def test_cancelled_worker_result_does_not_publish_root_copy(self):
        from packing_assistant.runtime.turn import run_turn
        event = Event()
        class FinishedWorker:
            confined = {"backend": "test", "enforces": {"write": True}}
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def close(self): pass
            def call(self, *args, **kwargs):
                event.set()
                return {"out": {"ok": True, "wrote": True, "files": [{"path": "completed.xlsx"}]}}
        with patch("packing_assistant.runtime.os_sandbox.resolve_backend", return_value=("os", "")), \
                patch("packing_assistant.runtime.os_sandbox.Worker", FinishedWorker), \
                patch("packing_assistant.office_job.publish_root_copy") as publish:
            result = run_turn("写会务清单", mode="steps", cancel_event=event)
        self.assertTrue(result["cancelled"])
        self.assertTrue(result["wrote"])
        self.assertEqual(result["files"], [{"path": "completed.xlsx"}])
        publish.assert_not_called()

    def test_waiting_worker_is_terminated_and_cancel_event_not_serialized(self):
        from packing_assistant.runtime.os_sandbox import Worker, WorkerCancelled
        event, entered = Event(), Event()
        # A local protocol child deliberately never responds. No kernel backend
        # or external service is required to exercise the real pipe wait/stop.
        code = "import sys,time,json; request=json.loads(sys.stdin.readline()); assert 'cancel_event' not in request['args']; time.sleep(30)"
        with tempfile.TemporaryDirectory(prefix="civil-cancel-worker-") as folder:
            worker = Worker(Path(folder))
            process = subprocess.Popen([sys.executable, "-u", "-c", code], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            worker.process = process
            original = worker._read
            def waiting(*args, **kwargs):
                entered.set()
                return original(*args, **kwargs)
            try:
                with patch.object(worker, "_read", side_effect=waiting), ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(worker.call, "probe", cancel_event=event)
                    self.assertTrue(entered.wait(3))
                    event.set()
                    with self.assertRaises(WorkerCancelled):
                        future.result(timeout=3)
                self.assertIsNotNone(process.poll())
            finally:
                event.set()
                worker.close()
                process.stderr.close()


class CancellationIsolationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"CIVIL_WORKTREE_ROOT": "",
                                                        "CIVIL_SANDBOX": "workspace-write"}))
        self.stack.enter_context(patch("packing_assistant.runtime.project_instructions.seed_session"))
        self.stack.enter_context(patch("packing_assistant.runtime.memory.assemble_context", return_value={
            "project": "offline cancellation test", "p0_confirmed": True}))
        self.stack.enter_context(patch("packing_assistant.runtime.memory.prompt_prefix", return_value=""))
        self.stack.enter_context(patch("packing_assistant.runtime.middleware.annotate"))
        self.stack.enter_context(patch.object(agent_loop, "_plan_calls", return_value={
            "calls": [{"name": "probe", "arguments": {}}], "follow": []}))
        self.scheduler = Scheduler()
        reset_watch()
        self.addCleanup(reset_watch)

    def run_agent(self, engine, **kwargs):
        options = {"session_id": "offline-cancel", "expert_id": "finance-tax",
                   "force_intent": "run", "p0_confirmed": True, "tools": engine,
                   "scheduler": self.scheduler}
        options.update(kwargs)
        return agent_loop.run_agent("出一份税务日历", **options)

    def test_worktree_is_reset_between_reused_worker_turns_and_after_failure(self):
        seen = []

        def turn(*args, **kwargs):
            seen.append(workspace_ctx.current_worktree())
            if len(seen) == 3:
                raise RuntimeError("scripted failure")
            return {"ok": True}

        with patch("packing_assistant.runtime.turn.run_turn", side_effect=turn), \
                patch.object(threads, "save_thread"), patch.object(threads, "append_rollout"), \
                patch.object(threads, "load_rollout", return_value=[]), \
                workspace_ctx.worktree_scope("C:/caller-job"):
            for index, root in enumerate(("C:/first-job", "", "C:/failed-job")):
                thread = threads.CivilThread(thread_id=f"scope-{index}", session_id=f"scope-{index}", worktree=root)
                threads._run_on_thread(thread, "offline", skill="", confirm=False)
                self.assertEqual(workspace_ctx.current_worktree(), "C:/caller-job")
        self.assertEqual(seen, ["C:/first-job", "", "C:/failed-job"])

    def test_cancelled_thread_keeps_cancelled_snapshot_state(self):
        thread = threads.CivilThread(thread_id="stopped", session_id="stopped")
        with patch("packing_assistant.runtime.turn.run_turn", return_value={
                "ok": False, "cancelled": True, "state": "cancelled", "error_code": "cancelled"}), \
                patch.object(threads, "save_thread"), patch.object(threads, "append_rollout"), \
                patch.object(threads, "load_rollout", return_value=[]):
            threads._run_on_thread(thread, "offline", skill="", confirm=False)
        self.assertEqual(thread.state, "cancelled")

    def test_cancel_is_not_invalid_args_and_does_not_open_shared_circuit(self):
        engine = ToolEngine(circuit_threshold=1)
        called = []
        engine.register("probe", lambda args: called.append("ran"))
        event = Event()
        event.set()
        with cancel.scope("only-this-run", event=event):
            stopped = engine.execute("probe")
        self.assertEqual(stopped["error_code"], "cancelled")
        self.assertTrue(stopped["cancelled"])
        self.assertFalse(called)
        self.assertFalse(engine._fail_streak)
        self.assertTrue(engine.execute("probe")["ok"])
        self.assertEqual(called, ["ran"])

    def test_event_cancel_reaches_tool_checkpoint_and_agent_stays_cancelled(self):
        event = Event()
        engine = ToolEngine()

        def handler(args):
            event.set()
            cancel.check()
            self.fail("cancelled checkpoint returned")

        engine.register("probe", handler)
        result = self.run_agent(engine, cancel_event=event)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["error_code"], "cancelled")
        self.assertFalse(engine._fail_streak)
        self.assertFalse(self.scheduler._locks)
        self.assertEqual(get_watch().snapshot()["holds"], {})

    def test_scheduler_cancel_retains_lease_until_active_handler_exits(self):
        entered, resume = Event(), Event()
        self.addCleanup(resume.set)
        engine = ToolEngine()

        def handler(args):
            entered.set()
            if not resume.wait(5):
                raise RuntimeError("test failed to release handler")
            cancel.check()
            self.fail("cancelled handler continued")

        engine.register("probe", handler, timeout_s=10)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.run_agent, engine)
            try:
                self.assertTrue(entered.wait(5))
                active = next(run for run in self.scheduler._runs.values() if run.state == "waiting_tool")
                self.assertTrue(self.scheduler.cancel(active.run_id))
                rejected = self.scheduler.create_run("offline-cancel")
                self.assertEqual(rejected.error_code, "session_busy")
                self.assertIn("session:offline-cancel", get_watch().snapshot()["holds"])
            finally:
                resume.set()
            result = future.result(timeout=5)
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["error_code"], "cancelled")
        self.assertFalse(self.scheduler._locks)
        self.assertEqual(get_watch().snapshot()["holds"], {})
        self.assertFalse(cancel.is_cancelled(active.run_id))

    def test_timeout_requests_worker_stop_and_defers_resource_release(self):
        entered, resume, observed_cancel, released = Event(), Event(), Event(), Event()
        self.addCleanup(resume.set)
        engine = ToolEngine()

        def handler(args):
            entered.set()
            if not resume.wait(5):
                raise RuntimeError("test failed to release handler")
            try:
                cancel.check()
            except cancel.RunCancelled:
                observed_cancel.set()
                raise
            self.fail("timed-out cooperative worker continued")

        engine.register("probe", handler, timeout_s=0.01)
        original_release = self.scheduler.release

        def release(session_id):
            original_release(session_id)
            released.set()

        with patch.object(self.scheduler, "release", side_effect=release):
            result = self.run_agent(engine)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(result["error_code"], "timeout")
                self.assertEqual(result["state"], "failed")
                self.assertTrue(result["worker_running"])
                self.assertIn("资源保持占用", result["reply"])
                self.assertFalse(released.is_set())
                self.assertEqual(self.scheduler.create_run("offline-cancel").error_code, "session_busy")
                self.assertIn("expert:finance-tax", get_watch().snapshot()["holds"])
            finally:
                resume.set()
            self.assertTrue(observed_cancel.wait(5))
            self.assertTrue(released.wait(5))
        self.assertFalse(self.scheduler._locks)
        self.assertEqual(get_watch().snapshot()["holds"], {})
        self.assertFalse(engine._workers)

    def test_finish_annotation_still_owns_session_lease(self):
        engine = ToolEngine()
        engine.register("probe", lambda args: {"ok": True})
        observed = []

        def annotate(*args, **kwargs):
            observed.append(self.scheduler.create_run("offline-cancel").error_code)

        with patch("packing_assistant.runtime.middleware.annotate", side_effect=annotate):
            result = self.run_agent(engine)
        self.assertTrue(result["ok"])
        self.assertEqual(observed, ["session_busy"])
        self.assertFalse(self.scheduler._locks)

    def test_cancel_during_chat_explanation_cannot_finish_successfully(self):
        event = Event()

        def explain(*args):
            event.set()
            return "must not be published as a successful reply"

        with patch.object(agent_loop, "_explain", side_effect=explain):
            result = self.run_agent(ToolEngine(), force_intent="chat", cancel_event=event)
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "cancelled")
        self.assertNotIn("must not", result["reply"])


if __name__ == "__main__":
    unittest.main()
