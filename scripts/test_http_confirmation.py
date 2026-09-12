#!/usr/bin/env python3
"""Human-confirmation types at the real workbench and gateway HTTP boundaries."""

from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from fastapi.testclient import TestClient
from pydantic import ValidationError
from scripts import test_workbench_flow as flow

INVALID = ("true", "yes", "false", 1, 0, None, [], {})


class WorkbenchConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = flow.WorkbenchFlowTests()
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)
        self.client = self.flow.client

    def test_chat_rejects_nonboolean_values_before_any_high_risk_execution(self) -> None:
        with patch.object(flow.agent_loop, "run_agent") as runner:
            for value in INVALID:
                with self.subTest(value=value):
                    response = self.client.post("/api/chat", json={
                        "message": "写一份消防专篇", "expert_ids": ["fire-protect"],
                        "session_id": self.flow.sid, "confirm_ok": value,
                    })
                    self.assertEqual(422, response.status_code, response.text)
            runner.assert_not_called()
        self.assertFalse(flow.chat_service._ACTIVE)
        self.assertFalse(list(self.flow.root.rglob("*.md")))

    def test_chat_false_waits_and_true_writes_an_actual_high_risk_draft(self) -> None:
        waiting, _ = self.flow.post("写一份消防专篇，缺失内容待填", expert_ids=["fire-protect"], confirm_ok=False)
        self.assertTrue(waiting["hitl_pending"], waiting)
        self.assertFalse(waiting["wrote"])
        completed, _ = self.flow.post("写一份消防专篇，缺失内容待填", expert_ids=["fire-protect"], confirm_ok=True)
        self.assertFalse(completed["hitl_pending"], completed)
        self.assertTrue(completed["ok"], completed)
        self.assertTrue(completed["wrote"], completed)
        self.assertTrue(any(item["name"].endswith(".md") and Path(item["path"]).is_file()
                            for item in completed["deliverables"]))

    def test_thread_entry_rejects_the_same_coercions_and_forwards_real_booleans(self) -> None:
        from packing_assistant.runtime import threads

        with patch.object(threads, "run_on_thread", return_value={"ok": True}) as runner:
            for value in INVALID:
                with self.subTest(value=value):
                    response = self.client.post("/api/threads", json={
                        "thread_id": "existing-probe", "text": "写一份消防专篇",
                        "skill": "fire-protect", "confirm_ok": value,
                    })
                    self.assertEqual(422, response.status_code, response.text)
            runner.assert_not_called()
            for value in (False, True):
                response = self.client.post("/api/threads", json={
                    "thread_id": "existing-probe", "text": "写一份消防专篇",
                    "skill": "fire-protect", "confirm_ok": value,
                })
                self.assertEqual(200, response.status_code, response.text)
                self.assertIs(value, runner.call_args.kwargs["confirm"])


class GatewayConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        from gateway import app as gateway

        self.gateway = gateway
        # Do not run storage maintenance or packing engines for type-boundary tests.
        self.client = TestClient(gateway.app)
        self.addCleanup(self.client.close)

    def test_json_routes_reject_nonboolean_confirmation_without_running_tools(self) -> None:
        routes = (
            ("/api/turn", "packing_assistant.product_turn.run_turn", ("p0_confirmed", "confirm_ok")),
            ("/api/agent", "packing_assistant.runtime.agent_loop.run_agent", ("p0_confirmed", "confirm_ok")),
            ("/api/tender/parse", "gateway.app._tender_parse_via_engine", ("p0_confirmed",)),
            ("/api/tender/delivery", "packing_assistant.tender_delivery.run_tender_delivery_pipeline", ("p0_confirmed",)),
        )
        for route, target, fields in routes:
            with self.subTest(route=route), patch(target, return_value={"ok": True}) as runner:
                for field in fields:
                    for value in INVALID:
                        response = self.client.post(route, json={"text": "写一份消防专篇", field: value})
                        self.assertEqual(422, response.status_code, (route, field, value, response.text))
                runner.assert_not_called()
                for field in fields:
                    for value in (False, True):
                        response = self.client.post(route, json={"text": "写一份消防专篇", field: value})
                        self.assertEqual(200, response.status_code, response.text)
                        self.assertIs(value, runner.call_args.kwargs["p0_confirmed"])

    def test_multipart_accepts_only_canonical_text_booleans(self) -> None:
        for route, field in (("/api/tender/parse/file", "file"), ("/api/tender/parse/files", "files")):
            with self.subTest(route=route), ExitStack() as stack:
                ingest = stack.enter_context(patch.object(self.gateway, "_tender_ingest_from_uploads", return_value={"text": "招标节选材料"}))
                runner = stack.enter_context(patch.object(self.gateway, "_tender_parse_via_engine", return_value={"ok": True}))
                for value in ("yes", "1", "0", "True", "False", " true "):
                    response = self.client.post(route, data={"p0_confirmed": value}, files={field: ("input.txt", b"fixture excerpt")})
                    self.assertEqual(422, response.status_code, (value, response.text))
                runner.assert_not_called()
                ingest.assert_not_called()
                for value in ("false", "true"):
                    response = self.client.post(route, data={"p0_confirmed": value}, files={field: ("input.txt", b"fixture excerpt")})
                    self.assertEqual(200, response.status_code, response.text)
                    self.assertIs(value == "true", runner.call_args.kwargs["p0_confirmed"])

    def test_packing_confirmation_models_do_not_coerce_flags_or_checklist_items(self) -> None:
        for model in (self.gateway.DemoRequest, self.gateway.PipelineRequest,
                      self.gateway.ProfilePipelineRequest, self.gateway.TraceRequest):
            for value in INVALID:
                with self.subTest(model=model.__name__, value=value), self.assertRaises(ValidationError):
                    model(enable_auto_confirm=value)
            for value in (False, True):
                self.assertIs(value, model(enable_auto_confirm=value).enable_auto_confirm)
        for value in INVALID:
            with self.assertRaises(ValidationError):
                self.gateway.ConfirmRequest(action="confirm", checklist_checked={"fixture": value})
            with self.assertRaises(ValidationError):
                self.gateway.ConfirmRequest(action="confirm", enforce_ns_checklist=value)
        confirmed = self.gateway.ConfirmRequest(action="confirm", checklist_checked={"fixture": True}, enforce_ns_checklist=True)
        self.assertIs(True, confirmed.checklist_checked["fixture"])
        self.assertIs(True, confirmed.enforce_ns_checklist)


if __name__ == "__main__":
    unittest.main(verbosity=2)
