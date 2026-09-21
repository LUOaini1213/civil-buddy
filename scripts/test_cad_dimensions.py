"""Offline evidence binding: do not turn labels into invented engineering values."""
from copy import deepcopy
import io
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
import ezdxf
from packing_assistant.cad3d.dimensions import extract_dimensions, bind_dimension, validate_bindings, detach_changed_bindings
from packing_assistant.cad3d.commands import apply_command


class DimensionsTest(unittest.TestCase):
    def setUp(self):
        drawing = ezdxf.new("R2010")
        drawing.units = 4
        drawing.layers.new("SECTION")
        space = drawing.modelspace()
        shape = space.add_lwpolyline([(0, 0), (50, 0), (50, 153), (0, 153)], close=True, dxfattribs={"layer": "SECTION"})
        dim = space.add_linear_dim(base=(0, -20), p1=(0, 0), p2=(1499.816, 0), text="1500")
        dim.render()
        self.drawing = drawing
        self.dim = dim.dimension
        self.doc = {"dimensions": extract_dimensions(drawing), "entities": [{"id": shape.dxf.handle, "layer": "SECTION", "status": "ready"}], "layers": [{"name": "SECTION"}]}
        self.cfg = {"mode": "section", "unit": "mm", "layers": {"SECTION": "section"},
                    "parameters": {"section": {"height_m": None, "base_m": 0}}, "overrides": {}, "confirmed_solid": False}
        self.binding = {"dimension_id": self.dim.dxf.handle, "role": "section", "parameter": "height_m", "value_source": "annotation"}

    def test_annotation_measurement_and_unfilled_length_stay_distinct(self):
        row = self.doc["dimensions"][0]
        self.assertEqual(row["annotation_value"], 1500)
        self.assertAlmostEqual(row["measurement"], 1499.816)
        self.assertIsNone(self.cfg["parameters"]["section"]["height_m"])
        self.assertTrue(row["reference_only"])

    def test_explicit_binding_uses_only_chosen_value(self):
        annotated = bind_dimension(self.doc, self.cfg, self.binding)["config"]
        measured = bind_dimension(self.doc, self.cfg, {**self.binding, "value_source": "measurement"})["config"]
        self.assertEqual(annotated["parameters"]["section"]["height_m"], 1.5)
        self.assertAlmostEqual(measured["parameters"]["section"]["height_m"], 1.499816)
        self.assertFalse(annotated["confirmed_solid"])
        self.assertIsNone(self.cfg["parameters"]["section"]["height_m"])
        validate_bindings(self.doc, annotated)

    def test_unsupported_or_ambiguous_text_is_not_a_number(self):
        for label in ("50x153", "L=2000", "<>±2", "生成 3000", "1500/1600", "1e999"):
            self.dim.dxf.text = label
            row = extract_dimensions(self.drawing)[0]
            self.assertIsNone(row["annotation_value"], label)

    def test_explicit_annotation_unit_wins_without_rescaling_geometry(self):
        self.dim.dxf.text = "2 m"
        self.doc["dimensions"] = extract_dimensions(self.drawing)
        result = bind_dimension(self.doc, self.cfg, self.binding)
        self.assertEqual(result["config"]["parameters"]["section"]["height_m"], 2)
        self.assertEqual(result["config"]["unit"], "mm")

    def test_unknown_ids_values_and_ambiguous_targets_are_rejected(self):
        for binding in ({**self.binding, "dimension_id": "invented"}, {**self.binding, "value": 99},
                        {**self.binding, "target_id": "A"}, {**self.binding, "role": "wall"},
                        {**self.binding, "parameter": "width_m"}, {**self.binding, "value_source": "model"}):
            with self.subTest(binding=binding), self.assertRaises(ValueError):
                bind_dimension(self.doc, self.cfg, binding)

    def test_angular_and_nonplanar_dimensions_are_not_length_evidence(self):
        self.dim.dxf.dimtype = 2
        self.assertFalse(extract_dimensions(self.drawing)[0]["bindable"])
        self.dim.dxf.dimtype = 0
        self.dim.dxf.defpoint2 = (0, 0, 10)
        self.assertFalse(extract_dimensions(self.drawing)[0]["bindable"])

    def test_stale_binding_cannot_lie_about_manual_value(self):
        cfg = bind_dimension(self.doc, self.cfg, self.binding)["config"]
        cfg["parameters"]["section"]["height_m"] = 3
        with self.assertRaises(ValueError): validate_bindings(self.doc, cfg)

    def test_command_change_removes_old_evidence_and_preserves_source(self):
        cfg = bind_dimension(self.doc, self.cfg, self.binding)["config"]
        original = deepcopy(self.doc)
        updated = apply_command(self.doc, cfg, "把拉伸长度改为2米")["config"]
        self.assertEqual(updated["dimension_bindings"], [])
        self.assertEqual(len(cfg["dimension_bindings"]), 1)
        self.assertEqual(self.doc, original)

    def test_duplicate_binding_and_bool_values_are_rejected(self):
        cfg = bind_dimension(self.doc, self.cfg, self.binding)["config"]
        cfg["dimension_bindings"].append(deepcopy(self.binding))
        with self.assertRaises(ValueError): validate_bindings(self.doc, cfg)
        cfg["dimension_bindings"].pop()
        cfg["parameters"]["section"]["height_m"] = True
        with self.assertRaises(ValueError): validate_bindings(self.doc, cfg)

    def test_excluded_entity_cannot_receive_binding(self):
        eid = self.doc["entities"][0]["id"]
        binding = {k:v for k,v in self.binding.items() if k != "role"} | {"target_id": eid}
        cfg = deepcopy(self.cfg)
        cfg["selection"] = {"include_ids": None, "exclude_ids": [eid], "groups": []}
        with self.assertRaises(ValueError): bind_dimension(self.doc, cfg, binding)

    def test_formatted_annotation_preserves_raw_source(self):
        self.dim.dxf.text = r"{\H19.06704x;1500}"
        row = extract_dimensions(self.drawing)[0]
        self.assertEqual(row["annotation_value"], 1500)
        self.assertEqual(row["text"], "1500")
        self.assertEqual(row["raw_text"], self.dim.dxf.text)
        self.dim.dxf.text = r"{\H2x;1500} +/- 2"
        self.assertIsNone(extract_dimensions(self.drawing)[0]["annotation_value"])

    def test_unbounded_integer_is_validation_error(self):
        cfg = bind_dimension(self.doc, self.cfg, self.binding)["config"]
        cfg["parameters"]["section"]["height_m"] = 10 ** 400
        with self.assertRaises(ValueError): validate_bindings(self.doc, cfg)

    def test_selection_edit_detaches_excluded_entity_binding(self):
        eid = self.doc["entities"][0]["id"]
        binding = {k:v for k,v in self.binding.items() if k != "role"} | {"target_id":eid}
        before = bind_dimension(self.doc, self.cfg, binding)["config"]
        after = deepcopy(before)
        after["selection"] = {"include_ids":None,"exclude_ids":[eid]}
        detach_changed_bindings(before, after)
        self.assertEqual(after["dimension_bindings"], [])
        self.assertEqual(after["overrides"][eid]["height_m"], 1.5)


if __name__ == "__main__": unittest.main()
