"""Offline host checks for review/apply, stale suggestions and cancellation."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import planning_chat_api as chat
from packing_assistant.engineering.planning_records import PlanningStore


class PlanningChatHost(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for manager in [patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_SANDBOX": "workspace-write"}),
                        patch.object(chat.api, "store", lambda: PlanningStore(self.root)),
                        patch.object(chat, "PROPOSALS", chat.cad.MemoryStore()),
                        patch.object(chat.api, "RUNS", chat.cad.MemoryStore())]:
            manager.start()
            self.addCleanup(manager.stop)
        app = FastAPI()
        app.include_router(chat.router)
        app.include_router(chat.api.router)
        app.include_router(chat.api.eng.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.context = {"plan": chat.api.example(), "method": "cpm"}

    def post(self, path, data, **kwargs):
        return self.client.post(chat.api.BASE + path, json=data, **kwargs)

    def propose(self, text="把 B 的工期改为 5 工作日"):
        response = self.post("/conversation", {**self.context, "message": text})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["ok"], response.text)
        return response.json()

    def apply(self, suggestion, **overrides):
        return self.post("/proposals/" + suggestion["proposal_id"] + "/apply",
                         {**self.context, "confirmed": True, **overrides})

    def save(self):
        response = self.post("/projects", {"name": "合成测试", "plan": self.context["plan"]})
        self.assertEqual(response.status_code, 200, response.text)
        project = response.json()["project"]
        self.context.update(project_id=project["id"], expected_revision=project["revision"])
        return project

    def test_propose_preview_no_write_apply_compute_and_explicit_save(self):
        original = deepcopy(self.context)
        proposal = self.propose()
        self.assertEqual(self.context, original)
        self.assertFalse((self.root / ".civil-buddy/out/engineering/plans").exists())
        self.assertEqual(self.apply(proposal, confirmed=False).status_code, 403)
        applied = self.apply(proposal)
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()["plan"]["tasks"][1]["duration"], 5)
        self.assertEqual(applied.json()["result"]["duration_workdays"], 9)
        self.assertFalse(applied.json()["saved"])
        self.assertFalse((self.root / ".civil-buddy/out/engineering/plans").exists())

    def test_stale_plan_method_revision_and_project_are_rejected(self):
        project = self.save()
        proposal = self.propose()
        modified = deepcopy(self.context["plan"])
        modified["tasks"][0]["duration"] = 3
        self.assertEqual(self.apply(proposal, plan=modified).status_code, 409)
        self.assertEqual(self.apply(proposal, method="resource").status_code, 409)
        self.assertEqual(self.apply(proposal, project_id=None, expected_revision=None).status_code, 409)
        baseline = self.post(f'/projects/{project["id"]}/baseline', {"expected_revision": 1})
        self.assertEqual(baseline.status_code, 200, baseline.text)
        self.assertEqual(self.apply(proposal).status_code, 409)
        self.assertEqual(chat.api.store().open(project["id"])["plan"], project["plan"])

    def test_unknown_ids_and_arbitrary_model_values_cannot_apply(self):
        response = self.post("/conversation", {**self.context, "message": "把 UNKNOWN 的工期改为 8 工作日"})
        self.assertFalse(response.json()["ok"])
        self.assertNotIn("proposal_id", response.json())
        proposal = self.propose()
        self.assertEqual(self.apply(proposal, code="print(1)").status_code, 422)
        with self.assertRaises(ValueError):
            from packing_assistant.engineering.planning_agent import propose_command
            forged = propose_command(self.context["plan"], "把 B 的工期改为 5 工作日")
            forged["plan"]["tasks"][1]["duration"] = 99
            chat.register_proposal(self.context, forged)

    def test_undo_requires_confirmation_and_preserves_stored_method(self):
        original = self.save()
        changed = deepcopy(self.context["plan"])
        changed["tasks"][1]["duration"] = 7
        response = self.post("/projects", {"id": original["id"], "expected_revision": 1,
                            "name": original["name"], "plan": changed})
        self.assertEqual(response.status_code, 200)
        self.context.update(plan=changed, expected_revision=2)
        proposal = self.propose("撤销上次保存")
        self.assertEqual(chat.api.store().open(original["id"])["revision"], 2)
        result = self.apply(proposal)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["project"]["revision"], 3)
        self.assertEqual(result.json()["project"]["plan"], original["plan"])
        self.assertEqual(self.apply(proposal).status_code, 409)

    def test_cancelled_request_never_publishes_proposal_or_result(self):
        ident = "f" * 32
        self.client.post(f"/api/engineering/operations/{ident}/cancel")
        response = self.post("/conversation", {**self.context, "message": "把 B 的工期改为 5 工作日"},
                             headers={"X-CAD-Operation-ID": ident})
        self.assertEqual(response.status_code, 499)
        self.assertEqual(len(chat.PROPOSALS._items), 0)
        self.assertEqual(len(chat.api.RUNS._items), 0)

    def test_expired_proposal_requires_new_review(self):
        proposal = self.propose()
        chat.PROPOSALS._items.clear()
        self.assertEqual(self.apply(proposal).status_code, 410)


if __name__ == "__main__":
    unittest.main()
