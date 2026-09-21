"""Offline synthetic intake evidence. These fixtures are not real shipment acceptance."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.logistics import parse_document, validate_document, audit_document, summarize
from packing_assistant.logistics import intake, ocr
from packing_assistant.logistics.ledger import UNSPECIFIED
from packing_assistant.runtime.cancel import RunCancelled, scope


HEADERS = ["package_id", "material_id", "name", "package_count", "quantity", "units_per_package", "unit", "length_mm", "width_mm", "height_mm", "dimension_scope", "net_kg", "gross_kg", "weight_scope"]
VALUES = ["C001", "P001", "Synthetic panel", 2, 10, 5, "pcs", 1200, 800, 100, "package", 100, 110, "package"]


def csv_bytes(headers=HEADERS, rows=None):
    import csv
    from io import StringIO
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    writer.writerows(rows or [VALUES])
    return out.getvalue().encode("utf-8-sig")


def pdf_bytes(pages=2, blank=False):
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(700, 800)
        if blank:
            continue
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        commands = []
        for x in (30, 210, 360, 650):
            commands.append(f"{x} 650 m {x} 730 l S")
        for y in (650, 690, 730):
            commands.append(f"30 {y} m 650 {y} l S")
        for x, y, text in ((40, 705, "Name"), (220, 705, "Quantity"), (370, 705, "Total net weight (kg)"), (40, 665, "Synthetic panel"), (220, 665, "10"), (370, 665, "100")):
            text = text.replace("(", r"\(").replace(")", r"\)")
            commands.append(f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


class IntakeTests(unittest.TestCase):
    def test_native_csv_keeps_separate_quantities_and_net_gross(self):
        doc = parse_document(csv_bytes(), "synthetic.csv", "off")
        row = doc["rows"][0]
        self.assertEqual([row[f] for f in HEADERS], VALUES)
        self.assertEqual(row["evidence"]["quantity"]["source"], {"row": 2, "column": 5})
        self.assertEqual(summarize(doc)["totals"], {"package_count": 2, "quantity": 10, "net_kg": 200, "gross_kg": 220})
        self.assertTrue(summarize(doc)["ready_for_packing"])

    def test_changing_column_order_cannot_change_interpretation(self):
        original = dict(zip(HEADERS, VALUES))
        headers = list(reversed(HEADERS))
        doc = parse_document(csv_bytes(headers, [[original[h] for h in headers]]), "reordered.csv")
        self.assertEqual({h: doc["rows"][0][h] for h in HEADERS}, original)

    def test_unknown_quantity_and_units_are_not_invented(self):
        doc = parse_document(csv_bytes(["name", "length", "width", "height", "net weight"], [["Synthetic", 1, 2, 3, 100]]), "unknown.csv")
        row = doc["rows"][0]
        self.assertEqual(row["quantity"], UNSPECIFIED)
        self.assertEqual(row["length_mm"], UNSPECIFIED)
        self.assertEqual(row["net_kg"], UNSPECIFIED)
        self.assertFalse(doc["report"]["ok"])
        self.assertFalse(summarize(doc)["ready_for_packing"])

    def test_explicit_units_and_scope_are_evidenced(self):
        doc = parse_document(csv_bytes(["name", "箱长(cm)", "箱宽(cm)", "箱高(cm)", "Net weight per package (kg)", "Gross weight per package (kg)", "箱数"], [["Synthetic", 120, 80, 10, 100, 110, 2]]), "units.csv")
        row = doc["rows"][0]
        self.assertEqual(row["length_mm"], 1200)
        self.assertEqual(row["dimension_scope"], "package")
        self.assertEqual(row["weight_scope"], "package")
        self.assertEqual(row["evidence"]["length_mm"]["raw"], "120")

    def test_scope_is_not_inferred_from_magnitude(self):
        values = list(VALUES); values[10] = ""; values[13] = ""
        doc = parse_document(csv_bytes(rows=[values]), "scope.csv")
        self.assertEqual(summarize(doc)["totals"]["gross_kg"], UNSPECIFIED)
        self.assertIn("unknown_scope", [i["code"] for i in doc["report"]["issues"]])

    def test_totals_and_quantity_reconcile_independently(self):
        values = list(VALUES); values[4] = 11
        total = ["", "", "Grand total", 2, 10, "", "", "", "", "", "", 201, 220, "row"]
        doc = parse_document(csv_bytes(rows=[values, total]), "mismatch.csv")
        self.assertEqual(len(doc["rows"]), 1)
        self.assertEqual(len(doc["totals"]), 1)
        codes = [i["code"] for i in doc["report"]["issues"]]
        self.assertIn("quantity_mismatch", codes)
        self.assertIn("total_mismatch", codes)

    def test_duplicate_headers_and_fractional_counts_remain_unresolved(self):
        doc = parse_document(csv_bytes(["name", "quantity", "件数", "package_count"], [["Synthetic", 10, 12, "2.5"]]), "conflict.csv")
        row = doc["rows"][0]
        self.assertEqual(row["quantity"], UNSPECIFIED)
        self.assertEqual(row["package_count"], UNSPECIFIED)
        self.assertFalse(doc["report"]["ok"])

    def test_repeated_headers_never_drop_repeated_cargo(self):
        doc = parse_document(csv_bytes(rows=[VALUES, HEADERS, VALUES]), "repeat.csv")
        self.assertEqual(len(doc["rows"]), 2)
        self.assertEqual([r["id"] for r in doc["rows"]], ["R00001", "R00002"])
        self.assertEqual(doc["rows"][1]["evidence"]["name"]["source"]["row"], 4)

    def test_xlsx_sheets_formula_and_formatted_ids(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = "Sheet A"
        for sheet in (wb.active, wb.create_sheet("Sheet B")):
            sheet.append(HEADERS); sheet.append(VALUES)
        wb.active["A2"] = 7; wb.active["A2"].number_format = "0000"
        wb.active["E2"] = "=2*5"
        wb.active["B2"] = None  # read_only EmptyCell has no row/column attributes
        data = BytesIO(); wb.save(data); wb.close()
        doc = parse_document(data.getvalue(), "synthetic.xlsx")
        self.assertEqual(len(doc["rows"]), 2)
        self.assertEqual(doc["rows"][0]["package_id"], "0007")
        self.assertEqual(doc["rows"][0]["quantity"], UNSPECIFIED)
        self.assertEqual(doc["rows"][0]["evidence"]["quantity"]["raw"], "=2*5")
        self.assertEqual(doc["rows"][1]["evidence"]["name"]["source"]["sheet"], "Sheet B")

    def test_real_pdf_table_geometry_and_page_duplicates(self):
        doc = parse_document(pdf_bytes(), "synthetic-two-pages.pdf", "off")
        self.assertEqual(len(doc["rows"]), 2)
        self.assertEqual([r["quantity"] for r in doc["rows"]], [10, 10])
        self.assertEqual([r["evidence"]["name"]["source"]["page"] for r in doc["rows"]], [1, 2])
        self.assertEqual(doc["rows"][0]["evidence"]["name"]["source"]["coordinate_system"], "pdf_points")
        self.assertEqual(len(doc["rows"][0]["evidence"]["name"]["source"]["bbox"]), 4)

    def test_blank_pdf_requires_ocr_without_empty_success(self):
        doc = parse_document(pdf_bytes(1, True), "synthetic-scan.pdf", "off")
        self.assertFalse(doc["report"]["ok"])
        self.assertIn("ocr_required", [i["code"] for i in doc["report"]["issues"]])

    def test_injected_local_ocr_preserves_raw_boxes_and_requires_confirmation(self):
        html = "<table><tr>" + "".join(f"<td>{h}</td>" for h in HEADERS) + "</tr><tr>" + "".join(f"<td>{v}</td>" for v in VALUES) + "</tr></table>"
        converted = ocr.tables_from_result({"table_res_list": [{"pred_html": html, "cell_box_list": [[i, 0, i + 1, 10] for i in range(28)]}]}, page=1)
        with patch.object(ocr, "extract_tables", return_value=converted):
            doc = parse_document(b"synthetic injected OCR bytes", "synthetic.png")
        self.assertEqual(doc["rows"][0]["quantity"], 10)
        self.assertEqual(doc["rows"][0]["evidence"]["quantity"]["source"]["bbox"], [18, 0, 19, 10])
        self.assertTrue(summarize(doc)["input_complete"])
        self.assertTrue(summarize(doc)["requires_review"])
        self.assertTrue(summarize(doc)["confirmation_required"])
        self.assertIn("ocr_requires_confirmation", [i["code"] for i in doc["report"]["issues"]])

    def test_same_package_material_rows_do_not_duplicate_package_totals(self):
        second = list(VALUES); second[1] = "P002"; second[2] = "Synthetic bolts"
        total = ["", "", "Grand total", 2, 20, "", "", "", "", "", "", 200, 220, "row"]
        doc = parse_document(csv_bytes(rows=[VALUES, second, total]), "same-package.csv")
        summary = summarize(doc)
        self.assertEqual(summary["totals"], {"package_count": 2, "quantity": 20, "net_kg": 200, "gross_kg": 220})
        self.assertTrue(summary["audit"]["ok"])

    def test_same_package_conflicting_weights_never_add_up(self):
        second = list(VALUES); second[1] = "P002"; second[12] = 115
        doc = parse_document(csv_bytes(rows=[VALUES, second]), "conflicting-package.csv")
        summary = summarize(doc)
        self.assertEqual(summary["totals"]["gross_kg"], UNSPECIFIED)
        self.assertEqual(summary["totals"]["package_count"], UNSPECIFIED)
        self.assertFalse(summary["ready_for_packing"])
        self.assertIn("package_group_conflict", [i["code"] for i in summary["audit"]["issues"]])

    def test_mixed_quantity_units_are_grouped_not_summed(self):
        second = list(VALUES); second[0] = "C002"; second[6] = "m"
        total = ["", "", "Grand total", 4, 20, "", "", "", "", "", "", 400, 440, "row"]
        doc = parse_document(csv_bytes(rows=[VALUES, second, total]), "mixed-units.csv")
        summary = summarize(doc)
        self.assertEqual(summary["totals"]["quantity"], UNSPECIFIED)
        self.assertEqual(summary["quantities_by_unit"], {"pcs": 10, "m": 10})
        self.assertIn("total_unverifiable", [i["code"] for i in summary["audit"]["issues"]])

    def test_ocr_environment_is_not_reported_ready_without_manifest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); exe = root / "python.exe"; exe.write_bytes(b"synthetic executable placeholder")
            manifest = root / "ready.json"
            with patch.dict(os.environ, {"CIVIL_LOGISTICS_OCR_PYTHON": str(exe), "CIVIL_LOGISTICS_OCR_READY_MANIFEST": str(manifest)}):
                cap = ocr.capability()
                self.assertTrue(cap["environment_found"]); self.assertFalse(cap["available"])
                model = root / "model.bin"; model.write_bytes(b"synthetic")
                manifest.write_text(json.dumps({"schema": "civil.logistics.ocr-ready.v1", "python": str(exe), "paddleocr": "test", "paddlepaddle": "test", "models": [{"path": str(model), "bytes": model.stat().st_size}]}), encoding="utf-8")
                self.assertTrue(ocr.capability()["available"])
                model.write_bytes(b"changed")
                self.assertFalse(ocr.capability()["available"])

    def test_complex_ocr_merged_table_is_explicitly_unsupported(self):
        result = ocr.tables_from_result({"table_res_list": [{"pred_html": '<table><tr><td rowspan="2">Name</td><td>Qty</td></tr><tr><td>10</td></tr></table>'}]}, page=1)
        self.assertEqual(result["tables"], [])
        self.assertEqual(result["issues"][0]["code"], "ocr_merged_cells")

    def test_corrupt_files_zip_and_limits(self):
        for data, name in ((b"bad", "x.xlsx"), (b"bad", "x.xls"), (b"a", "../x.csv")):
            with self.assertRaises((ValueError, OSError)):
                parse_document(data, name)
        data = BytesIO()
        with ZipFile(data, "w") as archive:
            for i in range(4097):
                archive.writestr(str(i), b"")
        with self.assertRaisesRegex(ValueError, "解压"):
            parse_document(data.getvalue(), "synthetic-bomb.xlsx")
        with patch.object(intake, "MAX_ROWS", 1), self.assertRaisesRegex(ValueError, "物料行"):
            parse_document(csv_bytes(rows=[VALUES, VALUES]), "limit.csv")

    def test_image_pixel_limit_checked_before_ocr_runtime(self):
        from PIL import Image
        image = BytesIO(); Image.new("RGB", (20, 20)).save(image, format="PNG")
        with patch.object(ocr, "MAX_PIXELS", 100), self.assertRaisesRegex(ValueError, "像素"):
            ocr.extract_tables(image.getvalue(), ".png")

    def test_validation_rejects_nonfinite_duplicate_ids_and_invalid_location(self):
        doc = parse_document(csv_bytes(), "synthetic.csv")
        bad = deepcopy(doc); bad["rows"][0]["net_kg"] = float("nan")
        with self.assertRaises(ValueError): validate_document(bad)
        bad = deepcopy(doc); bad["rows"].append(deepcopy(bad["rows"][0]))
        with self.assertRaises(ValueError): validate_document(bad)
        bad = deepcopy(doc); bad["rows"][0]["evidence"]["quantity"]["source"]["page"] = -1
        with self.assertRaises(ValueError): validate_document(bad)
        clone = validate_document(doc); clone["rows"][0]["quantity"] = 7
        self.assertEqual(doc["rows"][0]["quantity"], 10)

    def test_parallel_imports_do_not_share_stats_or_sources(self):
        def parse(index):
            values = list(VALUES); values[0] = f"C{index}"
            return parse_document(csv_bytes(rows=[values]), f"synthetic-{index}.csv")
        with ThreadPoolExecutor(max_workers=4) as pool:
            docs = list(pool.map(parse, range(8)))
        self.assertEqual([d["source"]["filename"] for d in docs], [f"synthetic-{i}.csv" for i in range(8)])
        self.assertEqual([d["rows"][0]["package_id"] for d in docs], [f"C{i}" for i in range(8)])

    def test_cancellation_prevents_publication(self):
        event = Event(); event.set()
        with scope(event=event), self.assertRaises(RunCancelled):
            parse_document(csv_bytes(), "synthetic.csv")

    def test_json_roundtrip_rebinds_hash_and_retains_original_evidence(self):
        original = parse_document(csv_bytes(), "synthetic.csv")
        raw = json.dumps(original).encode("utf-8")
        imported = parse_document(raw, "synthetic-ledger.json")
        self.assertEqual(imported["rows"], original["rows"])
        self.assertNotEqual(imported["source"]["sha256"], original["source"]["sha256"])
        self.assertEqual(imported["extraction"]["original_source"], original["source"])
        with self.assertRaises(ValueError):
            parse_document(b'{"rows":[]}', "not-ledger.json")
        with self.assertRaises(ValueError):
            parse_document(b'{"schema":1,"schema":2}', "duplicate.json")

    def test_total_word_in_spec_does_not_remove_material(self):
        doc = parse_document(csv_bytes(["name", "spec", "quantity", "unit"], [["Synthetic panel", "Total", 10, "pcs"]]), "spec.csv")
        self.assertEqual(len(doc["rows"]), 1)
        self.assertEqual(doc["rows"][0]["quantity"], 10)
        self.assertEqual(doc["totals"], [])

    def test_local_ocr_child_does_not_inherit_host_secrets(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-secret", "CIVIL_TOKEN": "synthetic-token", "AWS_SECRET_ACCESS_KEY": "synthetic-secret", "HTTPS_PROXY": "synthetic-proxy", "CIVIL_LOGISTICS_OCR_CONFIG": "local-models.json"}):
            env = ocr._worker_environment([1])
        self.assertFalse(any(k in env for k in ("OPENAI_API_KEY", "CIVIL_TOKEN", "AWS_SECRET_ACCESS_KEY", "HTTPS_PROXY")))
        self.assertEqual(env["CIVIL_LOGISTICS_OCR_CONFIG"], "local-models.json")
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")

    def test_chinese_headers_can_touch_explicit_units_without_spaces(self):
        doc = parse_document(csv_bytes(["品名", "材料编号", "净重kg", "毛重kg", "重量口径"], [["Synthetic", "MAT001", 100, 110, "每箱"]]), "compact-headers.csv")
        self.assertEqual(doc["rows"][0]["material_id"], "MAT001")
        self.assertEqual(doc["rows"][0]["net_kg"], 100)
        self.assertEqual(doc["rows"][0]["gross_kg"], 110)


if __name__ == "__main__":
    unittest.main(verbosity=2)
