#!/usr/bin/env python3
"""Workbench POST /api/chat / stream_turn uses the CLI model loop (tools + exclusive writes).

No live API key: ``complete`` is always a script, same contract as test_model_loop.py.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "CIVIL_AGENT_MODE", "CIVIL_APPROVAL"):
    os.environ.pop(name, None)

from packing_assistant.runtime import model_client  # noqa: E402
from packing_assistant.runtime.civil_config import CONFIRM  # noqa: E402
from packing_assistant.runtime.model_loop import TOOLS  # noqa: E402


class Script:
    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def __call__(self, messages, tools=None, **_kwargs):
        self.seen.append({"messages": copy.deepcopy(messages), "tools": tools})
        step = self.steps.pop(0) if self.steps else "（脚本已用完）"
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": f"call_{len(self.seen)}_{i}", "name": name, "arguments": arguments}
                                              for i, (name, arguments) in enumerate(step)]}


def _done(events):
    rows = [e for e in events if e.get("event") == "done"]
    assert rows, events
    return rows[-1]["data"]


def _plain_must_not_run(_messages):
    raise AssertionError("stream_plain must not run when agent_mode is model")


class WorkbenchModelTurnTests(unittest.TestCase):
    def setUp(self):
        self.base = (ROOT / "output" / "workbench-model-turn" / os.urandom(4).hex()).resolve()
        self.root = self.base / "out"
        self.uploads = self.base / "uploads"
        self.root.mkdir(parents=True)
        self.uploads.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.base, True)
        from packing_assistant.llm import set_runtime_llm

        set_runtime_llm(None)
        self.addCleanup(set_runtime_llm, None)
        for name in ("CIVIL_SANDBOX", "CIVIL_APPROVAL", "CIVIL_AGENT_MODE", "CIVIL_API_KEY", "CIVIL_API_BASE", "CIVIL_MODEL"):
            self.addCleanup(
                lambda key=name, old=os.environ.get(name): os.environ.__setitem__(key, old) if old is not None
                else os.environ.pop(key, None)
            )
            os.environ.pop(name, None)

    def _patch_out(self):
        import app
        from packing_assistant import expert_turn
        from packing_assistant.runtime import agent_loop

        return (
            patch.object(app, "OUT_ROOT", self.root),
            patch.object(agent_loop, "_OUT", self.root),
            patch.object(expert_turn, "_OUT", self.root),
        )

    def _stream(self, body, *, script=None, mode="model", key=True, approval=""):
        import app
        import chat_service
        import uploads
        from packing_assistant.llm import set_runtime_llm

        if mode:
            os.environ["CIVIL_AGENT_MODE"] = mode
        else:
            os.environ.pop("CIVIL_AGENT_MODE", None)
        if approval:
            os.environ["CIVIL_APPROVAL"] = approval
        else:
            os.environ.pop("CIVIL_APPROVAL", None)
        if mode == "model":
            os.environ["CIVIL_API_KEY"] = "sk-test-not-live"
            set_runtime_llm(None)
        else:
            os.environ.pop("CIVIL_API_KEY", None)
            set_runtime_llm(None)

        patches = list(self._patch_out())
        patches.append(patch.object(uploads, "UPLOAD_ROOT", self.uploads))
        if script is not None:
            patches.append(patch.object(model_client, "complete", script))
        for item in patches:
            item.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        sid = body.setdefault("session_id", "wb" + os.urandom(4).hex())
        lease = chat_service.SessionLease(sid)
        turn = chat_service.prepare_turn(app.OUT_ROOT, body)
        events = []
        for event in chat_service.stream_turn(
            app.OUT_ROOT,
            turn,
            key_available=key,
            plain_runner=_plain_must_not_run if mode == "model" else app.run_plain,
            lease=lease,
        ):
            if event.get("event") != "heartbeat":
                events.append(event)
        return events, _done(events), sid

    def test_model_run_skill_writes_through_exclusive_pipeline(self):
        script = Script(
            [("run_skill", {"skill_id": "finance-tax"})],
            "税务日历草稿已出。税额待持证人员按当期文件算。submit_blocked。",
        )
        events, done, _sid = self._stream(
            {"message": "出一份税务日历"},
            script=script,
            mode="model",
        )
        self.assertTrue(script.seen, script.seen)
        tools = script.seen[0]["tools"]
        self.assertTrue(tools, "completion must be sent with tools")
        names = {row["function"]["name"] for row in tools}
        self.assertIn("run_skill", names)
        self.assertEqual(tools, TOOLS)
        self.assertTrue(done.get("wrote"), done)
        self.assertTrue(done.get("submit_blocked"))
        self.assertTrue(done.get("deliverables"), done)
        names_out = {Path(str(f.get("name") or "")).name for f in done["deliverables"]}
        self.assertTrue(any("finance-tax__calendar" in n for n in names_out), names_out)
        blob = done.get("text") or ""
        self.assertNotIn("可以投标", blob)
        self.assertNotIn("可以开工", blob)
        for row in done["deliverables"]:
            path = Path(str(row.get("path") or ""))
            if path.suffix == ".md" and path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("可以投标", text)
                self.assertNotIn("可以开工", text)

    def test_http_chat_posts_tools_and_writes(self):
        from fastapi.testclient import TestClient

        import app
        import uploads
        from packing_assistant import expert_turn
        from packing_assistant.runtime import agent_loop
        from packing_assistant.llm import set_runtime_llm

        script = Script(
            [("run_skill", {"skill_id": "finance-tax"})],
            "税务日历草稿已出。",
        )
        os.environ["CIVIL_AGENT_MODE"] = "model"
        os.environ["CIVIL_API_KEY"] = "sk-test-not-live"
        set_runtime_llm(None)
        with patch.object(app, "OUT_ROOT", self.root), \
                patch.object(uploads, "UPLOAD_ROOT", self.uploads), \
                patch.object(agent_loop, "_OUT", self.root), \
                patch.object(expert_turn, "_OUT", self.root), \
                patch.object(model_client, "complete", script):
            client = TestClient(app.app)
            response = client.post(
                "/api/chat",
                json={"session_id": "wbhttp01", "message": "出一份税务日历"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(script.seen)
        self.assertTrue(script.seen[0]["tools"])
        done = None
        event_name = None
        for line in response.text.splitlines():
            if line.startswith("event: "):
                event_name = line[7:].strip()
            elif line.startswith("data: ") and event_name:
                payload = json.loads(line[6:])
                if event_name == "done":
                    done = payload
                event_name = None
        self.assertIsNotNone(done, response.text[:2000])
        self.assertTrue(done.get("wrote"), done)
        self.assertTrue(done.get("deliverables"), done)
        self.assertTrue(done.get("submit_blocked"))

    def test_high_risk_without_confirm_does_not_write(self):
        script = Script(
            [("run_skill", {"skill_id": "construction"})],
            "临边防护是高风险岗，需要确认句后才写盘。",
        )
        _events, done, _sid = self._stream(
            {"message": "写临边防护方案讨论提纲"},
            script=script,
            mode="model",
        )
        self.assertTrue(script.seen[0]["tools"])
        self.assertFalse(done.get("wrote"), done)
        self.assertTrue(done.get("hitl_pending"), done)
        self.assertIn(CONFIRM, done.get("text") or "")
        self.assertFalse(done.get("deliverables") or [])

    def test_never_still_requires_confirm_on_high_risk(self):
        script = Script(
            [("run_skill", {"skill_id": "construction"})],
            "高风险写盘仍须确认句。",
        )
        _events, done, _sid = self._stream(
            {"message": "写临边防护方案讨论提纲"},
            script=script,
            mode="model",
            approval="never",
        )
        self.assertFalse(done.get("wrote"), done)
        self.assertTrue(done.get("hitl_pending"), done)
        self.assertIn(CONFIRM, done.get("text") or "")

    def test_steps_writes_without_calling_the_model(self):
        with patch.object(model_client, "complete", side_effect=AssertionError("steps must not call complete")):
            events, done, _sid = self._stream(
                {"message": "出一份税务日历", "expert_ids": ["finance-tax"]},
                script=None,
                mode="steps",
                key=False,
            )
        self.assertTrue(done.get("wrote"), done)
        self.assertTrue(done.get("submit_blocked"))
        self.assertTrue(done.get("deliverables"), done)
        self.assertNotIn("可以投标", done.get("text") or "")
        self.assertNotIn("可以开工", done.get("text") or "")

    def test_steps_chat_does_not_write(self):
        _events, done, _sid = self._stream(
            {"message": "什么是 GST，先别写"},
            script=None,
            mode="steps",
            key=False,
        )
        self.assertFalse(done.get("wrote"), done)
        self.assertFalse(done.get("deliverables") or [])
        self.assertNotIn("可以投标", done.get("text") or "")
        self.assertNotIn("可以开工", done.get("text") or "")


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkbenchModelTurnTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("PASS workbench_model_turn")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
