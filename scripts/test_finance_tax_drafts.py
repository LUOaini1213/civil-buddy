#!/usr/bin/env python3
"""Tax records and exports retain user evidence without default current rates."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import expert_turn
from packing_assistant.tax_context import draft_tax, explain_tax, records
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import default_engine


def calendar(markdown):
    return markdown.split("## 1 ", 1)[1].split("## 2 ", 1)[0]


class TaxContentTests(unittest.TestCase):
    def test_no_material_has_no_default_region_rate_or_deadline(self):
        text = draft_tax("出一份税务日历", expert_turn.DISCLAIMER)
        self.assertIn("辖区：UNSPECIFIED", text)
        self.assertIn("| UNSPECIFIED | UNSPECIFIED | UNSPECIFIED | UNSPECIFIED | UNSPECIFIED | UNSPECIFIED | UNSPECIFIED |", calendar(text))
        for invented in ("9%", "GST（SG）", "F5", "已完成申报。"):
            self.assertNotIn(invented, calendar(text))
        self.assertIn("[A001]", text)
        self.assertIn("submit_blocked=true", text)

    def test_explicit_sg_without_rate_still_has_unknown_rate(self):
        row = records("辖区：SG；主体：测试主体；税种：GST；申报期：2026-Q2")[0]
        self.assertEqual(row["zone"], "SG")
        self.assertEqual(row["rate"], "UNSPECIFIED")
        self.assertNotIn("9%", explain_tax("新加坡 GST 税率是什么？"))

    def test_user_fields_are_in_calendar_and_evidence_tables(self):
        body = draft_tax("辖区：SG；主体：测试甲；税种：GST；申报期：测试期间；申报截止：用户节点；税率：7.25%；税额：用户金额；来源文件：测试资料.pdf；资料日期：2026-01-02；责任人：测试人", expert_turn.DISCLAIMER)
        self.assertIn("| SG | 测试甲 | GST | 测试期间 | 用户节点 | 7.25% | 用户金额 |", calendar(body))
        evidence = body.split("## 2 ", 1)[1].split("## 3 ", 1)[0]
        self.assertIn("| SG | GST | 7.25% | 测试资料.pdf | 2026-01-02 | 用户提供，适用性及现行版本未核验 | 测试人 |", evidence)
        self.assertNotIn("现行税率为", body)
        self.assertNotIn("9%", body)

    def test_explicit_rate_without_jurisdiction_remains_unassigned(self):
        body = draft_tax("税种：GST；税率：7.25%", expert_turn.DISCLAIMER)
        self.assertNotIn("7.25%", calendar(body))
        self.assertIn("| UNSPECIFIED | GST | 7.25% |", body.split("## 2 ", 1)[1])

    def test_table_rows_keep_regions_rates_and_empty_cells_separate(self):
        body = draft_tax("|辖区|主体|税种|税率|\n|---|---|---|---|\n|SG|甲|GST|7.25%|\n||乙|待核税种||\n|CN|丙|测试税|3.25%|\n|EU|丁|测试税|4.25%|", expert_turn.DISCLAIMER)
        table = calendar(body)
        self.assertIn("| SG | 甲 | GST | UNSPECIFIED | UNSPECIFIED | 7.25% |", table)
        self.assertIn("| UNSPECIFIED | 乙 | 待核税种 | UNSPECIFIED | UNSPECIFIED | UNSPECIFIED |", table)
        self.assertIn("| CN | 丙 | 测试税 | UNSPECIFIED | UNSPECIFIED | 3.25% |", table)
        self.assertIn("| EU | 丁 | 测试税 | UNSPECIFIED | UNSPECIFIED | 4.25% |", table)

    def test_top_level_region_can_apply_to_table_without_borrowing_a_sibling(self):
        rows = records("全局辖区：SG\n|主体|税种|税率|\n|---|---|---|\n|甲|GST|7.25%|\n|乙|GST||")
        self.assertEqual([r["zone"] for r in rows], ["SG", "SG"])
        self.assertEqual([r["rate"] for r in rows], ["7.25%", "UNSPECIFIED"])

    def test_dual_shared_percentage_and_conflicting_rates_are_not_applied(self):
        for source in ("CN/SG 税率：7.25%", "SG 税率：7.25% 或 4.25%", "SG 税率：7.25%；税率：4.25%"):
            with self.subTest(source=source):
                self.assertEqual(records(source)[0]["rate"], "UNSPECIFIED")

    def test_repeated_tax_records_do_not_inherit_prior_region(self):
        rows = records("辖区：SG；税种：GST；税率：7.25%\n税种：测试税；申报期：待定")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["zone"], "UNSPECIFIED")
        self.assertEqual(rows[1]["rate"], "UNSPECIFIED")

    def test_source_locator_alone_cannot_certify_a_current_rate(self):
        row = records("辖区：SG；税种：GST；来源：https://www.iras.gov.sg/example；资料日期：2026-01-01")[0]
        self.assertEqual(row["rate"], "UNSPECIFIED")
        self.assertIn("待补", row["review"])

    def test_confirmed_session_region_is_used_without_borrowing_project_words(self):
        from packing_assistant.runtime.agent_loop import _explain
        for expert in ("", "finance-tax"):
            reply = _explain("GST 税率是什么？", expert, "本会话槽：辖区=SG；项目=EU测试项目。")
            self.assertIn("辖区：SG", reply)
            self.assertIn("税率：UNSPECIFIED", reply)
            self.assertNotIn("辖区：DUAL", reply)
            self.assertNotIn("9%", reply)
            changed = _explain("中国的税率是什么？", expert, "本会话槽：辖区=SG；项目=测试。")
            self.assertIn("辖区：CN", changed)


class TaxRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="civil-tax-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for context in (
            patch.object(expert_turn, "_OUT", self.root),
            patch("packing_assistant.runtime.memory._OUT", self.root),
            patch("packing_assistant.runtime.scheduler.get_scheduler", return_value=Scheduler()),
            patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_JOB_ROOT": "", "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request", "PYTHON_DOTENV_DISABLED": "1"}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def export(self, result):
        self.assertTrue(result.get("wrote"), result)
        self.assertTrue(result["submit_blocked"])
        files = {Path(row["path"]).suffix: Path(row["path"]) for row in result["files"]}
        self.assertTrue({".md", ".docx", ".xlsx"}.issubset(files))
        markdown = files[".md"].read_text(encoding="utf-8")
        with ZipFile(files[".docx"]) as archive:
            xml = ET.fromstring(archive.read("word/document.xml"))
            word_text = "\n".join(node.text or "" for node in xml.iter() if node.tag.endswith("}t"))
        import openpyxl
        book = openpyxl.load_workbook(files[".xlsx"], data_only=False)
        try:
            cells = [cell for sheet in book for row in sheet for cell in row if cell.value is not None]
            values = [str(cell.value) for cell in cells]
            self.assertFalse(any(cell.data_type == "f" for cell in cells))
        finally:
            book.close()
        return markdown, word_text, values

    def test_named_tool_exports_unknown_rate_without_default(self):
        result = expert_turn.run_named_exclusive("finance-tax__calendar", {"text": "出一份税务日历", "session_id": "unknown"})
        markdown, word, cells = self.export(result)
        for value in (markdown, word, "\n".join(cells)):
            self.assertIn("UNSPECIFIED", value)
            self.assertNotIn("9%", value)

    def test_run_expert_turn_exports_given_fields_in_all_formats(self):
        result = expert_turn.run_expert_turn("写一份税务日历；辖区：SG；主体：导出测试；税种：GST；税率：7.25%；来源文件：测试.pdf", "finance-tax", session_id="expert")
        markdown, word, cells = self.export(result)
        self.assertIn("| SG | 导出测试 | GST | UNSPECIFIED | UNSPECIFIED | 7.25% |", calendar(markdown))
        for value in ("导出测试", "7.25%", "测试.pdf"):
            self.assertIn(value, word)
            self.assertIn(value, cells)

    def test_tool_engine_preserves_table_entities_once_and_formula_as_text(self):
        text = "|辖区|主体|税种|税率|来源|\n|---|---|---|---|---|\n|SG|甲&#124;乙&lt;丙|GST|7.25%|=1+1|\n|CN|字面&amp;lt;|测试税||x&lt;10|"
        result = default_engine().execute("finance-tax__calendar", {"text": text, "session_id": "engine"}, expert_id="finance-tax", intent="run")
        self.assertTrue(result["ok"], result)
        markdown, word, cells = self.export(result)
        self.assertIn("甲&#124;乙&lt;丙", calendar(markdown))
        for value in ("甲|乙<丙", "字面&lt;", "=1+1", "x<10"):
            self.assertIn(value, cells)
        self.assertIn("甲|乙<丙", word)

    def test_chat_explanations_skip_historical_kb_rate_and_never_write(self):
        from packing_assistant.product_turn import explain
        with patch.object(expert_turn, "_kb_snip", side_effect=AssertionError("Historical GST 9% must not be used")):
            result = expert_turn.run_expert_turn("什么是 GST？", "finance-tax", session_id="chat")
        self.assertEqual(result["intent"], "chat")
        self.assertFalse(result["wrote"])
        self.assertEqual(result["files"], [])
        for reply in (result["reply"], explain("GST 是什么？")):
            self.assertIn("UNSPECIFIED", reply)
            self.assertNotIn("9%", reply)
        self.assertFalse(list(self.root.rglob("*.md")))

    def test_tool_owner_chat_and_read_only_gates_still_precede_write(self):
        engine = default_engine()
        for owner, intent in (("finance-tax", "chat"), ("cost", "run")):
            result = engine.execute("finance-tax__calendar", {"text": "写一份税务日历"}, expert_id=owner, intent=intent)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["error_code"], "permission_denied")
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            result = engine.execute("finance-tax__calendar", {"text": "写一份税务日历"}, expert_id="finance-tax", intent="run")
            self.assertFalse(result["ok"], result)
        self.assertFalse(list(self.root.rglob("*.md")))


if __name__ == "__main__":
    unittest.main()
