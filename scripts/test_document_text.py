#!/usr/bin/env python3
"""Table text boundary: one shared width, budget accounting, verbatim fallback and key/value drafters."""

from __future__ import annotations

import html
import os
import random
import sys
import time
import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant import tax_context
from packing_assistant.document_text import csv_text, docx_document_text, table_markdown
from packing_assistant.post_drafts import admin, design_services, it

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TITLED = "| 材料清单 |  |  |\n| --- | --- | --- |\n| 名称 | 数量 | 重量 |\n| 钢梁 | 2 | 120 |"
LATE = [["h1", "h2"]] + [["v", "w"]] * 3 + [["x"] * 12] + [["y", "z"]]


def _widths(text: str) -> list[int]:
    return [len(line[1:-1].split("|")) for line in text.splitlines()]


def _raw_lines(table: list[list[object]]) -> list[str]:
    rows = [["" if value is None else str(value) for value in row] for row in table]
    return ["| " + " | ".join(html.escape(value.replace("\r", " ").replace("\n", "；"), quote=False).replace("|", "&#124;")
                              for value in row) + " |" for row in rows if any(value.strip() for value in row)]


def _shipped(table: list[list[object]], limit: int) -> str:
    """Pre-fix rendering of a table whose rows are no wider than the first: whole lines, one char of slack."""
    lines = _raw_lines(table)
    if not lines:
        return ""
    width = _widths(lines[0])[0]
    lines = [line + "  |" * (width - _widths(line)[0]) for line in lines]
    lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
    fits = [count for count in range(2, len(lines) + 1) if len("\n".join(lines[:count])) < limit]
    return "\n".join(lines[:fits[-1]]) if fits else ""


def _padded(rows: list[list[str]]) -> list[tuple[object, ...]]:
    width = max(map(len, rows))
    return [tuple(row) + (None,) * (width - len(row)) for row in rows]


class TableMarkdownTests(unittest.TestCase):
    def test_title_row_shares_the_table_width(self) -> None:
        self.assertEqual(TITLED, table_markdown([["材料清单"], ["名称", "数量", "重量"], ["钢梁", 2, 120]], 10_000))
        self.assertEqual(TITLED, csv_text("材料清单\n名称,数量,重量\n钢梁,2,120\n", 10_000))

    def test_wider_data_row_widens_header_and_neighbours(self) -> None:
        self.assertEqual(
            "| 名称 | 数量 |  |\n| --- | --- | --- |\n| 钢梁 | 2 | 备注：加急 |\n| 木方 | 5 |  |",
            table_markdown([["名称", "数量"], ["钢梁", 2, "备注：加急"], ["木方", 5]], 10_000),
        )

    def test_blank_rows_and_unaffordable_header(self) -> None:
        self.assertEqual("| a |  |\n| --- | --- |\n| b | c |", table_markdown([["a"], [], [None, ""], ["b", "c"]], 10_000))
        self.assertEqual("", table_markdown([], 10_000))
        self.assertEqual("", table_markdown([["a", "b"]], 10))
        for limit in range(40):
            self.assertIn(table_markdown([["a", "b"], ["c"] * 5], limit), ("", "| a | b |\n| --- | --- |"), limit)

    def test_rectangular_budget_is_unchanged(self) -> None:
        full = "| 名称 | 数量 | 重量 |\n| --- | --- | --- |\n| 钢梁 | 2 | 120 |\n| 木方 | 5 | 30 |"
        rows = [["名称", "数量", "重量"], ["钢梁", 2, 120], ["木方", 5, 30]]
        self.assertEqual(69, len(full))
        for limit, expected in ((0, ""), (36, ""), (37, full[:36]), (69, full[:53]), (70, full), (10_000, full)):
            self.assertEqual(expected, table_markdown(rows, limit), limit)

    def test_unaffordable_widening_keeps_the_wide_row_verbatim(self) -> None:
        narrow = "| h1 | h2 |\n| --- | --- |\n| v | w |\n| v | w |\n| v | w |"
        wide = "| x | x | x | x | x | x | x | x | x | x | x | x |"
        self.assertEqual(narrow, table_markdown(LATE, 105))
        self.assertEqual(narrow + "\n" + wide, table_markdown(LATE, 106))
        for limit in (117, 285):
            self.assertEqual(narrow + "\n" + wide + "\n| y | z |", table_markdown(LATE, limit), limit)
        self.assertEqual([55, 105, 115], [len(table_markdown(LATE, limit)) for limit in (105, 106, 117)])
        # The width stays frozen even when a later, smaller widening would fit.
        rows = [["h1", "h2"], ["v", "w"], ["x"] * 12, ["a", "b", "c"]]
        self.assertEqual([[2, 2, 2, 12, 3], [12] * 5], [_widths(table_markdown(rows, limit)) for limit in (150, 10_000)])

    def test_greedy_widening_is_not_monotone_in_the_limit(self) -> None:
        # Pinned on purpose: 286 affords the widening but then not the last row. An exact search would be O(n^2).
        for limit, lines in ((286, 6), (326, 7)):
            text = table_markdown(LATE, limit)
            self.assertEqual(([12] * lines, limit - 1), (_widths(text), len(text)), limit)
        self.assertNotIn("| y | z |", table_markdown(LATE, 286))
        for limit in range(400):
            self.assertLessEqual(len(table_markdown(LATE, limit)), limit)

    def test_job_file_budget_keeps_rows_after_a_late_wide_remark(self) -> None:
        lines = ["名称,数量,重量"] + [f"钢梁-{index:04d},{index % 9 + 1},{100 + index}" for index in range(300)]
        lines.insert(200, "备注,见附件," + ",".join("ABCDEFGHIJKLMNOPQR"))
        text = csv_text("\n".join(lines) + "\n", 8_000)
        self.assertEqual(303, len(text.splitlines()))
        self.assertEqual({3, 20}, set(_widths(text)))
        self.assertIn("见附件", text)
        self.assertIn("钢梁-0299", text)
        self.assertLessEqual(len(text), 8_000)

    def test_seeded_tables_keep_a_literal_prefix_within_the_limit(self) -> None:
        rng = random.Random(20260920)
        alphabet = ["", "a", "钢梁", "x|y", "<1&", "多\n行", " ", "120", None, 3.5, "很长的备注" * 4, "\r"]
        for _ in range(120):
            table = [[rng.choice(alphabet) for _ in range(rng.randint(0, 8))] for _ in range(rng.randint(0, 9))]
            raw = _raw_lines(table)
            rectangular = not raw or max(_widths("\n".join(raw))) == _widths(raw[0])[0]
            for limit in range(-1, len(table_markdown(table, 10 ** 9)) + 3):
                text = table_markdown(iter(table), limit)
                self.assertLessEqual(len(text), max(limit, 0))
                if rectangular:
                    self.assertEqual(_shipped(table, limit), text, (table, limit))
                lines = text.splitlines()
                if not lines:
                    continue
                width = _widths(lines[1])[0]
                self.assertEqual("| " + " | ".join(["---"] * width) + " |", lines[1])
                kept = lines[:1] + lines[2:]
                self.assertEqual(width, _widths(kept[0])[0])
                self.assertLessEqual(len(kept), len(raw))
                for line, source in zip(kept, raw):
                    padding = line[len(source):]
                    self.assertTrue(line.startswith(source) and padding == "  |" * (len(padding) // 3), (table, limit))
                    self.assertTrue(_widths(line)[0] == width if padding else _widths(line)[0] >= width, (table, limit))

    def test_generator_is_streamed_not_materialised(self) -> None:
        pulled = []

        def rows():
            for index in range(25_000):
                pulled.append(index)
                yield (str(cell) for cell in range(300))

        text = table_markdown(rows(), 200_000)
        self.assertLess(len(pulled), 200)
        self.assertEqual({256}, set(_widths(text)))
        self.assertLessEqual(len(text), 200_000)
        # The row cap is a boundary of its own: 20_000 rows plus the separator, whatever the budget allows.
        self.assertEqual(20_001, len(table_markdown(([str(index)] for index in range(20_050)), 10 ** 9).splitlines()))

    def test_every_row_after_the_freeze_is_kept_in_constant_time(self) -> None:
        rows = [["a", "b"]] * 15_000 + [["x"] * 40, ["y"] * 41] * 2_000
        started = time.perf_counter()
        # A budget that affords all 19_000 rows verbatim but never their widening: 15_000 kept rows would
        # cost 3 chars each per new column. Re-padding them per wide row would make this quadratic.
        text = table_markdown(iter(rows), 850_000)
        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertEqual(19_001, len(text.splitlines()))
        self.assertLessEqual(len(text), 850_000)
        self.assertEqual({2, 40, 41}, set(_widths(text)))


class DocxTableTests(unittest.TestCase):
    def test_merged_cells_are_padded_but_not_expanded(self) -> None:
        def cell(text: str, span: int = 1) -> str:
            merged = f'<w:tcPr><w:gridSpan w:val="{span}"/></w:tcPr>' if span > 1 else ""
            return f"<w:tc>{merged}<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"

        rows = [[("材料清单", 3)], [("名称",), ("数量",), ("重量",)], [("钢梁",), ("2",), ("120",)], [("合计", 2), ("120",)]]
        table = "".join("<w:tr>" + "".join(cell(*item) for item in row) + "</w:tr>" for row in rows)
        document = ElementTree.fromstring(
            f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>前言</w:t></w:r></w:p><w:tbl>{table}</w:tbl></w:body></w:document>')
        # Known limit: gridSpan is not expanded, so the total sits under 数量. Expanding it must change this pin on purpose.
        self.assertEqual("前言\n\n" + TITLED + "\n| 合计 | 120 |  |", docx_document_text(document, 10_000))
        for limit in (0, 5, 30, 60, 80, 200):
            self.assertLessEqual(len(docx_document_text(document, limit)), limit)


class ConsumerTests(unittest.TestCase):
    def test_tax_rows_wider_than_the_header_are_kept(self) -> None:
        records = tax_context.records(csv_text("辖区,税种,税率\nSG,GST,9%,见2026年通知\nCN,增值税,13%\n", 10_000))
        self.assertEqual([("SG", "GST", "9%"), ("CN", "增值税", "13%")], [(row["zone"], row["tax"], row["rate"]) for row in records])

    def test_key_value_drafters_ignore_trailing_empty_cells(self) -> None:
        # Each form has one row with real third and fourth cells; its known label must still not be read as a pair.
        # Each also repeats one label three times: bare, with an empty value, then with the value. A pair read from
        # either blank would be UNSPECIFIED and, being first, would shadow the value below it.
        cases = (
            ([["权限申请单"], ["系统名称", "工地考勤系统"], ["申请人"], ["申请人", ""], ["申请人", "张三"],
              ["工单号", "CHG-1", "备注", "加急"], ["变更窗口", "周六夜间"]],
             lambda text: it._Facts(text).entries,
             [("system", "工地考勤系统"), ("requester", "张三"), ("window", "周六夜间")]),
            ([["设计任务单"], ["项目名称"], ["项目名称", ""], ["项目名称", "试验园区"], ["单体名称", "SG"],
              ["辖区", "甲", "备注", "加急"], ["系统名称", "乙"]],
             lambda text: design_services._Facts("plumbing", text).records,
             [{"project": "试验园区", "unit": "SG", "system": "乙"}]),
            ([["用印申请单"], ["用印事由", "分包合同盖章"], ["申请人"], ["申请人", ""], ["申请人", "李四"],
              ["发文字号", "A-1", "备注", "加急"], ["用印份数", "3份"]],
             lambda text: admin._Facts(text).values,
             {"seal_reason": "分包合同盖章", "applicant": "李四", "copies": "3份"}),
        )
        for rows, read, expected in cases:
            raw = _raw_lines(rows)
            texts = {"ragged": table_markdown(rows, 10_000), "xlsx": table_markdown(_padded(rows), 10_000),
                     "pre-fix cache": "\n".join(raw[:1] + ["| --- |"] + raw[1:])}
            self.assertEqual([4] * 8, _widths(texts["ragged"]))
            self.assertEqual(texts["ragged"], texts["xlsx"])
            for shape, text in texts.items():
                with self.subTest(form=rows[0][0], shape=shape):
                    self.assertEqual(expected, read(text))

    def test_drafts_read_padded_forms_and_skip_blank_labels(self) -> None:
        text = table_markdown([["用印申请单"], ["用印事由", "分包合同盖章"], ["申请人"], ["申请人", ""],
                               ["申请人", "李四"], ["发文字号", "A-1", "备注", "加急"], ["用印份数", "3份"]], 10_000)
        draft = admin.build_draft("admin-doc", "admin-doc__draft", text)
        for expected in ("| 用印事由 | 分包合同盖章 |", "| 申请人 | 李四 |", "| 份数 | 3份 |",
                         "| 发文字号（仅录入原值，不生成序号） | UNSPECIFIED（待补） |"):
            self.assertIn(expected, draft)
        text = table_markdown([["权限申请单"], ["申请人"], ["申请人", ""], ["申请人", "张三"],
                               ["工单号", "CHG-1", "备注", "加急"]], 10_000)
        draft = it.build_draft("it-ops", "it-ops__runbook", text)
        for expected in ("| 申请人 | 张三 |", "| 工单号（用户提供） | UNSPECIFIED（待填） |"):
            self.assertIn(expected, draft)


if __name__ == "__main__":
    unittest.main()
