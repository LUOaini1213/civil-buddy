#!/usr/bin/env python3
"""Real API drafts must preserve object ownership and supplied daily facts."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
from scripts import test_workbench_flow as flow
import openpyxl
import chat_service
import projects
import session_context
from packing_assistant.office_job import tables_from_md
from packing_assistant.post_drafts.design_services import build_draft

STEEL = "构件：梁A；跨度：12m；用户规格：原表H300；连接方式：用户节点焊接；图号：A-01\n构件：梁B"


def section(markdown, title):
    return markdown.split("## " + title + "\n", 1)[1].split("\n## ", 1)[0]


class DraftContextIntegrityTests(unittest.TestCase):
    setUp = flow.WorkbenchFlowTests.setUp
    post = flow.WorkbenchFlowTests.post

    def seed(self, text):
        projects.touch_session(self.root, self.sid, text)
        projects.append_turn(self.root, self.sid, "user", text)

    def draft(self, text, expert="steel"):
        done, _ = self.post(text, expert_ids=[expert], confirm_text="我明白，将由持证人员签认")
        self.assertTrue(done["ok"] and done["wrote"], done)
        markdown = next(Path(f["path"]).read_text(encoding="utf-8") for f in done["deliverables"] if f["path"].endswith(".md"))
        workbook_path = next(f["path"] for f in done["deliverables"] if f["path"].endswith(".xlsx"))
        workbook = openpyxl.load_workbook(workbook_path, data_only=True)
        try:
            sheets = [list(sheet.values) for sheet in workbook]
        finally:
            workbook.close()
        return markdown, sheets, done

    def assert_members(self, markdown, sheets, expected):
        rows = tables_from_md(section(markdown, "材料与构件规格记录"))[0][1]
        header = rows[0]
        expected_rows = [(name, "[A001] / UNSPECIFIED" if specification == "UNSPECIFIED" else specification)
                         for name, specification in expected]
        self.assertEqual([(r[header.index("构件")], r[header.index("用户既有/提出规格")]) for r in rows[1:]], expected_rows)
        sheet = next(rows for rows in sheets if rows and "用户既有/提出规格" in rows[0])
        self.assertEqual([(r[sheet[0].index("构件")], r[sheet[0].index("用户既有/提出规格")]) for r in sheet[1:]], expected_rows)

    def test_new_http_steel_matches_direct_builder_without_synthetic_third_member(self):
        markdown, sheets, done = self.draft("写一份钢结构说明\n" + STEEL)
        direct = build_draft("steel", "steel__memo", STEEL)
        self.assertEqual(section(markdown, "材料与构件规格记录"), section(direct, "材料与构件规格记录"))
        self.assert_members(markdown, sheets, [("梁A", "原表H300"), ("梁B", "UNSPECIFIED")])
        ranges = tables_from_md(section(markdown, "结构体系与构件范围"))[0][1]
        self.assertEqual([r[ranges[0].index("用户跨度")] for r in ranges[1:]], ["12m", "[A001] / UNSPECIFIED"])
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["deliverables"], done["deliverables"])

    def test_historical_multi_object_fields_are_not_injected_into_new_member(self):
        self.seed(STEEL)
        markdown, sheets, _ = self.draft("写一份钢结构说明\n构件：梁C")
        self.assert_members(markdown, sheets, [("梁C", "UNSPECIFIED")])
        self.assertNotIn("原表H300", markdown)
        self.assertNotIn("12m", markdown)
        self.assertEqual(projects.read_full_history(self.root, self.sid)[0]["content"], STEEL)

    def test_explicit_history_reuse_preserves_both_original_rows_and_empty_values(self):
        self.seed(STEEL)
        markdown, sheets, _ = self.draft("根据之前的构件资料，写一份钢结构说明")
        self.assert_members(markdown, sheets, [("梁A", "原表H300"), ("梁B", "UNSPECIFIED")])

    def test_single_old_member_does_not_supply_values_to_new_identity(self):
        self.seed(STEEL.splitlines()[0])
        markdown, sheets, _ = self.draft("写一份钢结构说明\n构件：梁B")
        self.assert_members(markdown, sheets, [("梁B", "UNSPECIFIED")])

    def test_same_current_record_is_not_duplicated_on_repeated_write(self):
        message = "写一份钢结构说明\n" + STEEL
        self.draft(message)
        markdown, sheets, _ = self.draft(message)
        self.assert_members(markdown, sheets, [("梁A", "原表H300"), ("梁B", "UNSPECIFIED")])

    def test_current_named_member_is_not_preceded_by_an_old_duplicate(self):
        self.seed(STEEL.splitlines()[0])
        markdown, sheets, _ = self.draft("写一份钢结构说明\n构件：梁A；用户规格：新表H400")
        self.assert_members(markdown, sheets, [("梁A", "新表H400")])
        self.assertNotIn("原表H300", markdown)

    def test_negative_history_instruction_does_not_count_as_explicit_reuse(self):
        self.seed(STEEL)
        markdown, sheets, _ = self.draft("写一份钢结构说明，不要沿用之前的构件资料\n构件：梁C")
        self.assert_members(markdown, sheets, [("梁C", "UNSPECIFIED")])
        self.assertNotIn("原表H300", markdown)

    def test_historical_tables_require_explicit_reuse_and_keep_empty_cells(self):
        self.seed("| 构件 | 用户规格 |\n| --- | --- |\n| 梁A | 原表H300 |\n| 梁B | |")
        markdown, sheets, _ = self.draft("根据之前的表格资料，写一份钢结构说明")
        self.assert_members(markdown, sheets, [("梁A", "原表H300"), ("梁B", "UNSPECIFIED")])

    def test_single_meeting_and_current_correction_remain_usable_on_later_turn(self):
        self.seed("会议名称：记忆协调会。\n场地：北楼101。\n议程：资料核对。")
        first, _, _ = self.draft("写一份会议计划模板", "admin-office")
        self.assertIn("北楼101", first)
        second, _, _ = self.draft("更正：场地：南楼202。写一份会议计划模板", "admin-office")
        self.assertIn("记忆协调会", second)
        self.assertIn("南楼202", second)
        self.assertNotIn("北楼101", second)
        third, _, _ = self.draft("写一份会议计划模板", "admin-office")
        self.assertIn("记忆协调会", third)
        self.assertIn("南楼202", third)
        self.assertNotIn("北楼101", third)

    def test_new_daily_facts_fill_body_and_excel_once(self):
        markdown, sheets, _ = self.draft("写一份项目日报\n项目名称：东桥；日期：2026-09-12；形象进度：完成模板复核；机械材料：吊车一台待检", "pm-daily")
        self.assertIn("项目名称：东桥。日期：2026-09-12", section(markdown, "1 报头"))
        self.assertIn("完成模板复核", section(markdown, "4 形象进度"))
        self.assertIn("吊车一台待检", section(markdown, "6 人机料"))
        self.assertNotIn("数量 TBD", section(markdown, "6 人机料"))
        cells = dict(sheets[0][1:])
        self.assertEqual(cells["项目名称"], "东桥")
        self.assertEqual(cells["日期"], "2026-09-12")
        self.assertEqual(cells["形象进度"], "完成模板复核")
        self.assertEqual(cells["机械材料"], "吊车一台待检")

    def test_global_project_reused_but_current_override_is_not_duplicated(self):
        self.seed("项目名称：旧桥；日期：2026-09-11")
        first, sheets, _ = self.draft("写一份项目日报；形象进度：完成模板复核", "pm-daily")
        self.assertEqual(dict(sheets[0][1:])["项目名称"], "旧桥")
        second, sheets, _ = self.draft("写一份项目日报；项目名称：东桥；日期：2026-09-12", "pm-daily")
        self.assertEqual(dict(sheets[0][1:])["项目名称"], "东桥")
        self.assertEqual(dict(sheets[0][1:])["日期"], "2026-09-12")
        self.assertNotIn("旧桥", section(second, "1 报头"))

    def test_daily_literal_content_survives_excel_rendering_once(self):
        markdown, sheets, _ = self.draft("写一份日报；形象进度：复核 <10 | &lt; 项；机械材料：吊车一台待检", "pm-daily")
        self.assertEqual(dict(sheets[0][1:])["形象进度"], "复核 <10 | &lt; 项")
        self.assertIn("复核 <10 | &lt; 项", section(markdown, "4 形象进度"))

    def test_old_object_facts_remain_available_to_question_rag(self):
        self.seed(STEEL)
        captured = []

        def model(messages, **kwargs):
            captured.extend(messages)
            yield "梁A的用户规格为原表H300，梁B未提供。"

        with patch.object(flow.workbench, "has_key", return_value=True), patch("llm.stream_plain", side_effect=model):
            done, _ = self.post("之前梁A的用户规格是什么？", expert_ids=["steel"])
        self.assertFalse(done["wrote"])
        self.assertIn("原表H300", str(captured))
        self.assertTrue(any("原表H300" in c["snippet"] for c in done["citations"]))


if __name__ == "__main__":
    unittest.main()
