from packing_assistant.tools.pack_ship_solve import rows_needing_human


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