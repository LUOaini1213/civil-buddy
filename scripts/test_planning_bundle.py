"""Complete planning handoff: real results, isolated workspaces and hostile ZIPs."""
from copy import deepcopy
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import planning_api as api
from packing_assistant.engineering import planning_bundle as bundle
from packing_assistant.engineering.planning_records import PlanningStore, digest
from packing_assistant.engineering.planning_optimize import optimize
from packing_assistant.runtime.cancel import RunCancelled


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def repack(members):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return stream.getvalue()


def change_record(payload, mutation):
    members = unpack(payload)
    record = json.loads(members["project.json"])
    record.pop("checksum")
    mutation(record)
    record["checksum"] = digest(record)
    members["project.json"] = json.dumps(record, ensure_ascii=False).encode()
    manifest = json.loads(members["manifest.json"])
    manifest["members"]["project.json"] = {"sha256": hashlib.sha256(members["project.json"]).hexdigest(),
                                                "size": len(members["project.json"])}
    members["manifest.json"] = json.dumps(manifest).encode()
    return repack(members)


class PlanningBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.first, self.second = self.root / "first", self.root / "second"
        self.first.mkdir(); self.second.mkdir()
        self.active = self.first
        for context in (patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_SANDBOX": "workspace-write"}),
                        patch.object(api, "store", lambda: PlanningStore(self.active)),
                        patch.object(api, "RUNS", api.cad.MemoryStore()),
                        patch.object(api, "IMPORTS", api.cad.MemoryStore())):
            context.start(); self.addCleanup(context.stop)
        app = FastAPI(); app.include_router(api.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.raw = json.dumps(api.example(), ensure_ascii=False).encode()
        self.sha = hashlib.sha256(self.raw).hexdigest()

    def post(self, route, body, **kw):
        return self.client.post(api.BASE + route, json=body, **kw)

    def make_project(self, with_original=True):
        imported = self.client.post(api.BASE + "/import", files={"file": ("synthetic-original.json", self.raw)})
        self.assertEqual(imported.status_code, 200, imported.text)
        # Upload alone is a draft and writes no persistent project or raw file.
        self.assertEqual(list(PlanningStore(self.active).root.glob("*.json")), [])
        source_id = imported.json()["source_id"]
        if not with_original:
            source = api.IMPORTS.get(source_id); source.pop("source_file")
            source_id = api.IMPORTS.put(source)
        saved = self.post("/projects", {"name": "Synthetic complete project", "plan": api.example(),
                            "synthetic": True, "source_id": source_id})
        self.assertEqual(saved.status_code, 200, saved.text)
        project = saved.json()["project"]
        baseline = self.post(f"/projects/{project['id']}/baseline", {"expected_revision": project["revision"]})
        self.assertEqual(baseline.status_code, 200, baseline.text)
        project = baseline.json()["project"]
        solved = optimize(api.example())
        run_id = api.RUNS.put(dict(solved, method="resource"))
        weekly = [{"id": "W1", "task_id": "B", "week_start": "2026-09-21", "status": "done", "reason": "", "constraints": ""},
                  {"id": "W2", "task_id": "C", "week_start": "2026-09-21", "status": "missed", "reason": "Synthetic delay", "constraints": ""}]
        saved = self.post("/projects", {"name": project["name"], "plan": api.example(), "method": "resource", "run_id": run_id,
                            "id": project["id"], "expected_revision": project["revision"], "weekly": weekly})
        self.assertEqual(saved.status_code, 200, saved.text)
        return saved.json()["project"]

    def export(self, project):
        response = self.post(f"/projects/{project['id']}/export", {"expected_revision": project["revision"],
                                                                 "confirmation": api.cad.CONFIRMATION})
        self.assertEqual(response.status_code, 200, response.text[:300] if response.status_code != 200 else "")
        self.assertEqual(response.headers["content-type"], "application/zip")
        return response.content

    def import_file(self, data, **kwargs):
        return self.client.post(api.BASE + "/projects/import", files={"file": ("handoff.zip", data)}, **kwargs)

    def test_full_handoff_preserves_results_baseline_history_weekly_and_original(self):
        original = self.make_project()
        store = PlanningStore(self.first)
        before = store._path(original["id"]).read_bytes()
        data = self.export(original)
        members = unpack(data)
        self.assertEqual(set(members), {"manifest.json", "project.json", f"sources/{self.sha}.bin"})
        self.assertEqual(members[f"sources/{self.sha}.bin"], self.raw)
        manifest = json.loads(members["manifest.json"])
        self.assertEqual(manifest["missing_sources"], [])
        self.assertEqual(before.count(base64.b64encode(self.raw)), 1)
        self.assertNotIn("source_files", original)
        self.active = self.second
        with patch("packing_assistant.engineering.planning_optimize.optimize", side_effect=AssertionError("must not re-optimize")):
            response = self.import_file(data)
        self.assertEqual(response.status_code, 200, response.text)
        copied = response.json()["project"]
        self.assertNotEqual(copied["id"], original["id"])
        self.assertEqual(copied["revision"], original["revision"])
        for field in ("plan", "result", "method", "baseline", "weekly", "import_source", "versions"):
            self.assertEqual(copied[field], original[field])
        self.assertEqual(copied["result"]["duration_workdays"], 11)
        self.assertEqual(copied["baseline"]["result"]["duration_workdays"], 8)
        self.assertEqual(copied["weekly_report"][0]["ppc_percent"], 50)
        self.assertTrue(response.json()["confirmation_reset"])
        self.assertFalse(copied["bundle_origin"]["optimality_reverified"])
        self.assertEqual(copied["bundle_status"], {"complete": True, "source_file_count": 1, "missing_sources": []})
        self.assertEqual(store._path(original["id"]).read_bytes(), before)
        api.RUNS._items.clear(); api.IMPORTS._items.clear()
        restarted = self.client.get(api.BASE + "/projects/" + copied["id"])
        self.assertEqual(restarted.status_code, 200, restarted.text)
        self.assertEqual(restarted.json()["project"]["result"], original["result"])
        blob = PlanningStore(self.second).source_file(copied["id"], self.sha)
        self.assertEqual(base64.b64decode(blob["data"]), self.raw)
        for version in original["versions"]:
            old = PlanningStore(self.second).open(copied["id"], version["revision"])
            self.assertEqual(old["revision"], version["revision"])
        updated = self.post("/projects", {"name": "Synthetic continued", "plan": copied["plan"], "method": "resource",
                            "run_id": restarted.json()["run_id"], "id": copied["id"], "expected_revision": copied["revision"]})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["project"]["revision"], copied["revision"] + 1)

    def test_import_resets_authorizations_in_current_history_and_baseline(self):
        project = self.make_project()
        data = self.export(project)
        def approve(record):
            record.update(signed=True, confirmation=api.cad.CONFIRMATION, authorization={"export": True})
            record["history"][0]["signed"] = True
            record["baseline"]["approval"] = {"signed": True}
        self.active = self.second
        reply = self.import_file(change_record(data, approve))
        self.assertEqual(reply.status_code, 200, reply.text)
        copied = PlanningStore(self.second)._read(reply.json()["project"]["id"])
        for item in [copied, *copied["history"], copied["baseline"]]:
            self.assertFalse(set(item) & bundle.AUTH_FIELDS)
        # A previous confirmation inside the package does not authorize export.
        blocked = self.post(f"/projects/{copied['id']}/export", {"expected_revision": copied["revision"], "confirmation": ""})
        self.assertEqual(blocked.status_code, 403)

    def test_unknown_schema_fields_bad_checksums_and_bad_results_never_commit(self):
        project = self.make_project(); data = self.export(project)
        self.active = self.second
        changes = [lambda r: r.update(schema="unrecognized.v9"), lambda r: r.update(code="print('untrusted')"),
                   lambda r: r["result"].update(duration_workdays=999),
                   lambda r: r["baseline"]["result"].update(duration_workdays=99),
                   lambda r: r["history"][0]["result"]["tasks"][0].update(progress=90),
                   lambda r: r["history"][1].update(revision=r["history"][0]["revision"]),
                   lambda r: r["result"]["tasks"][2].update(start_offset=2, finish_offset=5, start="2026-09-23", end="2026-09-25"),
                   lambda r: r["result"].update(proven_optimal=False),
                   lambda r: r["import_source"]["source"].update(format="exe")]
        for change in changes:
            with self.subTest(change=change):
                response = self.import_file(change_record(data, change))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(list(PlanningStore(self.second).root.glob("*.json")), [])
        members = unpack(data); members[f"sources/{self.sha}.bin"] += b"changed"
        self.assertEqual(self.import_file(repack(members)).status_code, 422)

    def test_known_legacy_cpm_offset_columns_preserve_saved_resource_dates(self):
        data = self.export(self.make_project()); self.active = self.second
        def old_layout(record):
            for row in record["result"]["tasks"]:
                for key in ("early_start", "early_finish", "late_start", "late_finish"):
                    row[key + "_offset"] = row.pop("cpm_" + key + "_offset")
                    row.pop("cpm_" + key)
        legacy = change_record(data, old_layout)
        original = json.loads(unpack(legacy)["project.json"])["result"]
        reply = self.import_file(legacy)
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(reply.json()["project"]["result"], original)
        self.assertEqual(reply.json()["project"]["result"]["duration_workdays"], 11)
        # A made-up legacy offset is still rejected even if all hashes match.
        forged = change_record(legacy, lambda record: record["result"]["tasks"][0].update(early_start_offset=99))
        self.assertEqual(self.import_file(forged).status_code, 422)

    def test_resigned_bad_offsets_nonnumeric_values_and_deep_json_return_422(self):
        data = self.export(self.make_project()); self.active = self.second
        mutations = [lambda r: r["result"]["tasks"][0].update(start_offset=3654, finish_offset=3654),
                     lambda r: r["result"]["tasks"][0].update(start_offset=True),
                     lambda r: r["result"]["tasks"][0].update(start_offset="0"),
                     lambda r: r["result"]["tasks"][0].update(end=[]),
                     lambda r: r["result"].update(lower_bound_workdays={}),
                     lambda r: r["result"].update(engine=None),
                     lambda r: r["baseline"].update(result=[])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                response = self.import_file(change_record(data, mutate))
                self.assertEqual(response.status_code, 422, response.text)
        members = unpack(data)
        members["project.json"] = b'{"nested":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'
        manifest = json.loads(members["manifest.json"])
        manifest["members"]["project.json"] = {"size": len(members["project.json"]), "sha256": hashlib.sha256(members["project.json"]).hexdigest()}
        members["manifest.json"] = json.dumps(manifest).encode()
        self.assertEqual(self.import_file(repack(members)).status_code, 422)
        self.assertEqual(list(PlanningStore(self.second).root.glob("*.json")), [])
        members = unpack(data)
        raw = json.loads(members["project.json"]); raw["checksum"] = "0" * 64
        members["project.json"] = json.dumps(raw).encode()
        manifest = json.loads(members["manifest.json"])
        manifest["members"]["project.json"] = {"size": len(members["project.json"]), "sha256": hashlib.sha256(members["project.json"]).hexdigest()}
        members["manifest.json"] = json.dumps(manifest).encode()
        self.assertEqual(self.import_file(repack(members)).status_code, 422)

    def test_zip_allowlist_rejects_traversal_duplicate_symlink_and_unknown_members(self):
        data = self.export(self.make_project()); self.active = self.second
        members = unpack(data)
        for path in ("../escape", "/absolute", "C:/escape", "sources\\escape.bin", "PROJECT.JSON", "run.py"):
            response = self.import_file(repack({**members, path: b"untrusted"}))
            self.assertEqual(response.status_code, 422, response.text)
        for mode in ("duplicate", "symlink"):
            stream = io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(stream, "w") as archive:
                    for name, content in members.items():
                        info = zipfile.ZipInfo(name)
                        if mode == "symlink" and name.startswith("sources/"):
                            info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        archive.writestr(info, content)
                    if mode == "duplicate":
                        archive.writestr("project.json", members["project.json"])
            self.assertEqual(self.import_file(stream.getvalue()).status_code, 422)
        self.assertFalse((self.root / "escape").exists())
        self.assertEqual(list(PlanningStore(self.second).root.glob("*.json")), [])

    def test_size_budgets_and_malformed_archives_are_bounded(self):
        data = self.export(self.make_project()); self.active = self.second
        for field in ("MAX_BUNDLE", "MAX_EXPANDED", "MAX_MANIFEST", "MAX_PROJECT", "MAX_SOURCE"):
            with self.subTest(field=field), patch.object(bundle, field, 10):
                response = self.import_file(data)
                self.assertIn(response.status_code, (413, 422))
        for value in (b"not zip", data[:30], b""):
            self.assertIn(self.import_file(value).status_code, (413, 422))
        members = unpack(data)
        for index in range(40):
            members[f"sources/{index:064x}.bin"] = b"x"
        self.assertEqual(self.import_file(repack(members)).status_code, 422)

    def test_bundle_export_revision_signoff_and_read_only_gates(self):
        project = self.make_project(); data = self.export(project)
        path = PlanningStore(self.first)._path(project["id"]); before = path.read_bytes()
        route = f"/projects/{project['id']}/export"
        self.assertEqual(self.post(route, {"expected_revision": project["revision"], "confirmation": ""}).status_code, 403)
        self.assertEqual(self.post(route, {"expected_revision": project["revision"] - 1, "confirmation": api.cad.CONFIRMATION}).status_code, 409)
        self.assertEqual(self.post(route, {"confirmation": api.cad.CONFIRMATION}).status_code, 422)
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            self.assertEqual(self.post(route, {"expected_revision": project["revision"], "confirmation": api.cad.CONFIRMATION}).status_code, 403)
            self.assertEqual(self.import_file(data).status_code, 403)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.import_file(data, headers={"Origin": "https://other.invalid"}).status_code, 403)

    def test_legacy_missing_original_is_explicit_and_hash_matched_repair_is_atomic(self):
        legacy = self.make_project(with_original=False)
        self.assertFalse(legacy["bundle_status"]["complete"])
        self.assertEqual(legacy["bundle_status"]["missing_sources"], [{"filename": "synthetic-original.json", "sha256": self.sha}])
        data = self.export(legacy)
        self.assertEqual(len(unpack(data)), 2)
        self.active = self.second
        response = self.import_file(data)
        self.assertEqual(response.status_code, 200, response.text)
        copied = response.json()["project"]
        self.assertFalse(copied["bundle_status"]["complete"])
        path = PlanningStore(self.second)._path(copied["id"]); before = path.read_bytes()
        route = api.BASE + f"/projects/{copied['id']}/source?expected_revision={copied['revision']}"
        bad = self.client.post(route, files={"file": ("wrong.json", b"different")})
        self.assertEqual(bad.status_code, 422, bad.text); self.assertEqual(path.read_bytes(), before)
        stale = self.client.post(route.replace(f"={copied['revision']}", "=1"), files={"file": ("original.json", self.raw)})
        self.assertEqual(stale.status_code, 409, stale.text); self.assertEqual(path.read_bytes(), before)
        good = self.client.post(route, files={"file": ("renamed-original.json", self.raw)})
        self.assertEqual(good.status_code, 200, good.text)
        fixed = good.json()["project"]
        self.assertTrue(fixed["bundle_status"]["complete"])
        self.assertEqual(fixed["revision"], copied["revision"] + 1)
        self.assertEqual(fixed["result"], copied["result"])
        self.assertEqual(unpack(self.export(fixed))[f"sources/{self.sha}.bin"], self.raw)

    def test_import_cancel_before_commit_writes_no_project(self):
        from demo.projects import _write_atomic
        data = self.export(self.make_project()); self.active = self.second
        def interrupted(path, text, **kwargs):
            def stop():
                raise RunCancelled("synthetic pre-commit cancel")
            return _write_atomic(path, text, before_replace=stop)
        with patch("demo.projects._write_atomic", side_effect=interrupted):
            reply = self.import_file(data)
        self.assertEqual(reply.status_code, 499, reply.text)
        self.assertEqual(list(PlanningStore(self.second).root.glob("*.json")), [])
        self.assertEqual(list(PlanningStore(self.second).root.glob("*.tmp")), [])

    def test_import_cancel_after_commit_reports_success_with_usable_caches(self):
        from demo.projects import _write_atomic
        data = self.export(self.make_project()); self.active = self.second
        operation = "b" * 32
        def committed(path, text, **kwargs):
            _write_atomic(path, text, **kwargs)
            self.assertTrue(api.cad.cancel_import(operation)["was_running"])
        with patch("demo.projects._write_atomic", side_effect=committed):
            reply = self.import_file(data, headers={"X-CAD-Operation-ID": operation})
        self.assertEqual(reply.status_code, 200, reply.text)
        project = reply.json()["project"]
        self.assertEqual(api.RUNS.get(reply.json()["run_id"])["result"]["duration_workdays"], 11)
        self.assertEqual(api.IMPORTS.get(project["source_id"])["source_file"]["size"], len(self.raw))
        self.assertEqual(PlanningStore(self.second).open(project["id"])["revision"], project["revision"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
