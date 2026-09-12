#!/usr/bin/env python3
"""Cancellation through the workbench API, real blocked HTTP and tool boundaries."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from threading import Event, Thread, enumerate as threads
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from fastapi.testclient import TestClient
import app as workbench
import chat_service
import llm as demo_llm
import store
import turn_control
import uploads
from packing_assistant import expert_turn, llm
from packing_assistant.runtime import agent_loop, memory, session_handoff, session_packing
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import get_engine
from test_workbench_flow import sse_events


def eventually(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Condition did not become true before deadline")


class BlockedModel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.server.send_headers:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            chunk = ('data: ' + json.dumps({"choices": [{"delta": {"content": "已读取一段"}}]}, ensure_ascii=False) + '\n\n').encode()
            self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()
        self.server.started.set()
        self.connection.settimeout(0.1)
        while not self.server.stop_probe.is_set():
            try:
                if not self.connection.recv(1):
                    self.server.disconnected.set()
                    break
            except socket.timeout:
                continue
            except OSError:
                self.server.disconnected.set()
                break


class WorkbenchCancelTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / "output"
        output.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="test-workbench-cancel-", dir=output)
        self.root = Path(temporary.name).resolve()
        self.root.relative_to(output.resolve())
        self.addCleanup(temporary.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "CIVIL_JOB_ROOT": "",
            "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request"}))
        self.scheduler = Scheduler()
        for module, attribute, value in (
            (workbench, "OUT_ROOT", self.root), (agent_loop, "_OUT", self.root),
            (memory, "_OUT", self.root), (expert_turn, "_OUT", self.root),
            (session_handoff, "_DIR", self.root), (session_packing, "_DIR", self.root),
            (uploads, "UPLOAD_ROOT", self.root / "uploads"), (store, "DATA", self.root / "catalog.json"),
            (chat_service, "_ACTIVE", set()),
            (llm, "_RUNTIME_LLM", {"api_key": "", "base_url": "http://127.0.0.1:1", "model": "cancel-test"}),
        ):
            self.stack.enter_context(patch.object(module, attribute, value))
        self.stack.enter_context(patch.object(agent_loop, "get_scheduler", return_value=self.scheduler))
        self.stack.enter_context(patch.object(llm, "chat", side_effect=AssertionError("No online model allowed")))
        self.client = self.stack.enter_context(TestClient(workbench.app))
        self.pool = self.stack.enter_context(ThreadPoolExecutor(max_workers=3))
        self.sid = "cancel-" + uuid4().hex[:16]

    def post(self, message="你好", **options):
        return self.client.post("/api/chat", json={"message": message, "session_id": self.sid, **options})

    def cancel(self, sid=None):
        response = self.client.post(f"/api/sessions/{sid or self.sid}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def done(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        results = [e["data"] for e in sse_events(response) if e["event"] == "done"]
        self.assertEqual(len(results), 1, response.text)
        return results[0]

    def assert_released(self):
        self.assertNotIn(self.sid, chat_service._ACTIVE)
        self.assertNotIn(self.sid, self.scheduler._locks)
        self.assertFalse(turn_control.status(self.sid)["active"])

    def test_idle_and_finished_cancel_are_explicit_noops(self):
        self.assertEqual(self.cancel()["state"], "idle")
        self.assertFalse(self.cancel()["cancel_requested"])
        self.assertEqual(self.done(self.post())["state"], "done")
        completed = self.cancel()
        self.assertFalse(completed["cancel_requested"])
        self.assertEqual(completed["state"], "done")
        self.assert_released()

    def test_short_lease_remains_usable_for_export_and_release_is_idempotent(self):
        lease = chat_service.SessionLease(self.sid)
        with self.assertRaises(chat_service.SessionBusy):
            chat_service.SessionLease(self.sid)
        lease.release()
        lease.release()
        self.assert_released()
        self.assertTrue(self.done(self.post())["ok"])

    def test_cancel_during_admission_prevents_any_tool(self):
        entered, proceed = Event(), Event()
        original = chat_service.prepare_turn

        def paused(*args, **kwargs):
            entered.set()
            self.assertTrue(proceed.wait(4))
            return original(*args, **kwargs)

        with patch.object(chat_service, "prepare_turn", side_effect=paused):
            future = self.pool.submit(self.post, "写一份项目日报", expert_ids=["pm-daily"])
            self.assertTrue(entered.wait(3))
            try:
                self.assertTrue(self.cancel()["cancel_requested"])
            finally:
                proceed.set()
            done = self.done(future.result(timeout=4))
        self.assertTrue(done["cancelled"])
        self.assertFalse(done["wrote"])
        self.assertFalse(list(self.root.rglob("*.xlsx")))
        self.assert_released()

    def _blocked_model_case(self, send_headers):
        server = ThreadingHTTPServer(("127.0.0.1", 0), BlockedModel)
        server.send_headers = send_headers
        server.started, server.disconnected, server.stop_probe = Event(), Event(), Event()
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            config = {"api_key": "local-probe-not-a-secret", "base_url": f"http://127.0.0.1:{server.server_port}", "model": "probe"}
            with patch.dict(llm._RUNTIME_LLM, config), patch.object(workbench, "has_key", return_value=True):
                future = self.pool.submit(self.post, "解释一下土木资料整理")
                self.assertTrue(server.started.wait(3))
                started = time.monotonic()
                response = self.cancel()
                self.assertTrue(response["cancel_requested"])
                done = self.done(future.result(timeout=3))
                self.assertLess(time.monotonic() - started, 3)
                self.assertTrue(server.disconnected.wait(2), "The blocked upstream socket was not interrupted")
            self.assertEqual(done["state"], "cancelled")
            self.assertFalse(done["ok"])
            self.assertFalse(done["deliverables"])
            restored = self.client.get(f"/api/sessions/{self.sid}").json()
            self.assertEqual(restored["turn_state"]["state"], "cancelled")
            self.assertIn("已取消", restored["transcript"][-1]["text"])
            self.assert_released()
            eventually(lambda: not any(t.name == "civil-model-" + self.sid for t in threads()))
            self.assertTrue(self.done(self.post())["ok"])
        finally:
            server.stop_probe.set()
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_blocked_real_http_model_connection_is_closed_and_partial_restored(self):
        self._blocked_model_case(send_headers=True)

    def test_model_waiting_for_response_headers_is_cancelled_without_leaking_reader(self):
        self._blocked_model_case(send_headers=False)

    def test_current_tool_finishes_files_then_cancel_stops_later_posts(self):
        engine = get_engine()
        original = engine.execute
        entered, proceed = Event(), Event()
        calls = []

        def paused(name, *args, **kwargs):
            calls.append(name)
            result = original(name, *args, **kwargs)
            if name == "pm-daily__log":
                entered.set()
                self.assertTrue(proceed.wait(5))
            return result

        with patch.object(engine, "execute", side_effect=paused):
            future = self.pool.submit(self.post, "写一份本岗草稿", expert_ids=["pm-daily", "admin-office"])
            self.assertTrue(entered.wait(3))
            try:
                requested = self.cancel()
                self.assertEqual(requested["state"], "cancelling")
                self.assertTrue(requested["active"])
                self.assertEqual(self.post().status_code, 409)
                self.assertEqual(self.cancel()["state"], "cancelling")
                other = self.client.post("/api/chat", json={"message": "你好", "session_id": "other-" + uuid4().hex[:16]})
                self.assertTrue(self.done(other)["ok"])
            finally:
                proceed.set()
            done = self.done(future.result(timeout=4))
        self.assertTrue(done["cancelled"])
        self.assertTrue(done["wrote"])
        self.assertEqual(calls, ["pm-daily__log"])
        self.assertGreaterEqual({Path(f["path"]).suffix for f in done["deliverables"]}, {".md", ".xlsx"})
        for item in done["deliverables"]:
            response = self.client.get("/api/file", params={"path": item["path"]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, Path(item["path"]).read_bytes())
        detail = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(detail["deliverables"], done["deliverables"])
        self.assertEqual(detail["turn_state"]["state"], "cancelled")
        self.assert_released()
        self.assertTrue(self.done(self.post())["ok"])

    def test_cancel_at_tool_boundary_prevents_follow_on_export(self):
        event = Event()
        calls = []

        class Engine:
            def execute(self, name, *args, **kwargs):
                calls.append(name)
                event.set()
                return {"ok": True, "data": {"markdown": "# pending export"}}

        with patch.object(agent_loop, "_plan_calls", return_value={"calls": [{"name": "pack-ship__export", "arguments": {}}]}):
            result = agent_loop.run_agent("写一份装柜作业单", session_id=self.sid, expert_id="pack-ship", p0_confirmed=True,
                                          tools=Engine(), scheduler=self.scheduler, cancel_event=event)
        self.assertEqual(calls, ["pack-ship__export"])
        self.assertEqual(result["state"], "cancelled")
        self.assertFalse(result["wrote"])
        self.assertFalse(result["files"])
        self.assert_released()

    def test_disconnected_consumer_still_persists_cancelled_result_and_releases(self):
        entered, proceed = Event(), Event()

        def blocked(_):
            entered.set()
            proceed.wait(4)
            yield {"event": "token", "data": {"text": "应被丢弃"}}

        lease = chat_service.SessionLease(self.sid)
        turn = chat_service.prepare_turn(self.root, {"message": "你好", "session_id": self.sid})
        stream = chat_service.stream_turn(self.root, turn, key_available=True, plain_runner=blocked, lease=lease)
        try:
            next(stream)
            self.assertTrue(entered.wait(2))
            stream.close()
            # Mirrors the transport background/finally callback; it must not free
            # a still-running producer early, which owns result persistence.
            lease.release()
            eventually(lambda: not turn_control.status(self.sid)["active"])
        finally:
            proceed.set()
            stream.close()
        detail = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertIn("已取消", detail["transcript"][-1]["text"])
        self.assertNotIn("应被丢弃", detail["transcript"][-1]["text"])
        self.assertEqual(detail["turn_state"]["state"], "cancelled")
        self.assert_released()

    def test_real_http_disconnect_persists_result_without_stranding_a_lease(self):
        import httpx
        import uvicorn

        proceed = Event()

        def paused(_):
            yield {"event": "token", "data": {"text": "部分回复"}}
            proceed.wait(8)
            yield {"event": "done", "data": {"text": "完成回复"}}

        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            port = bound.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(workbench.app, host="127.0.0.1", port=port,
                                               log_level="error", access_log=False, lifespan="off"))
        worker = Thread(target=server.run, daemon=True)
        with patch.object(workbench, "run_plain", side_effect=paused), patch.object(workbench, "has_key", return_value=True):
            worker.start()
            try:
                eventually(lambda: server.started)
                with httpx.Client(timeout=3) as client:
                    with client.stream("POST", f"http://127.0.0.1:{port}/api/chat",
                                       json={"message": "你好", "session_id": self.sid}) as response:
                        self.assertEqual(response.status_code, 200)
                        for line in response.iter_lines():
                            if "部分回复" in line:
                                break
                    eventually(lambda: not turn_control.status(self.sid)["active"])
                    restored = client.get(f"http://127.0.0.1:{port}/api/sessions/{self.sid}").json()
                self.assertEqual(restored["turn_state"]["state"], "cancelled")
                self.assertIn("部分回复", restored["transcript"][-1]["text"])
                self.assertIn("已取消", restored["transcript"][-1]["text"])
                self.assert_released()
            finally:
                proceed.set()
                server.should_exit = True
                worker.join(timeout=4)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
