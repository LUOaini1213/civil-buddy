"""Offline beam/frame verification: analytic references, topology, and isolation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
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
from packing_assistant.engineering import frame
from packing_assistant.runtime import cancel


class FrameInputTests(unittest.TestCase):
    def test_unknown_fields_and_arbitrary_code_are_rejected(self):
        for key, value in (("code", "__import__('os').system('anything')"),
                           ("filename", "../../model.py"), ("solver", "nonlinear")):
            with self.subTest(key=key):
                data = frame.synthetic_example()
                data[key] = value
                with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)
        data = frame.synthetic_example()
        data["members"][0]["releases"] = [False] * 12
        with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)

    def test_numeric_units_and_material_consistency(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "4", 10**1000):
            with self.subTest(value=repr(value)[:30]):
                data = frame.synthetic_example()
                data["nodes"][1]["x_m"] = value
                with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)
        data = frame.synthetic_example(); data["units"] = "mm"
        with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)
        data = frame.synthetic_example(); data["materials"][0]["G_Pa"] = 20e9
        with self.assertRaisesRegex(frame.FrameAnalysisError, "各向同性"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["sections"][0]["Iy_m4"] = 0
        with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)

    def test_unknown_ids_duplicate_members_and_unsupported_supports(self):
        data = frame.synthetic_example(); data["members"][0]["i"] = "__unknown__"
        with self.assertRaisesRegex(frame.FrameAnalysisError, "未知"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["members"].append({**data["members"][0], "id": "B2", "i": "N2", "j": "N1"})
        with self.assertRaisesRegex(frame.FrameAnalysisError, "重复"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["nodes"][0]["support"][0] = 1
        with self.assertRaisesRegex(frame.FrameAnalysisError, "布尔"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["nodes"][1]["x_m"] = 0
        with self.assertRaisesRegex(frame.FrameAnalysisError, "重合"): frame.validate_frame(data)

    def test_loads_cannot_silently_disappear(self):
        data = frame.synthetic_example(); data["combinations"][0]["factors"] = {"unknown": 1}
        with self.assertRaisesRegex(frame.FrameAnalysisError, "工况"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["load_cases"].append({"id": "L2"})
        with self.assertRaisesRegex(frame.FrameAnalysisError, "显式荷载"): frame.validate_frame(data)
        data["nodal_loads"].append({"node_id": "N1", "case_id": "L2", "direction": "FX", "value": 0})
        with self.assertRaisesRegex(frame.FrameAnalysisError, "静默忽略"): frame.validate_frame(data)
        data = frame.synthetic_example(); data["member_loads"][0]["x2_m"] = 4000
        with self.assertRaises(frame.FrameAnalysisError): frame.validate_frame(data)

    def test_orphan_and_implicit_intermediate_node_rejected(self):
        data = frame.synthetic_example()
        data["nodes"].append({"id": "N3", "x_m": 0, "y_m": 1, "z_m": 0, "support": [False] * 6})
        with self.assertRaisesRegex(frame.FrameAnalysisError, "孤立"): frame.validate_frame(data)
        data["nodes"][2].update(x_m=2, y_m=0)
        with self.assertRaisesRegex(frame.FrameAnalysisError, "拆分"): frame.validate_frame(data)

    def test_budgets_missing_dependency_and_source_label(self):
        data = frame.synthetic_example(); data["samples"] = 10000
        with self.assertRaisesRegex(frame.FrameAnalysisError, "samples"): frame.validate_frame(data)
        with patch.object(frame, "MAX_RESULT_POINTS", 5):
            with self.assertRaisesRegex(frame.FrameAnalysisError, "预算"): frame.validate_frame(frame.synthetic_example())
        with patch.object(frame, "available", return_value=False):
            with self.assertRaisesRegex(frame.FrameAnalysisError, "requirements-analysis"): frame.analyze_frame(frame.synthetic_example())
        for kind in ("beam", "frame"):
            self.assertEqual(frame.validate_frame(frame.synthetic_example(kind))["source"], "synthetic")

    def test_cancelled_input_exits_before_engine(self):
        event = threading.Event(); event.set()
        with cancel.scope(event=event), patch.object(frame, "available") as imported:
            with self.assertRaises(cancel.RunCancelled): frame.analyze_frame(frame.synthetic_example())
            imported.assert_not_called()


@unittest.skipUnless(frame.available(), "optional PyniteFEA not installed")
class FrameSolverTests(unittest.TestCase):
    def test_long_member_cannot_silently_connect_a_nearby_node(self):
        from Pynite import FEModel3D
        # A synthetic long member is near an independently connected column.
        # Verify the actual engine topology, including its inclusive boundary,
        # so this regression does not merely repeat our validation formula.
        for gap, should_split in ((5e-8, True), (1.00001e-7, True), (2e-7, False)):
            with self.subTest(gap=gap):
                data = frame.synthetic_example()
                data["nodes"][1]["x_m"] = 100000.0
                data["member_loads"][0]["x2_m"] = 100000.0
                data["nodes"].extend([
                    {"id": "N3", "x_m": 50000., "y_m": gap, "z_m": 0., "support": [False] * 6},
                    {"id": "N4", "x_m": 50000., "y_m": 1., "z_m": 0., "support": [True] * 6},
                ])
                data["members"].append({"id": "B2", "i": "N3", "j": "N4", "material_id": "M1", "section_id": "S1", "rotation_deg": 0.})
                engine = FEModel3D()
                for row in data["materials"]:
                    engine.add_material(row["id"], row["E_Pa"], row["G_Pa"], row["nu"], row["density_kg_m3"])
                for row in data["sections"]:
                    engine.add_section(row["id"], row["A_m2"], row["Iy_m4"], row["Iz_m4"], row["J_m4"])
                for row in data["nodes"]:
                    engine.add_node(row["id"], row["x_m"], row["y_m"], row["z_m"])
                engine.add_member("B1", "N1", "N2", "M1", "S1")
                engine.members["B1"].descritize()
                edges = [(sub.i_node.name, sub.j_node.name) for sub in engine.members["B1"].sub_members.values()]
                if should_split:
                    self.assertEqual(edges, [("N1", "N3"), ("N3", "N2")])
                    with self.assertRaisesRegex(frame.FrameAnalysisError, "拆分"):
                        frame.validate_frame(data)
                else:
                    self.assertEqual(edges, [("N1", "N2")])
                    self.assertEqual(len(frame.validate_frame(data)["members"]), 2)

    def test_uniform_simply_supported_beam_against_closed_form(self):
        data = frame.synthetic_example(); snapshot = deepcopy(data)
        result = frame.analyze_frame(data)
        self.assertEqual(data, snapshot)
        combo = result["combinations"][0]
        curve = combo["members"][0]["curves"]
        load, length, elastic, inertia = 1000, 4, 200e9, 8e-6
        for node in combo["nodes"]:
            self.assertAlmostEqual(node["reaction_N"][1], load * length / 2, places=7)
        self.assertAlmostEqual(max(map(abs, curve["moment_z_Nm"])), load * length**2 / 8, places=7)
        self.assertAlmostEqual(max(map(abs, curve["dy_m"])), 5 * load * length**4 / (384 * elastic * inertia), places=12)
        self.assertAlmostEqual(curve["dy_m"][0], 0, places=12)
        self.assertAlmostEqual(curve["dy_m"][-1], 0, places=12)
        self.assertEqual(result["engine"]["name"], "PyniteFEA")
        json.dumps(result, allow_nan=False)

    def test_cantilever_tip_load_and_global_rotation(self):
        data = frame.synthetic_example()
        # A Y-aligned cantilever with a global X load verifies local/global axes.
        data["nodes"][0]["support"] = [True] * 6
        data["nodes"][1].update(x_m=0, y_m=4, support=[False] * 6)
        data["member_loads"] = []
        data["nodal_loads"] = [{"node_id": "N2", "case_id": "L1", "direction": "FX", "value": 1000}]
        result = frame.analyze_frame(data)["combinations"][0]
        root, tip = result["nodes"]
        self.assertAlmostEqual(root["reaction_N"][0], -1000, places=6)
        self.assertAlmostEqual(root["reaction_Nm"][2], 4000, places=6)
        self.assertAlmostEqual(tip["displacement_m"][0], 1000 * 4**3 / (3 * 200e9 * 8e-6), places=11)
        self.assertAlmostEqual(tip["rotation_rad"][2], -1000 * 4**2 / (2 * 200e9 * 8e-6), places=11)
        self.assertAlmostEqual(result["members"][0]["local_axes_global"][0][1], 1, places=12)

    def test_partial_and_triangular_distribution_reactions(self):
        data = frame.synthetic_example()
        # Full triangular load, zero at left and 1000 N/m at right: Rl=qL/6, Rr=qL/3.
        data["member_loads"][0]["w1_N_m"] = 0
        result = frame.analyze_frame(data)["combinations"][0]
        self.assertAlmostEqual(result["nodes"][0]["reaction_N"][1], 1000 * 4 / 6, places=7)
        self.assertAlmostEqual(result["nodes"][1]["reaction_N"][1], 1000 * 4 / 3, places=7)
        # Only the right half carries a uniform load; resultant at x=3 m.
        data = frame.synthetic_example(); data["member_loads"][0]["x1_m"] = 2
        result = frame.analyze_frame(data)["combinations"][0]
        self.assertAlmostEqual(result["nodes"][0]["reaction_N"][1], 500, places=7)
        self.assertAlmostEqual(result["nodes"][1]["reaction_N"][1], 1500, places=7)

    def test_explicit_load_combinations_scale_without_implicit_factors(self):
        data = frame.synthetic_example()
        data["combinations"].append({"id": "C2", "factors": {"L1": -2.0}})
        first, second = frame.analyze_frame(data)["combinations"]
        self.assertAlmostEqual(second["nodes"][0]["reaction_N"][1], -2 * first["nodes"][0]["reaction_N"][1], places=7)
        for one, two in zip(first["members"][0]["curves"]["dy_m"], second["members"][0]["curves"]["dy_m"]):
            self.assertAlmostEqual(two, -2 * one, places=12)

    def test_portal_frame_global_force_and_moment_equilibrium(self):
        data = frame.synthetic_example("frame")
        combo = frame.analyze_frame(data)["combinations"][0]
        nodes = {row["id"]: row for row in data["nodes"]}
        sum_fx, sum_fy, sum_mz = 1000.0, 0.0, -3000.0
        for result in combo["nodes"]:
            geometry = nodes[result["id"]]
            fx, fy, _ = result["reaction_N"]
            sum_fx += fx; sum_fy += fy
            sum_mz += result["reaction_Nm"][2] + geometry["x_m"] * fy - geometry["y_m"] * fx
        self.assertAlmostEqual(sum_fx, 0, places=6)
        self.assertAlmostEqual(sum_fy, 0, places=6)
        self.assertAlmostEqual(sum_mz, 0, places=6)
        self.assertGreater(combo["nodes"][1]["displacement_m"][0], 0)

    def test_unloaded_unrestrained_rotation_is_rejected(self):
        data = frame.synthetic_example()
        data["nodes"][0]["support"][3] = False
        with self.assertRaisesRegex(frame.FrameAnalysisError, "不稳定"): frame.analyze_frame(data)
        for node in data["nodes"]: node["support"] = [False] * 6
        with self.assertRaisesRegex(frame.FrameAnalysisError, "不稳定"): frame.analyze_frame(data)

    def test_cancellation_after_solver_discards_results_and_does_not_leak(self):
        from Pynite import FEModel3D
        original = FEModel3D.analyze_linear
        event = threading.Event()
        def run_then_cancel(model, *args, **kwargs):
            result = original(model, *args, **kwargs)
            event.set()
            return result
        with cancel.scope(event=event), patch.object(FEModel3D, "analyze_linear", run_then_cancel):
            with self.assertRaises(cancel.RunCancelled): frame.analyze_frame(frame.synthetic_example())
        self.assertTrue(frame.analyze_frame(frame.synthetic_example())["ok"])

    def test_parallel_models_have_separate_solver_state(self):
        first = frame.synthetic_example(); second = frame.synthetic_example()
        second["member_loads"][0].update(w1_N_m=500, w2_N_m=500)
        cwd = os.getcwd()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(frame.analyze_frame, [first, second]))
        self.assertEqual(os.getcwd(), cwd)
        one, two = [r["combinations"][0]["nodes"][0]["reaction_N"][1] for r in results]
        self.assertAlmostEqual(one, 2000, places=7)
        self.assertAlmostEqual(two, -1000, places=7)


if __name__ == "__main__": unittest.main()
