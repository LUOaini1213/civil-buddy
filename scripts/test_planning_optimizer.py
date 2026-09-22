"""Real OR-Tools checks against enumerated schedules and date boundaries."""
from copy import deepcopy
from itertools import product
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from ortools.sat.python import cp_model
from packing_assistant.engineering.planning import calculate
from packing_assistant.engineering.planning_optimize import optimize
from packing_assistant.runtime import cancel


def task(ident, duration, *deps, **metadata):
    return {"id": ident, "name": "Synthetic " + ident, "duration": duration,
            "dependencies": [{"task_id": first, "type": kind, "lag": lag} for first, kind, lag in deps], **metadata}


def plan(*tasks, capacity=1, start="2026-09-21", weekdays=None, holidays=None):
    return {"start_date": start, "calendar": {"weekdays": list(range(5)) if weekdays is None else weekdays,
                                             "holidays": [] if holidays is None else holidays},
            "tasks": list(tasks), "resources": [{"id": "crew", "name": "Synthetic crew", "capacity": capacity}]}


def indexed(value):
    return {row["id"]: row for row in value["result"]["tasks"]}


class OptimizerTests(unittest.TestCase):
    def test_hand_calculated_fork_join_with_one_and_two_crews(self):
        data = plan(task("A", 2), task("B", 4, ("A", "FS", 0), resources={"crew": 1}),
                    task("C", 3, ("A", "FS", 0), resources={"crew": 1}),
                    task("D", 2, ("B", "FS", 0), ("C", "FS", 0)))
        original = deepcopy(data)
        self.assertEqual(calculate(data)["result"]["duration_workdays"], 8)
        solved = optimize(data)["result"]
        self.assertEqual(solved["duration_workdays"], 11)
        self.assertEqual(solved["solver_status"], "OPTIMAL")
        self.assertTrue(solved["proven_optimal"])
        self.assertEqual(solved["resources"][0]["peak_demand"], 1)
        self.assertEqual(data, original)
        data["resources"][0]["capacity"] = 2
        self.assertEqual(optimize(data)["result"]["duration_workdays"], 8)

    def test_all_four_relations_with_resource_limits_match_brute_force(self):
        # Enumerate independent feasible starts, including B-before-A for SF.
        # This catches accidentally treating all dependency kinds as FS.
        for kind, lag in product(("FS", "SS", "FF", "SF"), (-1, 0, 1)):
            data = plan(task("A", 2, resources={"crew": 1}),
                        task("B", 2, ("A", kind, lag), resources={"crew": 1}))
            feasible = []
            for a, b in product(range(8), repeat=2):
                pred = a + (2 if kind[0] == "F" else 0)
                succ = b + (2 if kind[1] == "F" else 0)
                if succ >= pred + lag and (a + 2 <= b or b + 2 <= a):
                    feasible.append(max(a + 2, b + 2))
            with self.subTest(kind=kind, lag=lag):
                solved = optimize(data)
                self.assertEqual(solved["result"]["duration_workdays"], min(feasible))
                rows = indexed(solved)
                pred = rows["A"]["finish_offset" if kind[0] == "F" else "start_offset"]
                succ = rows["B"]["finish_offset" if kind[1] == "F" else "start_offset"]
                self.assertGreaterEqual(succ, pred + lag)
                self.assertLessEqual(solved["result"]["resources"][0]["peak_demand"], 1)

    def test_calendar_holiday_and_nonworking_start_match_cpm(self):
        data = plan(task("A", 2), task("B", 1, ("A", "FS", 0)),
                    start="2026-09-26", holidays=["2026-09-28"])
        plain, solved = calculate(data), optimize(data)
        for ident in ("A", "B"):
            self.assertEqual(indexed(plain)[ident]["start"], indexed(solved)[ident]["start"])
            self.assertEqual(indexed(plain)[ident]["end"], indexed(solved)[ident]["end"])
        self.assertEqual(solved["result"]["start_date"], "2026-09-29")
        self.assertTrue(any("首个可用工作日" in item for item in solved["result"]["warnings"]))

    def test_nested_summary_keeps_final_milestone_and_separates_cpm_fields(self):
        data = plan(task("ROOT", 0), task("W", 0, parent_id="ROOT"),
                    task("A", 2, parent_id="W", progress=50),
                    task("M", 0, ("A", "FS", 0), parent_id="W"))
        plain, solved = calculate(data), optimize(data)
        rows = indexed(solved)
        for ident in ("ROOT", "W"):
            self.assertEqual(rows[ident]["end"], "2026-09-23")
            self.assertEqual(rows[ident]["end"], rows["M"]["end"])
            self.assertEqual(rows[ident]["duration"], 2)
            self.assertEqual(rows[ident]["progress"], 50)
        for row in rows.values():
            self.assertFalse(row["critical"])
            self.assertIsNone(row["total_float"])
            for key in ("early_start", "early_finish", "late_start", "late_finish"):
                self.assertIsNone(row[key])
                self.assertIsNone(row[key + "_offset"])
                self.assertEqual(row["cpm_" + key], indexed(plain)[row["id"]][key])
                self.assertEqual(row["cpm_" + key + "_offset"], indexed(plain)[row["id"]][key + "_offset"])
        self.assertFalse(solved["result"]["critical_task_ids"])
        self.assertNotIn("未求资源受限最短工期", " ".join(solved["result"]["assumptions"]))

    def test_final_supported_day_occupancy_and_milestone_are_distinct(self):
        days = list(range(7))
        last = plan(task("A", 1, resources={"crew": 1}), start="2100-12-31", weekdays=days)
        result = optimize(last)
        self.assertEqual(indexed(result)["A"]["end"], "2100-12-31")
        self.assertEqual(indexed(result)["A"]["finish_offset"], 1)
        milestone = optimize(plan(task("M", 0), start="2100-12-31", weekdays=days))
        self.assertEqual(milestone["result"]["finish_date"], "2100-12-31")
        self.assertEqual(milestone["result"]["duration_workdays"], 0)
        independent = optimize(plan(task("A", 1), task("M", 0), start="2100-12-31", weekdays=days))
        self.assertEqual(indexed(independent)["M"]["start_offset"], 0)
        last["tasks"].append(task("M", 0, ("A", "FS", 0)))
        with self.assertRaisesRegex(ValueError, "2100"):
            optimize(last)

    def test_cross_year_2101_rejection_and_resource_delay_past_boundary(self):
        days = list(range(7))
        result = optimize(plan(task("A", 2), start="2099-12-31", weekdays=days))
        self.assertEqual(result["result"]["finish_date"], "2100-01-01")
        for data in [plan(task("A", 1), start="2101-01-01", weekdays=days),
                     plan(task("A", 2), start="2100-12-31", weekdays=days)]:
            with self.assertRaisesRegex(ValueError, "2100"):
                optimize(data)
        constrained = plan(task("A", 1, resources={"crew": 1}), task("B", 1, resources={"crew": 1}),
                           start="2100-12-31", weekdays=days)
        self.assertEqual(calculate(constrained)["result"]["duration_workdays"], 1)
        with self.assertRaisesRegex(ValueError, "无可行排程"):
            optimize(constrained)

    def test_overcapacity_and_nonfinite_timeout_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "单项需求"):
            optimize(plan(task("A", 1, resources={"crew": 2})))
        for seconds in (True, False, -1, 0, float("nan"), float("inf"), 10**1000):
            with self.subTest(seconds=str(seconds)[:20]), self.assertRaises(ValueError):
                optimize(plan(task("A", 1)), seconds=seconds)

    def test_cancel_after_actual_solver_discards_result_and_next_call_works(self):
        event = threading.Event()
        original = cp_model.CpSolver.solve

        def solve_then_cancel(solver, *args, **kwargs):
            result = original(solver, *args, **kwargs)
            event.set()
            return result

        with patch.object(cp_model.CpSolver, "solve", solve_then_cancel), cancel.scope(event=event):
            with self.assertRaises(cancel.RunCancelled):
                optimize(plan(task("A", 1)))
        self.assertEqual(optimize(plan(task("A", 1)))["result"]["duration_workdays"], 1)

    def test_feasible_status_does_not_claim_proven_optimal(self):
        original = cp_model.CpSolver.solve

        def solve_with_feasible_status(solver, *args, **kwargs):
            original(solver, *args, **kwargs)
            return cp_model.FEASIBLE

        with patch.object(cp_model.CpSolver, "solve", solve_with_feasible_status):
            result = optimize(plan(task("A", 1)))["result"]
        self.assertEqual(result["solver_status"], "FEASIBLE")
        self.assertFalse(result["proven_optimal"])
        self.assertIn("尚未证明最优", result["warnings"][-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
