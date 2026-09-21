"""Real in-memory DXF -> HTTP -> edited geometry -> reopened GLB acceptance."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import ezdxf
import trimesh
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import cad_api


def fixture(*, unit=4, invalid=False) -> bytes:
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = unit
    drawing.layers.new("WALL")
    drawing.layers.new("COLUMN")
    model = drawing.modelspace()
    model.add_lwpolyline([(1000, 2000), (3000, 2000), (3000, 3000), (1000, 3000)], close=not invalid, dxfattribs={"layer": "WALL"})
    model.add_lwpolyline([(1500, 2250), (2500, 2250), (2500, 2750), (1500, 2750)], close=True, dxfattribs={"layer": "WALL"})
    model.add_lwpolyline([(4000, 2000), (4500, 2000), (4500, 2500), (4000, 2500)], close=True, dxfattribs={"layer": "COLUMN"})
    buffer = io.StringIO()
    drawing.write(buffer)
    return buffer.getvalue().encode("utf-8")


def config(mode="building") -> dict:
    return {"mode": mode, "unit": "mm", "layers": {"WALL": "wall", "COLUMN": "column"} if mode == "building" else {"WALL": "section", "COLUMN": "ignore"},
            "parameters": {"wall": {"height_m": 3.0, "base_m": 0.0}, "column": {"height_m": 3.0, "base_m": 0.0}} if mode == "building" else {"section": {"height_m": 6.0, "base_m": 0.0}},
            "overrides": {}, "confirmed_solid": True}


class CadAPITests(unittest.TestCase):
    def setUp(self):
        self.documents = patch.object(cad_api, "DOCUMENTS", cad_api.MemoryStore())
        self.models = patch.object(cad_api, "MODELS", cad_api.MemoryStore())
        self.documents.start(); self.models.start()
        self.addCleanup(self.documents.stop); self.addCleanup(self.models.stop)
        app = FastAPI()
        app.include_router(cad_api.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def upload(self, **kwargs):
        response = self.client.post("/api/cad/import", files={"file": ("geometry.dxf", fixture(**kwargs), "application/dxf")})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def build(self, document_id, params=None):
        response = self.client.post("/api/cad/build", json={"document_id": document_id, "config": params or config()})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_build_edit_export_reopen_preserves_hole_and_dimensions(self):
        source = self.upload()
        initial = self.build(source["document_id"])
        wall = next(obj for obj in initial["model"]["objects"] if obj["role"] == "wall")
        self.assertAlmostEqual(wall["volume_m3"], 4.5)
        command = self.client.post("/api/cad/command", json={"document_id": source["document_id"], "config": config(), "message": "把墙高改成3.6米"})
        self.assertEqual(command.status_code, 200, command.text)
        updated = self.build(source["document_id"], command.json()["config"])
        for obj in updated["model"]["objects"]:
            self.assertAlmostEqual(obj["parameters"]["height_m"], 3.6 if obj["role"] == "wall" else 3.0)
        exported = self.client.post("/api/cad/export", json={"model_id": updated["model_id"], "confirmation": cad_api.CONFIRMATION, "format": "zip"})
        self.assertEqual(exported.status_code, 200, exported.text[:100] if not exported.is_success else "")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            params = json.loads(archive.read("cad-parameters.json"))
            self.assertEqual(params["source"]["sha256"], source["document"]["sha256"])
            self.assertIn("transform", params)
            scene = trimesh.load(io.BytesIO(archive.read("cad-preview.glb")), file_type="glb", force="scene")
        self.assertEqual(len(scene.geometry), 2)
        self.assertAlmostEqual(sum(abs(mesh.volume) for mesh in scene.geometry.values()), 6.15, places=5)
        self.assertAlmostEqual(scene.bounds[1][1] - scene.bounds[0][1], 3.6, places=5)

    def test_section_export_is_a_real_hollow_mesh(self):
        doc = self.upload()
        model = self.build(doc["document_id"], config("section"))
        obj = model["model"]["objects"][0]
        self.assertAlmostEqual(obj["volume_m3"], 9.0)
        response = self.client.post("/api/cad/export", json={"model_id": model["model_id"], "confirmation": cad_api.CONFIRMATION, "format": "glb"})
        self.assertEqual(response.content[:4], b"glTF")
        scene = trimesh.load(io.BytesIO(response.content), file_type="glb", force="scene")
        self.assertTrue(all(mesh.is_watertight for mesh in scene.geometry.values()))
        self.assertAlmostEqual(scene.extents[1], 6.0, places=5)

    def test_import_does_not_generate_or_export(self):
        self.upload()
        self.assertEqual(len(cad_api.MODELS._items), 0)

    def test_shipped_page_and_both_examples(self):
        page = self.client.get("/cad")
        self.assertEqual(page.status_code, 200)
        self.assertIn("cad.js", page.text)
        self.assertEqual(page.headers["cache-control"], "no-cache")
        for mode in ("building", "section"):
            response = self.client.get("/api/cad/examples/" + mode)
            self.assertEqual(response.status_code, 200)
            imported = self.client.post("/api/cad/import", files={"file": (mode + ".dxf", response.content)})
            self.assertEqual(imported.status_code, 200, imported.text)
            self.assertTrue(imported.json()["document"]["entities"])

    def test_missing_units_never_fall_back_to_mm(self):
        doc = self.upload(unit=0)
        params = config(); params["unit"] = ""
        response = self.client.post("/api/cad/build", json={"document_id": doc["document_id"], "config": params})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(cad_api.MODELS._items), 0)

    def test_manual_upload_only_requires_dimensions_of_mapped_roles(self):
        doc = self.upload()
        params = config()
        params["layers"]["COLUMN"] = "ignore"
        for role in ("column", "slab", "section"):
            params["parameters"][role] = {"height_m": None, "base_m": 0}
        model = self.build(doc["document_id"], params)
        self.assertEqual({obj["role"] for obj in model["model"]["objects"]}, {"wall"})

    def test_solid_confirmation_requires_boolean_true(self):
        doc = self.upload()
        for value in (False, "true", "false", 1, None):
            with self.subTest(value=value):
                params = config(); params["confirmed_solid"] = value
                response = self.client.post("/api/cad/build", json={"document_id": doc["document_id"], "config": params})
                self.assertEqual(response.status_code, 422, response.text)

    def test_export_confirmation_cannot_be_coerced(self):
        doc = self.upload(); model = self.build(doc["document_id"])
        for value in ("", True, "我明白", cad_api.CONFIRMATION + " "):
            response = self.client.post("/api/cad/export", json={"model_id": model["model_id"], "confirmation": value})
            self.assertIn(response.status_code, (403, 422))

    def test_invalid_layer_is_reported_and_other_layer_can_build(self):
        doc = self.upload(invalid=True)
        result = self.build(doc["document_id"])
        self.assertEqual({obj["role"] for obj in result["model"]["objects"]}, {"column"})
        self.assertTrue(any(item["status"] == "failed" for item in result["model"]["report"]))

    def test_empty_model_is_not_success(self):
        doc = self.upload(invalid=True)
        params = config(); params["layers"]["COLUMN"] = "ignore"
        response = self.client.post("/api/cad/build", json={"document_id": doc["document_id"], "config": params})
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json()["detail"]["report"])
        self.assertEqual(len(cad_api.MODELS._items), 0)

    def test_unknown_commands_and_injected_vertices_do_not_change_cache(self):
        doc = self.upload(); model = self.build(doc["document_id"])
        response = self.client.post("/api/cad/command", json={"document_id": doc["document_id"], "config": config(), "message": "墙高现在是多少？"})
        self.assertEqual(response.status_code, 422)
        injected = self.client.post("/api/cad/build", json={"document_id": doc["document_id"], "config": config(), "document": {"vertices": [[100, 100]]}})
        self.assertEqual(injected.status_code, 422)
        self.assertEqual(cad_api.MODELS.get(model["model_id"]), model["model"])

    def test_format_filename_and_unparseable_bytes(self):
        for name, payload, status in [("x.dwg", b"AC1032", 415), ("x.dxf", b"bad", 422), ("x.dxf", b"", 422)]:
            response = self.client.post("/api/cad/import", files={"file": (name, payload)})
            self.assertEqual(response.status_code, status, response.text)
        response = self.client.post("/api/cad/import", files={"file": ("../../private.DXF", fixture())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document"]["filename"], "private.DXF")

    def test_unknown_and_expired_ids(self):
        response = self.client.post("/api/cad/build", json={"document_id": "a" * 32, "config": config()})
        self.assertEqual(response.status_code, 410)
        for key in ("../../secret", "", "a" * 33):
            response = self.client.post("/api/cad/build", json={"document_id": key, "config": config()})
            self.assertEqual(response.status_code, 422)

    def test_request_limits_before_parsing(self):
        with patch.object(cad_api, "MAX_UPLOAD_BYTES", 32):
            response = self.client.post("/api/cad/import", files={"file": ("large.dxf", b"x" * 100000)})
            self.assertEqual(response.status_code, 413)
        response = self.client.post("/api/cad/build", content=b"x" * (cad_api.MAX_JSON_BYTES + 1))
        self.assertEqual(response.status_code, 413)

    def test_uploads_do_not_spill_to_disk(self):
        import tempfile
        spools = []
        def spool(*args, **kwargs):
            value = tempfile.SpooledTemporaryFile(*args, **kwargs)
            spools.append(value)
            return value
        with patch("starlette.formparsers.SpooledTemporaryFile", side_effect=spool):
            response = self.client.post("/api/cad/import", files={"file": ("large.dxf", b"x" * (2 * 1024 * 1024))})
        self.assertEqual(response.status_code, 422)
        self.assertTrue(spools)
        self.assertTrue(all(not file._rolled and file.closed for file in spools))

    def test_missing_or_malformed_multipart_is_a_client_error(self):
        for headers, body in (
            ({}, b""),
            ({"Content-Type": "application/json"}, b"{}"),
            ({"Content-Type": "multipart/form-data"}, b""),
            ({"Content-Type": "multipart/form-data; boundary=x"}, b"--x\r\nbad\r\n\r\nhi\r\n--x--"),
        ):
            with self.subTest(headers=headers):
                response = self.client.post("/api/cad/import", headers=headers, content=body)
                self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(len(cad_api.DOCUMENTS._items), 0)

    def test_malformed_later_part_closes_an_already_open_file(self):
        import tempfile
        spools = []
        def spool(*args, **kwargs):
            value = tempfile.SpooledTemporaryFile(*args, **kwargs)
            spools.append(value)
            return value
        body = (b'--x\r\nContent-Disposition: form-data; name="file"; filename="x.dxf"\r\n\r\ndata'
                b'\r\n--x\r\nbad\r\n\r\ndata\r\n--x--')
        with patch("starlette.formparsers.SpooledTemporaryFile", side_effect=spool):
            response = self.client.post("/api/cad/import", content=body, headers={"Content-Type": "multipart/form-data; boundary=x"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(spools)
        self.assertTrue(all(file.closed for file in spools))

    def test_cross_origin_is_rejected(self):
        response = self.client.post("/api/cad/import", files={"file": ("x.dxf", fixture())}, headers={"Origin": "https://other.invalid"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get("/api/cad/capabilities", headers={"Origin": "http://testserver"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/cad/capabilities", headers={"Origin": "http://["})
        self.assertEqual(response.status_code, 403)

    def test_nonfinite_json_is_rejected_in_untouched_fields(self):
        doc = self.upload()
        body = {"document_id": doc["document_id"], "config": config(), "message": "墙高3米"}
        body["config"]["parameters"]["column"]["base_m"] = float("nan")
        for constant in ("NaN", "Infinity", "-Infinity", "1e9999"):
            response = self.client.post("/api/cad/command", content=json.dumps(body).replace("NaN", constant), headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 422, response.text)

    def test_missing_optional_dependencies_leave_page_available(self):
        with patch.object(cad_api.importlib.util, "find_spec", return_value=None):
            response = self.client.get("/api/cad/capabilities")
            self.assertFalse(response.json()["available"])
            response = self.client.post("/api/cad/import", files={"file": ("x.dxf", fixture())})
            self.assertEqual(response.status_code, 503)

    def test_bounded_immutable_cache_and_ttl(self):
        store = cad_api.MemoryStore(max_items=1, max_bytes=1000)
        value = {"x": [1]}; first = store.put(value); value["x"].append(2)
        read = store.get(first); read["x"].append(3)
        self.assertEqual(store.get(first), {"x": [1]})
        store.put({"y": []})
        with self.assertRaises(cad_api.HTTPException):
            store.get(first)
        with self.assertRaises(ValueError):
            store.put({"oversize": "x" * 2000})
        expired = cad_api.MemoryStore(ttl=-1); key = expired.put({})
        with self.assertRaises(cad_api.HTTPException):
            expired.get(key)


if __name__ == "__main__":
    unittest.main()
