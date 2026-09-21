"""Persistent CAD acceptance: atomic recipes, optimistic revisions and portable ZIPs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import trimesh
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import cad_api
from packing_assistant.cad3d.geometry import inspect_dxf, build_model, export_glb
from packing_assistant.cad3d.projects import CadProjectStore, ProjectConflict
from scripts.test_cad_api import fixture, config


class CadProjectCase(unittest.TestCase):
    def setUp(self):
        (ROOT / "output").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="cad-project-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = CadProjectStore(self.base / "projects")
        self.source = fixture()
        self.doc = inspect_dxf(self.source, "original.dxf")
        self.cfg = config()
        self.model = self.build(self.cfg)
        self.env = patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write"})
        self.env.start(); self.addCleanup(self.env.stop)

    def build(self, cfg):
        model = build_model(self.doc, cfg)
        model["source"] = {key: self.doc[key] for key in ("filename", "sha256", "units")}
        return model

    def save(self, **kw):
        args = dict(name="有孔建筑", document=self.doc, source=self.source, draft_config=self.cfg, model=self.model)
        args.update(kw)
        return self.store.save(**args)

    def rewrite_bundle(self, bundle, mutate=None, source=None, extra=None):
        with zipfile.ZipFile(io.BytesIO(bundle)) as z:
            manifest = json.loads(z.read("manifest.json"))
            drawing = z.read("drawing.dxf") if source is None else source
        if mutate: mutate(manifest)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("manifest.json", json.dumps(manifest))
            z.writestr("drawing.dxf", drawing)
            if extra: z.writestr(*extra)
        return out.getvalue()


class ProjectTests(CadProjectCase):
    def test_reopen_in_fresh_process_preserves_source_and_holes(self):
        saved = self.save()
        code = "from pathlib import Path; import json,sys; from packing_assistant.cad3d.projects import CadProjectStore; s=CadProjectStore(Path(sys.argv[1])).open(sys.argv[2]); print(json.dumps(s))"
        run = subprocess.run([sys.executable, "-c", code, str(self.store.root), saved["id"]], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
        restored = json.loads(run.stdout)
        self.assertEqual(restored["model"], self.model)
        self.assertEqual(self.store.source(saved["id"]), self.source)
        self.assertTrue(restored["confirmation_reset"])
        scene = trimesh.load(io.BytesIO(export_glb(restored["model"])), file_type="glb", force="scene")
        self.assertAlmostEqual(sum(abs(m.volume) for m in scene.geometry.values()), 5.25, places=5)
        self.assertTrue(all(m.is_watertight for m in scene.geometry.values()))

    def test_draft_and_failed_generation_keep_last_model(self):
        saved = self.save()
        draft = deepcopy(self.cfg); draft["parameters"]["wall"]["height_m"] = None
        updated = self.store.update(saved["id"], expected_revision=1, draft_config=draft)
        with self.assertRaises(ValueError): self.build(draft)
        restored = self.store.open(saved["id"])
        self.assertEqual(updated["revision"], 2)
        self.assertEqual(len(updated["versions"]), 1)
        self.assertIsNone(restored["draft_config"]["parameters"]["wall"]["height_m"])
        self.assertEqual(restored["model"], self.model)

    def test_new_incomplete_draft_can_be_reopened_without_model(self):
        draft = deepcopy(self.cfg); draft.update(unit="", confirmed_solid=False)
        draft["parameters"]["wall"]["height_m"] = None
        saved = self.save(draft_config=draft, model=None)
        restored = self.store.open(saved["id"])
        self.assertNotIn("model", restored)
        self.assertEqual(restored["draft_config"], draft)

    def test_versions_and_old_version_restore_do_not_rewrite_history(self):
        saved = self.save()
        cfg = deepcopy(self.cfg); cfg["parameters"]["wall"]["height_m"] = 3.6
        changed = self.store.update(saved["id"], expected_revision=1, draft_config=cfg, model=self.build(cfg))
        prior = self.store.open(saved["id"], version=1)
        self.assertEqual(prior["project"]["revision"], 2)
        self.assertEqual(prior["applied_config"]["parameters"]["wall"]["height_m"], 3)
        self.assertEqual(changed["versions"][1]["version"], 2)
        restored = self.store.update(saved["id"], expected_revision=2, draft_config=prior["applied_config"], model=prior["model"])
        self.assertEqual(len(restored["versions"]), 3)

    def test_repeated_model_save_does_not_duplicate_version(self):
        saved = self.save()
        same = self.save(project_id=saved["id"], expected_revision=1)
        self.assertEqual(len(same["versions"]), 1)
        self.assertEqual(same["revision"], 2)

    def test_concurrent_revision_writes_have_one_winner(self):
        saved = self.save()
        def writer(height):
            cfg = deepcopy(self.cfg); cfg["parameters"]["wall"]["height_m"] = height
            try:
                return CadProjectStore(self.store.root).update(saved["id"], expected_revision=1, draft_config=cfg)
            except ProjectConflict:
                return "conflict"
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(writer, (4, 5)))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.open(saved["id"])["project"]["revision"], 2)

    def test_save_interruption_preserves_old_manifest_and_cleans_temp(self):
        saved = self.save()
        path = self.store.root / saved["id"] / "project.json"
        original = path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError): self.save(project_id=saved["id"], expected_revision=1)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])
        self.assertEqual(self.store.open(saved["id"])["model"], self.model)

    def test_cancel_during_flush_does_not_publish_new_revision(self):
        from packing_assistant.runtime import cancel
        saved = self.save()
        path = self.store.root / saved["id"] / "project.json"
        original = path.read_bytes(); event = threading.Event()
        fsync = os.fsync
        def cancel_after_flush(fd):
            fsync(fd); event.set()
        with cancel.scope(event=event), patch("demo.projects.os.fsync", side_effect=cancel_after_flush):
            with self.assertRaises(cancel.RunCancelled): self.save(project_id=saved["id"], expected_revision=1)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_import_in_other_store_is_new_identity_and_rebuilds_same_geometry(self):
        saved = self.save()
        bundle = self.store.export_bundle(saved["id"], 1)
        other = CadProjectStore(self.base / "colleague")
        imported = other.import_bundle(bundle)
        self.assertNotEqual(imported["project"]["id"], saved["id"])
        self.assertEqual(imported["project"]["revision"], 1)
        self.assertTrue(imported["confirmation_reset"])
        self.assertEqual(imported["model"], self.model)
        self.assertEqual(other.source(imported["project"]["id"]), self.source)

    def test_project_export_rejects_stale_revision(self):
        saved = self.save()
        self.store.update(saved["id"], expected_revision=1, draft_config=self.cfg)
        with self.assertRaises(ProjectConflict): self.store.export_bundle(saved["id"], 1)

    def test_corrupt_bundle_checksum_paths_duplicates_and_approvals_rejected(self):
        saved = self.save(); bundle = self.store.export_bundle(saved["id"])
        variants = [b"bad zip", self.rewrite_bundle(bundle, source=b"wrong drawing"),
                    self.rewrite_bundle(bundle, extra=("../outside", "bad")),
                    self.rewrite_bundle(bundle, mutate=lambda x: x.update(approved=True)),
                    self.rewrite_bundle(bundle, mutate=lambda x: x["draft_config"].update(unit={})),
                    self.rewrite_bundle(bundle, mutate=lambda x: x["source"].update(filename="a" * 201 + ".dxf")),
                    self.rewrite_bundle(bundle, mutate=lambda x: x["source"].update(filename="../drawing.dxf")),
                    self.rewrite_bundle(bundle, mutate=lambda x: x.update(versions=[{}]))]
        for payload in variants:
            with self.subTest(payload=payload[:20]):
                with self.assertRaises(ValueError): self.store.import_bundle(payload)
                self.assertEqual(len(self.store.list_projects()), 1)
        self.assertFalse((self.base / "outside").exists())

    def test_zip_symlink_rejected(self):
        out = io.BytesIO(); entry = zipfile.ZipInfo("drawing.dxf"); entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("manifest.json", "{}"); z.writestr(entry, "../elsewhere")
        with self.assertRaises(ValueError): self.store.import_bundle(out.getvalue())
        self.assertEqual(self.store.list_projects(), [])

    def test_corrupt_local_record_remains_visible_and_is_not_overwritten(self):
        saved = self.save(); path = self.store.root / saved["id"] / "project.json"
        for payload in (b"[]", b"{}", b"not json", b"[" * 1200 + b"]" * 1200):
            path.write_bytes(payload)
            self.assertIn("error", self.store.list_projects()[0])
            with self.assertRaises(ValueError): self.save(project_id=saved["id"], expected_revision=1)
            self.assertEqual(path.read_bytes(), payload)

    def test_original_cannot_be_replaced_or_mismatched_with_model(self):
        saved = self.save()
        different = fixture(invalid=True); document = inspect_dxf(different, "changed.dxf")
        with self.assertRaises(ValueError):
            self.save(project_id=saved["id"], expected_revision=1, source=different, document=document, model=None)
        cfg = deepcopy(self.cfg); cfg["parameters"]["wall"]["height_m"] = 4
        with self.assertRaises(ValueError): self.save(draft_config=cfg)
        self.assertEqual(self.store.source(saved["id"]), self.source)

    def test_invalid_ids_unknown_config_and_readonly_never_write(self):
        for bad in ("../elsewhere", "C:\\outside", "g" * 32, ""):
            with self.assertRaises(ValueError): self.store.open(bad)
        for change in ({"layers": {"WALL": {}}}, {"unit": []}, {"overrides": {"unknown": {"height_m": 2}}}):
            with self.assertRaises(ValueError): self.save(draft_config={**self.cfg, **change})
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            with self.assertRaises(PermissionError): self.save()
        self.assertEqual(self.store.list_projects(), [])


class ProjectHTTPTests(CadProjectCase):
    def setUp(self):
        super().setUp()
        for field, value in (("project_store", lambda: self.store), ("DOCUMENTS", cad_api.MemoryStore()), ("MODELS", cad_api.MemoryStore())):
            mock = patch.object(cad_api, field, value); mock.start(); self.addCleanup(mock.stop)
        app = FastAPI(); app.include_router(cad_api.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def uploaded(self):
        response = self.client.post("/api/cad/import", files={"file": ("original.dxf", self.source)})
        self.assertEqual(response.status_code, 200, response.text)
        source = response.json()
        model = self.client.post("/api/cad/build", json={"document_id": source["document_id"], "config": self.cfg})
        self.assertEqual(model.status_code, 200, model.text)
        return {"name": "HTTP 项目", "document_id": source["document_id"], "config": self.cfg, "model_id": model.json()["model_id"]}

    def test_http_restart_recovery_build_export_and_import(self):
        request = self.uploaded()
        saved = self.client.post("/api/cad/projects", json=request)
        self.assertEqual(saved.status_code, 200, saved.text)
        project = saved.json()["project"]; pid = project["id"]
        cad_api.DOCUMENTS._items.clear(); cad_api.MODELS._items.clear()
        opened = self.client.get("/api/cad/projects/" + pid)
        self.assertEqual(opened.status_code, 200, opened.text)
        snapshot = opened.json()
        self.assertNotIn("_source_b64", snapshot["document"])
        self.assertEqual(snapshot["model"], self.model)
        built = self.client.post("/api/cad/build", json={"document_id": snapshot["document_id"], "config": self.cfg})
        self.assertEqual(built.status_code, 200, built.text)
        denied = self.client.post(f"/api/cad/projects/{pid}/export", json={"confirmation": "", "expected_revision": 1})
        self.assertEqual(denied.status_code, 403)
        exported = self.client.post(f"/api/cad/projects/{pid}/export", json={"confirmation": cad_api.CONFIRMATION, "expected_revision": 1})
        self.assertEqual(exported.status_code, 200, exported.text[:80])
        imported = self.client.post("/api/cad/projects/import", files={"file": ("project.zip", exported.content)})
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertNotEqual(imported.json()["project"]["id"], pid)
        self.assertTrue(imported.json()["confirmation_reset"])
        self.assertEqual(imported.json()["model"], snapshot["model"])
        self.assertEqual(len(self.client.get("/api/cad/projects").json()["projects"]), 2)

    def test_http_conflicts_expiration_and_invalid_package(self):
        request = self.uploaded(); response = self.client.post("/api/cad/projects", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        pid = response.json()["project"]["id"]
        request.update(project_id=pid, expected_revision=1)
        self.assertEqual(self.client.post("/api/cad/projects", json=request).status_code, 200)
        self.assertEqual(self.client.post("/api/cad/projects", json=request).status_code, 409)
        self.assertEqual(self.client.post(f"/api/cad/projects/{pid}/export", json={"confirmation": cad_api.CONFIRMATION, "expected_revision": 1}).status_code, 409)
        self.assertEqual(self.client.get(f"/api/cad/projects/{pid}?version=99").status_code, 404)
        self.assertEqual(self.client.post("/api/cad/projects/import", files={"file": ("bad.zip", b"no")}).status_code, 422)
        cad_api.DOCUMENTS._items.clear()
        self.assertEqual(self.client.post("/api/cad/projects", json=request).status_code, 410)
        self.assertEqual(self.store.open(pid)["project"]["revision"], 2)

    def test_huge_integer_returns_validation_error_instead_of_server_error(self):
        request = self.uploaded(); request.pop("model_id")
        request["config"]["parameters"]["wall"]["height_m"] = 10 ** 400
        response = self.client.post("/api/cad/projects", json=request)
        self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post("/api/cad/build", json={key: request[key] for key in ("document_id", "config")})
        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
