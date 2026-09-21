#!/usr/bin/env python3
"""Offline source selection, 2D diagnosis and bounded NURBS regressions."""
from __future__ import annotations

import copy
import io
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.cad3d import geometry
from packing_assistant.cad3d.geometry import CAD3DError, analyze_document, build_model, inspect_dxf
from packing_assistant.cad3d.selection import checked_selection


class CADTestCase(unittest.TestCase):
    def setUp(self):
        import ezdxf
        self.drawing = ezdxf.new("R2010")
        self.drawing.units = 4
        self.space = self.drawing.modelspace()

    def ring(self, bounds=(0, 0, 100, 100), layer="SECTION"):
        x, y, X, Y = bounds
        return self.space.add_lwpolyline([(x, y), (X, y), (X, Y), (x, Y)], close=True, dxfattribs={"layer": layer})

    def inspect(self):
        text = io.StringIO()
        self.drawing.write(text)
        return inspect_dxf(text.getvalue().encode(), "synthetic-selection.dxf")

    def config(self, **changes):
        return {"mode": "section", "unit": "mm", "layers": {"SECTION": "section"}, **changes}

    def model_config(self, **changes):
        return self.config(confirmed_solid=True, parameters={"section": {"height_m": 1, "base_m": 0}}, **changes)


class SelectionTests(CADTestCase):
    def test_heightless_preview_and_explicit_confirmation_separate(self):
        outer = self.ring()
        hole = self.ring((10, 10, 90, 90))
        result = analyze_document(self.inspect(), self.config())
        self.assertTrue(result["buildable"])
        self.assertTrue(result["requires_confirmation"])
        contour = result["contours"][0]
        self.assertEqual((contour["outer_id"], contour["hole_ids"]), (outer.dxf.handle, [hole.dxf.handle]))
        self.assertAlmostEqual(contour["area_mm2"], 3600)
        with self.assertRaises(CAD3DError):
            build_model(self.inspect(), self.config())
        json.dumps(result, allow_nan=False)

    def test_exclude_enclosing_frame_keep_hole_source_and_step_footprint(self):
        frame = self.ring((-20, -20, 120, 120))
        outer = self.ring()
        hole = self.ring((10, 10, 90, 90))
        cfg = self.model_config(selection={"include_ids": [outer.dxf.handle, hole.dxf.handle]})
        model = build_model(self.inspect(), cfg)
        self.assertEqual(model["summary"], {"modeled": 2, "ignored": 1, "failed": 0})
        self.assertEqual(model["objects"][0]["hole_count"], 1)
        self.assertEqual(len(model["objects"][0]["footprint"]["holes"]), 1)
        self.assertEqual(next(row for row in model["report"] if row["id"] == frame.dxf.handle)["status"], "ignored")

    def test_outer_only_or_explicit_hole_exclusion_blocks(self):
        outer = self.ring()
        hole = self.ring((10, 10, 90, 90))
        for selection in ({"include_ids": [outer.dxf.handle]}, {"exclude_ids": [hole.dxf.handle]}):
            with self.subTest(selection=selection):
                doc = self.inspect()
                analysis = analyze_document(doc, self.config(selection=selection))
                self.assertFalse(analysis["buildable"])
                diagnostic = next(row for row in analysis["diagnostics"] if row["code"] == "omitted_boundary")
                self.assertEqual(set(diagnostic["entity_ids"]), {outer.dxf.handle, hole.dxf.handle})
                self.assertEqual(build_model(doc, self.model_config(selection=selection))["objects"], [])

    def test_invalid_unselected_internal_curve_still_blocks(self):
        outer = self.ring()
        edge = self.space.add_line((20, 20), (80, 80), dxfattribs={"layer": "SECTION"})
        result = analyze_document(self.inspect(), self.config(selection={"include_ids": [outer.dxf.handle]}))
        self.assertFalse(result["buildable"])
        self.assertTrue(any(edge.dxf.handle in row["entity_ids"] and row["code"] == "omitted_boundary" for row in result["diagnostics"]))

    def test_unsupported_unlocatable_exclusion_blocks(self):
        outer = self.ring()
        ellipse = self.space.add_ellipse((50, 50), (25, 0), ratio=.5, dxfattribs={"layer": "SECTION"})
        result = analyze_document(self.inspect(), self.config(selection={"exclude_ids": [ellipse.dxf.handle]}))
        self.assertFalse(result["buildable"])
        self.assertTrue(any(row["code"] == "omitted_boundary" for row in result["diagnostics"]))

    def test_explicit_annotation_exclusion_valid_but_selected_annotation_blocks(self):
        self.ring()
        text = self.space.add_text("REFERENCE", dxfattribs={"layer": "SECTION", "insert": (20, 20)})
        doc = self.inspect()
        self.assertFalse(analyze_document(doc, self.config())["buildable"])
        self.assertTrue(analyze_document(doc, self.config(selection={"exclude_ids": [text.dxf.handle]}))["buildable"])

    def test_duplicate_rings_located_excluding_copy_preserves_material(self):
        first, second = self.ring(), self.ring()
        doc = self.inspect()
        before = analyze_document(doc, self.config())
        duplicate = next(row for row in before["diagnostics"] if row["code"] == "duplicate")
        self.assertEqual(set(duplicate["entity_ids"]), {first.dxf.handle, second.dxf.handle})
        self.assertTrue(duplicate["points"])
        after = analyze_document(doc, self.config(selection={"exclude_ids": [second.dxf.handle]}))
        self.assertTrue(after["buildable"])
        self.assertAlmostEqual(after["contours"][0]["area_mm2"], 10000)

    def test_duplicate_line_can_be_excluded_then_chain_reassembled(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        originals = [self.space.add_line(a, b, dxfattribs={"layer": "SECTION"}) for a, b in zip(pts, pts[1:])]
        copy_line = self.space.add_line((100, 0), (0, 0), dxfattribs={"layer": "SECTION"})
        doc = self.inspect()
        before = analyze_document(doc, self.config())
        self.assertTrue(any(row["code"] == "duplicate" for row in before["diagnostics"]))
        cfg = self.model_config(selection={"exclude_ids": [copy_line.dxf.handle]})
        model = build_model(doc, cfg)
        self.assertEqual(model["summary"], {"modeled": 4, "ignored": 1, "failed": 0})
        self.assertEqual(model["objects"][0]["source_entity_ids"], [e.dxf.handle for e in originals])

    def test_gap_diagnostic_has_source_points_and_mm_no_snap(self):
        self.space.add_line((1000, 2000), (1100, 2000), dxfattribs={"layer": "SECTION"})
        self.space.add_line((1100, 2000), (1100, 2100), dxfattribs={"layer": "SECTION"})
        self.space.add_line((1100, 2100), (1000, 2100), dxfattribs={"layer": "SECTION"})
        self.space.add_line((1000, 2100), (1000, 2000.05), dxfattribs={"layer": "SECTION"})
        result = analyze_document(self.inspect(), self.config())
        rows = [row for row in result["diagnostics"] if row["code"] == "open_contour"]
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["gap_mm"], .05)
        self.assertEqual(rows[0]["points"], [[1000, 2000], [1000, 2000.05]])
        self.assertFalse(result["buildable"])

    def test_selection_rejects_unknown_duplicate_type_and_bounds(self):
        entity = self.ring()
        doc = self.inspect()
        bad = [{"include_ids": ["MISSING"]}, {"include_ids": [entity.dxf.handle] * 2},
               {"exclude_ids": "all"}, {"exclude_ids": [1]}, {"all": True},
               {"groups": [{"name": "A", "entity_ids": [entity.dxf.handle]}] * 2},
               {"groups": [{"name": "A", "entity_ids": []}]},
               {"include_ids": [entity.dxf.handle] * (geometry.MAX_ENTITIES + 1)},
               {"groups": [{}] * 65}, {"groups": [{"name": "\n", "entity_ids": [entity.dxf.handle]}]}]
        for selection in bad:
            with self.subTest(selection=selection), self.assertRaises(CAD3DError):
                checked_selection(doc, selection)

    def test_group_canonical_order_and_empty_selection(self):
        first, second = self.ring(), self.ring((200, 0, 300, 100))
        doc = self.inspect()
        selected = checked_selection(doc, {"groups": [{"name": " side ", "entity_ids": [second.dxf.handle, first.dxf.handle]}]})
        self.assertEqual(selected["groups"], [{"name": "side", "entity_ids": [first.dxf.handle, second.dxf.handle]}])
        self.assertEqual(analyze_document(doc, self.config(selection={"include_ids": []}))["diagnostics"][0]["code"], "empty_selection")

    def test_old_config_does_not_gain_selection(self):
        self.ring()
        self.assertNotIn("selection", build_model(self.inspect(), self.model_config())["config"])

    def test_document_and_config_not_mutated(self):
        self.ring()
        doc, config = self.inspect(), self.config()
        original = copy.deepcopy((doc, config))
        analyze_document(doc, config)
        self.assertEqual((doc, config), original)

    def test_source_region_cannot_turn_cropped_outer_hole_into_material(self):
        outer = self.ring()
        self.ring((25, 25, 75, 75))
        text = io.StringIO()
        self.drawing.write(text)
        doc = inspect_dxf(text.getvalue().encode(), "synthetic-region.dxf",
                          source_filter={"layers": ["SECTION"], "bounds": [20, 20, 80, 80]})
        result = analyze_document(doc, self.config())
        self.assertFalse(result["buildable"])
        self.assertTrue(any(outer.dxf.handle in row["entity_ids"] for row in result["diagnostics"]))
        self.assertTrue(next(row for row in doc["entities"] if row["id"] == outer.dxf.handle)["display_only"])

    def test_diagnostics_count_is_bounded_without_losing_later_failures(self):
        from packing_assistant.cad3d.diagnostics import MAX_DIAGNOSTICS
        for _ in range(30):
            self.ring()
        self.ring(layer="LATER")
        self.ring(layer="LATER")
        doc = self.inspect()
        cfg = self.model_config(layers={"SECTION": "section", "LATER": "section"})
        model = build_model(doc, cfg)
        self.assertLessEqual(len(model["diagnostics"]), MAX_DIAGNOSTICS + 1)
        self.assertTrue(any(row["code"] == "diagnostic_limit" for row in model["diagnostics"]))
        self.assertEqual(model["objects"], [])
        self.assertEqual(model["summary"]["failed"], 32)


class SplineTests(CADTestCase):
    def circle_spline(self, radius=100, center=(0, 0), layer="SECTION"):
        r = radius
        points = [(r, 0), (r, r), (0, r), (-r, r), (-r, 0), (-r, -r), (0, -r), (r, -r), (r, 0)]
        points = [(x + center[0], y + center[1]) for x, y in points]
        weights = [1, 2 ** -.5, 1, 2 ** -.5, 1, 2 ** -.5, 1, 2 ** -.5, 1]
        return self.space.add_rational_spline(points, weights, degree=2,
                                              knots=[0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4],
                                              dxfattribs={"layer": layer})

    def test_rational_circle_hole_error_volume_and_glb(self):
        from shapely.geometry import LineString, Point
        import trimesh
        outer = self.circle_spline()
        self.circle_spline(50)
        doc = self.inspect()
        result = analyze_document(doc, self.config())
        self.assertTrue(result["buildable"], result["diagnostics"])
        contour = result["contours"][0]
        self.assertEqual(len(contour["hole_ids"]), 1)
        source = next(e for e in doc["entities"] if e["id"] == outer.dxf.handle)
        polyline = LineString([*source["points"], source["points"][0]])
        worst = max(polyline.distance(Point(100 * math.cos(a * math.pi / 3600), 100 * math.sin(a * math.pi / 3600))) for a in range(7200))
        self.assertLessEqual(worst, source["curve_max_error_mm"])
        self.assertLessEqual(source["curve_max_error_mm"], .1)
        model = build_model(doc, self.model_config())
        self.assertAlmostEqual(model["objects"][0]["volume_m3"], math.pi * (.1 ** 2 - .05 ** 2), delta=.00003)
        scene = trimesh.load(io.BytesIO(geometry.export_glb(model)), file_type="glb", force="scene")
        self.assertTrue(next(iter(scene.geometry.values())).is_watertight)

    def test_inflected_cubic_midpoint_on_chord_does_not_hide_bends(self):
        from shapely.geometry import LineString, Point
        from packing_assistant.cad3d.splines import read_spline, sample_spline
        entity = self.space.add_open_spline([(0, 0), (30, 100), (70, -100), (100, 0)], dxfattribs={"layer": "SECTION"})
        segment = read_spline(entity, (1, 0, 0, 0))
        points, bound = sample_spline(segment, .1)
        self.assertGreater(len(points), 10)
        self.assertLessEqual(bound, .1)
        shape = LineString(points)
        reference = entity.construction_tool()
        self.assertLessEqual(max(shape.distance(Point(point.x, point.y)) for point in reference.points(i / 2000 for i in range(2001))), bound)

    def test_adjacent_spans_hidden_self_intersection_is_rejected(self):
        self.space.add_open_spline([(-1, 0), (0, .05), (0, 0), (-.1, .001), (-1, .1)], degree=2,
                                   knots=[0, 0, 0, 1, 1, 2, 2, 2], dxfattribs={"layer": "SECTION"})
        self.space.add_line((-1, .1), (-1, 0), dxfattribs={"layer": "SECTION"})
        result = analyze_document(self.inspect(), self.config())
        self.assertFalse(result["buildable"])
        self.assertTrue(any("自交" in row["message"] for row in result["diagnostics"]))

    def test_spline_crossing_closing_line_below_tolerance_is_rejected(self):
        self.space.add_open_spline([(0, 0), (.33, .2), (.66, -.01), (1, 0)], dxfattribs={"layer": "SECTION"})
        self.space.add_line((1, 0), (0, 0), dxfattribs={"layer": "SECTION"})
        result = analyze_document(self.inspect(), self.config())
        self.assertFalse(result["buildable"])
        self.assertTrue(any("自交" in row["message"] for row in result["diagnostics"]))

    def test_knot_refinement_rational_nonuniform_matches_original(self):
        from shapely.geometry import LineString, Point
        from packing_assistant.cad3d.splines import read_spline, sample_spline
        entity = self.space.add_rational_spline([(0, 0), (10, 60), (50, -30), (80, 40), (110, 0), (150, 20)],
                                                [1, .8, 1.1, 1, .9, 1], degree=3,
                                                knots=[0, 0, 0, 0, .3, .65, 1, 1, 1, 1], dxfattribs={"layer": "SECTION"})
        points, bound = sample_spline(read_spline(entity, (1, 0, 0, 0)), .02)
        reference, shape = entity.construction_tool(), LineString(points)
        worst = max(shape.distance(Point(point.x, point.y)) for point in reference.points(i / 3000 for i in range(3001)))
        self.assertLessEqual(worst, bound)
        self.assertLessEqual(bound, .02)

    def test_spline_and_lines_form_closed_chain_with_provenance(self):
        spline = self.space.add_open_spline([(0, 0), (30, 40), (70, 40), (100, 0)], dxfattribs={"layer": "SECTION"})
        line = self.space.add_line((100, 0), (0, 0), dxfattribs={"layer": "SECTION"})
        doc = self.inspect()
        model = build_model(doc, self.model_config())
        self.assertEqual(model["summary"], {"modeled": 2, "ignored": 0, "failed": 0})
        self.assertEqual(set(model["objects"][0]["source_entity_ids"]), {spline.dxf.handle, line.dxf.handle})

    def test_open_spline_has_curved_preview_and_gap(self):
        self.space.add_open_spline([(0, 0), (30, 100), (70, 100), (100, 0)], dxfattribs={"layer": "SECTION"})
        doc = self.inspect()
        self.assertGreater(len(doc["entities"][0]["points"]), 2)
        self.assertAlmostEqual(analyze_document(doc, self.config())["diagnostics"][0]["gap_mm"], 100)

    def test_spline_invalid_plane_weights_periodic_and_fit_only_reported(self):
        for case in ("plane", "weight", "unclamped", "fit"):
            with self.subTest(case=case):
                self.setUp()
                if case == "fit":
                    entity = self.space.add_spline([(0, 0), (50, 50), (100, 0)], dxfattribs={"layer": "SECTION"})
                else:
                    entity = self.circle_spline()
                if case == "plane":
                    entity.control_points = [(x, y, 1) for x, y, z in entity.control_points]
                elif case == "weight":
                    weights = list(entity.weights)
                    weights[2] = 0
                    entity.weights = weights
                elif case == "unclamped":
                    entity.knots = list(range(len(entity.knots)))
                result = analyze_document(self.inspect(), self.config())
                self.assertFalse(result["buildable"])
                self.assertTrue(result["diagnostics"])

    def test_spline_budget_and_cancellation(self):
        from packing_assistant.cad3d.splines import read_spline, sample_spline
        spline = self.circle_spline()
        source = read_spline(spline, (1, 0, 0, 0))
        with patch.object(geometry, "MAX_ENTITY_VERTICES", 8), self.assertRaises(CAD3DError):
            sample_spline(source, .001)
        with patch.object(geometry, "_checkpoint", side_effect=RuntimeError("cancelled")), self.assertRaisesRegex(RuntimeError, "cancelled"):
            sample_spline(source, .1)

    def test_spline_instance_and_units_preserve_dimensions(self):
        import ezdxf
        spline = self.circle_spline(10)
        block = self.drawing.blocks.new("PROFILE")
        block.add_entity(spline.copy())
        self.space.delete_entity(spline)
        insertion = self.space.add_blockref("PROFILE", (1000, 2000), dxfattribs={"xscale": 2, "yscale": 2, "zscale": 2, "rotation": 45})
        result = build_model(self.inspect(), self.model_config())
        self.assertEqual(len(result["objects"]), 1)
        self.assertTrue(result["objects"][0]["source_entity_ids"][0].startswith(insertion.dxf.handle + "/"))
        self.assertAlmostEqual(result["objects"][0]["bounds"]["max"][0], .04, delta=.0002)
        for unit, factor in (("mm", .001), ("m", 1), ("in", .0254)):
            self.setUp()
            self.circle_spline(.02 / factor)
            d = self.inspect()
            a = analyze_document(d, self.config(unit=unit))
            self.assertTrue(a["buildable"], a["diagnostics"])
            self.assertAlmostEqual(a["contours"][0]["area_m2"], math.pi * .02 ** 2, delta=.00002)


if __name__ == "__main__":
    unittest.main()
