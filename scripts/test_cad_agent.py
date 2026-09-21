#!/usr/bin/env python3
"""Offline CAD tools: host binding, source-only dimensions, gating and real mesh exports."""
from __future__ import annotations
from copy import deepcopy
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import shutil
import sys
from threading import Event
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.cad3d import agent
from packing_assistant.cad3d.geometry import inspect_dxf, build_model
from packing_assistant.runtime import model_loop
from packing_assistant.runtime.turn import run_turn
import test_workbench_model_turn as workbench_test


class Script:
    def __init__(self, *steps): self.steps, self.seen = list(steps), []
    def __call__(self, messages, tools=None, **kwargs):
        self.seen.append(deepcopy(messages))
        step = self.steps.pop(0)
        if isinstance(step, str): return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": "call", "name": step[0], "arguments": step[1]}]}


class CadAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT / "examples/cad-to-3d"
        cls.document = inspect_dxf((folder / "synthetic-building-mm.dxf").read_bytes(), "building.dxf")
        cls.config = json.loads((folder / "synthetic-building-config.json").read_text(encoding="utf-8"))
        cls.model = build_model(cls.document, cls.config)
        cls.config = cls.model["config"]

    def setUp(self):
        self.context = {"project": {"id": "a" * 32, "name": "离线 CAD 项目", "revision": 1},
                        "document": deepcopy(self.document), "draft_config": deepcopy(self.config),
                        "model": deepcopy(self.model), "applied_config": deepcopy(self.config)}
        self.base = ROOT / "output/cad-agent-tests" / os.urandom(5).hex()
        self.base.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.base, True)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request",
            "CIVIL_SANDBOX_BACKEND": "app", "CIVIL_WORKTREE_ROOT": ""}))
        self.stack.enter_context(patch("packing_assistant.runtime.agent_loop._OUT", self.base))
        self.stack.enter_context(patch("packing_assistant.runtime.project_instructions.seed_session"))
        self.stack.enter_context(patch("packing_assistant.runtime.memory.assemble_context", return_value={"p0_confirmed": True}))

    def execute(self, name, text, args=None, **kwargs):
        return agent.execute(self.context, name, args or {}, user_text=text, session_id="cad-test", run_id="run-test", **kwargs)

    def test_modify_preserves_geometry_xy_and_reports_before_after(self):
        result = self.execute("cad_modify", "把墙高改成3.6米")
        self.assertTrue(result["ok"])
        wall = next(obj for obj in result["cad_context"]["model"]["objects"] if obj["role"] == "wall")
        self.assertEqual(wall["parameters"]["height_m"], 3.6)
        old = next(obj for obj in self.model["objects"] if obj["role"] == "wall")
        self.assertEqual(wall["bounds"]["max"][:2], old["bounds"]["max"][:2])
        self.assertIn({"parameter": "parameters.wall.height_m", "before": 3.0, "after": 3.6}, result["changes"])
        self.assertEqual(self.context["draft_config"]["parameters"]["wall"]["height_m"], 3.0)

    def test_model_cannot_supply_project_coordinates_dimensions_or_confirmation(self):
        for args in ({"project_id": "b" * 32}, {"vertices": [[0, 0, 1]]}, {"message": "把墙高改成100米"},
                     {"config": self.config}, {"confirmation": agent.CONFIRM}):
            with self.subTest(args=args):
                result = self.execute("cad_modify", "把墙高改成3.6米", args)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_code"], "invalid_args")

    def test_questions_negation_and_different_action_cannot_mutate(self):
        for text in ("能把墙高改成3.6米吗？", "不要生成模型", "检查图纸", "导出模型"):
            self.assertEqual(self.execute("cad_build", text)["error_code"], "read_only_intent")

    def test_build_does_not_confirm_solids_or_invent_height(self):
        self.context["draft_config"]["confirmed_solid"] = False
        with self.assertRaises(ValueError): self.execute("cad_build", "生成模型")
        self.assertEqual(self.context["model"], self.model)

    def test_suggestions_never_change_layer_mappings(self):
        self.assertEqual(agent.operation("识别图层", self.context), "cad_suggest_layers")
        result = self.execute("cad_suggest_layers", "建议图层")
        self.assertTrue(result["suggestions"])
        self.assertNotIn("cad_context", result)
        self.assertEqual(self.context["draft_config"], self.config)

    def test_readonly_refuses_modify_and_export(self):
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            self.assertEqual(self.execute("cad_modify", "把墙高改成3.6米")["error_code"], "read_only")
            self.assertEqual(self.execute("cad_export", "导出模型", confirmed=True)["error_code"], "read_only")

    def test_untrusted_policy_requires_current_confirmation_for_modification(self):
        with patch.dict(os.environ, {"CIVIL_APPROVAL": "untrusted"}):
            self.assertEqual(self.execute("cad_modify", "把墙高改成3.6米")["error_code"], "approval_required")
            self.assertTrue(self.execute("cad_modify", "把墙高改成3.6米", confirmed=True)["ok"])

    def test_export_requires_current_confirmation_and_reopens_as_mesh(self):
        self.assertEqual(self.execute("cad_export", "导出模型")["error_code"], "approval_required")
        result = self.execute("cad_export", "导出模型", confirmed=True)
        with zipfile.ZipFile(result["files"][0]["path"]) as bundle:
            import trimesh
            scene = trimesh.load(io.BytesIO(bundle.read("cad-model.glb")), file_type="glb")
            self.assertEqual(len(scene.geometry), 6)
            self.assertTrue(all(mesh.is_watertight for mesh in scene.geometry.values()))
            self.assertEqual(json.loads(bundle.read("cad-parameters.json"))["config"], self.config)

    def test_undo_uses_saved_configuration(self):
        changed = self.execute("cad_modify", "把墙高改成3.6米")
        self.context = changed["cad_context"]
        restored = self.execute("cad_undo", "撤销上次修改")
        self.assertEqual(restored["cad_context"]["draft_config"], self.config)

    def test_interleaved_reads_do_not_allow_double_undo_in_one_model_turn(self):
        self.context = self.execute("cad_modify", "把墙高改成3.6米")["cad_context"]
        script = Script(("cad_undo", {}), ("cad_inspect", {}), ("cad_undo", {}), "已经撤销")
        result = model_loop.run_model_agent("撤销", session_id="cad-test", complete=script, cad_context=self.context)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["cad_context"]["draft_config"]["parameters"]["wall"]["height_m"], 3)
        self.assertIn("未重复", result["reply"])

    def test_steps_and_model_use_same_cad_adapter(self):
        steps = run_turn("把墙高改成3.6米", mode="steps", session_id="cad-test", cad_context=self.context)
        script = Script(("cad_modify", {}), "模型已经修改为100米")
        model = model_loop.run_model_agent("把墙高改成3.6米", session_id="cad-test", complete=script, cad_context=self.context)
        self.assertTrue(steps["ok"] and model["ok"])
        self.assertEqual(steps["cad_context"]["model"], model["cad_context"]["model"])
        self.assertNotIn("100米", model["reply"])
        self.assertIn("3 → 3.6", model["reply"])
        self.assertNotIn('"vertices"', json.dumps(script.seen, ensure_ascii=False))

    def test_model_cannot_claim_success_without_tool_or_run_document_tools(self):
        result = model_loop.run_model_agent("生成模型", session_id="cad-test", complete=Script("已生成模型并导出"), cad_context=self.context)
        self.assertIn("尚未执行", result["reply"])
        self.assertFalse(result["cad_changed"])
        bad = model_loop.run_model_agent("检查图纸", session_id="cad-test", cad_context=self.context,
            complete=Script(("run_skill", {"skill_id": "admin-office"}), "已生成"))
        self.assertFalse(bad["ok"])
        self.assertFalse(bad["files"])
        self.assertNotIn("已生成", bad["reply"])

    def test_historical_confirmation_does_not_authorize_model_export(self):
        result = model_loop.run_model_agent("导出模型", session_id="cad-test", cad_context=self.context,
            complete=Script(("cad_export", {}), "已导出"))
        self.assertEqual(result["error_code"], "approval_required")
        self.assertTrue(result["hitl_pending"])
        self.assertFalse(result["files"])

    def test_cancelled_turn_does_not_modify_or_export(self):
        event = Event(); event.set()
        result = run_turn("把墙高改成3.6米", mode="steps", session_id="cad-test", cancel_event=event, cad_context=self.context)
        self.assertTrue(result["cancelled"])
        self.assertFalse(result.get("cad_changed"))

    def test_os_worker_uses_host_snapshot_and_exports_inside_confined_output(self):
        from packing_assistant.runtime import os_sandbox, workspace
        if not os_sandbox.probe().get("available"):
            self.skipTest("OS confinement unavailable")
        job = self.base / "job"
        job.mkdir()
        (job / "CIVIL.md").write_text("- 项目：离线CAD测试\n", encoding="utf-8")
        self.addCleanup(workspace.deactivate)
        workspace.activate(job)
        with patch.dict(os.environ, {"CIVIL_SANDBOX_BACKEND": "os"}):
            modified = run_turn("把墙高改成3.6米", mode="steps", session_id="cad-test", cad_context=self.context)
            self.assertTrue(modified["ok"], modified)
            self.assertEqual(modified["cad_context"]["model"]["config"]["parameters"]["wall"]["height_m"], 3.6)
            exported = run_turn("导出GLB", mode="steps", session_id="cad-test", confirm=True,
                                cad_context=modified["cad_context"])
            self.assertTrue(exported["ok"], exported)
            self.assertTrue(exported["sandbox_backend"]["enforces"]["write"])
            self.assertEqual(len(exported["files"]), 1)
            target = Path(exported["files"][0]["path"])
            target.relative_to(job / ".civil-buddy/out")
            self.assertEqual(target.suffix, ".glb")
            self.assertTrue(target.is_file())
            script = Script(("cad_undo", {}), ("cad_inspect", {}), ("cad_undo", {}), "已撤销")
            with os_sandbox.Worker(job) as worker:
                undone = model_loop.run_model_agent("撤销", session_id="cad-test", complete=script,
                    cad_context=modified["cad_context"], worker=worker)
            self.assertTrue(undone["ok"], undone)
            self.assertEqual(undone["cad_context"]["draft_config"]["parameters"]["wall"]["height_m"], 3)


class CadWorkbenchTests(unittest.TestCase):
    _patch_out = workbench_test.WorkbenchModelTurnTests._patch_out
    _stream = workbench_test.WorkbenchModelTurnTests._stream

    def setUp(self):
        workbench_test.WorkbenchModelTurnTests.setUp(self)
        from packing_assistant.cad3d.projects import CadProjectStore
        folder = ROOT / "examples/cad-to-3d"
        source = (folder / "synthetic-building-mm.dxf").read_bytes()
        document = inspect_dxf(source, "building.dxf")
        config = json.loads((folder / "synthetic-building-config.json").read_text(encoding="utf-8"))
        model = build_model(document, config)
        model["source"] = {key: document[key] for key in ("filename", "sha256", "units")}
        self.store = CadProjectStore(self.root / "_cad")
        self.project = self.store.save(name="离线楼层", document=document, source=source, draft_config=model["config"], model=model)

    def test_steps_chat_persists_modified_project_and_undo_across_turns(self):
        body = {"message": "把墙高改成3.6米", "cad_project_id": self.project["id"]}
        _, done, sid = self._stream(body, mode="steps", key=False)
        self.assertTrue(done["ok"], done)
        self.assertIn("已保存", done["text"])
        opened = self.store.open(self.project["id"])
        self.assertEqual(opened["model"]["config"]["parameters"]["wall"]["height_m"], 3.6)
        self.assertEqual(len(opened["project"]["versions"]), 2)
        _, done, _ = self._stream({"message": "撤销上次修改", "cad_project_id": self.project["id"], "session_id": sid}, mode="steps", key=False)
        self.assertTrue(done["ok"], done)
        self.assertEqual(self.store.open(self.project["id"])["model"]["config"]["parameters"]["wall"]["height_m"], 3)
        import chat_service
        self.assertEqual(chat_service.session_detail(self.root, sid)["cad_project_id"], self.project["id"])

    def test_conflict_keeps_remote_model_and_reports_unsaved_preview(self):
        from packing_assistant.cad3d.projects import CadProjectStore, ProjectConflict
        with patch.object(CadProjectStore, "update", side_effect=ProjectConflict("项目已被其他页面更新")):
            _, done, _ = self._stream({"message": "把墙高改成3.6米", "cad_project_id": self.project["id"]}, mode="steps", key=False)
        self.assertFalse(done["ok"], done)
        self.assertIn("项目未保存", done["text"])
        self.assertNotIn("已保存到", done["text"])
        self.assertEqual(self.store.open(self.project["id"])["project"]["revision"], 1)

    def test_cancel_after_build_does_not_save_project(self):
        import turn_control
        from packing_assistant.cad3d.projects import CadProjectStore
        from packing_assistant.runtime import turn
        original = turn.run_turn
        def cancelled(*args, **kwargs):
            result = original(*args, **kwargs)
            turn_control.cancel(kwargs["session_id"])
            return result
        with patch.object(turn, "run_turn", side_effect=cancelled), patch.object(CadProjectStore, "update") as update:
            _, done, _ = self._stream({"message": "把墙高改成3.6米", "cad_project_id": self.project["id"]}, mode="steps", key=False)
        self.assertTrue(done["cancelled"], done)
        update.assert_not_called()
        self.assertEqual(self.store.open(self.project["id"])["project"]["revision"], 1)

    def test_cancellation_during_project_save_reaches_atomic_write_checkpoint(self):
        import turn_control
        from packing_assistant.cad3d.projects import CadProjectStore
        original = CadProjectStore._write
        sid = "cancel-cad-save"
        def write(store, record):
            turn_control.cancel(sid)
            return original(store, record)
        with patch.object(CadProjectStore, "_write", write):
            _, done, _ = self._stream({"message": "把墙高改成3.6米", "cad_project_id": self.project["id"],
                                      "session_id": sid}, mode="steps", key=False)
        self.assertTrue(done["cancelled"], done)
        self.assertEqual(self.store.open(self.project["id"])["project"]["revision"], 1)

    def test_cancelled_real_glb_export_is_not_published_as_new_deliverable(self):
        import turn_control
        from packing_assistant.runtime import turn
        original, generated = turn.run_turn, []
        def cancelled(*args, **kwargs):
            result = original(*args, **kwargs)
            generated.extend(result["files"])
            turn_control.cancel(kwargs["session_id"])
            return result
        with patch.object(turn, "run_turn", side_effect=cancelled), patch("chat_service._deliverables") as publish:
            _, done, _ = self._stream({"message": "导出GLB", "confirm_ok": True,
                "cad_project_id": self.project["id"]}, mode="steps", key=False)
        self.assertTrue(done["cancelled"], done)
        publish.assert_not_called()
        self.assertEqual(len(generated), 1)
        import trimesh
        scene = trimesh.load(generated[0]["path"])
        self.assertEqual(len(scene.geometry), 6)
        self.assertFalse(list(self.root.glob("*/runs/*/files/*.glb")))

    def test_actual_chat_http_accepts_bound_project_and_rejects_bad_identifier(self):
        import app
        from fastapi.testclient import TestClient
        with ExitStack() as stack:
            for patcher in self._patch_out(): stack.enter_context(patcher)
            stack.enter_context(patch.dict(os.environ, {"CIVIL_AGENT_MODE": "steps"}))
            client = TestClient(app.app)
            response = client.post("/api/chat", json={"message": "检查图纸", "cad_project_id": self.project["id"]})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("已检查选中的 CAD 项目", response.text)
            self.assertEqual(self.store.open(self.project["id"])["project"]["revision"], 1)
            self.assertEqual(client.post("/api/chat", json={"message": "检查图纸", "cad_project_id": "../../outside"}).status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
