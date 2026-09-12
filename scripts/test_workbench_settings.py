#!/usr/bin/env python3
"""Workbench model settings and shared clients; fixtures never contact a provider."""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from packing_assistant import llm as shared_llm
from model_settings import get_settings, set_settings
import context


@contextmanager
def _local_response(body: bytes, *, status: int = 200, content_type: str = "text/event-stream", declared_extra: int = 0):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:
            pass

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body) + declared_extra))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        set_settings({"api_key": "local-fixture-key", "base_url": f"http://127.0.0.1:{server.server_port}/v1", "model": "fixture-model"})
        yield
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


class ModelSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        env = patch.dict(os.environ, {
            "CIVIL_API_KEY": "", "OPENAI_API_KEY": "", "LLM_API_KEY": "", "DEEPSEEK_API_KEY": "",
            "CIVIL_API_BASE": "", "OPENAI_BASE_URL": "", "LLM_BASE_URL": "", "DEEPSEEK_BASE_URL": "",
            "CIVIL_MODEL": "", "OPENAI_MODEL": "", "LLM_MODEL": "", "DEEPSEEK_MODEL": "",
            "PYTHON_DOTENV_DISABLED": "1", "NO_PROXY": "127.0.0.1,localhost",
        })
        env.start()
        self.addCleanup(env.stop)
        shared_llm.set_runtime_llm(None)
        self.addCleanup(shared_llm.set_runtime_llm, None)
        previous = context.runtime_policy()
        semantic = context.semantic_summary_enabled()
        context.set_runtime_policy(None)
        context.set_semantic_summary(None)
        self.addCleanup(context.set_runtime_policy, previous)
        self.addCleanup(context.set_semantic_summary, semantic)

    def test_unconfigured_payload_matches_workbench_contract(self) -> None:
        result = get_settings()
        self.assertEqual(set(result), {"ok", "source", "configured", "base_url", "model", "key_masked", "context", "semantic_summary"})
        self.assertEqual(result["source"], "env")
        self.assertFalse(result["configured"])
        self.assertEqual(result["key_masked"], "")
        self.assertIs(result["semantic_summary"], False)
        self.assertIs(result["context"]["semantic_summary"], False)

    def test_semantic_option_is_process_local_preserved_when_omitted_and_cleared_without_model_io(self) -> None:
        with patch.object(shared_llm, "chat", side_effect=AssertionError("settings must not call a model")):
            enabled = set_settings({"semantic_summary": True, "context_limit": 8192, "output_reserve": 1024})
            self.assertIs(enabled["semantic_summary"], True)
            self.assertIs(enabled["context"]["semantic_summary"], True)
            self.assertFalse(enabled["configured"])
            self.assertIs(set_settings({"model": "changed-model"})["semantic_summary"], True)
            self.assertIs(set_settings({"semantic_summary": False})["semantic_summary"], False)
            set_settings({"semantic_summary": True})
            cleared = set_settings({"clear": True})
        self.assertIs(cleared["semantic_summary"], False)
        self.assertEqual(cleared["source"], "env")
        self.assertIsNone(context.runtime_policy())

    def test_invalid_semantic_or_limits_cannot_partially_change_model_budget_or_option(self) -> None:
        set_settings({"model": "initial-model", "api_key": "fixture-key", "context_limit": 8192,
                      "output_reserve": 1024, "semantic_summary": True})
        before = get_settings()
        bad = [dict(semantic_summary=value, model="should-not-change", context_limit=16384, output_reserve=2048)
               for value in ("true", "false", "yes", 1, 0, None, [], {})]
        bad += [{"clear": True, "semantic_summary": "true"},
                {"model": "should-not-change", "semantic_summary": False, "context_limit": 1024, "output_reserve": 2048},
                {"model": "invalid model", "semantic_summary": False, "context_limit": 16384, "output_reserve": 2048}]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                set_settings(payload)
            self.assertEqual(get_settings(), before)

    def test_http_semantic_flag_is_strict_and_omission_keeps_current_configuration(self) -> None:
        from fastapi.testclient import TestClient
        import app
        with TestClient(app.app) as client, patch.object(shared_llm, "chat", side_effect=AssertionError("no model I/O")):
            self.assertTrue(client.get("/api/health").json()["capabilities"]["semantic_summary"])
            before = get_settings()
            for value in ("true", "false", "yes", 1, 0, None, [], {}):
                response = client.post("/api/llm-config", json={"semantic_summary": value, "model": "do-not-change", "context_limit": 8192})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(get_settings(), before)
            for enabled in (False, True):
                response = client.post("/api/llm-config", json={"semantic_summary": enabled})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIs(response.json()["semantic_summary"], enabled)
            self.assertIs(client.post("/api/llm-config", json={"model": "changed-model"}).json()["semantic_summary"], True)
            self.assertIs(client.post("/api/llm-config", json={"clear": True}).json()["semantic_summary"], False)

    def test_runtime_override_masking_blank_preservation_and_clear(self) -> None:
        with patch.dict(os.environ, {"CIVIL_API_KEY": "environment-fixture", "CIVIL_MODEL": "environment-model"}):
            result = set_settings({"api_key": "runtime-fixture-key", "base_url": "http://localhost:9999/v1/", "model": "local-model"})
            self.assertEqual(result["source"], "runtime")
            self.assertTrue(result["configured"])
            self.assertEqual(result["base_url"], "http://localhost:9999/v1")
            self.assertNotIn("runtime-fixture-key", json.dumps(result))
            self.assertEqual(result["key_masked"], "runt" + "*" * 11 + "-key")
            set_settings({"api_key": "  ", "base_url": "", "model": "changed-model"})
            self.assertEqual(shared_llm.llm_config()["api_key"], "runtime-fixture-key")
            self.assertEqual(shared_llm.llm_config()["model"], "changed-model")
            cleared = set_settings({"clear": True})
            self.assertEqual(cleared["source"], "env")
            self.assertEqual(cleared["model"], "environment-model")
            self.assertEqual(shared_llm.llm_config()["api_key"], "environment-fixture")

    def test_short_key_is_fully_masked(self) -> None:
        self.assertEqual(set_settings({"api_key": "short"})["key_masked"], "*****")

    def test_invalid_updates_leave_previous_configuration_unchanged(self) -> None:
        set_settings({"api_key": "fixture-key", "base_url": "http://localhost:9999/v1", "model": "fixture-model"})
        before = shared_llm.llm_config()
        invalid = (
            {"base_url": "file:///tmp/model"},
            {"base_url": "https://user:password@example.test/v1"},
            {"base_url": "https://example.test/v1?token=fixture"},
            {"base_url": "https://example.test/v1#fragment"},
            {"base_url": "http://localhost:99999/v1"},
            {"base_url": "https://exa mple.test/v1"},
            {"model": "a model"},
            {"model": "model\x00name"},
            {"api_key": "fixture\nheader"},
            {"api_key": None},
            {"clear": "true"},
        )
        for payload in invalid:
            with self.subTest(payload=tuple(payload)):
                with self.assertRaises(ValueError):
                    set_settings(payload)
                self.assertEqual(shared_llm.llm_config(), before)

    def test_environment_url_credentials_are_not_returned(self) -> None:
        with patch.dict(os.environ, {"CIVIL_API_BASE": "https://user:fixture-password@example.test/v1?token=fixture#fragment"}):
            self.assertEqual(get_settings()["base_url"], "https://example.test/v1")

    def test_shared_snapshots_cannot_mutate_the_runtime_config(self) -> None:
        original = {"api_key": "fixture-key", "base_url": "http://localhost/v1", "model": "initial"}
        shared_llm.set_runtime_llm(original)
        original["model"] = "mutated"
        snapshot = shared_llm.runtime_llm()
        snapshot["model"] = "also-mutated"
        self.assertEqual(shared_llm.llm_config()["model"], "initial")

    def test_demo_and_shared_chat_use_same_runtime_config_against_local_api(self) -> None:
        requests: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append({"path": self.path, "authorization": self.headers.get("Authorization"), "body": body})
                response = json.dumps({
                    "id": "offline-fixture", "object": "chat.completion", "created": 0,
                    "model": "fixture-model", "choices": [{"index": 0, "message": {"role": "assistant", "content": "local reply"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/v1"
            set_settings({"api_key": "local-fixture-key", "base_url": base, "model": "fixture-model"})
            from llm import chat as demo_chat

            self.assertEqual(demo_chat([{"role": "user", "content": "offline fixture"}])["content"], "local reply")
            self.assertEqual(shared_llm.chat("offline system", "offline fixture"), "local reply")
            self.assertEqual(len(requests), 2)
            for request in requests:
                self.assertEqual(request["path"], "/v1/chat/completions")
                self.assertEqual(request["authorization"], "Bearer local-fixture-key")
                self.assertEqual(request["body"]["model"], "fixture-model")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_stream_accepts_sse_framing_and_only_finishes_after_done(self) -> None:
        from llm import stream_plain

        body = ('\ufeff: heartbeat\r\ndata:{\r\ndata:"choices":[{"delta":{"content":"中文"},"finish_reason":null}]}\r\n\r\n'
                ': heartbeat\n\ndata: {"choices":[{"delta":{"content":"回答"},"finish_reason":"stop"}]}\n\n'
                'data: {"choices":[],"usage":{"total_tokens":3}}\n\ndata:[DONE]\n\n').encode()
        with _local_response(body):
            self.assertEqual("".join(stream_plain([{"role": "user", "content": "offline fixture"}])), "中文回答")

    def test_stream_eof_without_done_preserves_tokens_and_reports_incomplete(self) -> None:
        from llm import LLMError, stream_plain

        body = b'data: {"choices":[{"delta":{"content":"partial reply"},"finish_reason":null}]}\n\n'
        with _local_response(body):
            iterator = stream_plain([{"role": "user", "content": "offline fixture"}])
            self.assertEqual(next(iterator), "partial reply")
            with self.assertRaisesRegex(LLMError, "未收到完成标记"):
                next(iterator)

    def test_stream_broken_http_body_is_a_sanitized_failure(self) -> None:
        from llm import LLMError, stream_plain

        body = b'data: {"choices":[{"delta":{"content":"partial reply"},"finish_reason":null}]}\n\n'
        with _local_response(body, declared_extra=100):
            iterator = stream_plain([{"role": "user", "content": "offline fixture"}])
            self.assertEqual(next(iterator), "partial reply")
            with self.assertRaisesRegex(LLMError, "连接异常"):
                next(iterator)

    def test_http_error_body_is_never_returned_by_either_client_mode(self) -> None:
        from llm import LLMError, chat, stream_plain

        body = b'{"error":"provider echoed local-fixture-key and private document"}'
        with _local_response(body, status=401, content_type="application/json"):
            for operation in (lambda: chat([{"role": "user", "content": "offline fixture"}]),
                              lambda: list(stream_plain([{"role": "user", "content": "offline fixture"}]))):
                with self.assertRaises(LLMError) as caught:
                    operation()
                self.assertIn("401", str(caught.exception))
                self.assertNotIn("local-fixture-key", str(caught.exception))
                self.assertNotIn("private document", str(caught.exception))

    def test_provider_stream_errors_and_malformed_chunks_cannot_finish(self) -> None:
        from llm import LLMError, stream_plain

        cases = (
            b'event:error\ndata:{"message":"local-fixture-key"}\n\ndata:[DONE]\n\n',
            b'data:{"error":{"message":"local-fixture-key"}}\n\ndata:[DONE]\n\n',
            b'data:malformed local-fixture-key\n\ndata:[DONE]\n\n',
            b'data:{"choices":[{"delta":{"content":"truncated"},"finish_reason":"length"}]}\n\ndata:[DONE]\n\n',
            b'data:[DONE]\n\n',
        )
        for index, body in enumerate(cases):
            with self.subTest(index=index), _local_response(body):
                with self.assertRaises(LLMError) as caught:
                    list(stream_plain([{"role": "user", "content": "offline fixture"}]))
                self.assertNotIn("local-fixture-key", str(caught.exception))

    def test_nonstream_provider_error_and_invalid_json_are_sanitized(self) -> None:
        from llm import LLMError, chat

        for body in (b'{"error":{"message":"local-fixture-key"}}', b'local-fixture-key invalid JSON'):
            with _local_response(body, content_type="application/json"):
                with self.assertRaises(LLMError) as caught:
                    chat([{"role": "user", "content": "offline fixture"}])
                self.assertNotIn("local-fixture-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
