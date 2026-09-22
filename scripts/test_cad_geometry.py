#!/usr/bin/env python3
"""Offline CAD geometry invariants using explicitly synthetic drawing fixtures."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import math
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
                         ["invalid", "invalid", "ready", "unsupported", "ready", "invalid"])
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
        self.doc.modelspace().add_ellipse((50, 50), (25, 0), ratio=0.5, dxfattribs={"layer": "SECTION"})
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
        for height in (None, "3", True, 0, -1, float("nan"), float("inf"), 10 ** 400):
            with self.subTest(height=height), self.assertRaises(CAD3DError):
                build_model(document, self.config(parameters={"section": {"height_m": height, "base_m": 0}}))
        for base in (None, "0", False, float("inf"), -(10 ** 400)):
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
        self.assertEqual(model["config"], {**config, "curve_tolerance_mm": 0.1})
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

    def test_block_insert_expands_and_preserves_original_instance_handle(self):
        block = self.doc.blocks.new("SYNTHETIC")
        source = block.add_lwpolyline([(0, 0), (100, 0), (100, 100)], close=True)
        insertion = self.doc.modelspace().add_blockref("SYNTHETIC", (0, 0))
        document = self.inspect()
        self.assertEqual(len(document["entities"]), 1)
        self.assertEqual(document["entities"][0]["status"], "ready")
        self.assertEqual(document["entities"][0]["id"], f"{insertion.dxf.handle}/{source.dxf.handle}")

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

    def line_ring(self, bounds=(0, 0, 100, 100), layer="SECTION"):
        x0, y0, x1, y1 = bounds
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        # Deliberately unordered and independently reversed edges.
        return [self.doc.modelspace().add_line(points[a], points[b], dxfattribs={"layer": layer})
                for a, b in ((2, 1), (0, 1), (3, 0), (3, 2))]

    def test_line_loops_keep_holes_dimensions_and_every_source(self):
        outer = self.line_ring()
        inner = self.line_ring((10, 10, 90, 90))
        document = self.inspect()
        self.assertEqual(len(document["entities"]), 2)
        self.assertEqual(document["layers"][0]["entity_count"], 8)
        model = build_model(document, self.config())
        self.assertEqual(model["summary"], {"modeled": 8, "ignored": 0, "failed": 0})
        self.assertEqual(len(model["objects"]), 1)
        obj = model["objects"][0]
        self.assertEqual(obj["hole_count"], 1)
        self.assertAlmostEqual(obj["volume_m3"], 0.0072, places=12)
        expected = {edge.dxf.handle for edge in [*outer, *inner]}
        self.assertEqual(set(obj["source_entity_ids"]), expected)
        self.assertEqual({row["id"] for row in model["report"]}, expected)
        self.assertEqual({row["handle"] for row in obj["source_entities"]}, expected)

    def test_line_gap_is_not_healed_by_large_curve_tolerance(self):
        edges = self.line_ring()
        edges[0].dxf.start = (100, 100.00000001, 0)
        model = build_model(self.inspect(), self.config(curve_tolerance_mm=10))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 4)
        self.assertTrue(all("未闭合" in row["reason"] for row in model["report"]))

    def test_line_branch_and_zero_length_edges_block_layer(self):
        self.line_ring()
        self.doc.modelspace().add_line((0, 0), (50, 50), dxfattribs={"layer": "SECTION"})
        zero = self.doc.modelspace().add_line((20, 20), (20, 20), dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["summary"]["failed"], 6)
        self.assertIn("零长度", next(row for row in model["report"] if row["id"] == zero.dxf.handle)["reason"])

    def test_edges_on_different_layers_cannot_complete_each_other(self):
        edges = self.line_ring()
        edges[0].dxf.layer = "SECOND"
        model = build_model(self.inspect(), self.config(layers={"SECTION": "section", "SECOND": "section"}))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 4)

    def test_arc_and_line_semicircle_preserves_shape_and_source_ids(self):
        arc = self.doc.modelspace().add_arc((0, 0), 100, 0, 180, dxfattribs={"layer": "SECTION"})
        line = self.doc.modelspace().add_line((-100, 0), (100, 0), dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        obj = model["objects"][0]
        self.assertEqual(set(obj["source_entity_ids"]), {arc.dxf.handle, line.dxf.handle})
        self.assertLess(abs(obj["volume_m3"] - math.pi * 0.1 ** 2), 0.00006)
        self.assertEqual(obj["bounds"]["max"][0], 0.2)
        self.assertGreater(obj["bounds"]["max"][1], 0.0999)
        self.assertLessEqual(model["transform"]["curve_max_error_mm"], 0.1)

    def test_arcs_join_at_nonquadrant_endpoints_with_only_roundoff_difference(self):
        self.doc.modelspace().add_arc((0, 0), 100, 13, 193, dxfattribs={"layer": "SECTION"})
        self.doc.modelspace().add_arc((0, 0), 100, 193, 373, dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["summary"]["modeled"], 2)
        self.assertAlmostEqual(model["objects"][0]["volume_m3"], 2 * math.pi * 0.01, delta=0.0001)

    def test_large_coordinate_arc_gap_is_not_closed_by_relative_roundoff(self):
        self.doc.units = 6
        base = 1e11
        space = self.doc.modelspace()
        space.add_arc((base, base), 10, 0, 90, dxfattribs={"layer": "SECTION"})
        space.add_line((base + 0.00015, base + 10), (base, base), dxfattribs={"layer": "SECTION"})
        space.add_line((base, base), (base + 10, base), dxfattribs={"layer": "SECTION"})
        self.assertGreater((base + 0.00015 - base) * 1000, 0.15)
        model = build_model(self.inspect(), self.config(unit="m"))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 3)
        self.assertTrue(all("未闭合" in row["reason"] for row in model["report"]))

    def test_confirmed_units_recheck_previously_joined_roundoff(self):
        self.doc.units = 4
        base = 1e6
        space = self.doc.modelspace()
        space.add_arc((base, base), 10, 0, 90, dxfattribs={"layer": "SECTION"})
        space.add_line((base + 1.5e-9, base + 10), (base, base), dxfattribs={"layer": "SECTION"})
        space.add_line((base, base), (base + 10, base), dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        self.assertEqual(len(build_model(document, self.config())["objects"]), 1)
        model = build_model(document, self.config(unit="m"))
        self.assertEqual(model["objects"], [])
        self.assertTrue(all("端点偏差" in row["reason"] for row in model["report"]))

    def test_circle_hole_is_preserved_in_reopened_glb(self):
        import trimesh
        self.doc.modelspace().add_circle((0, 0), 100, dxfattribs={"layer": "SECTION"})
        self.doc.modelspace().add_circle((0, 0), 50, dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        obj = model["objects"][0]
        self.assertEqual(obj["hole_count"], 1)
        self.assertAlmostEqual(obj["volume_m3"], math.pi * (0.1 ** 2 - 0.05 ** 2) * 2, delta=0.0001)
        self.assertEqual(obj["bounds"], {"min": [0, 0, 0], "max": [0.2, 0.2, 2]})
        reopened = trimesh.load(io.BytesIO(export_glb(model)), file_type="glb", force="scene")
        mesh = next(iter(reopened.geometry.values()))
        self.assertTrue(mesh.is_watertight)
        self.assertAlmostEqual(mesh.volume, obj["volume_m3"], places=7)
        from shapely.geometry import Point, Polygon
        hole = Point(0.1, 0.1).buffer(0.0498)
        for face in obj["faces"]:
            points = [obj["vertices"][index] for index in face]
            if all(point[2] == 2 for point in points):
                self.assertLess(Polygon([point[:2] for point in points]).intersection(hole).area, 1e-12)

    def test_curve_error_cannot_hide_overlapping_circles(self):
        angle = math.radians(7.5)
        self.doc.modelspace().add_circle((0, 0), 10, dxfattribs={"layer": "SECTION"})
        self.doc.modelspace().add_circle((19.95 * math.cos(angle), 19.95 * math.sin(angle)), 10,
                                        dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        coarse = build_model(document, self.config())
        self.assertEqual(coarse["objects"], [])
        self.assertEqual(coarse["summary"]["failed"], 2)
        self.assertTrue(all("离散误差" in row["reason"] for row in coarse["report"]))
        fine = build_model(document, self.config(curve_tolerance_mm=0.001))
        self.assertEqual(fine["objects"], [])
        self.assertTrue(all("相交" in row["reason"] for row in fine["report"]))

    def test_close_circle_hole_requires_tighter_tolerance_before_modeling(self):
        for radius in (10, 9.95):
            self.doc.modelspace().add_circle((0, 0), radius, dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        coarse = build_model(document, self.config())
        self.assertEqual(coarse["objects"], [])
        self.assertTrue(all("离散误差" in row["reason"] for row in coarse["report"]))
        fine = build_model(document, self.config(curve_tolerance_mm=0.001))
        self.assertEqual(len(fine["objects"]), 1)
        self.assertEqual(fine["objects"][0]["hole_count"], 1)

    def test_bulge_positive_negative_and_old_polyline_form_real_circles(self):
        for kind, bulge in (("LWPOLYLINE", 1), ("LWPOLYLINE", -1), ("POLYLINE", 1)):
            with self.subTest(kind=kind, bulge=bulge):
                self.setUp()
                if kind == "LWPOLYLINE":
                    self.doc.modelspace().add_lwpolyline([(-100, 0, bulge), (100, 0, bulge)],
                                                       format="xyb", close=True, dxfattribs={"layer": "SECTION"})
                else:
                    entity = self.doc.modelspace().add_polyline2d([(-100, 0), (100, 0)], close=True,
                                                                 dxfattribs={"layer": "SECTION"})
                    for vertex in entity.vertices:
                        vertex.dxf.bulge = bulge
                model = build_model(self.inspect(), self.config())
                self.assertAlmostEqual(model["objects"][0]["volume_m3"], 2 * math.pi * 0.01, delta=0.0001)
                self.assertLessEqual(model["transform"]["curve_max_error_mm"], 0.1)

    def test_confirmed_unit_resamples_curves_in_physical_millimetres(self):
        self.doc.modelspace().add_circle((0, 0), 1, dxfattribs={"layer": "SECTION"})
        document = self.inspect()  # header says mm; user will confirm m
        snapshot = copy.deepcopy(document)
        model = build_model(document, self.config(unit="m"))
        points = model["preview_entities"][0]["points"]
        self.assertGreater(len(points), len(document["entities"][0]["points"]))
        self.assertEqual(model["objects"][0]["bounds"]["max"], [2, 2, 2])
        for first, last in zip(points, [*points[1:], points[0]]):
            sagitta_mm = (1 - math.hypot((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)) * 1000
            self.assertLessEqual(sagitta_mm, 0.1 + 1e-9)
        self.assertEqual(document, snapshot)

    def test_tighter_tolerance_adds_vertices_and_is_recorded(self):
        self.doc.modelspace().add_circle((0, 0), 100, dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        coarse = build_model(document, self.config(curve_tolerance_mm=1))
        fine = build_model(document, self.config(curve_tolerance_mm=0.01))
        self.assertGreater(len(fine["preview_entities"][0]["points"]), len(coarse["preview_entities"][0]["points"]))
        self.assertLessEqual(fine["transform"]["curve_max_error_mm"], 0.01)
        self.assertEqual(fine["config"]["curve_tolerance_mm"], 0.01)

    def test_curve_tolerance_invalid_values_are_rejected(self):
        self.ring()
        document = self.inspect()
        for tolerance in (0, -1, True, None, "0.1", float("nan"), float("inf"), 0.0001, 11, 10 ** 400):
            with self.subTest(tolerance=tolerance), self.assertRaises(CAD3DError):
                build_model(document, self.config(curve_tolerance_mm=tolerance))

    def test_tessellation_limit_reports_failure_without_relaxing_tolerance(self):
        self.doc.modelspace().add_circle((0, 0), 1000, dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        model = build_model(document, self.config(unit="m", curve_tolerance_mm=0.001))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["config"]["curve_tolerance_mm"], 0.001)
        self.assertIn("弦高误差", model["report"][0]["reason"])

    def test_unitless_drawing_keeps_explicit_confirmation_requirement(self):
        self.doc.units = 0
        self.doc.modelspace().add_circle((0, 0), 1, dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        self.assertIsNone(document["units"]["meters_per_unit"])
        self.assertEqual(document["preview_unit"], "mm")
        with self.assertRaisesRegex(CAD3DError, "单位"):
            build_model(document, self.config(unit=""))
        self.assertEqual(build_model(document, self.config(unit="m"))["objects"][0]["bounds"]["max"], [2, 2, 2])

    def test_insert_uniform_scale_rotation_base_point_and_two_instances(self):
        block = self.doc.blocks.new("HOLLOW", base_point=(10, 20))
        outer = block.add_lwpolyline([(10, 20), (110, 20), (110, 70), (10, 70)], close=True)
        inner = block.add_lwpolyline([(20, 30), (100, 30), (100, 60), (20, 60)], close=True)
        inserts = [self.doc.modelspace().add_blockref("HOLLOW", position, dxfattribs={
            "layer": "SECTION", "rotation": 90, "xscale": 2, "yscale": 2, "zscale": 2})
                   for position in ((0, 0), (1000, 0))]
        model = build_model(self.inspect(), self.config())
        self.assertEqual(len(model["objects"]), 2)
        self.assertEqual(model["summary"]["modeled"], 4)
        for obj in model["objects"]:
            self.assertEqual(obj["hole_count"], 1)
            self.assertAlmostEqual(obj["volume_m3"], (0.1 * 0.05 - 0.08 * 0.03) * 4 * 2)
            self.assertAlmostEqual(obj["bounds"]["max"][0] - obj["bounds"]["min"][0], 0.1)
            self.assertAlmostEqual(obj["bounds"]["max"][1] - obj["bounds"]["min"][1], 0.2)
        self.assertEqual({source for obj in model["objects"] for source in obj["source_entity_ids"]},
                         {f"{insertion.dxf.handle}/{entity.dxf.handle}" for insertion in inserts for entity in (outer, inner)})

    def test_nested_insert_and_nonzero_child_layer_are_preserved(self):
        child = self.doc.blocks.new("CHILD")
        circle = child.add_circle((0, 0), 100, dxfattribs={"layer": "EXPLICIT"})
        parent = self.doc.blocks.new("PARENT")
        nested = parent.add_blockref("CHILD", (100, 0))
        outer = self.doc.modelspace().add_blockref("PARENT", (0, 100), dxfattribs={"layer": "SECTION", "rotation": 90})
        document = self.inspect()
        entity = document["entities"][0]
        self.assertEqual(entity["layer"], "EXPLICIT")
        self.assertEqual(entity["id"], f"{outer.dxf.handle}/{nested.dxf.handle}/{circle.dxf.handle}")
        model = build_model(document, self.config(layers={"EXPLICIT": "section"}))
        self.assertEqual(model["transform"]["origin_source_units"], [-100, 100, 0])
        self.assertEqual(len(model["objects"][0]["source_entities"][0]["insert_path"]), 2)

    def test_unsupported_insert_transforms_are_reported_without_partial_model(self):
        block = self.doc.blocks.new("BOX")
        block.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        for attributes in ({"xscale": 2}, {"xscale": -1}, {"extrusion": (0, 1, 0)}, {"column_count": 2}):
            self.doc.modelspace().add_blockref("BOX", (0, 0), dxfattribs={"layer": "SECTION", **attributes})
        self.doc.modelspace().add_blockref("BOX", (0, 0, 5), dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["summary"]["failed"], 10)
        self.assertEqual(model["objects"], [])
        self.assertTrue(all("块参照" in row["reason"] for row in model["report"]))

    def test_recursive_block_and_expansion_budget_fail_safely(self):
        block = self.doc.blocks.new("RECURSIVE")
        block.add_blockref("RECURSIVE", (0, 0))
        self.doc.modelspace().add_blockref("RECURSIVE", (0, 0), dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        self.assertEqual(document["entities"][0]["status"], "unsupported")
        self.assertIn("循环", document["entities"][0]["reason"])
        with patch.object(geometry, "MAX_ENTITIES", 1), self.assertRaisesRegex(CAD3DError, "展开后"):
            self.inspect()

    def test_unsupported_child_of_selected_block_cannot_fill_hole(self):
        block = self.doc.blocks.new("BLOCK_WITH_UNSUPPORTED_HOLE")
        block.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        block.add_ellipse((50, 50), (25, 0), ratio=0.5)
        self.doc.modelspace().add_blockref(block.name, (0, 0), dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 2)

    def test_unsupported_insert_on_ignored_layer_blocks_explicit_hole_layer(self):
        for attributes in ({"xscale": 2}, {"xscale": -1}, {"extrusion": (0, 1, 0)}, {"column_count": 2}):
            with self.subTest(attributes=attributes):
                self.setUp()
                self.doc.modelspace().add_circle((0, 0), 100, dxfattribs={"layer": "SECTION"})
                block = self.doc.blocks.new("HOLE")
                hole = block.add_circle((0, 0), 10, dxfattribs={"layer": "SECTION"})
                insertion = self.doc.modelspace().add_blockref("HOLE", (0, 0), dxfattribs=attributes)
                document = self.inspect()
                config = self.config(layers={"SECTION": "section", "0": "ignore"})
                model = build_model(document, config)
                self.assertEqual(model["objects"], [])
                self.assertEqual(model["summary"], {"modeled": 0, "ignored": 1, "failed": 2})
                source = next(row for row in model["report"] if row["id"] == f"{insertion.dxf.handle}/{hole.dxf.handle}")
                self.assertEqual(source["layer"], "SECTION")
                self.assertIn("所属块参照未处理", source["reason"])

    def test_unsupported_insert_propagates_failure_through_nested_layer_inheritance(self):
        self.doc.modelspace().add_circle((0, 0), 100, dxfattribs={"layer": "SECTION"})
        leaf = self.doc.blocks.new("LEAF")
        leaf.add_circle((0, 0), 10)  # layer 0 inherits nested SECTION
        middle = self.doc.blocks.new("MIDDLE")
        middle.add_blockref("LEAF", (0, 0), dxfattribs={"layer": "SECTION"})
        parent = self.doc.blocks.new("PARENT")
        parent.add_blockref("MIDDLE", (0, 0))
        self.doc.modelspace().add_blockref("PARENT", (0, 0), dxfattribs={"xscale": 2})
        model = build_model(self.inspect(), self.config(layers={"SECTION": "section", "0": "ignore"}))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 3)

    def test_nonplanar_arc_circle_and_line_are_never_projected(self):
        space = self.doc.modelspace()
        space.add_circle((0, 0, 1), 100, dxfattribs={"layer": "SECTION"})
        space.add_arc((0, 0), 100, 0, 180, dxfattribs={"layer": "SECTION", "extrusion": (0, 1, 0)})
        space.add_line((0, 0), (1, 1, 1), dxfattribs={"layer": "SECTION"})
        document = self.inspect()
        self.assertEqual([entity["status"] for entity in document["entities"]], ["unsupported"] * 3)

    def test_geometry_stops_at_cooperative_cancellation_checkpoint(self):
        from packing_assistant.runtime.cancel import RunCancelled
        self.ring()
        document = self.inspect()
        with patch("packing_assistant.runtime.cancel.check", side_effect=RunCancelled("scripted")):
            with self.assertRaises(RunCancelled):
                build_model(document, self.config())

    def test_curves_have_same_dimensions_for_all_confirmed_units(self):
        for unit, factor in geometry.UNIT_FACTORS.items():
            with self.subTest(unit=unit):
                self.setUp()
                self.doc.modelspace().add_circle((0, 0), 0.1 / factor, dxfattribs={"layer": "SECTION"})
                model = build_model(self.inspect(), self.config(unit=unit))
                obj = model["objects"][0]
                self.assertAlmostEqual(obj["bounds"]["max"][0], 0.2)
                self.assertAlmostEqual(obj["volume_m3"], math.pi * 0.01 * 2, delta=0.0001)
                self.assertLessEqual(model["transform"]["curve_max_error_mm"], 0.1)

    def test_far_apart_small_curves_cannot_silently_lose_glb_precision(self):
        for center in ((0, 0), (900000000, 0)):
            self.doc.modelspace().add_circle(center, 1, dxfattribs={"layer": "SECTION"})
        model = build_model(self.inspect(), self.config())
        self.assertEqual(model["objects"], [])
        self.assertTrue(all("float32" in row["reason"] for row in model["report"]))

    def test_extended_synthetic_fixtures_generate_and_reopen(self):
        import trimesh
        folder = ROOT / "examples" / "cad-to-3d"
        for name, count, modeled in (("curved-building", 6, 14), ("bulge-section", 1, 2)):
            with self.subTest(name=name):
                filename = f"synthetic-{name}-mm.dxf"
                document = inspect_dxf((folder / filename).read_bytes(), filename)
                config = json.loads((folder / f"synthetic-{name}-config.json").read_text(encoding="utf-8"))
                model = build_model(document, config)
                self.assertEqual(len(model["objects"]), count)
                self.assertEqual(model["summary"], {"modeled": modeled, "ignored": 0, "failed": 0})
                scene = trimesh.load(io.BytesIO(export_glb(model)), file_type="glb", force="scene")
                self.assertEqual(len(scene.geometry), count)
                self.assertTrue(all(mesh.is_watertight for mesh in scene.geometry.values()))
                self.assertAlmostEqual(sum(mesh.volume for mesh in scene.geometry.values()),
                                       sum(obj["volume_m3"] for obj in model["objects"]), places=5)
                if name == "curved-building":
                    columns = [obj for obj in model["objects"] if obj["role"] == "column"]
                    self.assertTrue(all(obj["source_entities"][0]["insert_path"] for obj in columns))


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
