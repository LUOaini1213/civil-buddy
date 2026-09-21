"""Offline acceptance of the host-bound CAD section tool in steps and model turns."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import importlib.util
import io
import os
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.cad3d import agent
from packing_assistant.engineering import worker
from packing_assistant.runtime import cancel, model_loop
from packing_assistant.runtime.turn import run_turn

HAS_DEPS = all(importlib.util.find_spec(name) for name in ("ezdxf", "shapely", "sectionproperties"))
TOOL = "cad_section_properties"


class Script:
    def __init__(self, *steps):
        self.steps, self.tools = list(steps), []

    def __call__(self, messages, tools=None, **kwargs):
        self.tools.append({tool["function"]["name"] for tool in tools or []})
        step = self.steps.pop(0)
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": "call", "name": step[0], "arguments": step[1]}]}


class SectionAgentTests(unittest.TestCase):
    def setUp(self):
        self.context = {"project": {"id": "a" * 32, "name": "Synthetic section", "revision": 1},
                        "document": {"filename": "synthetic.dxf", "sha256": "b" * 64, "layers": [], "entities": []},
                        "draft_config": {"mode": "section", "unit": "mm", "confirmed_solid": True,
                                         "layers": {"SECTION": "section"}}, "model": None}
        self.result = {"kind": "section", "engine": "sectionproperties", "engine_version": "scripted",
                       "unit": "mm", "regions": [{"outer_id": "A", "layer": "SECTION", "hole_ids": ["B"],
                           "area_mm2": 1500., "centroid_source": [50., 30.],
                           "Ixx_mm4": 862500., "Iyy_mm4": 1962500., "Ixy_mm4": 0.}]}
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request",
            "CIVIL_SANDBOX_BACKEND": "app", "CIVIL_WORKTREE_ROOT": "", "CIVIL_OS_SANDBOX_POLICY": ""}))
        stack.enter_context(patch("packing_assistant.runtime.project_instructions.seed_session"))
        stack.enter_context(patch("packing_assistant.runtime.memory.assemble_context", return_value={}))

    def execute(self, text="计算截面性质", args=None):
        return agent.execute(self.context, TOOL, args or {}, user_text=text, session_id="section-agent", run_id="run-section")

    def test_requires_explicit_current_intent_and_empty_tool_arguments(self):
        for text in ("如何计算截面性质", "计算截面性质吗？", "不要计算截面性质", "检查图纸", "生成模型"):
            with self.subTest(text=text), patch.object(worker, "run") as run:
                self.assertNotEqual(agent.operation(text, self.context), TOOL)
                self.assertEqual(self.execute(text)["error_code"], "read_only_intent")
                run.assert_not_called()
        for args in ({"document_id": "c" * 32}, {"path": "C:/private.dxf"}, {"height": 30},
                     {"vertices": [[0, 0, 0]]}, {"config": {}}, {"confirmation": agent.CONFIRM}):
            with self.subTest(args=args), patch.object(worker, "run") as run:
                self.assertEqual(self.execute(args=args)["error_code"], "invalid_args")
                run.assert_not_called()
        for text in ("计算截面性质", "请重新计算当前截面几何性质"):
            self.assertEqual(agent.operation(text, self.context), TOOL)

    def test_uses_only_host_snapshot_and_has_no_write_result_even_readonly(self):
        before = deepcopy(self.context)
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}), patch.object(worker, "run", return_value=self.result) as run:
            result = self.execute()
        self.assertTrue(result["ok"], result)
        self.assertEqual(run.call_args.args, ("section", {"document": before["document"], "config": before["draft_config"]}))
        self.assertEqual(self.context, before)
        self.assertFalse(result.get("cad_changed"))
        self.assertNotIn("cad_context", result)
        self.assertNotIn("files", result)

    def test_steps_and_scripted_model_show_actual_result_not_model_claim(self):
        before = deepcopy(self.context)
        with patch.object(worker, "run", return_value=deepcopy(self.result)):
            steps = run_turn("计算截面性质", mode="steps", session_id="section-agent", cad_context=self.context)
            script = Script((TOOL, {}), "面积为999999且已生成模型")
            model = model_loop.run_model_agent("计算截面性质", session_id="section-agent", complete=script, cad_context=self.context)
        for result in (steps, model):
            self.assertTrue(result["ok"], result)
            self.assertIn("面积 1500 mm²", result["reply"])
            self.assertIn("孔洞 1 个", result["reply"])
            self.assertNotIn("999999", result["reply"])
            self.assertFalse(result["cad_changed"])
            self.assertFalse(result["files"])
            self.assertFalse(result["wrote"])
        self.assertIn(TOOL, script.tools[0])
        self.assertEqual(self.context, before)

    def test_questions_do_not_expose_or_execute_compute_and_no_tool_means_no_success(self):
        script = Script((TOOL, {}), "已计算")
        with patch.object(worker, "run") as run:
            result = model_loop.run_model_agent("如何计算截面性质？", session_id="section-agent", complete=script, cad_context=self.context)
            run.assert_not_called()
        self.assertNotIn(TOOL, script.tools[0])
        self.assertFalse(result["ok"])
        self.assertNotIn("已计算", result["reply"])
        result = model_loop.run_model_agent("计算截面性质", session_id="section-agent", complete=Script("已计算"), cad_context=self.context)
        self.assertIn("尚未执行", result["reply"])
        self.assertNotIn("已计算", result["reply"])

    def test_worker_failure_or_empty_output_cannot_publish_success(self):
        for failure in (ImportError("依赖缺失"), TimeoutError("计算超时"), ValueError("无效轮廓 A"), OSError("启动失败")):
            with self.subTest(failure=failure), patch.object(worker, "run", side_effect=failure):
                result = run_turn("计算截面性质", mode="steps", session_id="section-agent", cad_context=self.context)
                self.assertFalse(result["ok"])
                self.assertIn(str(failure), result["reply"])
                self.assertNotIn("已计算", result["reply"])
        with patch.object(worker, "run", return_value={"kind": "section", "regions": []}):
            self.assertFalse(self.execute()["ok"])

    def test_cancel_before_and_after_worker_is_not_success_and_next_request_isolated(self):
        event = Event(); event.set()
        with patch.object(worker, "run") as run:
            result = run_turn("计算截面性质", mode="steps", cancel_event=event, cad_context=self.context)
            self.assertTrue(result["cancelled"]); run.assert_not_called()
        event.clear()
        def finish_then_cancel(*args, **kwargs):
            event.set()
            return deepcopy(self.result)
        with patch.object(worker, "run", side_effect=finish_then_cancel), cancel.scope(event=event):
            with self.assertRaises(cancel.RunCancelled): self.execute()
        with patch.object(worker, "run", return_value=deepcopy(self.result)):
            self.assertTrue(self.execute()["ok"])

    def test_confined_worker_remains_registered_and_does_not_bypass_no_spawn(self):
        self.assertIn(TOOL, model_loop.CONFINED_TOOLS)
        with patch.dict(os.environ, {"CIVIL_OS_SANDBOX_POLICY": "{}"}), patch.object(worker, "run") as run:
            result = self.execute()
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "sandbox_unavailable")
            self.assertIn("禁止启动", result["reason"])
            run.assert_not_called()

    @unittest.skipUnless(HAS_DEPS, "Install requirements-engineering.txt")
    def test_real_worker_hole_area_without_length_and_unchanged_context(self):
        import ezdxf
        from packing_assistant.cad3d.geometry import inspect_dxf
        doc = ezdxf.new("R2010"); doc.units = 4
        for ring in ([(0, 0), (100, 0), (100, 60), (0, 60)], [(5, 5), (95, 5), (95, 55), (5, 55)]):
            doc.modelspace().add_lwpolyline(ring, close=True, dxfattribs={"layer": "SECTION"})
        stream = io.StringIO(); doc.write(stream)
        self.context["document"] = inspect_dxf(stream.getvalue().encode(), "synthetic-section.dxf")
        before = deepcopy(self.context)
        result = self.execute()
        self.assertTrue(result["ok"], result)
        row = result["section_properties"]["regions"][0]
        self.assertAlmostEqual(row["area_mm2"], 100 * 60 - 90 * 50, places=6)
        self.assertAlmostEqual(row["Ixx_mm4"], (100 * 60**3 - 90 * 50**3) / 12, places=5)
        self.assertEqual(len(row["hole_ids"]), 1)
        self.assertEqual(self.context, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
