"""Offline main-chat binding, proposal registration and cancellation boundaries."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from fastapi import HTTPException
from fastapi.testclient import TestClient
import app
import chat_service
import planning_api
import planning_chat_api
import store
import turn_control
import uploads
from packing_assistant import expert_turn, llm
from packing_assistant.engineering.planning import calculate
from packing_assistant.engineering.planning_agent import propose_command
from packing_assistant.engineering.planning_records import PlanningStore
from packing_assistant.runtime import agent_loop, memory, model_client, os_sandbox, session_handoff, session_packing, turn


def events(response):
    kind = ""
    found = []
    for line in response.text.splitlines():
        if line.startswith("event: "):
            kind = line[7:]
        elif line.startswith("data: "):
            found.append({"event": kind, "data": json.loads(line[6:])})
    return found


class PlanningChatHostTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "output").mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="test-planning-chat-host-", dir=ROOT / "output")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.out = self.root / "chat"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "PYTHON_DOTENV_DISABLED": "1", "CIVIL_JOB_ROOT": "", "CIVIL_TOKEN": "",
            "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request", "CIVIL_AGENT_MODE": "steps",
        }))
        for module, key, value in (
            (app, "OUT_ROOT", self.out), (agent_loop, "_OUT", self.out), (memory, "_OUT", self.out),
            (expert_turn, "_OUT", self.out), (session_handoff, "_DIR", self.out), (session_packing, "_DIR", self.out),
            (uploads, "UPLOAD_ROOT", self.root / "uploads"), (store, "DATA", self.root / "catalog.json"),
            (llm, "_RUNTIME_LLM", {"api_key": "", "base_url": "http://127.0.0.1:1", "model": "offline-test"}),
        ):
            self.stack.enter_context(patch.object(module, key, value))
        self.stack.enter_context(patch.object(os_sandbox, "resolve_backend", return_value=("app", "")))
        self.no_model = self.stack.enter_context(patch.object(model_client, "complete", side_effect=AssertionError("No live model allowed")))
        self.plans = PlanningStore(self.root)
        self.stack.enter_context(patch.object(planning_api, "store", return_value=self.plans))
        self.project = self.plans.save(name="Synthetic host test", **calculate(planning_api.example()), synthetic=True)
        self.sid = "plan-chat-" + uuid4().hex[:12]
        self.client = self.stack.enter_context(TestClient(app.app))

    def post(self, message, **extra):
        payload = {"message": message, "session_id": self.sid, "planning_project_id": self.project["id"], **extra}
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        rows = events(response)
        self.assertFalse([row for row in rows if row["event"] == "error"], rows)
        done = [row["data"] for row in rows if row["event"] == "done"]
        self.assertEqual(len(done), 1, rows)
        self.assertFalse(done[0]["wrote"])
        self.assertEqual(done[0]["deliverables"], [])
        return done[0]

    def proposal_result(self):
        return {"ok": True, "reply": "已形成待确认建议，当前计划未修改。", "files": [], "artifacts": [],
                "planning_proposal": propose_command(self.project["plan"], "任务 B 工期改为 5 工作日", "cpm")}

    def test_binding_validation_and_exclusivity_precede_project_lookup(self):
        with patch.object(planning_api, "store") as lookup:
            for ident in ("../escape", "a" * 31, "A" * 32, "a" * 32 + "\n"):
                with self.subTest(ident=ident):
                    response = self.client.post("/api/chat", json={"message": "检查计划", "planning_project_id": ident})
                    self.assertEqual(response.status_code, 422)
            response = self.client.post("/api/chat", json={"message": "检查计划", "planning_project_id": self.project["id"], "cad_project_id": "b" * 32})
            self.assertEqual(response.status_code, 400)
            self.assertIn("只能绑定", response.text)
            lookup.assert_not_called()
        with self.assertRaises(ValueError):
            chat_service.prepare_turn(self.out, {"message": "检查计划", "planning_project_id": ["bad"]})

    def test_missing_project_fails_before_creating_session(self):
        response = self.client.post("/api/chat", json={"message": "检查计划", "session_id": self.sid, "planning_project_id": "0" * 32})
        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.out / self.sid).exists())

    def test_prepare_passes_only_current_public_context_and_preserves_method(self):
        selected = deepcopy(self.project)
        selected.update(method="resource", can_undo=True, history=[{"private": "never pass"}], source_files={"secret": "never pass"})
        with patch.object(self.plans, "open", return_value=selected):
            prepared = chat_service.prepare_turn(self.out, {"message": "检查计划", "planning_project_id": self.project["id"]})
        context = prepared["planning_context"]
        self.assertEqual(set(context), {"project", "plan", "result", "method"})
        self.assertEqual(context["project"], {"id": self.project["id"], "name": self.project["name"], "revision": 1, "can_undo": True})
        self.assertEqual(context["method"], "resource")
        self.assertEqual(context["result"], self.project["result"])
        self.assertEqual(prepared["intent"], "chat")
        self.assertIsNone(prepared["cad_context"])

    def test_steps_inspection_uses_runtime_and_restores_binding_without_writing_plan(self):
        with patch.object(turn, "run_turn", wraps=turn.run_turn) as runtime:
            done = self.post("检查当前计划")
        self.assertTrue(done["ok"], done)
        self.assertIn("8 工作日", done["text"])
        self.assertEqual(runtime.call_args.kwargs["planning_context"]["project"]["id"], self.project["id"])
        self.assertEqual(self.plans.open(self.project["id"]), self.project)
        detail = self.client.get("/api/sessions/" + self.sid).json()
        self.assertEqual(detail["planning_project_id"], self.project["id"])
        self.assertEqual(detail["cad_project_id"], "")
        self.assertEqual(detail["transcript"][-1]["text"], done["text"])
        self.no_model.assert_not_called()

    def test_steps_proposal_registers_link_with_real_router_without_saving(self):
        done = self.post("任务 B 工期改为 5 工作日")
        self.assertTrue(done["ok"], done)
        self.assertIn("4 → 5", done["text"])
        match = re.search(r"/engineering/planning\?project_id=([0-9a-f]{32})&proposal_id=([0-9a-f]{32})", done["text"])
        self.assertIsNotNone(match, done)
        self.assertEqual(match[1], self.project["id"])
        response = self.client.get("/api/engineering/planning/proposals/" + match[2])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["changes"][0]["before"], 4)
        self.assertEqual(response.json()["changes"][0]["after"], 5)
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_undo_is_only_a_review_link_and_keeps_current_revision(self):
        modified = deepcopy(self.project["plan"])
        modified["tasks"][1]["duration"] = 5
        self.project = self.plans.save(name=self.project["name"], project_id=self.project["id"], expected_revision=1, **calculate(modified))
        done = self.post("撤销上次保存")
        self.assertTrue(done["ok"], done)
        self.assertIn("proposal_id=", done["text"])
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_cancel_before_registration_never_publishes_proposal(self):
        def cancelled(*args, **kwargs):
            kwargs["cancel_event"].set()
            return self.proposal_result()
        with patch.object(turn, "run_turn", side_effect=cancelled), patch.object(planning_chat_api, "register_proposal") as register:
            done = self.post("任务 B 工期改为 5 工作日")
        self.assertTrue(done["cancelled"])
        self.assertNotIn("proposal_id=", done["text"])
        register.assert_not_called()
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_cancel_during_registration_never_returns_the_link(self):
        def cancelled_registration(*args, **kwargs):
            turn_control.cancel(self.sid)
            return "f" * 32
        with patch.object(turn, "run_turn", return_value=self.proposal_result()), patch.object(planning_chat_api, "register_proposal", side_effect=cancelled_registration):
            done = self.post("任务 B 工期改为 5 工作日")
        self.assertTrue(done["cancelled"])
        self.assertNotIn("proposal_id=", done["text"])
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_cancel_after_run_record_does_not_publish_link_in_reply_or_restored_history(self):
        original = chat_service._record
        def cancel_after_record(root, prepared, result, files, nodes):
            original(root, prepared, result, files, nodes)
            if result.get("ok") and prepared.get("planning_project_id"):
                turn_control.cancel(self.sid)
        with patch.object(chat_service, "_record", side_effect=cancel_after_record), \
             patch.object(planning_chat_api, "register_proposal", wraps=planning_chat_api.register_proposal) as register:
            done = self.post("任务 B 工期改为 5 工作日")
        register.assert_called_once()
        self.assertTrue(done["cancelled"])
        self.assertFalse(done["ok"])
        self.assertIn("本轮建议未发布", done["text"])
        self.assertNotIn("proposal_id=", done["text"])
        detail = self.client.get("/api/sessions/" + self.sid).json()
        self.assertEqual(detail["transcript"][-1]["text"], done["text"])
        self.assertNotIn("proposal_id=", json.dumps(detail, ensure_ascii=False))
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_cancel_after_success_seal_does_not_revoke_completed_reply(self):
        original = chat_service.projects.append_turn
        attempted = []
        def cancel_after_seal(root, sid, role, text):
            if role == "assistant" and "proposal_id=" in text:
                attempted.append(turn_control.cancel(sid))
            return original(root, sid, role, text)
        with patch.object(chat_service.projects, "append_turn", side_effect=cancel_after_seal):
            done = self.post("任务 B 工期改为 5 工作日")
        self.assertEqual(len(attempted), 1)
        self.assertFalse(attempted[0]["cancel_requested"])
        self.assertTrue(done["ok"])
        self.assertFalse(done["cancelled"])
        self.assertIn("proposal_id=", done["text"])
        self.assertEqual(self.client.get("/api/sessions/" + self.sid).json()["transcript"][-1]["text"], done["text"])
        self.assertEqual(self.plans.open(self.project["id"]), self.project)

    def test_stale_registration_returns_readable_failure_without_link(self):
        with patch.object(turn, "run_turn", return_value=self.proposal_result()), patch.object(planning_chat_api, "register_proposal", side_effect=HTTPException(409, "保存版本已变化")):
            done = self.post("任务 B 工期改为 5 工作日")
        self.assertFalse(done["ok"])
        self.assertIn("保存版本已变化", done["text"])
        self.assertNotIn("proposal_id=", done["text"])

    def test_malformed_proposal_id_cannot_make_untrusted_link(self):
        with patch.object(turn, "run_turn", return_value=self.proposal_result()), patch.object(planning_chat_api, "register_proposal", return_value="evil)&x=https://example.invalid"):
            done = self.post("任务 B 工期改为 5 工作日")
        self.assertFalse(done["ok"])
        self.assertIn("建议编号无效", done["text"])
        self.assertNotIn("example.invalid", done["text"])

    def test_unbinding_is_persisted_on_next_turn(self):
        self.post("检查计划")
        self.post("你好", planning_project_id="")
        detail = self.client.get("/api/sessions/" + self.sid).json()
        self.assertEqual(detail["planning_project_id"], "")
        self.assertEqual(detail["cad_project_id"], "")


if __name__ == "__main__":
    unittest.main()
