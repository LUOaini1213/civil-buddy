"""Synthetic merged-cell reconciliation; contains no private packing-list data."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from packing_assistant.logistics import ledger
from packing_assistant.logistics.agent import propose_changes


def document():
    rows = []
    for index, (quantity, net) in enumerate(((4, 20), (6, 30)), 1):
        rows.append(dict.fromkeys(ledger.FIELDS, ledger.UNSPECIFIED) | {
            "id": f"R{index:05d}", "name": "Synthetic item", "quantity": quantity,
            "unit": "pcs", "net_kg": net, "weight_scope": "row", "evidence": {}})
    for field, value in (("gross_kg", 70), ("package_count", 2)):
        group = {"id": "synthetic:" + field, "row_ids": [r["id"] for r in rows],
                 "anchor_row_id": rows[0]["id"], "source": {"page": 2, "bbox": [10, 20, 80, 60]}}
        rows[0][field] = value
        for row in rows:
            row["evidence"][field] = {"raw": str(value) if row is rows[0] else "",
                                      "source": group["source"], "group": deepcopy(group)}
    return {"schema": ledger.SCHEMA, "source": {"filename": "synthetic.pdf", "sha256": "a"*64, "bytes": 100},
            "extraction": {}, "rows": rows,
            "totals": [{"label": "Total", "values": {"quantity": 10, "package_count": 2, "gross_kg": 70, "net_kg": 50},
                        "row_ids": [r["id"] for r in rows], "source": {"page": 2}}]}


class SharedCellTests(unittest.TestCase):
    def test_group_facts_count_once_without_filling_member_rows(self):
        doc = ledger.validate_document(document())
        summary = ledger.summarize(doc)
        self.assertEqual(summary["totals"], {"package_count": 2, "quantity": 10, "gross_kg": 70, "net_kg": 50})
        self.assertEqual(doc["rows"][1]["gross_kg"], ledger.UNSPECIFIED)
        self.assertTrue(summary["audit"]["ok"])
        self.assertFalse(summary["input_complete"])
        self.assertEqual(sum(i["code"] == "shared_cell" for i in summary["audit"]["issues"]), 2)

    def test_agent_summary_preserves_fractional_weight_digits(self):
        from packing_assistant.logistics.agent import execute
        doc = document()
        doc["rows"][0]["gross_kg"] = 12345.67
        doc["totals"][0]["values"]["gross_kg"] = 12345.67
        reply = execute({"project": {"id": "a"*32, "revision": 1}, "document": doc}, "logistics_summarize", {}, "汇总")
        self.assertTrue(reply["ok"])
        self.assertIn("毛重：12345.67 kg", reply["reply"])

    def test_partial_selection_has_no_share_of_group_amount(self):
        row = ledger.validate_document(document())["rows"][0]
        sums = ledger.aggregate_rows([row])["totals"]
        self.assertEqual(sums["gross_kg"], ledger.UNSPECIFIED)
        self.assertEqual(sums["package_count"], ledger.UNSPECIFIED)
        self.assertEqual(sums["net_kg"], 20)

    def test_missing_duplicate_or_conflicting_members_are_rejected(self):
        for mutation in (lambda d: d["rows"][1]["evidence"].pop("gross_kg"),
                         lambda d: d["rows"][1].update(gross_kg=70),
                         lambda d: d["rows"][1]["evidence"]["gross_kg"]["group"].update(row_ids=["R00002", "R00001"]),
                         lambda d: d["rows"][0]["evidence"]["gross_kg"]["group"]["row_ids"].append("R99999")):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                doc = document()
                mutation(doc)
                ledger.validate_document(doc)

    def test_group_weight_cannot_become_per_package_weight(self):
        doc = document()
        doc["rows"][0]["weight_scope"] = "package"
        with self.assertRaisesRegex(ValueError, "共享合并重量"):
            ledger.validate_document(doc)

    def test_group_edit_cannot_change_one_members_amount(self):
        for ident in ("R00001", "R00002"):
            with self.subTest(ident=ident), self.assertRaisesRegex(ValueError, "合并单元格"):
                propose_changes(document(), [{"row_id": ident, "field": "gross_kg", "value": 75}], "explicit synthetic edit")
        updated = propose_changes(document(), [{"row_id": "R00002", "field": "net_kg", "value": 31}], "explicit synthetic edit")
        self.assertEqual(updated["document"]["rows"][1]["net_kg"], 31)

    def test_mixed_units_do_not_adopt_the_source_mixed_total(self):
        doc = document()
        doc["rows"][1]["unit"] = "米"
        summary = ledger.summarize(doc)
        self.assertEqual(summary["quantities_by_unit"], {"pcs": 4, "米": 6})
        self.assertEqual(summary["totals"]["quantity"], ledger.UNSPECIFIED)
        self.assertIn("mixed_unit_source_total", {i["code"] for i in summary["audit"]["issues"]})

    def test_container_identifier_is_not_a_package_identifier(self):
        doc = document()
        for row in doc["rows"]:
            row["container_id"] = "SYNTHETIC-CONTAINER"
        summary = ledger.summarize(doc)
        self.assertEqual(summary["totals"]["package_count"], 2)
        self.assertNotIn("package_group_conflict", {i["code"] for i in summary["audit"]["issues"]})

    def test_shared_count_cannot_multiply_one_rows_per_package_weight(self):
        doc = document()
        for row in doc["rows"]:
            row["evidence"].pop("gross_kg")
            row["weight_scope"] = "package"
            row["gross_kg"] = 7
        checked = ledger.validate_document(doc)
        totals = ledger.aggregate_rows(checked["rows"][:1])["totals"]
        self.assertEqual(totals["net_kg"], ledger.UNSPECIFIED)
        self.assertEqual(totals["gross_kg"], ledger.UNSPECIFIED)

    def test_shared_gross_must_not_be_below_same_groups_net(self):
        doc = document()
        doc["rows"][0]["gross_kg"] = 40
        doc["totals"][0]["values"]["gross_kg"] = 40
        audit = ledger.audit_document(doc)
        self.assertFalse(audit["ok"])
        self.assertIn("group_gross_below_net", {i["code"] for i in audit["issues"]})

    def test_merged_counts_or_length_quantity_cannot_enter_solver(self):
        from packing_assistant.logistics.packing import prepare
        doc = document()
        for row in doc["rows"]:
            row["evidence"].pop("gross_kg")
            row.update(length_mm=100, width_mm=100, height_mm=100, dimension_scope="package", weight_scope="package", gross_kg=60)
        doc["totals"] = []
        result = prepare({"confirmed": True, "document": doc}, "packaged", "20GP", 1)
        self.assertFalse(result["ok"])
        self.assertIn("共享数值", str(result["needs_human"]))
        doc = document()
        doc["rows"] = doc["rows"][:1]
        doc["rows"][0].update(evidence={}, package_count=ledger.UNSPECIFIED, unit="米", dimension_scope="item", weight_scope="item", length_mm=100, width_mm=100, height_mm=100)
        doc["totals"] = []
        result = prepare({"confirmed": True, "document": doc}, "materials", "20GP", 1)
        self.assertFalse(result["ok"])
        self.assertIn("不能把米", str(result["needs_human"]))

    def test_net_and_gross_with_different_ranges_are_not_compared_per_row(self):
        doc = document()
        for row in doc["rows"]:
            row["evidence"].pop("gross_kg")
        doc["rows"][0].update(gross_kg=25, net_kg=50)
        doc["rows"][1].update(gross_kg=35, net_kg=ledger.UNSPECIFIED)
        group = {"id": "synthetic:net", "row_ids": [r["id"] for r in doc["rows"]],
                 "anchor_row_id": "R00001", "source": {"page": 2, "bbox": [80, 20, 100, 60]}}
        for row in doc["rows"]:
            row["evidence"]["net_kg"] = {"raw": "50", "source": group["source"], "group": deepcopy(group)}
        doc["totals"][0]["values"]["gross_kg"] = 60
        self.assertTrue(ledger.audit_document(doc)["ok"])


if __name__ == "__main__":
    unittest.main()
