"""Offline plan persistence, real resource solving and HTTP integration tests."""
from __future__ import annotations
from copy import deepcopy
import json
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
from demo import planning_api as api
from packing_assistant.engineering.planning import calculate
from packing_assistant.engineering.planning_records import PlanningStore, weekly_report
from packing_assistant.engineering.planning_optimize import optimize


class PlanningWorkbench(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for context in [patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_SANDBOX": "workspace-write"}),
                        patch.object(api, "store", lambda: PlanningStore(self.root)),
                        patch.object(api, "RUNS", api.cad.MemoryStore(max_bytes=4 * 1024 * 1024))]:
            context.start()
            self.addCleanup(context.stop)
        app = FastAPI()
        app.include_router(api.router)
        app.include_router(api.eng.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.plan = api.example()

    def post(self, route, data, **kw):
        return self.client.post(api.BASE + route, json=data, **kw)

    def run_plan(self, plan=None, method="cpm"):
        reply = self.post("/optimize" if method == "resource" else "/calculate",
                          {"plan": self.plan if plan is None else plan})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def test_hand_calculated_resource_cases(self):
        plain = calculate(self.plan)
        self.assertEqual(plain["result"]["duration_workdays"], 8)
        solved = optimize(self.plan)
        self.assertEqual(solved["result"]["duration_workdays"], 11)
        self.assertTrue(solved["result"]["proven_optimal"])
        rows = {r["id"]: r for r in solved["result"]["tasks"]}
        self.assertTrue(rows["B"]["finish_offset"] <= rows["C"]["start_offset"] or
                        rows["C"]["finish_offset"] <= rows["B"]["start_offset"])
        self.assertTrue(all(r["total_float"] is None for r in rows.values()))
        self.plan["resources"][0]["capacity"] = 2
        self.assertEqual(optimize(self.plan)["result"]["duration_workdays"], 8)
        self.assertEqual(plain["plan"]["resources"][0]["capacity"], 1)

    def test_overcapacity_resource_fails_and_nonworking_days(self):
        self.plan["tasks"][1]["resources"]["crew"] = 2
        with self.assertRaises(ValueError):
            optimize(self.plan)
        self.plan["resources"][0]["capacity"] = 2
        self.plan["calendar"]["holidays"] = ["2026-09-23"]
        result = optimize(self.plan)["result"]
        self.assertNotIn("2026-09-23", [r["start"] for r in result["tasks"]])

    def test_save_baseline_history_restart_and_corrupt_record(self):
        first = self.post("/projects", {"name": "合成计划", "plan": self.plan})
        self.assertEqual(first.status_code, 200, first.text)
        project = first.json()["project"]
        ident = project["id"]
        baseline = self.post(f"/projects/{ident}/baseline", {"expected_revision": 1})
        self.assertEqual(baseline.status_code, 200, baseline.text)
        self.plan["tasks"][1]["duration"] = 5
        updated = self.post("/projects", {"name": "合成计划", "plan": self.plan, "id": ident, "expected_revision": 2})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["project"]["result"]["duration_workdays"], 9)
        self.assertEqual(updated.json()["project"]["baseline"]["result"]["duration_workdays"], 8)
        self.assertEqual(updated.json()["project"]["baseline_comparison"][-1]["finish_variance_calendar_days"], 1)
        api.RUNS._items.clear()
        reopened = self.client.get(api.BASE + f"/projects/{ident}").json()
        self.assertEqual(reopened["project"]["revision"], 3)
        old = self.client.get(api.BASE + f"/projects/{ident}?version=1").json()["project"]
        self.assertTrue(old["historical"])
        self.assertEqual(old["result"]["duration_workdays"], 8)
        conflict = self.post("/projects", {"name": "冲突", "plan": self.plan, "id": ident, "expected_revision": 1})
        self.assertEqual(conflict.status_code, 409)
        undone = self.post(f"/projects/{ident}/undo", {"expected_revision": 3}).json()["project"]
        self.assertEqual(undone["result"]["duration_workdays"], 8)
        self.assertEqual(undone["revision"], 4)
        path = api.store()._path(ident)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["result"]["duration_workdays"] = 999
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.client.get(api.BASE + f"/projects/{ident}").status_code, 422)
        listed = self.client.get(api.BASE + "/projects").json()["projects"]
        self.assertIn("error", listed[0])

    def test_optimized_result_provenance_and_weekly_ppc(self):
        response = self.post("/optimize", {"plan": self.plan})
        self.assertEqual(response.status_code, 200, response.text)
        computed = response.json()
        weekly = [{"id": "w1", "task_id": "B", "week_start": "2026-09-21", "status": "done", "reason": "", "constraints": ""},
                  {"id": "w2", "task_id": "C", "week_start": "2026-09-21", "status": "planned", "reason": "", "constraints": "图纸未确认"}]
        body = {"name": "合成资源方案", "plan": self.plan, "run_id": computed["run_id"], "weekly": weekly}
        response = self.post("/projects", body)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["project"]
        self.assertEqual(saved["method"], "resource")
        self.assertEqual(saved["result"]["duration_workdays"], 11)
        self.assertEqual(saved["weekly_report"][0]["ppc_percent"], 50)
        self.assertFalse(saved["weekly_report"][0]["finalized"])
        body["plan"] = deepcopy(self.plan)
        body["plan"]["tasks"][0]["duration"] = 3
        self.assertEqual(self.post("/projects", body).status_code, 422)
        body["plan"] = self.plan
        body["weekly"][1]["status"] = "missed"
        self.assertEqual(self.post("/projects", body).status_code, 422)

    def test_export_gate_and_real_formats_roundtrip(self):
        computed = self.run_plan()
        blocked = self.post("/export", {"plan": self.plan, "run_id": computed["run_id"], "format": "json", "confirmation": ""})
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("签认", blocked.json()["detail"])
        for fmt in ("json", "csv", "xlsx", "xml"):
            exported = self.post("/export", {"plan": self.plan, "run_id": computed["run_id"],
                                             "format": fmt, "confirmation": api.cad.CONFIRMATION})
            self.assertEqual(exported.status_code, 200, exported.text[:300] if fmt != "xlsx" else "XLSX failed")
            imported = self.client.post(api.BASE + "/import", files={"file": ("plan." + fmt, exported.content)})
            self.assertEqual(imported.status_code, 200, imported.text)
            self.assertTrue(imported.json()["requires_confirmation"])
            self.assertEqual(calculate(imported.json()["plan"])["result"]["duration_workdays"], 8)

    def test_cancellation_isolation_read_only_origin_and_no_code(self):
        identifier = "c" * 32
        self.client.post("/api/engineering/operations/" + identifier + "/cancel")
        response = self.post("/projects", {"name": "Cancelled", "plan": self.plan}, headers={"X-CAD-Operation-ID": identifier})
        self.assertEqual(response.status_code, 499)
        self.assertEqual(api.store().list_projects(), [])
        computed = self.run_plan()
        self.assertEqual(self.post("/calculate", {"plan": self.plan}, headers={"Origin": "https://other.invalid"}).status_code, 403)
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            self.assertEqual(self.post("/projects", {"name": "Read only", "plan": self.plan}).status_code, 403)
            blocked = self.post("/export", {"plan": self.plan, "run_id": computed["run_id"],
                                            "format": "json", "confirmation": api.cad.CONFIRMATION})
            self.assertEqual(blocked.status_code, 403)
            self.assertIn("只读", blocked.json()["detail"])
        self.assertEqual(self.post("/calculate", {"plan": self.plan, "code": "print(1)"}).status_code, 422)
        self.assertEqual(self.client.get(api.BASE + "/projects/not-an-id").status_code, 422)

    def test_import_provenance_survives_restart_and_resource_export(self):
        computed = self.run_plan()
        exported = self.post("/export", {"plan": self.plan, "run_id": computed["run_id"],
                                         "format": "xml", "confirmation": api.cad.CONFIRMATION})
        self.assertEqual(exported.status_code, 200, exported.text)
        imported = self.client.post(api.BASE + "/import", files={"file": ("synthetic.xml", exported.content)}).json()
        saved = self.post("/projects", {"name": "合成导入验收", "plan": imported["plan"],
            "synthetic": True, "source_id": imported["source_id"]}).json()["project"]
        api.IMPORTS._items.clear()
        api.RUNS._items.clear()
        opened = self.client.get(api.BASE + "/projects/" + saved["id"]).json()
        self.assertTrue(opened["project"]["synthetic"])
        self.assertEqual(opened["project"]["import_source"]["source"]["filename"], "synthetic.xml")
        self.assertIn("source_id", opened["project"])
        solved = self.post("/optimize", {"plan": self.plan}).json()
        for fmt in ("json", "csv", "xlsx", "xml"):
            reply = self.post("/export", {"plan": self.plan, "format": fmt, "run_id": solved["run_id"],
                                          "confirmation": api.cad.CONFIRMATION})
            self.assertEqual(reply.status_code, 200)

    def test_resource_edit_cannot_silently_save_as_cpm_and_old_record_survives(self):
        computed = self.run_plan(method="resource")
        response = self.post("/projects", {"name": "合成资源方案", "plan": self.plan,
                            "run_id": computed["run_id"], "method": "resource"})
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["project"]
        path = api.store()._path(saved["id"])
        before = path.read_bytes()
        changed = deepcopy(self.plan)
        changed["tasks"][1]["progress"] = 50
        body = {"name": saved["name"], "plan": changed, "id": saved["id"], "expected_revision": saved["revision"]}
        # The server must infer the existing resource method even when the
        # caller omits it. Progress-only changes still invalidate the snapshot.
        for fields in ({}, {"method": "resource"}):
            with self.subTest(fields=fields):
                reply = self.post("/projects", {**body, **fields})
                self.assertEqual(reply.status_code, 422, reply.text)
                self.assertIn("不会自动切换为 CPM", reply.json()["detail"])
                self.assertEqual(path.read_bytes(), before)
        stale = self.post("/projects", {**body, "method": "resource", "run_id": computed["run_id"]})
        self.assertEqual(stale.status_code, 422, stale.text)
        self.assertIn("旧参数", stale.json()["detail"])
        self.assertEqual(path.read_bytes(), before)
        unchanged = api.store().open(saved["id"])
        self.assertEqual(unchanged["revision"], saved["revision"])
        self.assertEqual(unchanged["method"], "resource")
        self.assertEqual(unchanged["result"]["duration_workdays"], 11)
        self.assertEqual(unchanged["plan"]["tasks"][1]["progress"], 0)
        # Switching method is possible after an explicit CPM run, with the
        # matching new snapshot. The previous resource version remains intact.
        plain = self.run_plan(changed)
        switched = self.post("/projects", {**body, "method": "cpm", "run_id": plain["run_id"]})
        self.assertEqual(switched.status_code, 200, switched.text)
        updated = switched.json()["project"]
        self.assertEqual(updated["revision"], saved["revision"] + 1)
        self.assertEqual(updated["method"], "cpm")
        self.assertEqual(updated["result"]["duration_workdays"], 8)
        self.assertEqual(updated["plan"]["tasks"][1]["progress"], 50)
        historical = api.store().open(saved["id"], saved["revision"])
        self.assertEqual(historical["method"], "resource")
        self.assertEqual(historical["result"]["duration_workdays"], 11)

    def test_save_rejects_method_mismatch_without_mutation(self):
        resource = self.run_plan(method="resource")
        reply = self.post("/projects", {"name": "合成方法核对", "plan": self.plan,
                                       "run_id": resource["run_id"], "method": "resource"})
        self.assertEqual(reply.status_code, 200, reply.text)
        saved = reply.json()["project"]
        path = api.store()._path(saved["id"])
        before = path.read_bytes()
        plain = self.run_plan()
        for run_id, wrong_method in ((resource["run_id"], "cpm"), (plain["run_id"], "resource")):
            with self.subTest(method=wrong_method):
                rejected = self.post("/projects", {"name": saved["name"], "plan": self.plan,
                    "id": saved["id"], "expected_revision": saved["revision"],
                    "run_id": run_id, "method": wrong_method})
                self.assertEqual(rejected.status_code, 422, rejected.text)
                self.assertIn("方式与结果来源不一致", rejected.json()["detail"])
                self.assertEqual(path.read_bytes(), before)

    def test_export_requires_current_matching_run(self):
        computed = self.run_plan()
        body = {"plan": self.plan, "format": "json", "confirmation": api.cad.CONFIRMATION}
        self.assertEqual(self.post("/export", body).status_code, 422)
        self.assertEqual(self.post("/export", {**body, "run_id": None}).status_code, 422)
        changed = deepcopy(self.plan)
        changed["tasks"][0]["progress"] = 25
        rejected = self.post("/export", {**body, "plan": changed, "run_id": computed["run_id"]})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertIn("旧参数", rejected.json()["detail"])
        self.assertNotIn("attachment", rejected.headers.get("Content-Disposition", ""))
        valid = self.post("/export", {**body, "run_id": computed["run_id"]})
        self.assertEqual(valid.status_code, 200, valid.text)

    def test_malformed_weekly_and_rehashed_broken_baseline_are_rejected(self):
        from packing_assistant.engineering.planning_records import digest
        row = {"id": "w1", "task_id": "B", "week_start": "2026-09-21", "status": "planned", "reason": "", "constraints": ""}
        for field in ("task_id", "status"):
            for invalid in ([], {}, True, None):
                bad = dict(row)
                bad[field] = invalid
                reply = self.post("/projects", {"name": "Malformed", "plan": self.plan, "weekly": [bad]})
                self.assertEqual(reply.status_code, 422)
        saved = self.post("/projects", {"name": "Broken baseline", "plan": self.plan}).json()["project"]
        path = api.store()._path(saved["id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("checksum")
        data["baseline"] = {"created_at": data["created_at"], "revision": 1, "plan": data["plan"], "result": {"tasks": []}}
        data["checksum"] = digest(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.client.get(api.BASE + "/projects/" + saved["id"]).status_code, 422)

    def test_mpp_timeout_returns_gateway_error_without_mutation(self):
        with patch("packing_assistant.engineering.planning_exchange.import_plan", side_effect=TimeoutError("test timeout")):
            reply = self.client.post(api.BASE + "/import", files={"file": ("synthetic.mpp", b"fixture")})
        self.assertEqual(reply.status_code, 504)
        self.assertEqual(api.store().list_projects(), [])

    def test_interrupted_commit_preserves_previous_bytes(self):
        from packing_assistant.runtime.cancel import RunCancelled
        from demo.projects import _write_atomic
        saved = self.post("/projects", {"name": "Original", "plan": self.plan}).json()["project"]
        path = api.store()._path(saved["id"])
        before = path.read_bytes()

        def interrupted(path, data, **kw):
            def stop():
                raise RunCancelled("test")
            return _write_atomic(path, data, before_replace=stop)

        with patch("demo.projects._write_atomic", side_effect=interrupted):
            reply = self.post("/projects", {"name": "Changed", "plan": self.plan, "id": saved["id"], "expected_revision": 1})
        self.assertEqual(reply.status_code, 499)
        self.assertEqual(path.read_bytes(), before)

    def test_cancel_after_atomic_commit_returns_saved_revision_and_live_caches(self):
        from demo.projects import _write_atomic
        imported = self.client.post(api.BASE + "/import", files={
            "file": ("synthetic-commit-source.json", json.dumps(self.plan).encode())})
        self.assertEqual(imported.status_code, 200, imported.text)
        initial = self.post("/projects", {"name": "Synthetic original", "plan": self.plan,
                                         "source_id": imported.json()["source_id"]})
        self.assertEqual(initial.status_code, 200, initial.text)
        project = initial.json()["project"]
        ident = project["id"]
        path = api.store()._path(ident)

        for index, action in enumerate(("save", "baseline", "undo"), 1):
            operation_id = "e" * 31 + str(index)
            before_revision = project["revision"]
            before_bytes = path.read_bytes()

            def commit_then_cancel(target, data, **kwargs):
                _write_atomic(target, data, **kwargs)
                # Simulate a real cancel arriving immediately after replace,
                # while cad.operation still owns this request's event.
                self.assertTrue(api.cad.cancel_import(operation_id)["was_running"])

            with self.subTest(action=action), patch("demo.projects._write_atomic", side_effect=commit_then_cancel):
                if action == "save":
                    response = self.post("/projects", {"name": "Synthetic committed", "plan": self.plan,
                                         "id": ident, "expected_revision": before_revision},
                                         headers={"X-CAD-Operation-ID": operation_id})
                else:
                    response = self.post(f"/projects/{ident}/{action}", {"expected_revision": before_revision},
                                         headers={"X-CAD-Operation-ID": operation_id})
            self.assertEqual(response.status_code, 200, response.text)
            project = response.json()["project"]
            self.assertEqual(project["revision"], before_revision + 1)
            self.assertNotEqual(path.read_bytes(), before_bytes)
            persisted = api.store().open(ident)
            self.assertEqual(persisted["revision"], project["revision"])
            self.assertEqual(persisted["name"], project["name"])
            self.assertEqual(persisted["baseline"], project["baseline"])
            if action == "baseline":
                self.assertEqual(project["baseline"]["revision"], before_revision)
            elif action == "undo":
                self.assertIsNone(project["baseline"])
            source = api.IMPORTS.get(project["source_id"])
            self.assertEqual({key: value for key, value in source.items() if key != "source_file"}, project["import_source"])
            self.assertEqual(source["source_file"]["size"], len(json.dumps(self.plan).encode()))
            self.assertEqual(source["source"]["filename"], "synthetic-commit-source.json")
            run_id = response.json()["run_id"]
            self.assertEqual(api.RUNS.get(run_id)["plan"], project["plan"])
            self.assertEqual(api.RUNS.get(run_id)["result"], project["result"])
            exported = self.post("/export", {"plan": project["plan"], "run_id": run_id,
                                             "format": "json", "confirmation": api.cad.CONFIRMATION})
            self.assertEqual(exported.status_code, 200, exported.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
