"""Offline CAD section verification against independent analytic area integrals."""
from copy import deepcopy
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from packing_assistant.cad3d.geometry import inspect_dxf
from packing_assistant.engineering.section import analyze_section
from packing_assistant.runtime import cancel

HAS_DEPS = all(importlib.util.find_spec(name) for name in ("ezdxf", "shapely", "sectionproperties"))


@unittest.skipUnless(HAS_DEPS, "optional sectionproperties/CAD dependencies not installed")
class SectionTests(unittest.TestCase):
    def drawing(self, rings, *, unit="mm", origin=(0, 0), rotation=0, close=True):
        import ezdxf
        doc = ezdxf.new("R2010")
        doc.units = 4 if unit == "mm" else 6
        factor = 1 if unit == "mm" else .001
        angle = math.radians(rotation)
        cosine, sine = math.cos(angle), math.sin(angle)
        for ring in rings:
            points = [((x*cosine-y*sine)*factor+origin[0], (x*sine+y*cosine)*factor+origin[1]) for x, y in ring]
            doc.modelspace().add_lwpolyline(points, close=close, dxfattribs={"layer": "SECTION"})
        stream = io.StringIO(); doc.write(stream)
        inspected = inspect_dxf(stream.getvalue().encode(), "synthetic-section-properties.dxf")
        config = {"mode": "section", "unit": unit, "confirmed_solid": True, "layers": {"SECTION": "section"}}
        return inspected, config

    def rectangle(self, x, y, width, height):
        return [(x, y), (x+width, y), (x+width, y+height), (x, y+height)]

    def test_centered_hollow_rectangle_preserves_hole_and_properties(self):
        outer = self.rectangle(0, 0, 100, 60)
        hole = self.rectangle(5, 5, 90, 50)
        doc, config = self.drawing([outer, hole])
        snapshot = deepcopy((doc, config))
        result = analyze_section(doc, config)
        self.assertEqual((doc, config), snapshot)
        row = result["regions"][0]
        area = 100*60-90*50
        ixx = (100*60**3 - 90*50**3)/12
        iyy = (60*100**3 - 50*90**3)/12
        self.assertEqual(len(row["hole_ids"]), 1)
        self.assertAlmostEqual(row["area_mm2"], area, places=7)
        self.assertAlmostEqual(row["Ixx_mm4"], ixx, places=5)
        self.assertAlmostEqual(row["Iyy_mm4"], iyy, places=5)
        self.assertEqual(row["Ixy_mm4"], 0)
        self.assertAlmostEqual(row["centroid_source"][0], 50, places=9)
        self.assertAlmostEqual(row["centroid_source"][1], 30, places=9)
        self.assertAlmostEqual(row["rx_mm"], math.sqrt(ixx/area), places=9)
        self.assertAlmostEqual(row["I11_mm4"], iyy, places=5)
        self.assertAlmostEqual(row["principal_angle_deg"], -90, places=7)
        json.dumps(result, allow_nan=False)

    def test_eccentric_hole_signed_integrals_and_parallel_axis(self):
        # An off-centre hole catches accidental bounding-box or filled-hole use.
        doc, cfg = self.drawing([self.rectangle(0, 0, 100, 80), self.rectangle(10, 15, 20, 30)])
        row = analyze_section(doc, cfg)["regions"][0]
        areas, centers = (8000, -600), ((50, 40), (20, 30))
        area = sum(areas)
        cx = sum(a*c[0] for a, c in zip(areas, centers))/area
        cy = sum(a*c[1] for a, c in zip(areas, centers))/area
        ixx = 100*80**3/12 - 20*30**3/12 + sum(a*(c[1]-cy)**2 for a, c in zip(areas, centers))
        iyy = 80*100**3/12 - 30*20**3/12 + sum(a*(c[0]-cx)**2 for a, c in zip(areas, centers))
        ixy = sum(a*(c[0]-cx)*(c[1]-cy) for a, c in zip(areas, centers))
        for actual, expected in ((row["area_mm2"],area), (row["Ixx_mm4"],ixx), (row["Iyy_mm4"],iyy), (row["Ixy_mm4"],ixy)):
            self.assertTrue(math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-6),(actual,expected))
        self.assertAlmostEqual(row["centroid_source"][0], cx, places=8)
        self.assertAlmostEqual(row["centroid_source"][1], cy, places=8)

    def test_large_translation_does_not_change_centroidal_inertia(self):
        rings = [self.rectangle(0,0,100,60), self.rectangle(5,5,90,50)]
        base = analyze_section(*self.drawing(rings))["regions"][0]
        shifted = analyze_section(*self.drawing(rings,origin=(1e9,-2e9)))["regions"][0]
        for key in ("area_mm2","Ixx_mm4","Iyy_mm4","Ixy_mm4","I11_mm4","I22_mm4"):
            self.assertTrue(math.isclose(base[key],shifted[key],rel_tol=1e-11,abs_tol=1e-6),key)
        self.assertAlmostEqual(shifted["centroid_source"][0],1e9+50,places=6)
        self.assertAlmostEqual(shifted["centroid_source"][1],-2e9+30,places=6)

    def test_rotation_and_major_principal_axis_convention(self):
        # Tall rectangle has I11 about original +X; rotate geometry CCW 30°.
        rings = [self.rectangle(-20,-50,40,100)]
        row = analyze_section(*self.drawing(rings,rotation=30))["regions"][0]
        first, second = 40*100**3/12, 100*40**3/12
        theta = math.radians(30)
        self.assertAlmostEqual(row["I11_mm4"],first,places=5)
        self.assertAlmostEqual(row["I22_mm4"],second,places=5)
        self.assertAlmostEqual(row["Ixx_mm4"],first*math.cos(theta)**2+second*math.sin(theta)**2,places=5)
        self.assertAlmostEqual(row["Ixy_mm4"],(second-first)*math.sin(theta)*math.cos(theta),places=5)
        self.assertTrue(row["principal_angle_defined"])
        self.assertAlmostEqual(row["principal_angle_deg"],30,places=8)

    def test_equal_principal_moments_do_not_invent_an_angle(self):
        row = analyze_section(*self.drawing([self.rectangle(0,0,40,40)],rotation=17))["regions"][0]
        self.assertFalse(row["principal_angle_defined"])
        self.assertIsNone(row["principal_angle_deg"])
        self.assertEqual(row["Ixy_mm4"],0)

    def test_mm_and_m_inputs_have_same_mm_output(self):
        rings = [self.rectangle(0,0,100,60),self.rectangle(5,5,90,50)]
        millimeters = analyze_section(*self.drawing(rings,unit="mm"))["regions"][0]
        meters = analyze_section(*self.drawing(rings,unit="m"))["regions"][0]
        for key in ("area_mm2","Ixx_mm4","Iyy_mm4","Ixy_mm4","rx_mm","ry_mm"):
            self.assertTrue(math.isclose(millimeters[key],meters[key],rel_tol=1e-10,abs_tol=1e-6),key)
        self.assertAlmostEqual(meters["centroid_source"][0],.05,places=12)
        self.assertAlmostEqual(meters["centroid_source"][1],.03,places=12)

    def test_disconnected_regions_stay_separate(self):
        doc,cfg=self.drawing([self.rectangle(0,0,20,40),self.rectangle(100,200,30,10)])
        result=analyze_section(doc,cfg)
        self.assertEqual(len(result["regions"]),2)
        self.assertAlmostEqual(result["total_area_mm2"],1100,places=7)
        first,second=result["regions"]
        self.assertAlmostEqual(first["Ixx_mm4"],20*40**3/12,places=6)
        self.assertAlmostEqual(second["Ixx_mm4"],30*10**3/12,places=6)
        self.assertNotIn("combined_Ixx_mm4",result)

    def test_missing_units_confirmation_invalid_contour_and_building_rejected(self):
        doc,cfg=self.drawing([self.rectangle(0,0,100,60)])
        missing=deepcopy(cfg);missing.pop("unit")
        with self.assertRaisesRegex(ValueError,"单位"):analyze_section(doc,missing)
        missing=deepcopy(cfg);missing["confirmed_solid"]=False
        with self.assertRaisesRegex(ValueError,"确认"):analyze_section(doc,missing)
        missing=deepcopy(cfg);missing["mode"]="building"
        with self.assertRaisesRegex(ValueError,"截面模式"):analyze_section(doc,missing)
        doc,cfg=self.drawing([self.rectangle(0,0,100,60)],close=False)
        with self.assertRaisesRegex(ValueError,"轮廓问题"):analyze_section(doc,cfg)

    def test_no_extrusion_length_required_but_missing_hole_blocks(self):
        doc,cfg=self.drawing([self.rectangle(0,0,100,60),self.rectangle(5,5,90,50)])
        cfg["parameters"]={"section":{"height_m":None,"base_m":None}}
        self.assertGreater(analyze_section(doc,cfg)["total_area_mm2"],0)
        cfg["selection"]={"include_ids":[doc["entities"][0]["id"]]}
        with self.assertRaisesRegex(ValueError,"轮廓问题"):analyze_section(doc,cfg)

    def test_cancel_before_mesh_and_after_solver_discards_output(self):
        from sectionproperties.analysis.section import Section
        doc,cfg=self.drawing([self.rectangle(0,0,100,60)])
        event=threading.Event();event.set()
        with cancel.scope(event=event):
            with self.assertRaises(cancel.RunCancelled):analyze_section(doc,cfg)
        event.clear();original=Section.calculate_geometric_properties
        def solve_then_cancel(section):
            result=original(section);event.set();return result
        with cancel.scope(event=event),patch.object(Section,"calculate_geometric_properties",solve_then_cancel):
            with self.assertRaises(cancel.RunCancelled):analyze_section(doc,cfg)
        self.assertGreater(analyze_section(doc,cfg)["total_area_mm2"],0)


if __name__ == "__main__":unittest.main()
