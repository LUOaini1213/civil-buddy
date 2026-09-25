#!/usr/bin/env python3
"""Only a person approves a high-risk write, and only for the turn they typed the sentence in.

MCP: the caller is a model — it can ask for a post, never approve one, and the launch scope binds civil.turn.
civil serve: a program drives it too — only confirm_text with the exact sentence, per turn, approves.
Memory: an earlier confirmed turn does not carry over (model loop, expert turn, tender parse wording).
The HTTP boundaries (gateway + workbench) are pinned in test_http_confirmation.py.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "demo")]
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "CIVIL_AGENT_MODE",
             "CIVIL_APPROVAL", "CIVIL_SANDBOX"):
    os.environ.pop(name, None)

import mcp_stdio  # noqa: E402
import mcp_surface  # noqa: E402
from packing_assistant.runtime import model_loop, threads, workspace  # noqa: E402
from packing_assistant.runtime.app_server import handle_rpc  # noqa: E402
from packing_assistant.runtime.civil_config import CONFIRM  # noqa: E402

HIGH = "写一份消防专篇，缺失内容待填"
TENDER = "第一章 投标人须知\n★工期60日历天。\n★投标保证金人民币20万元。\n"


class Script:
    def __init__(self, *steps):
        self.steps = list(steps)

    def __call__(self, messages, tools=None, **_kw):
        step = self.steps.pop(0) if self.steps else "完成。"
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": f"c{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(step)]}


class JobFolder(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="civil-approval-")
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.addCleanup(workspace.deactivate)
        self.job = Path(temporary.name).resolve()
        (self.job / "CIVIL.md").write_text("- 项目：东桥改造工程\n- 辖区：SG\n", encoding="utf-8")
        os.chdir(self.job)
        with patch.object(Path, "home", return_value=self.job / "no-home"):
            workspace.activate(self.job)

    def written(self):
        return sorted(p.name for p in self.job.rglob("*") if p.suffix in {".md", ".docx", ".xlsx"} and p.name != "CIVIL.md")


class McpApprovalTests(JobFolder):
    def test_no_tool_advertises_or_accepts_an_approval_flag(self):
        for scope in ({"expert_id": "fire-protect"}, {"pack": "bid"}, {"expert_id": "construction"}):
            for tool in mcp_surface.list_tools(**scope):
                props = tool["inputSchema"].get("properties") or {}
                self.assertNotIn("confirm_ok", props, (scope, tool["name"]))
                self.assertNotIn("p0_confirmed", props, (scope, tool["name"]))
        table = self.job / "list.csv"
        table.write_text("S/N,Description of Goods,Q'ty,L (mm),W (mm),H (mm),G.W. (kg)\n1,Plate,2,800,800,50,40\n", encoding="utf-8")
        calls = (("civil.turn", {"text": HIGH, "confirm_ok": True}, {"expert_id": "fire-protect"}),
                 ("fire-protect__brief", {"text": HIGH, "p0_confirmed": True}, {"expert_id": "fire-protect"}),
                 ("tender.parse", {"text": TENDER, "p0_confirmed": True}, {"expert_id": "bid-parse"}),
                 ("pack-ship__ingest", {"file_path": str(table), "confirm_ok": True}, {"expert_id": "pack-ship"}))  # open schema
        with patch("packing_assistant.runtime.agent_loop.run_agent") as runner:
            for name, args, scope in calls:
                result = mcp_surface.call_tool(name, args, **scope)
                self.assertEqual((result["ok"], result.get("error_code")), (False, "invalid_args"), (name, result))
            runner.assert_not_called()
        self.assertEqual(self.written(), [])

    def test_a_high_risk_post_over_mcp_is_approval_required_and_writes_nothing(self):
        turn = mcp_surface.call_tool("civil.turn", {"text": HIGH + "。" + CONFIRM, "session_id": "mcp-high"},
                                     expert_id="fire-protect")
        self.assertEqual((turn["ok"], turn["error_code"], turn["wrote"]), (False, "approval_required", False), turn)
        tool = mcp_surface.call_tool("fire-protect__brief", {"text": HIGH}, expert_id="fire-protect")
        self.assertEqual((tool["ok"], tool["error_code"]), (False, "approval_required"), tool)
        target = self.job / "own.md"
        raw = mcp_surface.call_tool("write_deliverable", {"path": str(target), "text": "模型自己写的稿"}, expert_id="fire-protect")
        self.assertEqual((raw["ok"], raw["error_code"]), (False, "approval_required"), raw)
        # --pack design defaults to a low-risk post, but fire-protect is in the same pack.
        packed = mcp_surface.call_tool("write_deliverable", {"path": str(target), "text": "模型自己写的消防专篇"}, pack="design")
        self.assertEqual((packed["ok"], packed["error_code"]), (False, "approval_required"), packed)
        self.assertFalse(target.exists())
        self.assertEqual(self.written(), [])
        rpc = mcp_stdio.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "civil.turn", "arguments": {"text": HIGH}}}, expert="fire-protect")
        self.assertTrue(rpc["result"]["isError"])
        self.assertEqual(json.loads(rpc["result"]["content"][0]["text"])["error_code"], "approval_required")
        low = mcp_surface.call_tool("civil.turn", {"text": "写一份项目日报，部位：东桥3号墩，天气：晴", "session_id": "mcp-low"}, expert_id="pm-daily")
        self.assertTrue(low["ok"] and low["wrote"], low)       # a low-risk post needs no person and still writes

    def test_the_launch_scope_binds_civil_turn(self):
        def turn(args, **launch):
            with patch("packing_assistant.runtime.agent_loop.run_agent", return_value={"ok": True, "wrote": False}) as runner:
                out = mcp_stdio.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                        "params": {"name": "civil.turn", "arguments": {"text": "写一份草稿", **args}}}, **launch)
            body = json.loads(out["result"]["content"][0]["text"])
            return body, (runner.call_args.kwargs["expert_id"] if runner.called else None)

        body, ran = turn({"skill": "fire-protect"}, pack="bid")
        self.assertEqual((body["error_code"], ran), ("permission_denied", None))
        self.assertEqual(turn({"expert_id": "safety-brief"}, pack="bid")[1], None)
        self.assertEqual(turn({"skill": "bid-tech"}, pack="bid")[1], "bid-tech")
        self.assertEqual(turn({}, pack="bid")[1], "bid-parse")
        self.assertEqual(turn({"skill": "bid-tech"}, expert="bid-parse")[1], None)
        self.assertEqual(turn({"skill": "bid-parse"}, expert="bid-parse")[1], "bid-parse")
        self.assertEqual(turn({"skill": "fire-protect"})[1], "fire-protect")       # an unscoped server stays unscoped


class AppServerApprovalTests(JobFolder):
    def setUp(self):
        super().setUp()
        stored = patch.object(threads, "_DIR", self.job / "threads")
        stored.start()
        self.addCleanup(stored.stop)

    def rpc(self, method, **params):
        return handle_rpc({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})

    def test_civil_serve_takes_only_the_typed_sentence(self):
        for flag in (True, "true", 1):
            refused = self.rpc("turn/start", text=HIGH, skill="fire-protect", confirm=flag)
            self.assertIn("confirm_text", refused.get("error", {}).get("message", ""), (flag, refused))
        self.assertEqual(self.written(), [])
        tid = self.rpc("thread/start", title="serve", confirm=True)["result"]["thread_id"]
        later = self.rpc("turn/start", thread_id=tid, text=HIGH, skill="fire-protect", confirm=False)["result"]
        self.assertTrue(later["hitl_pending"] and not later["wrote"], later)     # thread/start never pre-approves
        wrong = self.rpc("turn/start", thread_id=tid, text=HIGH, skill="fire-protect", confirm_text="我明白")["result"]
        self.assertTrue(wrong["hitl_pending"] and not wrong["wrote"], wrong)
        self.assertEqual(self.written(), [])
        signed = threads.new_thread("终端里签认过", confirm=True).thread_id      # what TUI /confirm or the desktop persists
        borrowed = self.rpc("turn/start", thread_id=signed, text=HIGH, skill="fire-protect")
        self.assertIn("confirm_text", borrowed.get("error", {}).get("message", ""), borrowed)
        self.assertEqual(self.written(), [])
        done = self.rpc("turn/start", thread_id=tid, text=HIGH, skill="fire-protect", confirm_text=CONFIRM)["result"]
        self.assertTrue(done["wrote"] and not done["hitl_pending"], done)


class PerTurnApprovalTests(JobFolder):
    SAFE = "编一份临边防护安全交底，部位：东桥3号墩"

    def test_model_loop_asks_again_in_a_later_turn(self):
        model_loop.run_model_agent("你好", session_id="s-model", p0_confirmed=True, complete=Script("你好。"))
        later = model_loop.run_model_agent(self.SAFE, session_id="s-model", complete=Script(
            [("run_skill", {"skill_id": "safety-brief"})], "需要确认句。"))
        self.assertTrue(later["hitl_pending"] and not later["wrote"], later)
        self.assertEqual(self.written(), [])
        same = model_loop.run_model_agent(self.SAFE, session_id="s-model", p0_confirmed=True, complete=Script(
            [("run_skill", {"skill_id": "safety-brief"})], "已出。"))
        self.assertTrue(same["wrote"] and not same["hitl_pending"], same)

    def test_expert_turn_and_tender_wording_do_not_inherit_an_earlier_confirmation(self):
        from packing_assistant.expert_turn import run_expert_turn
        from packing_assistant.runtime.agent_loop import run_agent

        run_expert_turn("什么是 GST", "fire-protect", confirm_ok=True, session_id="s-expert", force_intent="chat")
        later = run_expert_turn(HIGH, "fire-protect", session_id="s-expert", force_intent="run")
        self.assertTrue(later["hitl_pending"] and not later["wrote"], later)
        run_agent("什么是 GST", session_id="s-bid", p0_confirmed=True, force_intent="chat")
        parsed = run_agent(TENDER + "请解析招标", session_id="s-bid", expert_id="bid-parse", force_intent="run")
        self.assertNotIn("P0 noted by operator", str(parsed.get("bidbook_markdown") or ""))
        self.assertIs(parsed["context"]["p0_confirmed"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
