"""Real semantic core + loopback model HTTP + shipped workbench SSE routes."""
from __future__ import annotations

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Event, Thread
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import test_workbench_flow as flow
import chat_service
import context
import projects
import semantic_memory
import semantic_service
import turn_control


class LocalModel:
    def __init__(self):
        self.requests = []
        self.mode = "valid"
        self.release = Event()
        self.summary_entered = Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(data)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if data.get("stream") else "application/json")
                self.end_headers()
                if data.get("stream"):
                    chunk = {"choices": [{"delta": {"content": "本地模型测试回答完成。"}, "finish_reason": "stop"}]}
                    body = "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\ndata: [DONE]\n\n"
                else:
                    owner.summary_entered.set()
                    if owner.mode == "blocked":
                        owner.release.wait(5)
                    source = json.loads(data["messages"][-1]["content"])["sources"][0]
                    quote = source["text"][:24]
                    item = {"kind": "goal", "text": "较早讨论强调接口协调。", "evidence": [{
                        "message_id": source["message_id"], "start": source["start"],
                        "end": source["start"] + len(quote), "quote": quote}]}
                    answer = json.dumps({"items": [item]}, ensure_ascii=False)
                    if owner.mode == "invalid":
                        answer = "malformed summary fixture"
                    if owner.mode == "unsupported_number":
                        item["text"] = "预算为987654321元。"
                        answer = json.dumps({"items": [item]}, ensure_ascii=False)
                    if owner.mode == "empty":
                        answer = '{"items":[]}'
                    body = json.dumps({"choices": [{"message": {"role": "assistant", "content": answer}}]}, ensure_ascii=False)
                try:
                    self.wfile.write(body.encode("utf-8"))
                    self.wfile.flush()
                except (ConnectionError, OSError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)

    @property
    def summaries(self):
        return [r for r in self.requests if not r.get("stream")]

    @property
    def answers(self):
        return [r for r in self.requests if r.get("stream")]


class SemanticHttpTests(unittest.TestCase):
    post = flow.WorkbenchFlowTests.post

    def setUp(self):
        flow.WorkbenchFlowTests.setUp(self)
        self.addCleanup(context.set_runtime_policy, context.runtime_policy())
        self.addCleanup(context.set_semantic_summary, context.semantic_summary_enabled())
        context.set_runtime_policy({"limit": 12000, "reserve": 1500})
        context.set_semantic_summary(True)
        self.model = LocalModel()
        self.addCleanup(self.model.close)
        self.stack.enter_context(patch.object(flow.llm, "_RUNTIME_LLM", {
            "api_key": "loopback-fixture", "base_url": self.model.url, "model": "loopback-model"}))
        projects.touch_session(self.root, self.sid, "语义摘要实际链路验收")
        for i in range(8):
            projects.append_turn(self.root, self.sid, "user", f"接口协调讨论记录{i}。" + "注意方案之间的衔接。" * 3)
        for i in range(4):
            projects.append_turn(self.root, self.sid, "assistant", f"近期原文标记{i}。" + "相关资料需要继续核对。" * 150)
        self.original = projects.read_full_history(self.root, self.sid)

    def ask(self):
        return self.post("请解释此前沟通中需要关注的问题？", expert_ids=["pm-daily"])

    def test_real_http_summary_answer_sources_restore_and_budget(self):
        done, events = self.ask()
        self.assertTrue(done["ok"], done)
        self.assertEqual(len(self.model.summaries), 1)
        self.assertEqual(len(self.model.answers), 1)
        summary = self.model.summaries[0]
        self.assertEqual(summary["max_tokens"], 1024)
        self.assertLessEqual(context.messages_tokens(summary["messages"]), 3500)
        sent_sources = json.loads(summary["messages"][-1]["content"])["sources"]
        self.assertEqual([s["message_id"] for s in sent_sources], [r["id"] for r in self.original[:-4]])
        answer = self.model.answers[0]
        self.assertEqual(answer["max_tokens"], 1500)
        self.assertLessEqual(context.validate_request(answer["messages"])["used"], 10500)
        self.assertIn("较早讨论强调接口协调", json.dumps(answer["messages"], ensure_ascii=False))
        self.assertFalse(any(m["content"] == self.original[0]["content"] for m in answer["messages"]))
        self.assertEqual(done["context"]["semantic_replaced_messages"], 8)
        self.assertTrue(done["context"]["semantic"]["included"])
        self.assertEqual(done["context"]["semantic"]["status"], "generated")
        self.assertIn("compacting", [e["data"].get("phase") for e in events if e["event"] == "status"])
        history = projects.read_full_history(self.root, self.sid)
        self.assertEqual(history[:len(self.original)], self.original)
        self.assertEqual(len(history), len(self.original) + 2)
        cache = semantic_memory.load(self.root, self.sid, history=history)
        self.assertIsNotNone(cache)
        self.assertFalse(cache["verified"])
        self.assertFalse(cache["authorizes_actions"])
        self.assertLessEqual((self.root / self.sid / "semantic.summary.json").stat().st_size, 65536)
        cites = [c for c in done["citations"] if c.get("title", "").startswith("语义摘要原文")]
        self.assertTrue(cites, done["citations"])
        for cite in cites:
            response = self.client.get(cite["url"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["text"], cite["snippet"])
        detail = self.client.get("/api/context", params={"session_id": self.sid}).json()
        self.assertIn("较早讨论强调接口协调", detail["semantic_memory_text"])
        self.assertNotIn("较早讨论强调接口协调", detail["memory_text"])
        # A fresh plan advances over new raw records instead of summarizing summaries.
        plan = semantic_memory.prepare(self.root, self.sid, history, 3500, 1024)
        self.assertIsNotNone(plan)
        newer_sources = json.loads(semantic_memory.messages(plan)[-1]["content"])["sources"]
        self.assertEqual(newer_sources[0]["message_id"], self.original[8]["id"])
        self.assertNotIn("较早讨论强调接口协调", json.dumps(newer_sources, ensure_ascii=False))

    def test_invalid_or_unsupported_summary_falls_back_to_answer(self):
        for mode in ("invalid", "unsupported_number"):
            with self.subTest(mode=mode):
                self.model.mode = mode
                done, _ = self.ask()
                self.assertTrue(done["ok"], done)
                self.assertEqual(done["context"]["semantic"]["status"], "fallback")
                self.assertNotIn("semantic-memory", done["context"]["sources_used"])
                self.assertFalse((self.root / self.sid / "semantic.summary.json").exists())
        self.assertEqual(len(self.model.answers), 2)

    def test_empty_summary_does_not_remove_original_prefix(self):
        self.model.mode = "empty"
        done, _ = self.ask()
        self.assertTrue(done["ok"])
        self.assertNotIn("semantic-memory", done["context"]["sources_used"])
        self.assertEqual(done["context"].get("semantic_replaced_messages", 0), 0)
        self.assertFalse(done["context"]["semantic"]["included"])
        self.assertEqual(done["context"]["semantic"]["covered_messages"], 8)

    def test_cache_write_error_still_answers_and_retains_full_transcript(self):
        with patch.object(semantic_memory, "persist", side_effect=OSError("fixture cache unavailable")):
            done, _ = self.ask()
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["context"]["semantic"]["status"], "fallback")
        self.assertEqual(len(self.model.answers), 1)
        self.assertEqual(projects.read_full_history(self.root, self.sid)[:len(self.original)], self.original)

    def test_http_body_deadline_falls_back_and_late_response_is_not_persisted(self):
        self.model.mode = "blocked"
        with patch.object(semantic_service, "SUMMARY_TIMEOUT_SECONDS", .4):
            done, _ = self.ask()
        self.assertTrue(self.model.summary_entered.is_set())
        self.assertTrue(done["ok"], done)
        self.assertEqual(done["context"]["semantic"]["error_code"], "timeout")
        self.assertEqual(len(self.model.answers), 1)
        self.model.release.set()
        self.assertFalse((self.root / self.sid / "semantic.summary.json").exists())

    def test_identical_failure_uses_cooldown_without_repeating_http(self):
        self.model.mode = "invalid"
        turn = chat_service.prepare_turn(self.root, {"session_id": self.sid, "message": "请解释此前沟通中需要关注的问题？"})
        before = deepcopy(turn["requests"])
        for _ in range(2):
            list(semantic_service.events(self.root, turn, turn_control.TurnControl(self.sid), key_available=True))
        self.assertEqual(len(self.model.summaries), 1)
        self.assertEqual(turn["context"]["semantic"]["status"], "cooldown")
        self.assertEqual(turn["requests"], before)

    def test_switch_off_does_not_make_extra_model_request(self):
        context.set_semantic_summary(False)
        done, _ = self.post("请继续解释资料核对的注意点？", expert_ids=["pm-daily"])
        self.assertTrue(done["ok"])
        self.assertEqual(done["intent"], "chat")
        self.assertFalse(done["wrote"])
        self.assertFalse(done["deliverables"])
        self.assertEqual(len(self.model.summaries), 0)
        self.assertEqual(len(self.model.answers), 1)

    def test_current_long_goal_invalidates_summary_before_any_extra_model_call(self):
        projects.append_turn(self.root, self.sid, "user", "任务目标：整理东桥施工资料。")
        context.set_runtime_policy({"limit": 48000, "reserve": 1500})
        message = "请解释这些要求。\n任务目标：" + "西桥" * 2250
        done, _ = self.post(message, expert_ids=["pm-daily"])
        self.assertTrue(done["ok"])
        self.assertEqual(done["context"]["semantic"]["status"], "current_override")
        self.assertEqual(len(self.model.summaries), 0)
        self.assertEqual(len(self.model.answers), 1)
        self.assertIn(message, [item["content"] for item in self.model.answers[0]["messages"]])


if __name__ == "__main__":
    unittest.main()
