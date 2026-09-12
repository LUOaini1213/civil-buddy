#!/usr/bin/env python3
"""Inspect actual daily-report and related draft artifacts for unsupported facts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import expert_turn


class DailyReportContentTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="civil-daily-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        output = patch.object(expert_turn, "_OUT", self.root)
        output.start()
        self.addCleanup(output.stop)
        environment = patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_JOB_ROOT": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def _draft(self, tool: str, text: str, **fields) -> tuple[str, dict]:
        result = expert_turn.run_named_exclusive(tool, {
            "text": text, "session_id": "content-test", "confirm_ok": True, **fields,
        })
        self.assertTrue(result["wrote"], result.get("reply"))
        self.assertTrue(result["submit_blocked"])
        path = next(Path(row["path"]) for row in result["files"] if row["path"].endswith(".md"))
        return path.read_text(encoding="utf-8"), result

    def _chapter(self, text: str, title: str) -> str:
        return text.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]

    def test_template_request_does_not_become_site_or_assume_singapore(self) -> None:
        text, result = self._draft("pm-daily__log", "@项目日报 写一份项目日报模板")
        self.assertIn("- 辖区：UNSPECIFIED", text)
        self.assertIn("| 部位 | [A001] 待填部位 |", text)
        self.assertIn("| 天气 | 天气待填 |", text)
        self.assertIn("| 出勤 | 出勤待填 |", text)
        self.assertNotIn("| 部位 | @", text)
        self.assertNotIn("SG：BCA", text)
        import openpyxl

        path = next(Path(row["path"]) for row in result["files"] if row["path"].endswith(".xlsx"))
        workbook = openpyxl.load_workbook(path, data_only=True)
        try:
            rows = list(workbook.worksheets[0].values)
            self.assertIn(("部位", "[A001] 待填部位"), rows)
            self.assertNotIn(("部位", "@项目日报 写一份项目日报模板"), rows)
        finally:
            workbook.close()

    def test_report_copies_only_supplied_site_weather_and_attendance(self) -> None:
        text, _ = self._draft("pm-daily__log", "@项目日报 写一份日报；辖区：CN；部位：1号楼三层；天气：暴雨；木工12人；钢筋工5人")
        self.assertIn("- 辖区：CN", text)
        self.assertIn("| 部位 | 1号楼三层 |", text)
        self.assertIn("用户口述：暴雨。", text)
        self.assertIn("木工12人；钢筋工5人", text)
        self.assertNotIn("17人", text)
        self.assertNotIn("SG：BCA", text)

    def test_pipe_names_and_trade_names_do_not_invent_weather_or_people(self) -> None:
        text, _ = self._draft("pm-daily__log", "写一份项目日报；部位：地下室；雨水管安装；防雪措施；钢筋工；出勤待填")
        self.assertIn("| 天气 | 天气待填 |", text)
        self.assertIn("| 出勤 | 出勤待填 |", text)
        self.assertIn("| 部位 | 地下室 |", text)

    def test_forecasts_and_plans_are_not_reported_as_actual_conditions(self) -> None:
        text, _ = self._draft("pm-daily__log", "写一份项目日报；明日预报晴；安排木工20人；部位：待填")
        self.assertIn("| 天气 | 天气待填 |", text)
        self.assertIn("| 出勤 | 出勤待填 |", text)
        self.assertIn("| 部位 | [A001] 待填部位 |", text)

    def test_structured_tool_fields_preserve_explicit_project_data(self) -> None:
        text, _ = self._draft("pm-daily__log", "生成项目日报模板", site="东侧作业面", weather="晴转多云", attendance="普工8人", jurisdiction="SG")
        self.assertIn("- 辖区：SG", text)
        self.assertIn("| 部位 | 东侧作业面 |", text)
        self.assertIn("用户口述：晴转多云", text)
        self.assertIn("普工8人", text)
        self.assertIn("SG：BCA", text)

    def test_named_facts_reach_report_chapters_and_excel_cells(self) -> None:
        text, result = self._draft("pm-daily__log", "@项目日报 写一份日报；项目名称：东岸改造工程；日期：2026-09-12；部位：1号楼三层；安全质量记事：围挡已完成复查；明日计划：复核东侧围挡并核对材料清单")
        header = self._chapter(text, "1 报头")
        safety = self._chapter(text, "7 安全质量记事")
        tomorrow = self._chapter(text, "8 明日拟安排")
        self.assertIn("项目名称：东岸改造工程", header)
        self.assertIn("日期：2026-09-12", header)
        self.assertNotIn("项目名称待填", header)
        self.assertIn("用户提供的安全质量记事：围挡已完成复查", safety)
        self.assertNotIn("用户未提供巡查事实", safety)
        self.assertIn("用户提供的明日计划：复核东侧围挡并核对材料清单", tomorrow)
        import openpyxl

        path = next(Path(row["path"]) for row in result["files"] if row["path"].endswith(".xlsx"))
        workbook = openpyxl.load_workbook(path, data_only=True)
        try:
            cells = dict(list(workbook.worksheets[0].values)[1:])
            self.assertEqual(cells["项目名称"], "东岸改造工程")
            self.assertEqual(cells["日期"], "2026-09-12")
            self.assertEqual(cells["安全质量记事"], "围挡已完成复查")
            self.assertEqual(cells["明日计划"], "复核东侧围挡并核对材料清单")
        finally:
            workbook.close()

    def test_unlabelled_sentences_and_placeholder_fields_stay_unfilled(self) -> None:
        for request in (
            "写一份日报；东岸改造工程于2026-09-12复查围挡，明天核对材料",
            "写一份日报；项目名称：待填；日期：未提供；安全质量记事：未知；明日计划：TBD",
        ):
            with self.subTest(request=request):
                text, _ = self._draft("pm-daily__log", request)
                self.assertIn("项目名称待填", self._chapter(text, "1 报头"))
                self.assertIn("日期待填", self._chapter(text, "1 报头"))
                self.assertIn("安全质量记事待填", self._chapter(text, "7 安全质量记事"))
                self.assertIn("明日计划待填", self._chapter(text, "8 明日拟安排"))

    def test_adjacent_labels_do_not_bleed_into_other_chapters(self) -> None:
        text, _ = self._draft("pm-daily__log", "写一份日报\n工程名称:东岸改造工程 报告日期:2026年9月12日\n安全记事:围挡已复查，整改证据未提供 明日安排:整理整改证据")
        header = self._chapter(text, "1 报头")
        safety = self._chapter(text, "7 安全质量记事")
        tomorrow = self._chapter(text, "8 明日拟安排")
        self.assertIn("项目名称：东岸改造工程。日期：2026年9月12日", header)
        self.assertIn("围挡已复查，整改证据未提供", safety)
        self.assertNotIn("整理整改证据", safety)
        self.assertIn("整理整改证据", tomorrow)

    def test_unprovided_jurisdiction_is_unknown_in_other_written_drafts(self) -> None:
        for tool, request in (
            ("survey__record", "写一份测量记录"),
            ("construction__scheme_draft", "写一份施工方案讨论提纲"),
            ("method-hazard__judge_hazard", "写一份危大判定书 临边开挖"),
            ("lab-mix__report", "写一份配合比报告 C40"),
        ):
            with self.subTest(tool=tool):
                text, _ = self._draft(tool, request)
                self.assertIn("辖区：UNSPECIFIED", text)
                self.assertNotIn("辖区：SG", text)


if __name__ == "__main__":
    unittest.main()
