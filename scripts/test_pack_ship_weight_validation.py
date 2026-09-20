#!/usr/bin/env python3
"""The weight gate on rows handed over as an array (the file parser has its own flag).

Runs under pytest and, like every other script here, directly: `python scripts/test_pack_ship_weight_validation.py`.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.pack_ship_solve import rows_needing_human, run_plan  # noqa: E402


def test_zero_weight_without_meta_requires_human():
    materials = [
        {
            "id": "TEST-002",
            "name": "Unknown Weight Panel",
            "quantity": 1,
            "length_mm": 2000,
            "width_mm": 1000,
            "height_mm": 100,
            "weight_kg": 0,
        }
    ]

    needs = rows_needing_human(materials)

    assert len(needs) == 1
    assert needs[0]["id"] == "TEST-002"
    assert needs[0]["reason"] == "missing_weight"


def test_positive_weight_does_not_require_human():
    materials = [
        {
            "id": "TEST-003",
            "name": "Valid Panel",
            "quantity": 1,
            "length_mm": 2000,
            "width_mm": 1000,
            "height_mm": 100,
            "weight_kg": 100,
        }
    ]

    assert rows_needing_human(materials) == []

def test_positive_unit_weight_with_zero_total_weight_does_not_require_human():
    materials = [
        {
            "id": "TEST-004",
            "name": "Valid Unit Weight",
            "quantity": 2,
            "weight_kg": 12.5,
            "total_weight_kg": 0,
        }
    ]

    assert rows_needing_human(materials) == []


def test_nan_weight_requires_human():
    materials = [
        {
            "id": "TEST-005",
            "name": "NaN Weight",
            "quantity": 1,
            "weight_kg": float("nan"),
        }
    ]

    needs = rows_needing_human(materials)

    assert len(needs) == 1
    assert needs[0]["id"] == "TEST-005"


def test_infinite_weight_requires_human():
    materials = [
        {
            "id": "TEST-006",
            "name": "Infinite Weight",
            "quantity": 1,
            "weight_kg": float("inf"),
        }
    ]

    needs = rows_needing_human(materials)

    assert len(needs) == 1
    assert needs[0]["id"] == "TEST-006"


BASE = {"id": "ROW", "name": "Panel", "quantity": 2, "length_mm": 2000, "width_mm": 1000, "height_mm": 100}


def test_a_garbage_cell_is_not_excused_by_a_good_one():
    # each of these reached the engine before: 'abc' crashed it, -3 and NaN became the row's total weight
    for extra in ({"weight_kg": 12.5, "total_weight_kg": "abc"}, {"weight_kg": "abc", "total_weight_kg": 25},
                  {"weight_kg": 12.5, "total_weight_kg": -3}, {"weight_kg": 12.5, "total_weight_kg": float("nan")},
                  {"weight_kg": 12.5, "total_weight_kg": float("inf")}, {"weight_kg": True}):
        assert len(rows_needing_human([{**BASE, **extra}])) == 1, extra


def test_every_row_that_passes_is_one_the_engine_can_use():
    for extra in ({"weight_kg": 12.5}, {"total_weight_kg": 25}, {"weight_kg": 12.5, "total_weight_kg": 0},
                  {"weight_kg": 0, "total_weight_kg": 25}, {"weight_kg": "12.5"}, {"weight_kg": 12.5, "total_weight_kg": ""}):
        row = {**BASE, **extra}
        assert rows_needing_human([row]) == [], extra
        plan = run_plan(materials=[row])
        assert plan["ok"] is True and plan["source"] == "solver", (extra, plan.get("error"))
        assert math.isfinite(plan["weight_utilization"]) and plan["weight_utilization"] > 0, (extra, plan["weight_utilization"])


def test_no_container_count_comes_out_of_an_unusable_weight():
    for extra in ({"weight_kg": 0}, {"weight_kg": -5}, {"weight_kg": "abc"}, {"weight_kg": float("nan")}, {},
                  {"weight_kg": 12.5, "total_weight_kg": -3}):
        plan = run_plan(materials=[{**BASE, **extra}])
        assert plan["ok"] is False and plan["source"] == "needs_human", (extra, plan)
        assert "containers_used" not in plan, extra


if __name__ == "__main__":
    cases = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for case in cases:
        case()
    print(f"PASS pack_ship_weight_validation cases={len(cases)}")
