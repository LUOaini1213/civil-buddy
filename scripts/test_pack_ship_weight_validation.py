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