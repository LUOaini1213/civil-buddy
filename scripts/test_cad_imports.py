"""Offline bounded staged imports, source evidence, cancellation and HTTP checks.

Optional real acceptance: --real-dxf <local DXF>; originals are never copied.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import ezdxf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import cad_api
from packing_assistant.cad3d import imports
from packing_assistant.cad3d.geometry import analyze_document, inspect_dxf
from packing_assistant.runtime import cancel


def bytes_for(drawing):
    stream = io.StringIO()
    drawing.write(stream)
    return stream.getvalue().encode("utf-8")


def fixture(*, dimension=False):
    drawing = ezdxf.new("R2010")
    drawing.units = 4
    drawing.layers.new("SECTION")
    drawing.layers.new("DIM")
    space = drawing.modelspace()
    space.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True, dxfattribs={"layer": "SECTION"})
    space.add_lwpolyline([(25, 25), (75, 25), (75, 75), (25, 75)], close=True, dxfattribs={"layer": "SECTION"})
    if dimension:
        space.add_linear_dim(base=(0, -20), p1=(0, 0), p2=(600, 0), text="600", dxfattribs={"layer": "DIM"}).render()
    return drawing


def blank_config():
    return {"mode": "section", "unit": "mm", "layers": {"SECTION": "section"},
            "parameters": {"section": {}}, "overrides": {}, "confirmed_solid": False}


class ImportCoreTests(unittest.TestCase):
    def test_scan_is_sampled_and_source_hash_is_original(self):
        drawing = fixture()
        for x in range(20): drawing.modelspace().add_line((x, 0), (x, 1))
        source = bytes_for(drawing)
        with patch.object(imports, "MAX_PREVIEW_ENTITIES", 5):
            result = imports.scan_dxf(source, "display.dxf")
        self.assertEqual(result["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(len(result["preview"]), 5)
        self.assertTrue(result["preview_sampled"])
        self.assertTrue(all(row["display_only"] for row in result["preview"]))
        self.assertLessEqual(max(len(row["points"]) for row in result["preview"]), imports.MAX_PREVIEW_POINTS)

    def test_nested_transform_filter_preserves_instance_ids_and_hole(self):
        drawing = ezdxf.new("R2010")
        drawing.units = 4
        drawing.layers.new("SECTION")
        block = drawing.blocks.new("PROFILE")
        outer = block.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
        hole = block.add_circle((5, 5), 2)
        root = drawing.modelspace().add_blockref("PROFILE", (100, 200), dxfattribs={"layer": "SECTION", "rotation": 90, "xscale": 2, "yscale": 2, "zscale": 2})
        drawing.modelspace().add_blockref("PROFILE", (500, 500), dxfattribs={"layer": "SECTION"})
        source = bytes_for(drawing)
        document = inspect_dxf(source, "block.dxf", source_filter={"layers": ["SECTION"], "bounds": [79, 199, 101, 221]})
        selected = document["source_filter_audit"]["selected_entity_ids"]
        self.assertEqual(set(selected), {f"{root.dxf.handle}/{outer.dxf.handle}", f"{root.dxf.handle}/{hole.dxf.handle}"})
        self.assertEqual(document["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(len(document["entities"]), 2)
        self.assertTrue(all(row["status"] == "ready" for row in document["entities"]))

    def test_crossing_entities_are_reported_not_clipped(self):
        drawing = fixture()
        roots, recipe, audit = imports.filter_modelspace(drawing, {"layers": ["SECTION"], "bounds": [20, 20, 80, 80]})
        self.assertEqual(len(roots), 1)
        self.assertEqual(audit["excluded_crossing"], 1)
        self.assertIn("未裁切", audit["excluded"][0]["reason"])
        self.assertEqual(recipe["bounds"], [20, 20, 80, 80])

    def test_region_cannot_turn_a_hole_into_a_solid(self):
        document = inspect_dxf(bytes_for(fixture()), "rings.dxf", source_filter={"layers": ["SECTION"], "bounds": [20, 20, 80, 80]})
        result = analyze_document(document, blank_config())
        self.assertFalse(result["buildable"])
        self.assertTrue(result["diagnostics"])

    def test_array_parent_rejection_is_retained_for_selected_child_layer(self):
        drawing = ezdxf.new()
        drawing.layers.new("SECTION")
        block = drawing.blocks.new("ARRAY")
        block.add_circle((0, 0), 1, dxfattribs={"layer": "SECTION"})
        insert = drawing.modelspace().add_blockref("ARRAY", (0, 0), dxfattribs={"row_count": 2, "row_spacing": 10})
        document = inspect_dxf(bytes_for(drawing), "array.dxf", source_filter={"layers": ["SECTION"]})
        self.assertIn(insert.dxf.handle, document["source_filter_audit"]["selected_entity_ids"])
        self.assertTrue(document["entities"])
        self.assertTrue(any(entity["status"] != "ready" for entity in document["entities"]))

    def test_cached_overview_avoids_expansion_but_selection_has_budget(self):
        drawing = fixture()
        block = drawing.blocks.new("REPEATED")
        block.add_circle((0, 0), 1)
        for x in range(30): drawing.modelspace().add_blockref("REPEATED", (1000+x*10, 0), dxfattribs={"layer": "SECTION"})
        with patch.object(imports, "MAX_SCAN_EXPANDED_ENTITIES", 40):
            result = imports.scan_dxf(bytes_for(drawing), "repeat.dxf")
            self.assertEqual(result["counts"]["expanded"], 32)
            roots, _, audit = imports.filter_modelspace(drawing, {"layers": ["SECTION"], "bounds": [998, -2, 1002, 2]})
            self.assertEqual(len(roots), 1)
            self.assertEqual(audit["selected"], 1)
            with self.assertRaisesRegex(ValueError, "展开"):
                imports.filter_modelspace(drawing, {"layers": ["SECTION"]})

    def test_cached_block_depth_cannot_bypass_limit(self):
        drawing = ezdxf.new()
        for i in range(4):
            block = drawing.blocks.new(f"B{i}")
            if i: block.add_blockref(f"B{i-1}", (0, 0))
            else: block.add_circle((0, 0), 1)
            drawing.modelspace().add_blockref(f"B{i}", (0, 0))
        with patch.object(imports, "MAX_SCAN_BLOCK_DEPTH", 3):
            with self.assertRaisesRegex(ValueError, "嵌套"):
                imports.scan_dxf(bytes_for(drawing), "nested.dxf")

    def test_size_database_and_invalid_input_limits(self):
        source = bytes_for(fixture())
        with patch.object(imports, "MAX_SCAN_BYTES", len(source)-1):
            with self.assertRaises(ValueError): imports.scan_dxf(source, "big.dxf")
        with patch.object(imports, "MAX_SCAN_DATABASE_ENTITIES", 1):
            with self.assertRaisesRegex(ValueError, "数据库"): imports.scan_dxf(source, "many.dxf")
        for data in (b"broken", b"AutoCAD Binary DXF\r\n", b""):
            with self.assertRaises(ValueError): imports.scan_dxf(data, "bad.dxf")
        for recipe in ({"layers": []}, {"layers": ["SECTION"], "value": 2}, {"layers": ["SECTION"], "bounds": [False, 0, 1, 1]}, {"layers": ["SECTION"], "bounds": [0, 0, float("inf"), 1]}, {"layers": ["SECTION"], "bounds": [0, 0, 10**400, 1]}):
            with self.assertRaises(ValueError): imports.normalize_filter(recipe)
        with self.assertRaisesRegex(ValueError, "不存在"):
            imports.filter_modelspace(fixture(), {"layers": ["UNKNOWN"]})

    def test_precancel_does_not_parse_or_cache(self):
        event = Event(); event.set()
        with cancel.scope(event=event), patch("ezdxf.read") as read:
            with self.assertRaises(cancel.RunCancelled): imports.scan_dxf(bytes_for(fixture()), "cancel.dxf")
            with self.assertRaises(cancel.RunCancelled): cad_api.MemoryStore().put({"ok": True})
        read.assert_not_called()


class StagedAPITests(unittest.TestCase):
    def setUp(self):
        for name in ("DOCUMENTS", "IMPORTS", "MODELS"):
            mock = patch.object(cad_api, name, cad_api.MemoryStore(max_bytes=64*1024*1024))
            mock.start(); self.addCleanup(mock.stop)
        app = FastAPI(); app.include_router(cad_api.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def scan(self, data=None, headers=None):
        return self.client.post("/api/cad/import/scan", files={"file": ("source.dxf", data or bytes_for(fixture()), "application/dxf")}, headers=headers)

    def test_scan_select_analyze_without_height_or_model(self):
        response = self.scan(); self.assertEqual(response.status_code, 200, response.text)
        scanned = response.json()
        chosen = self.client.post("/api/cad/import/select", json={"import_id": scanned["import_id"], "layers": ["SECTION"], "bounds": [-1, -1, 101, 101]})
        self.assertEqual(chosen.status_code, 200, chosen.text)
        doc = chosen.json()
        self.assertEqual(doc["document"]["sha256"], scanned["index"]["sha256"])
        analyzed = self.client.post("/api/cad/analyze", json={"document_id": doc["document_id"], "config": blank_config()})
        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        self.assertEqual(len(analyzed.json()["contours"]), 1)
        self.assertEqual(len(analyzed.json()["contours"][0]["hole_ids"]), 1)
        self.assertEqual(len(cad_api.MODELS._items), 0)
        generated = self.client.post("/api/cad/build", json={"document_id": doc["document_id"], "config": blank_config()})
        self.assertEqual(generated.status_code, 422)

    def test_over_ten_mib_uses_stages(self):
        source = bytes_for(fixture())
        marker = b"  0\nEOF\n"
        self.assertTrue(source.endswith(marker))
        source = source[:-len(marker)] + (b"999\n" + b"x"*1024 + b"\n")*11000 + marker
        self.assertGreater(len(source), cad_api.MAX_UPLOAD_BYTES)
        direct = self.client.post("/api/cad/import", files={"file": ("big.dxf", source, "application/dxf")})
        self.assertEqual(direct.status_code, 413)
        scanned = self.scan(source); self.assertEqual(scanned.status_code, 200, scanned.text)
        result = self.client.post("/api/cad/import/select", json={"import_id": scanned.json()["import_id"], "layers": ["SECTION"]})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["document"]["sha256"], hashlib.sha256(source).hexdigest())

    def test_dimension_binding_uses_only_server_evidence(self):
        scanned = self.scan(bytes_for(fixture(dimension=True))).json()
        result = self.client.post("/api/cad/import/select", json={"import_id": scanned["import_id"], "layers": ["SECTION", "DIM"]}).json()
        dimension = result["document"]["dimensions"][0]
        binding = {"dimension_id": dimension["id"], "role": "section", "parameter": "height_m", "value_source": "annotation"}
        body = {"document_id": result["document_id"], "config": blank_config(), "binding": binding}
        response = self.client.post("/api/cad/bind-dimension", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["config"]["parameters"]["section"]["height_m"], .6)
        for extra in ({"value": 100}, {"target_id": result["document"]["entities"][0]["id"]}, {"dimension_id": "unknown"}):
            response = self.client.post("/api/cad/bind-dimension", json={**body, "binding": {**binding, **extra}})
            self.assertEqual(response.status_code, 422, response.text)

    def test_cancel_isolated_and_prevents_publication(self):
        identifier = "a"*32
        entered, resume = Event(), Event()
        actual = imports.scan_dxf
        def delayed(data, filename):
            entered.set()
            if not resume.wait(5): raise AssertionError("test synchronization timeout")
            # Simulate a completed calculation that did not itself checkpoint.
            return {"filename": filename, "sha256": hashlib.sha256(data).hexdigest()}
        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(imports, "scan_dxf", delayed):
            pending = pool.submit(self.scan, headers={"X-CAD-Operation-ID": identifier})
            self.assertTrue(entered.wait(5))
            duplicate = self.scan(headers={"X-CAD-Operation-ID": identifier})
            self.assertEqual(duplicate.status_code, 409)
            cancelled = self.client.post(f"/api/cad/import/{identifier}/cancel")
            self.assertTrue(cancelled.json()["cancelled"])
            with patch.object(imports, "scan_dxf", actual):
                other = self.scan(headers={"X-CAD-Operation-ID": "b"*32})
                self.assertEqual(other.status_code, 200, other.text)
            resume.set()
            self.assertEqual(pending.result(5).status_code, 499)
        self.assertEqual(len(cad_api.IMPORTS._items), 1)
        self.assertNotIn(identifier, cad_api.OPERATIONS)

    def test_select_cancel_after_inspection_does_not_publish_document(self):
        scanned = self.scan().json()
        identifier = "c"*32
        from packing_assistant.cad3d import geometry
        actual = geometry.inspect_dxf
        def interrupted(*args, **kwargs):
            result = actual(*args, **kwargs)
            cad_api.OPERATIONS[identifier].set()
            return result
        with patch.object(geometry, "inspect_dxf", interrupted):
            response = self.client.post("/api/cad/import/select", headers={"X-CAD-Operation-ID": identifier}, json={"import_id": scanned["import_id"], "layers": ["SECTION"]})
        self.assertEqual(response.status_code, 499)
        self.assertEqual(len(cad_api.DOCUMENTS._items), 0)

    def test_cancel_before_upload_processing_still_prevents_scan(self):
        identifier = "e"*32
        response = self.client.post(f"/api/cad/import/{identifier}/cancel")
        self.assertTrue(response.json()["cancelled"])
        with patch.object(imports, "scan_dxf") as scanner:
            response = self.scan(headers={"X-CAD-Operation-ID": identifier})
        self.assertEqual(response.status_code, 499)
        scanner.assert_not_called()
        self.assertEqual(len(cad_api.IMPORTS._items), 0)

    def test_bad_upload_schema_origin_and_expired_scan(self):
        self.assertEqual(self.scan(b"not a drawing").status_code, 422)
        with patch.object(cad_api, "MAX_SCAN_BYTES", 1024):
            self.assertEqual(self.scan().status_code, 413)
        self.assertEqual(len(cad_api.IMPORTS._items), 0)
        self.assertEqual(self.scan(headers={"Origin": "https://foreign.example"}).status_code, 403)
        self.assertEqual(self.scan(headers={"X-CAD-Operation-ID": "bad"}).status_code, 422)
        source = self.scan().json()
        for extra in ({"bounds": [False, 0, 10, 10]}, {"bounds": [0, 0, 10**400, 1]}, {"bounds": [0, 0, 1e13, 1]}, {"vertices": [[0, 0]]}, {"layers": []}):
            body = {"import_id": source["import_id"], "layers": ["SECTION"], **extra}
            self.assertEqual(self.client.post("/api/cad/import/select", json=body).status_code, 422)
        self.assertEqual(self.client.post("/api/cad/import/select", json={"import_id": "f"*32, "layers": ["SECTION"]}).status_code, 410)

    def test_step_export_keeps_signature_gate(self):
        identifier = cad_api.MODELS.put({"objects": []})
        from packing_assistant.cad3d import step
        with patch.object(step, "export_step", return_value=b"ISO-10303-21; END-ISO-10303-21;") as export:
            denied = self.client.post("/api/cad/export", json={"model_id": identifier, "format": "step", "confirmation": "yes"})
            self.assertEqual(denied.status_code, 403); export.assert_not_called()
            response = self.client.post("/api/cad/export", json={"model_id": identifier, "format": "step", "confirmation": cad_api.CONFIRMATION})
            self.assertEqual(response.status_code, 200)
            self.assertIn("application/step", response.headers["content-type"])

    def test_readonly_blocks_all_model_formats_and_project_packages(self):
        identifier = cad_api.MODELS.put({"objects": []})
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}), patch.object(cad_api, "export_model") as export, patch.object(cad_api, "project_store") as store:
            for format in ("step", "glb", "json", "zip"):
                response = self.client.post("/api/cad/export", json={"model_id": identifier, "format": format, "confirmation": cad_api.CONFIRMATION})
                self.assertEqual(response.status_code, 403, response.text)
                self.assertIn("只读", response.json()["detail"])
            response = self.client.post(f"/api/cad/projects/{'a'*32}/export", json={"confirmation": cad_api.CONFIRMATION, "expected_revision": 1})
            self.assertEqual(response.status_code, 403, response.text)
            export.assert_not_called()
            store.assert_not_called()


def real_acceptance(path):
    source = Path(path).read_bytes()
    app = FastAPI(); app.include_router(cad_api.router)
    with TestClient(app) as client:
        scan = client.post("/api/cad/import/scan", files={"file": (Path(path).name, source, "application/dxf")})
        assert scan.status_code == 200, scan.text
        index = scan.json()["index"]
        # These explicit FRAME bounds select a documented small VMU region.
        body = {"import_id": scan.json()["import_id"], "layers": ["FRAME"], "bounds": [-250000, -110000, -230000, -95000]}
        select = client.post("/api/cad/import/select", json=body)
        assert select.status_code == 200, select.text
        result = select.json()
        assert result["document"]["sha256"] == hashlib.sha256(source).hexdigest()
        config = {**blank_config(), "layers": {"FRAME": "section"}}
        analysis = client.post("/api/cad/analyze", json={"document_id": result["document_id"], "config": config})
        assert analysis.status_code == 200, analysis.text
        print(json.dumps({"real_file": Path(path).name, "source_bytes": len(source), "sha256": index["sha256"],
                          "counts": index["counts"], "selected_entities": len(result["document"]["entities"]),
                          "source_filter": result["document"]["source_filter"], "contours": len(analysis.json()["contours"]),
                          "diagnostics": len(analysis.json()["diagnostics"]), "models_created": len(cad_api.MODELS._items)}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--real-dxf": real_acceptance(sys.argv[2])
    else: unittest.main()
