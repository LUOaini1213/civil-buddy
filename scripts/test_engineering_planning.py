"""Offline planning verification against hand-calculated networks and calendars."""
from copy import deepcopy
from itertools import product
import json
import os
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from packing_assistant.engineering.planning import calculate, validate_plan
from packing_assistant.runtime import cancel


def task(ident, duration, *dependencies, **metadata):
    return {"id": ident, "name": "Synthetic " + ident, "duration": duration,
            "dependencies": [{"task_id": predecessor, "type": relation, "lag": lag} for predecessor, relation, lag in dependencies], **metadata}


def plan(*tasks, weekdays=None, holidays=None, start="2026-09-21", resources=None):
    return {"start_date": start, "calendar": {"weekdays": list(range(5)) if weekdays is None else weekdays, "holidays": [] if holidays is None else holidays}, "tasks": list(tasks), "resources": [] if resources is None else resources}


def fork_join():
    return plan(task("A", 2), task("B", 4, ("A", "FS", 0)), task("C", 3, ("A", "FS", 0)), task("D", 2, ("B", "FS", 0), ("C", "FS", 0)))


def rows(value):
    return {row["id"]: row for row in value["result"]["tasks"]}


class PlanningTests(unittest.TestCase):
    def test_eight_day_fork_join_and_float(self):
        original = fork_join(); snapshot = deepcopy(original)
        data = calculate(original); result = data["result"]; indexed = rows(data)
        self.assertEqual(original, snapshot)
        self.assertEqual(result["duration_workdays"], 8)
        self.assertEqual(result["critical_task_ids"], ["A", "B", "D"])
        self.assertEqual(indexed["C"]["total_float"], 1)
        self.assertEqual([(indexed[key]["start_offset"], indexed[key]["finish_offset"]) for key in "ABCD"], [(0, 2), (2, 6), (2, 5), (6, 8)])
        self.assertEqual(result["finish_date"], "2026-09-30")
        self.assertEqual(indexed["C"]["late_start"], "2026-09-24")
        self.assertEqual(indexed["C"]["late_finish"], "2026-09-28")
        self.assertEqual(validate_plan(data["plan"]), data["plan"])
        json.dumps(data, allow_nan=False)

    def test_multiple_critical_branches_and_disconnected_tasks(self):
        data = fork_join(); data["tasks"][2]["duration"] = 4
        data["tasks"].append(task("E", 1))
        result = calculate(data)
        self.assertEqual(set(result["result"]["critical_task_ids"]), set("ABCD"))
        self.assertEqual(rows(result)["E"]["total_float"], 7)

    def test_four_dependency_types_positive_and_negative_lag(self):
        # X occupies [0,5), A [5,9). Each B lasts 3. These are direct
        # inequalities, not a second invocation of the production algorithm.
        expected = {("FS", 2): 11, ("SS", 2): 7, ("FF", 2): 8, ("SF", 2): 4,
                    ("FS", -1): 8, ("SS", -1): 4, ("FF", -1): 5, ("SF", -1): 1}
        for (relation, lag), start in expected.items():
            with self.subTest(relation=relation, lag=lag):
                data = calculate(plan(task("X", 5), task("A", 4, ("X", "FS", 0)), task("B", 3, ("A", relation, lag))))
                by_id = rows(data)
                self.assertEqual(by_id["B"]["start_offset"], start)
                self.assertEqual(by_id["B"]["finish_offset"], start + 3)
                self.assertTrue(all(row["total_float"] >= 0 for row in data["result"]["tasks"]))
        data = calculate(plan(task("A", 2), task("B", 3, ("A", "SF", -2))))
        self.assertEqual(rows(data)["B"]["start_offset"], 0)

    def test_backward_pass_with_general_relations(self):
        # A starts at 0, B starts at 2 due to SS+2. B's ten days set H=12;
        # A cannot move at all even though its own end is at day 4.
        data = calculate(plan(task("A", 4), task("B", 10, ("A", "SS", 2))))
        self.assertEqual(data["result"]["duration_workdays"], 12)
        self.assertEqual(rows(data)["A"]["late_start_offset"], 0)
        self.assertEqual(rows(data)["A"]["late_finish_offset"], 4)
        self.assertEqual(set(data["result"]["critical_task_ids"]), {"A", "B"})

    def test_general_relation_bounds_match_exhaustive_small_schedules(self):
        # Enumerate feasible schedules independently of any graph recurrence.
        # Min/max starts among minimum-duration schedules are exact ES/LS.
        durations = {"A": 2, "B": 1, "C": 2}
        for first, second, lag in product(("FS", "SS", "FF", "SF"), ("FS", "SS", "FF", "SF"), (-1, 0, 1)):
            data = plan(task("A", 2), task("B", 1, ("A", first, lag)), task("C", 2, ("B", second, -lag), ("A", "FF", 0)), weekdays=list(range(7)))
            feasible = []
            for starts in product(range(9), repeat=3):
                start = dict(zip("ABC", starts))
                finish = {ident: start[ident] + duration for ident, duration in durations.items()}
                valid = True
                for item in data["tasks"]:
                    for dependency in item["dependencies"]:
                        relation = dependency["type"]
                        predecessor_event = (start if relation[0] == "S" else finish)[dependency["task_id"]]
                        successor_event = (start if relation[1] == "S" else finish)[item["id"]]
                        if successor_event < predecessor_event + dependency["lag"]:
                            valid = False
                if valid:
                    feasible.append((max(finish.values()), start))
            optimum = min(value[0] for value in feasible)
            optimal = [value[1] for value in feasible if value[0] == optimum]
            result = calculate(data); indexed = rows(result)
            with self.subTest(first=first, second=second, lag=lag):
                self.assertEqual(result["result"]["duration_workdays"], optimum)
                for ident in "ABC":
                    self.assertEqual(indexed[ident]["early_start_offset"], min(start[ident] for start in optimal))
                    self.assertEqual(indexed[ident]["late_start_offset"], max(start[ident] for start in optimal))

    def test_weekends_holidays_and_nonworking_start(self):
        data = calculate(plan(task("A", 2), task("B", 1, ("A", "FS", 0)), start="2026-09-25", holidays=["2026-09-28"]))
        by_id = rows(data)
        self.assertEqual((by_id["A"]["start"], by_id["A"]["end"]), ("2026-09-25", "2026-09-29"))
        self.assertEqual(by_id["B"]["start"], "2026-09-30")
        weekend = calculate(plan(task("A", 1), start="2026-09-26"))
        self.assertEqual(weekend["plan"]["start_date"], "2026-09-26")
        self.assertEqual(rows(weekend)["A"]["start"], "2026-09-28")
        self.assertTrue(weekend["result"]["warnings"])

    def test_milestones_and_inclusive_display_dates(self):
        data = calculate(plan(task("A", 2), task("M", 0, ("A", "FS", 0)), task("B", 1, ("M", "FS", 0))))
        by_id = rows(data)
        self.assertEqual(by_id["A"]["end"], "2026-09-22")
        self.assertEqual((by_id["M"]["start"], by_id["M"]["end"]), ("2026-09-23", "2026-09-23"))
        self.assertEqual(by_id["M"]["start"], by_id["B"]["start"])
        self.assertEqual(by_id["M"]["start_offset"], by_id["M"]["finish_offset"])
        only = calculate(plan(task("M", 0)))
        self.assertEqual(only["result"]["duration_workdays"], 0)
        self.assertEqual(only["result"]["finish_date"], "2026-09-21")

    def test_wbs_is_derived_without_double_counting(self):
        data = calculate(plan(task("ROOT", 0), task("SUB", 0, parent_id="ROOT"),
                              task("A", 2, parent_id="SUB", progress=100),
                              task("B", 4, ("A", "FS", 0), parent_id="ROOT", progress=50)))
        by_id = rows(data)
        self.assertEqual(by_id["ROOT"]["duration"], 6)
        self.assertAlmostEqual(by_id["ROOT"]["progress"], 200 / 3)
        self.assertEqual(by_id["ROOT"]["total_float"], None)
        self.assertEqual(set(by_id["ROOT"]["descendant_ids"]), {"A", "B"})
        self.assertEqual(set(data["result"]["critical_task_ids"]), {"A", "B"})
        self.assertEqual(data["plan"]["tasks"][0]["duration"], 0)
        for bad in [plan(task("P", 5), task("A", 1, parent_id="P")),
                    plan(task("P", 0, ("B", "FS", 0)), task("A", 1, parent_id="P"), task("B", 1)),
                    plan(task("P", 0), task("A", 1, parent_id="P"), task("B", 1, ("P", "FS", 0)))]:
            with self.assertRaisesRegex(ValueError, "汇总"):
                validate_plan(bad)

    def test_resource_conflicts_are_diagnostics_not_optimization(self):
        data = fork_join(); data["resources"] = [{"id": "CREW", "name": "Synthetic crew", "capacity": 1}]
        data["tasks"][1]["resources"] = data["tasks"][2]["resources"] = {"CREW": 1}
        result = calculate(data)["result"]
        self.assertEqual(result["duration_workdays"], 8)
        self.assertFalse(result["resource_feasible"])
        self.assertFalse(result["resource_optimized"])
        self.assertEqual(result["resource_conflicts"], [{"resource_id": "CREW", "start_offset": 2, "finish_offset": 5,
                         "start": "2026-09-23", "end": "2026-09-25", "demand": 2, "capacity": 1, "task_ids": ["B", "C"]}])
        data["resources"][0]["capacity"] = 2
        self.assertTrue(calculate(data)["result"]["resource_feasible"])
        sequential = plan(task("A", 1, resources={"CREW": 1}), task("B", 1, ("A", "FS", 0), resources={"CREW": 1}), resources=[{"id": "CREW", "name": "Crew", "capacity": 1}])
        self.assertEqual(calculate(sequential)["result"]["resources"][0]["peak_demand"], 1)

    def test_actual_dates_are_preserved_without_silent_rescheduling(self):
        data = plan(task("A", 2, actual_start="2026-09-24", actual_finish="2026-09-30", progress=80))
        result = calculate(data)
        self.assertEqual(rows(result)["A"]["start"], "2026-09-21")
        self.assertEqual(result["plan"]["tasks"][0]["actual_start"], "2026-09-24")
        self.assertIn("未使用实际记录", result["result"]["warnings"][0])
        self.assertEqual(len(result["result"]["warnings"]), 2)

    def test_cycles_unknown_ids_and_duplicate_relations(self):
        bad_plans = [plan(task("A", 1, ("B", "FS", 0)), task("B", 1, ("A", "SS", 0))),
                     plan(task("A", 1, ("UNKNOWN", "FS", 0))),
                     plan(task("A", 1, parent_id="B"), task("B", 1, parent_id="A")),
                     plan(task("A", 1, parent_id="UNKNOWN")), plan(task("A", 1), task("A", 2)),
                     plan(task("A", 1), task("B", 1, ("A", "FS", 0), ("A", "FS", 1)))]
        for value in bad_plans:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value)
        # Different constraints between the same pair remain meaningful.
        value = calculate(plan(task("A", 10), task("B", 4, ("A", "SS", 1), ("A", "FF", 2))))
        self.assertEqual(rows(value)["B"]["start_offset"], 8)

    def test_invalid_types_unknown_fields_and_never_invent_duration(self):
        for field, bad_values in {"duration": [True, -1, .5, "2", float("nan"), 10**1000],
                                  "progress": [False, -1, 101, "50", float("inf"), float("nan"), 10**1000]}.items():
            for value in bad_values:
                data = plan(task("A", 1)); data["tasks"][0][field] = value
                with self.subTest(field=field, value=str(value)[:20]), self.assertRaises(ValueError):
                    validate_plan(data)
        for mutate in [lambda data: data["tasks"][0].pop("duration"),
                       lambda data: data.update(code="print('untrusted')"),
                       lambda data: data["tasks"][0].update(filename="../../x"),
                       lambda data: data["tasks"][0].update(resources={"unknown": 1}),
                       lambda data: data["calendar"].update(weekdays=[True]),
                       lambda data: data["calendar"].update(weekdays=[]),
                       lambda data: data["calendar"].update(holidays=["2026-02-30"]),
                       lambda data: data["tasks"][0].update(actual_start="2026-09-25", actual_finish="2026-09-24")]:
            data = plan(task("A", 1)); mutate(data)
            with self.assertRaises(ValueError): validate_plan(data)

    def test_ten_year_task_and_calendar_budgets(self):
        with self.assertRaisesRegex(ValueError, "250"):
            validate_plan(plan(*(task("T" + str(index), 1) for index in range(251))))
        with self.assertRaisesRegex(ValueError, "10 年"):
            validate_plan(plan(task("A", 2000), task("B", 2000, ("A", "FS", 0))))
        with self.assertRaisesRegex(ValueError, "10 年"):
            validate_plan(plan(task("A", 600), weekdays=[0]))
        # Exactly 3652 continuously working days fit this ten-year window.
        result = calculate(plan(task("A", 3652), weekdays=list(range(7))))
        self.assertEqual(result["result"]["duration_workdays"], 3652)

    def test_shared_year_limit_and_final_day_milestone_boundaries(self):
        days = list(range(7))
        value = calculate(plan(task("A", 2), start="2099-12-31", weekdays=days))
        self.assertEqual(value["result"]["finish_date"], "2100-01-01")
        # Occupying the final date is valid; a following-day milestone is not.
        last = calculate(plan(task("A", 1), task("M", 0), start="2100-12-31", weekdays=days))
        self.assertEqual(rows(last)["A"]["end"], "2100-12-31")
        self.assertEqual(rows(last)["M"]["late_start"], "2100-12-31")
        only_milestone = calculate(plan(task("M", 0), start="2100-12-31", weekdays=days))
        self.assertEqual(only_milestone["result"]["finish_date"], "2100-12-31")
        for data in [plan(task("A", 1), start="2101-01-01", weekdays=days),
                     plan(task("A", 2), start="2100-12-31", weekdays=days),
                     plan(task("A", 1), task("M", 0, ("A", "FS", 0)), start="2100-12-31", weekdays=days),
                     plan(task("A", 1), holidays=["2101-01-01"]),
                     plan(task("A", 1, actual_start="2101-01-01"))]:
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "2100"):
                calculate(data)

    def test_pre_cancel_and_subsequent_call_are_isolated(self):
        event = threading.Event(); event.set()
        with cancel.scope(event=event), self.assertRaises(cancel.RunCancelled):
            calculate(fork_join())
        self.assertEqual(calculate(fork_join())["result"]["duration_workdays"], 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
