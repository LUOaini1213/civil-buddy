"""Offline logistics tools and main-chat binding; never calls a live model."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.logistics.intake import parse_document
from packing_assistant.logistics.ledger import audit_document, summarize
from packing_assistant.runtime import model_loop
from packing_assistant.runtime.turn import run_turn

DATA = ("package_id,material_id,name,package_count,quantity,units_per_package,unit,"
        "package length mm,package width mm,package height mm,net weight per package kg,gross weight per package kg\n"
        "BOX-A,MAT-A,Synthetic panel,2,10,5,PCS,1200,800,100,100,110\n").encode()


def context(document):
    return {"project": {"id": "a" * 32, "name": "Synthetic", "revision": 1, "can_undo": False, "confirmed": False},
            "document": document, "audit": audit_document(document), "summary": summarize(document)}


class Script:
    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def __call__(self, messages, tools=None, **kwargs):
        self.seen.append(deepcopy(tools))
        step = self.steps.pop(0) if self.steps else "已生成装箱方案，共 999 柜。"
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": "offline-call", "name": step[0], "arguments": step[1]}]}


class LogisticsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document(DATA, "synthetic.csv", ocr_backend="none")
        self.context = context(self.document)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"CIVIL_SANDBOX_BACKEND": "app", "CIVIL_SANDBOX": "workspace-write"}))
        self.stack.enter_context(patch("packing_assistant.runtime.project_instructions.seed_session"))
        self.stack.enter_context(patch("packing_assistant.runtime.memory.assemble_context", return_value={}))

    def model(self, message, *steps, **kwargs):
        return model_loop.run_model_agent(message, logistics_context=self.context, complete=Script(*steps), **kwargs)

    def test_result_overrides_model_invented_success(self):
        result = self.model("检查箱单", ("logistics_audit", {}))
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["wrote"])
        self.assertNotIn("999", result["reply"])
        self.assertIsNone(result["logistics_proposal"])
        empty = self.model("检查箱单", "已修改所有数据")
        self.assertFalse(empty["ok"])
        self.assertEqual(empty["error_code"], "logistics_not_run")

    def test_proposal_uses_only_user_values_and_preserves_context(self):
        before = deepcopy(self.context)
        ident = self.document["rows"][0]["id"]
        result = self.model(f"把 {ident} 毛重改为 120 kg", ("logistics_propose", {}))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["logistics_proposal"]["changes"][0]["after"], 120)
        self.assertEqual(self.context, before)
        self.assertFalse(result["wrote"])

    def test_unauthorized_tools_and_model_parameters_rejected(self):
        for name, args in (("pack_plan", {"file": "secret.xlsx"}),
                           ("logistics_propose", {"quantity": 999}), ("logistics_audit", ["not-an-object"]),
                           ("logistics_undo", {})):
            with self.subTest(name=name, args=args):
                result = self.model("检查箱单", (name, args))
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["wrote"])
                self.assertIsNone(result["logistics_proposal"])

    def test_steps_cancel_exclusivity_and_confined_worker_forwarding(self):
        event = Event()
        event.set()
        result = run_turn("检查箱单", logistics_context=self.context, mode="steps", cancel_event=event)
        self.assertTrue(result["cancelled"])
        self.assertIsNone(result["logistics_proposal"])
        mixed = run_turn("检查", logistics_context=self.context, planning_context={"id": "other"}, mode="steps")
        self.assertEqual(mixed["error_code"], "ambiguous_context")
        from packing_assistant.runtime.os_sandbox.worker import _model_tool
        class Worker:
            def call(self, method, **kwargs):
                self.args = kwargs
                return {"out": _model_tool(kwargs)}
        worker = Worker()
        turn = model_loop._Turn(session_id="offline", run_id="offline", user_text="检查箱单",
                                confirmed=False, approve=None, logistics_context=self.context)
        result = model_loop._dispatch(turn, "logistics_audit", {}, worker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(worker.args["logistics_context"], self.context)
        self.assertEqual(turn.logistics_results, [result])


class LogisticsHostTests(unittest.TestCase):
    def setUp(self):
        import app, logistics_api, uploads, store
        from fastapi.testclient import TestClient
        from packing_assistant import expert_turn, llm
        from packing_assistant.runtime import agent_loop, memory, os_sandbox, session_handoff, session_packing
        from packing_assistant.logistics.records import LogisticsStore
        self.app, self.api = app, logistics_api
        (ROOT / "output").mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="test-logistics-chat-", dir=ROOT / "output")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"CIVIL_JOB_ROOT": "", "CIVIL_TOKEN": "", "CIVIL_AGENT_MODE": "steps",
                                                       "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request"}))
        for module, key, value in ((app, "OUT_ROOT", root / "chat"), (agent_loop, "_OUT", root / "chat"),
            (memory, "_OUT", root / "chat"), (expert_turn, "_OUT", root / "chat"),
            (session_handoff, "_DIR", root / "chat"), (session_packing, "_DIR", root / "chat"),
            (uploads, "UPLOAD_ROOT", root / "uploads"), (store, "DATA", root / "catalog.json"),
            (llm, "_RUNTIME_LLM", {"api_key": "", "base_url": "http://127.0.0.1:1", "model": "offline"})):
            self.stack.enter_context(patch.object(module, key, value))
        self.stack.enter_context(patch.object(os_sandbox, "resolve_backend", return_value=("app", "")))
        self.stack.enter_context(patch("packing_assistant.runtime.model_client.complete", side_effect=AssertionError("No live model")))
        self.store = LogisticsStore(root)
        self.stack.enter_context(patch.object(logistics_api, "store", return_value=self.store))
        self.project = self.store.create("Synthetic", parse_document(DATA, "synthetic.csv", ocr_backend="none"), DATA)
        self.client = self.stack.enter_context(TestClient(app.app))

    def remote_client(self):
        from fastapi.testclient import TestClient
        return self.stack.enter_context(TestClient(self.app.app, base_url="http://remote.invalid", client=("192.0.2.1", 12345)))

    def post(self, message):
        response = self.client.post("/api/chat", json={"message": message, "session_id": "logistics-chat-offline",
                                    "logistics_project_id": self.project["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        kind, done = "", []
        for line in response.text.splitlines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: ") and kind == "done":
                done.append(json.loads(line[6:]))
        self.assertEqual(len(done), 1, response.text)
        self.assertFalse(done[0]["wrote"])
        self.assertEqual(done[0]["deliverables"], [])
        return done[0]

    def test_inspect_and_propose_persist_binding_not_ledger_changes(self):
        result = self.post("检查箱单")
        self.assertTrue(result["ok"], result)
        ident = self.project["document"]["rows"][0]["id"]
        result = self.post(f"把 {ident} 毛重改为 120 kg")
        self.assertTrue(result["ok"], result)
        link = re.search(r"/logistics\?project_id=([0-9a-f]{32})&proposal_id=([0-9a-f]{32})", result["text"])
        self.assertIsNotNone(link, result)
        self.assertEqual(self.client.get("/api/logistics/proposals/" + link[2]).status_code, 200)
        self.assertEqual(self.store.open(self.project["id"]), self.project)
        detail = self.client.get("/api/sessions/logistics-chat-offline").json()
        self.assertEqual(detail["logistics_project_id"], self.project["id"])

    def test_conflicting_binding_and_late_cancel_never_publish_proposal(self):
        response = self.client.post("/api/chat", json={"message": "检查", "logistics_project_id": self.project["id"],
                                                    "planning_project_id": "b" * 32})
        self.assertEqual(response.status_code, 400)
        import turn_control
        original = self.api.register_proposal
        def cancelling(*args, **kwargs):
            result = original(*args, **kwargs)
            turn_control.cancel("logistics-chat-offline")
            return result
        with patch.object(self.api, "register_proposal", side_effect=cancelling):
            ident = self.project["document"]["rows"][0]["id"]
            result = self.post(f"把 {ident} 毛重改为 120 kg")
        self.assertTrue(result["cancelled"])
        self.assertNotIn("proposal_id=", result["text"])
        self.assertEqual(self.store.open(self.project["id"]), self.project)

    def test_foreground_and_background_reject_remote_project_access_before_read(self):
        import chat_service
        client = self.remote_client()
        for background in (False, True):
            with patch.object(chat_service, "prepare_turn", side_effect=AssertionError("remote request reached preparation")):
                response = client.post("/api/chat", json={"message": "汇总箱单", "session_id": "remote-logistics-probe",
                    "logistics_project_id": self.project["id"], "background": background})
            self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.store.open(self.project["id"]), self.project)

    def test_existing_logistics_session_cannot_omit_or_clear_binding_to_bypass(self):
        self.post("检查箱单")
        client = self.remote_client()
        for background in (False, True):
            for extra in ({}, {"logistics_project_id": ""}):
                response = client.post("/api/chat", json={"message": "汇总", "session_id": "logistics-chat-offline", "background": background, **extra})
                self.assertEqual(response.status_code, 403, response.text)
        # Explicitly clearing the latest binding must not expose older source-derived history.
        response = self.client.post("/api/chat", json={"message": "你好", "session_id": "logistics-chat-offline", "logistics_project_id": ""})
        self.assertEqual(response.status_code, 200, response.text)
        import chat_service
        with chat_service._LOCK:
            chat_service._LOGISTICS_SESSIONS.clear()  # simulate a restart; inspect saved history
        self.assertEqual(client.post("/api/chat", json={"message": "继续", "session_id": "logistics-chat-offline"}).status_code, 403)

    def test_logistics_session_restore_and_event_replay_are_local_only(self):
        self.post("检查箱单")
        client = self.remote_client()
        for suffix in ("", "/events", "/live"):
            response = client.get("/api/sessions/logistics-chat-offline" + suffix)
            self.assertEqual(response.status_code, 403, response.text)
            self.assertNotIn(str(self.store.root), response.text)
        self.assertEqual(self.client.get("/api/sessions/logistics-chat-offline").status_code, 200)

    def test_remote_session_list_omits_logistics_prompt_titles_and_search_counts(self):
        self.post("物流专属原始材料毛重明细，检查箱单")
        ordinary = self.client.post("/api/chat", json={"message": "普通公开会话", "session_id": "ordinary-list-visible"})
        self.assertEqual(ordinary.status_code, 200, ordinary.text)
        local = self.client.get("/api/sessions").json()
        self.assertIn("logistics-chat-offline", [row["session_id"] for row in local["sessions"]])
        remote = self.remote_client()
        response = remote.get("/api/sessions")
        self.assertEqual(response.status_code, 200, response.text)
        listing = response.json()
        self.assertEqual([row["session_id"] for row in listing["sessions"]], ["ordinary-list-visible"])
        self.assertEqual(listing["total"], 1)
        self.assertNotIn("物流专属", response.text)
        hidden_search = remote.get("/api/sessions", params={"q": "物流专属"}).json()
        self.assertEqual(hidden_search["total"], 0)
        self.assertEqual(hidden_search["sessions"], [])
        visible_search = remote.get("/api/sessions", params={"q": "普通公开", "limit": 1}).json()
        self.assertEqual(visible_search["total"], 1)
        self.assertEqual(visible_search["sessions"][0]["session_id"], "ordinary-list-visible")

    def test_same_origin_gate_covers_bound_chat_and_local_unbound_chat_stays_available(self):
        response = self.client.post("/api/chat", headers={"Origin": "https://evil.invalid"}, json={"message": "检查", "logistics_project_id": self.project["id"]})
        self.assertEqual(response.status_code, 403, response.text)
        remote = self.remote_client()
        response = remote.post("/api/chat", json={"message": "你好", "session_id": "ordinary-remote-chat"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_background_first_turn_protected_before_record_exists(self):
        import chat_service
        body = {"message": "检查", "session_id": "unrecorded-logistics", "logistics_project_id": self.project["id"]}
        prepared = chat_service.prepare_turn(self.app.OUT_ROOT, body)
        self.assertIsNotNone(prepared["logistics_context"])
        self.assertEqual(chat_service.read_runs(self.app.OUT_ROOT, body["session_id"]), [])
        remote = self.remote_client()
        self.assertEqual(remote.post("/api/chat", json={"message": "继续", "session_id": body["session_id"]}).status_code, 403)
        self.assertEqual(remote.get("/api/sessions/" + body["session_id"] + "/events").status_code, 403)
        self.assertEqual(remote.get("/api/sessions/" + body["session_id"] + "/live").status_code, 403)

    def test_oversized_metadata_fails_closed_without_path_disclosure(self):
        folder = self.app.OUT_ROOT / "damaged-logistics" / "runs" / "test"
        folder.mkdir(parents=True)
        (folder / "workbench.json").write_bytes(b" " * (128 * 1024 + 1))
        response = self.remote_client().post("/api/chat", json={"message": "继续", "session_id": "damaged-logistics"})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertNotIn(str(folder), response.text)


if __name__ == "__main__":
    unittest.main()
