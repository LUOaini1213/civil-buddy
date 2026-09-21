#!/usr/bin/env python3
"""Offline CAD geometry invariants using explicitly synthetic drawing fixtures."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.cad3d import CAD3DError, build_model, export_glb, inspect_dxf
from packing_assistant.cad3d import geometry

HAS_CAD = all(importlib.util.find_spec(name) for name in
              ("ezdxf", "shapely", "trimesh", "mapbox_earcut"))


@unittest.skipUnless(HAS_CAD, "Install requirements-cad.txt to run CAD geometry tests")
class GeometryTests(unittest.TestCase):
    def setUp(self):
        import ezdxf
        self.doc = ezdxf.new("R2010")
        self.doc.units = 4

    def ring(self, layer="SECTION", bounds=(0, 0, 100, 100), kind="LWPOLYLINE"):
        if layer not in self.doc.layers:
            self.doc.layers.new(layer)
        x0, y0, x1, y1 = bounds
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        add = (self.doc.modelspace().add_lwpolyline if kind == "LWPOLYLINE"
               else self.doc.modelspace().add_polyline2d)
        return add(points, close=True, dxfattribs={"layer": layer})

    def inspect(self):
        stream = io.StringIO()
        self.doc.write(stream)
        return inspect_dxf(stream.getvalue().encode("utf-8"), "synthetic-test.dxf")

    def config(self, **changes):
        config = {"mode": "section", "unit": "mm", "confirmed_solid": True,
                  "layers": {"SECTION": "section"},
                  "parameters": {"section": {"height_m": 2, "base_m": 0}},
                  "overrides": {}}
        config.update(changes)
        return config

    def test_hollow_section_volume_dimensions_and_reopened_glb(self):
        import trimesh
        outer = self.ring()
        inner = self.ring(bounds=(10, 10, 90, 90))
        doc = self.inspect()
        model = build_model(doc, self.config())
        self.assertEqual(doc["units"], {"code": 4, "name": "mm", "meters_per_unit": 0.001})
        self.assertEqual(len(model["objects"]), 1)
        obj = model["objects"][0]
        self.assertEqual(obj["source_entity_ids"], [outer.dxf.handle, inner.dxf.handle])
        self.assertEqual(obj["hole_count"], 1)
        self.assertAlmostEqual(obj["volume_m3"], 0.0072, places=12)
        self.assertEqual(obj["bounds"], {"min": [0, 0, 0], "max": [0.1, 0.1, 2]})
        glb = export_glb(model)
        self.assertEqual(glb[:4], b"glTF")
        scene = trimesh.load(io.BytesIO(glb), file_type="glb", force="scene")
        self.assertEqual(len(scene.geometry), 1)
        reopened = next(iter(scene.geometry.values()))
        self.assertTrue(reopened.is_watertight)
        self.assertAlmostEqual(reopened.volume, 0.0072, places=8)
        self.assertAlmostEqual(scene.extents[0], 0.1, places=6)
        self.assertAlmostEqual(scene.extents[1], 2, places=6)
        self.assertAlmostEqual(scene.extents[2], 0.1, places=6)
        # Test top cap triangles actually exclude the hole; volume alone could
        # miss an incorrectly capped inner void compensated by inward side faces.
        from shapely.geometry import Polygon
        void = Polygon([(0.01, 0.01), (0.09, 0.01), (0.09, 0.09), (0.01, 0.09)])
        vertices = obj["vertices"]
        for face in obj["faces"]:
            triangle = [vertices[index] for index in face]
            if all(abs(p[2] - 2) < 1e-9 for p in triangle):
                self.assertLess(Polygon([p[:2] for p in triangle]).intersection(void).area, 1e-12)
        chunk_length, chunk_type = struct.unpack("<II", glb[12:20])
        self.assertEqual(chunk_type, 0x4E4F534A)
        header = json.loads(glb[20:20 + chunk_length])
        self.assertEqual(header["meshes"][0]["extras"]["source_entity_ids"], obj["source_entity_ids"])
        json.dumps(model, allow_nan=False)

    def test_mm_and_m_have_identical_geometry(self):
        self.ring(bounds=(0, 0, 1000, 2000))
        mm = self.inspect()
        metre = copy.deepcopy(mm)
        for entity in metre["entities"]:
            entity["points"] = [[x / 1000, y / 1000] for x, y in entity["points"]]
        first = build_model(mm, self.config())["objects"][0]
        second = build_model(metre, self.config(unit="m"))["objects"][0]
        self.assertEqual(first["vertices"], second["vertices"])
        self.assertEqual(first["faces"], second["faces"])
        self.assertEqual(first["volume_m3"], second["volume_m3"])

    def test_other_confirmed_units(self):
        self.ring(bounds=(0, 0, 1, 1))
        for unit, factor in [("cm", 0.01), ("in", 0.0254), ("ft", 0.3048)]:
            with self.subTest(unit=unit):
                obj = build_model(self.inspect(), self.config(unit=unit))["objects"][0]
                self.assertAlmostEqual(obj["volume_m3"], factor ** 2 * 2)

    def test_unknown_source_units_require_confirmation(self):
        self.doc.units = 0
        self.ring()
        document = self.inspect()
        self.assertIsNone(document["units"]["meters_per_unit"])
        for unit in (None, "", "yd"):
            with self.subTest(unit=unit), self.assertRaisesRegex(CAD3DError, "确认图纸单位"):
                build_model(document, self.config(unit=unit))
        self.assertEqual(len(build_model(document, self.config())["objects"]), 1)

    def test_real_cad_offset_is_recorded_and_removed_without_scaling_change(self):
        self.ring(bounds=(500000000, 300000000, 500001000, 300002000))
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["transform"]["origin_source_units"], [500000000, 300000000, 0])
        self.assertEqual(model["objects"][0]["bounds"], {"min": [0, 0, 0], "max": [1, 2, 2]})
        self.assertAlmostEqual(model["objects"][0]["volume_m3"], 4)

    def test_ignored_far_anchor_cannot_flatten_selected_thin_section(self):
        import trimesh
        self.ring(layer="ANCHOR", bounds=(0, 0, 10, 10))
        self.ring(bounds=(999998000, 0, 999998010, 1000))
        config = self.config(layers={"ANCHOR": "ignore", "SECTION": "section"},
                             parameters={"section": {"height_m": 1, "base_m": 0}})
        model = build_model(self.inspect(), config)
        self.assertEqual(model["summary"], {"modeled": 1, "ignored": 1, "failed": 0})
        self.assertEqual(model["transform"]["origin_source_units"], [999998000, 0, 0])
        obj = model["objects"][0]
        self.assertAlmostEqual(obj["volume_m3"], 0.01)
        scene = trimesh.load(io.BytesIO(export_glb(model)), file_type="glb", force="scene")
        reopened = next(iter(scene.geometry.values()))
        self.assertAlmostEqual(reopened.extents[0], 0.01, places=8)
        self.assertAlmostEqual(reopened.volume, 0.01, places=8)

    def test_distant_selected_thin_section_reports_float32_failure(self):
        self.ring(layer="NEAR", bounds=(0, 0, 1000, 1000))
        far = self.ring(bounds=(999998000, 0, 999998010, 1000))
        config = self.config(layers={"NEAR": "section", "SECTION": "section"},
                             parameters={"section": {"height_m": 1, "base_m": 0}})
        for width in (10, 100):
            far.set_points([(999998000, 0), (999998000 + width, 0),
                            (999998000 + width, 1000), (999998000, 1000)])
            with self.subTest(width_mm=width):
                model = build_model(self.inspect(), config)
                self.assertEqual([obj["layer"] for obj in model["objects"]], ["NEAR"])
                self.assertEqual(model["summary"], {"modeled": 1, "ignored": 0, "failed": 1})
                self.assertIn("float32", model["report"][1]["reason"])

    def test_per_object_height_edit_keeps_other_object_byte_identical(self):
        first = self.ring(bounds=(0, 0, 100, 100))
        self.ring(bounds=(200, 0, 300, 100))
        doc = self.inspect()
        model = build_model(doc, self.config())
        config = self.config(overrides={first.dxf.handle: {"height_m": 3.6}})
        changed = build_model(doc, config)
        self.assertEqual(model["objects"][1], changed["objects"][1])
        self.assertEqual(model["transform"], changed["transform"])
        self.assertAlmostEqual(changed["objects"][0]["bounds"]["max"][2], 3.6)
        self.assertEqual(config["overrides"], {first.dxf.handle: {"height_m": 3.6}})

    def test_negative_base_is_preserved(self):
        self.ring()
        config = self.config(parameters={"section": {"height_m": 0.12, "base_m": -0.12}})
        obj = build_model(self.inspect(), config)["objects"][0]
        self.assertAlmostEqual(obj["bounds"]["min"][2], -0.12)
        self.assertAlmostEqual(obj["bounds"]["max"][2], 0)

    def test_nested_island_is_separate_solid_and_hole_is_preserved(self):
        self.ring()
        self.ring(bounds=(10, 10, 90, 90))
        self.ring(bounds=(40, 40, 60, 60))
        model = build_model(self.inspect(), self.config())
        self.assertEqual(len(model["objects"]), 2)
        self.assertAlmostEqual(sum(o["volume_m3"] for o in model["objects"]), 0.008)
        self.assertEqual(model["summary"]["modeled"], 3)

    def test_closed_polyline2d_supported(self):
        self.ring(kind="POLYLINE")
        doc = self.inspect()
        self.assertEqual(doc["entities"][0]["status"], "ready")
        self.assertAlmostEqual(build_model(doc, self.config())["objects"][0]["volume_m3"], 0.02)

    def test_old_polyline_fitted_curves_are_not_control_frame_solids(self):
        polyline = self.ring(kind="POLYLINE")
        for flags, smooth, vertex_flags in ((3, 0, 0), (5, 6, 16), (1, 0, 8)):
            with self.subTest(flags=flags, smooth=smooth, vertex_flags=vertex_flags):
                polyline.dxf.flags = flags
                polyline.dxf.smooth_type = smooth
                for vertex in polyline.vertices:
                    vertex.dxf.flags = vertex_flags
                document = self.inspect()
                self.assertEqual(document["entities"][0]["status"], "unsupported")
                self.assertIn("拟合曲线", document["entities"][0]["reason"])
                self.assertEqual(build_model(document, self.config())["summary"]["failed"], 1)

    def test_open_self_crossing_curved_and_elevated_are_reported(self):
        self.doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10)])
        self.doc.modelspace().add_lwpolyline([(0, 0), (10, 10), (0, 10), (10, 0)], close=True)
        curved = self.ring()
        curved.set_points([(0, 0, 0.5), (100, 0, 0), (100, 100, 0)], format="xyb")
        elevated = self.ring()
        elevated.dxf.elevation = 3
        self.doc.modelspace().add_circle((20, 20), 2)
        self.doc.modelspace().add_line((0, 0), (1, 1))
        doc = self.inspect()
        self.assertEqual([e["status"] for e in doc["entities"]],
                         ["invalid", "invalid", "unsupported", "unsupported", "unsupported", "unsupported"])
        self.assertTrue(all(e["reason"] for e in doc["entities"]))

    def test_nonplanar_tilted_and_width_entities_are_not_projected(self):
        poly = self.ring(kind="POLYLINE")
        poly.vertices[1].dxf.location = (100, 0, 1)
        tilted = self.ring()
        tilted.dxf.extrusion = (0, 1, 0)
        wide = self.ring()
        wide.dxf.const_width = 5
        self.assertEqual([e["status"] for e in self.inspect()["entities"]], ["unsupported"] * 3)

    def test_partial_failures_do_not_hide_missing_hole(self):
        self.ring()
        self.doc.modelspace().add_circle((50, 50), 25, dxfattribs={"layer": "SECTION"})
        self.ring(layer="GOOD", bounds=(200, 0, 300, 100))
        config = self.config(layers={"SECTION": "section", "GOOD": "section"})
        model = build_model(self.inspect(), config)
        self.assertEqual([o["layer"] for o in model["objects"]], ["GOOD"])
        self.assertEqual(model["summary"], {"modeled": 1, "ignored": 0, "failed": 2})

    def test_touching_crossing_and_duplicate_contours_block_layer(self):
        first = self.ring()
        second = self.ring(bounds=(100, 0, 200, 100))
        for points in [[(100, 0), (200, 0), (200, 100), (100, 100)],
                       [(50, 0), (150, 0), (150, 100), (50, 100)],
                       [(0, 0), (100, 0), (100, 100), (0, 100)]]:
            second.set_points(points)
            model = build_model(self.inspect(), self.config())
            self.assertEqual(model["objects"], [])
            self.assertEqual(model["summary"]["failed"], 2)
            self.assertIn("相触", model["report"][0]["reason"])

    def test_hole_override_rejected(self):
        self.ring()
        inner = self.ring(bounds=(10, 10, 90, 90))
        with self.assertRaisesRegex(CAD3DError, "孔洞边界"):
            build_model(self.inspect(), self.config(overrides={inner.dxf.handle: {"height_m": 1}}))

    def test_selected_roles_must_match_mode(self):
        self.ring()
        with self.assertRaisesRegex(CAD3DError, "不支持角色"):
            build_model(self.inspect(), self.config(mode="building"))
        with self.assertRaisesRegex(CAD3DError, "实体材料区域"):
            build_model(self.inspect(), self.config(confirmed_solid=False))

    def test_invalid_parameters_rejected(self):
        self.ring()
        document = self.inspect()
        for height in (None, "3", True, 0, -1, float("nan"), float("inf")):
            with self.subTest(height=height), self.assertRaises(CAD3DError):
                build_model(document, self.config(parameters={"section": {"height_m": height, "base_m": 0}}))
        for base in (None, "0", False, float("inf")):
            with self.subTest(base=base), self.assertRaises(CAD3DError):
                build_model(document, self.config(parameters={"section": {"height_m": 1, "base_m": base}}))
        with self.assertRaisesRegex(CAD3DError, "未知参数"):
            build_model(document, self.config(parameters={"section": {"height_m": 1, "base_m": 0, "scale": 9}}))
        with self.assertRaisesRegex(CAD3DError, "未知图层"):
            build_model(document, self.config(layers={"absent": "section"}))

    def test_inactive_ui_parameter_placeholders_do_not_block_wall_only_model(self):
        self.ring(layer="WALL")
        config = self.config(mode="building", layers={"WALL": "wall"}, parameters={
            "wall": {"height_m": 3, "base_m": 0},
            "column": {"height_m": None, "base_m": 0},
            "slab": {"height_m": None, "base_m": None},
            "section": {"height_m": None, "base_m": 0},
        })
        model = build_model(self.inspect(), config)
        self.assertEqual(len(model["objects"]), 1)
        self.assertEqual(model["config"], config)
        config["parameters"]["section"]["height_m"] = float("inf")
        with self.assertRaisesRegex(CAD3DError, "有限"):
            build_model(self.inspect(), config)

    def test_empty_and_ignored_models_cannot_export(self):
        self.ring()
        model = build_model(self.inspect(), self.config(layers={"SECTION": "ignore"}))
        self.assertEqual(model["summary"]["ignored"], 1)
        with self.assertRaisesRegex(CAD3DError, "没有成功建模"):
            export_glb(model)

    def test_file_entity_vertex_and_layer_limits(self):
        self.ring()
        document = self.inspect()
        with patch.object(geometry, "MAX_DXF_BYTES", 5), self.assertRaisesRegex(CAD3DError, "限制"):
            inspect_dxf(b"123456", "x.dxf")
        with patch.object(geometry, "MAX_ENTITIES", 0), self.assertRaisesRegex(CAD3DError, "实体限制"):
            self.inspect()
        with patch.object(geometry, "MAX_VERTICES", 3), self.assertRaisesRegex(CAD3DError, "顶点限制"):
            self.inspect()
        with patch.object(geometry, "MAX_ENTITY_VERTICES", 3), self.assertRaisesRegex(CAD3DError, "顶点限制"):
            self.inspect()
        with patch.object(geometry, "MAX_DATABASE_ENTITIES", 0), self.assertRaisesRegex(CAD3DError, "数据库"):
            self.inspect()
        with patch.object(geometry, "MAX_LAYER_RINGS", 0):
            model = build_model(document, self.config())
            self.assertEqual(model["summary"]["failed"], 1)

    def test_nonfinite_and_duplicate_document_entities_rejected(self):
        self.ring()
        document = self.inspect()
        duplicate = copy.deepcopy(document)
        duplicate["entities"].append(copy.deepcopy(duplicate["entities"][0]))
        with self.assertRaisesRegex(CAD3DError, "重复"):
            build_model(duplicate, self.config())
        document["entities"][0]["points"][0][0] = float("nan")
        with self.assertRaisesRegex(CAD3DError, "有限"):
            build_model(document, self.config())

    def test_crlf_files_have_the_same_entities_as_lf(self):
        self.ring()
        stream = io.StringIO()
        self.doc.write(stream)
        source = stream.getvalue().replace("\r\n", "\n")
        lf = inspect_dxf(source.encode(), "synthetic-lf.dxf")
        crlf = inspect_dxf(source.replace("\n", "\r\n").encode(), "synthetic-crlf.dxf")
        self.assertEqual(len(crlf["entities"]), 1)
        self.assertEqual(lf["entities"], crlf["entities"])

    def test_malformed_config_values_raise_validation_errors(self):
        self.ring()
        document = self.inspect()
        for field in ("mode", "unit", "layers", "parameters", "overrides"):
            for bad in ([], None, 42, True):
                with self.subTest(field=field, bad=bad), self.assertRaises(CAD3DError):
                    build_model(document, self.config(**{field: bad}))
        for bad in ([], {}, None, True):
            with self.subTest(role=bad), self.assertRaises(CAD3DError):
                build_model(document, self.config(layers={"SECTION": bad}))
        with self.assertRaisesRegex(CAD3DError, "未知设置"):
            build_model(document, self.config(unknown=1))

    def test_block_insert_is_reported_without_exploding_geometry(self):
        block = self.doc.blocks.new("SYNTHETIC")
        block.add_lwpolyline([(0, 0), (100, 0), (100, 100)], close=True)
        self.doc.modelspace().add_blockref("SYNTHETIC", (0, 0))
        document = self.inspect()
        self.assertEqual(len(document["entities"]), 1)
        self.assertEqual(document["entities"][0]["status"], "unsupported")
        self.assertIn("块参照", document["entities"][0]["reason"])

    def test_synthetic_building_fixture_has_expected_real_geometry(self):
        folder = ROOT / "examples" / "cad-to-3d"
        document = inspect_dxf((folder / "synthetic-building-mm.dxf").read_bytes(), "building.dxf")
        config = json.loads((folder / "synthetic-building-config.json").read_text())
        model = build_model(document, config)
        self.assertEqual(len(model["objects"]), 6)
        self.assertEqual(model["summary"], {"modeled": 8, "ignored": 0, "failed": 0})
        volumes = {}
        for obj in model["objects"]:
            volumes[obj["role"]] = volumes.get(obj["role"], 0) + obj["volume_m3"]
        self.assertAlmostEqual(volumes["wall"], 11.52)
        self.assertAlmostEqual(volumes["column"], 1.92)
        self.assertAlmostEqual(volumes["slab"], 2.76)


class InputAndDependencyTests(unittest.TestCase):
    def test_format_errors_are_explainable(self):
        for data, filename in ((b"", "x.dxf"), (b"ACAD", "x.dwg"),
                               (b"AutoCAD Binary DXF", "x.dxf")):
            with self.subTest(filename=filename), self.assertRaises(CAD3DError):
                inspect_dxf(data, filename)

    def test_missing_optional_dependency_is_deferred_and_explainable(self):
        with patch.object(geometry.importlib, "import_module", side_effect=ImportError("synthetic missing dependency")):
            with self.assertRaisesRegex(CAD3DError, "pip install"):
                inspect_dxf(b"synthetic-not-parsed", "fixture.dxf")


if __name__ == "__main__":
    unittest.main()
