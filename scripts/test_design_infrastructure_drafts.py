#!/usr/bin/env python3
"""Inspect six infrastructure posts and their actual Markdown/Excel exports."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import expert_turn
from packing_assistant.expert_roster import get_expert
from packing_assistant.post_drafts.design_infrastructure import PROFILES, build_draft
from packing_assistant.tools.tender_review import forbidden_hits


def draft(post: str, text: str = "写一份内部讨论提纲") -> str:
    return build_draft(post, PROFILES[post].tool, text)


def section(markdown: str, title: str) -> str:
    return markdown.split(title, 1)[1].split("\n## ", 1)[0]


class InfrastructureDraftTests(unittest.TestCase):
    def test_all_post_contracts_and_empty_professional_chapters(self):
        for post, profile in PROFILES.items():
            with self.subTest(post=post):
                self.assertIn(profile.tool, get_expert(post).exclusive)
                self.assertIsNone(build_draft(post, "wrong__tool", "input"))
                text = draft(post)
                self.assertEqual(len(re.findall(r"^## \d+ ", text, re.M)), 10)
                self.assertIn("辖区：UNSPECIFIED", text)
                self.assertFalse(forbidden_hits(text))
                self.assertNotIn("## 用户原文", text)
                for output in profile.outputs:
                    self.assertIn(f"| {output} | UNSPECIFIED | 未计算或未核验 |", text)

    def test_port_inputs_go_to_hydrology_and_not_computed_dimensions(self):
        text = draft("port", "码头名称：东岸泊位；设计船型：用户船型X；高水位：3.2m；波浪：用户文件浪高；水文文件：水文A.pdf；前沿高程：4m")
        hydro = section(text, "3 水位、波浪与潮流")
        self.assertIn("| 设计高水位 | 3.2m |", hydro)
        self.assertIn("水文A.pdf", hydro)
        self.assertIn("| 桩长 | UNSPECIFIED |", text)
        self.assertIn("| 前沿高程 | 4m |", section(text, "5 前沿高程与泊位尺度"))

    def test_municipal_sections_keep_user_cross_section_and_drainage(self):
        text = draft("municipal", "道路名称：东街；横断面：规划断面A；排水出路：南侧干管；接驳标高：1.5m；管线名称：通信管道")
        self.assertIn("规划断面A", section(text, "4 横断与路幅分配"))
        self.assertIn("南侧干管", section(text, "7 路基与排水出路"))
        self.assertIn("通信管道", section(text, "8 管线综合"))
        self.assertIn("| 计算管径 | UNSPECIFIED |", text)
        self.assertNotIn("SDRE Rev I", text)

    def test_bridge_candidates_do_not_become_selected_or_calculated_design(self):
        text = draft("bridge", "桥名：河道一桥；跨径：用户图示30m；候选桥型：梁桥与拱桥；施工约束：不能占用河道")
        self.assertIn("梁桥与拱桥", section(text, "4 桥型比选"))
        self.assertIn("用户图示30m", section(text, "5 上部结构"))
        self.assertIn("| 计算梁高 | UNSPECIFIED |", text)
        self.assertIn("| 计算桩长 | UNSPECIFIED |", text)
        self.assertNotIn("最优方案为", text)

    def test_matrix_row_boundaries_survive_identifier_last_or_empty(self):
        for second in ("二桥", ""):
            text = draft("bridge", "| 跨径 | 桥名 |\n| --- | --- |\n| 30m | 一桥 |\n| 40m | " + second + " |")
            first, later = text.split("# 独立材料记录 2", 1)
            self.assertIn("| 跨径组合 | 30m |", first)
            self.assertNotIn("40m", first)
            self.assertIn("| 跨径组合 | 40m |", later)
            self.assertNotIn("30m", later)
            self.assertIn("| 桥梁名称 | " + (second or "UNSPECIFIED") + " |", later)

    def test_text_records_do_not_borrow_missing_span(self):
        text = draft("bridge", "桥名：一桥；跨径：30m\n桥名：二桥；桥位：东侧")
        second = text.split("# 独立材料记录 2", 1)[1]
        self.assertIn("| 跨径组合 | UNSPECIFIED |", second)
        self.assertNotIn("30m", second)
        self.assertIn("| 桥位 | 东侧 |", second)

    def test_compact_markdown_keeps_empty_first_and_middle_cells(self):
        text = draft("bridge", "|桥名|跨径|荷载等级|\n|---|---|---|\n||40m|用户等级B|\n|三桥||用户等级C|")
        first, later = text.split("# 独立材料记录 2", 1)
        self.assertIn("| 桥梁名称 | UNSPECIFIED |", first)
        self.assertIn("| 跨径组合 | 40m |", first)
        self.assertIn("| 荷载等级 | 用户等级B |", first)
        self.assertIn("| 桥梁名称 | 三桥 |", later)
        self.assertIn("| 跨径组合 | UNSPECIFIED |", later)
        self.assertNotIn("40m", later)

    def test_single_line_suffix_ids_keep_adjacent_values_local(self):
        text = draft("bridge", "跨径：30m；桥名：一桥；跨径：40m；桥名：二桥；桥位：东侧")
        first, later = text.split("# 独立材料记录 2", 1)
        self.assertIn("| 桥梁名称 | 一桥 |", first)
        self.assertIn("| 跨径组合 | 30m |", first)
        self.assertNotIn("40m", first)
        self.assertIn("| 桥梁名称 | 二桥 |", later)
        self.assertIn("| 跨径组合 | 40m |", later)
        self.assertIn("| 桥位 | 东侧 |", later)
        self.assertNotIn("30m", later)

    def test_repeated_id_records_and_single_suffix_lines_do_not_merge_values(self):
        for text in ("跨径：30m；桥名：同名桥；跨径：40m；桥名：同名桥",
                     "跨径：30m；桥名：一桥\n跨径：40m；桥名：二桥"):
            with self.subTest(text=text):
                first, later = draft("bridge", text).split("# 独立材料记录 2", 1)
                self.assertIn("| 跨径组合 | 30m |", first)
                self.assertNotIn("40m", first)
                self.assertIn("| 跨径组合 | 40m |", later)
                self.assertNotIn("30m", later)

    def test_object_jurisdictions_do_not_come_from_sibling_records(self):
        text = draft("bridge", "桥名：一桥；辖区：CN；跨径：30m\n桥名：二桥；跨径：40m\n桥名：三桥；辖区：SG；跨径：50m")
        second = text.split("# 独立材料记录 2", 1)[1].split("# 独立材料记录 3", 1)[0]
        self.assertIn("- 辖区：UNSPECIFIED", second)
        self.assertIn("| UNSPECIFIED | UNSPECIFIED |", second)
        self.assertNotIn("- 辖区：DUAL", second)
        self.assertNotIn("| CN |", second)
        self.assertNotIn("| SG |", second)

    def test_explicit_preamble_is_shared_but_local_override_drops_unscoped_basis(self):
        text = draft("bridge", "项目名称：统一项目；辖区：CN；适用依据：用户CN项目文件；依据版本：版本甲\n桥名：一桥；跨径：30m\n桥名：二桥；跨径：40m\n桥名：三桥；辖区：SG")
        second = text.split("# 独立材料记录 2", 1)[1].split("# 独立材料记录 3", 1)[0]
        third = text.split("# 独立材料记录 3", 1)[1]
        self.assertIn("| 项目名称 | 统一项目 |", second)
        self.assertIn("| CN | 用户CN项目文件 | 版本甲 |", second)
        self.assertIn("| SG | UNSPECIFIED | UNSPECIFIED |", third)
        self.assertNotIn("用户CN项目文件", third)
        bare = draft("bridge", "SG\n桥名：一桥\n桥名：二桥")
        self.assertEqual(bare.count("- 辖区：SG"), 2)

    def test_table_entities_decode_once_while_plain_entities_remain_literal(self):
        table = draft("bridge", "|桥名|跨径|\n|---|---|\n|=A&#124;B &lt; 10|字面&amp;lt;|")
        self.assertIn("| 桥梁名称 | =A&#124;B &lt; 10 |", table)
        self.assertIn("| 跨径组合 | 字面&amp;lt; |", table)
        plain = draft("bridge", "桥名：字面&lt;；跨径：用户A|B < 10")
        self.assertIn("| 桥梁名称 | 字面&amp;lt; |", plain)
        self.assertIn("| 跨径组合 | 用户A&#124;B &lt; 10 |", plain)

    def test_key_value_table_populates_only_explicit_fields(self):
        text = draft("municipal", "| 栏位 | 内容 |\n| --- | --- |\n| 道路名称 | 东街 |\n| 红线宽度 | 24m |\n| 设计速度 | 未提供 |")
        self.assertIn("| 道路名称 | 东街 |", text)
        self.assertIn("| 红线宽 | 24m |", text)
        self.assertIn("| 设计速度 | UNSPECIFIED |", text)

    def test_tunnel_method_has_specific_review_and_no_parameters(self):
        shield = draft("tunnel", "隧道名称：A区间；工法：盾构；管片资料：附件C.pdf；工程类型：轨道交通")
        self.assertIn("盾构：管片、接缝密封与同步注浆资料单独核对", shield)
        self.assertIn("附件C.pdf", section(shield, "5 开挖与支护"))
        mined = draft("tunnel", "隧道名称：B隧道；工法：矿山法；围岩等级：用户报告IV级")
        self.assertIn("矿山法：围岩分段、开挖步序", mined)
        for text in (shield, mined):
            self.assertIn("| 注浆压力 | UNSPECIFIED |", text)
            self.assertIn("| 沉降控制值 | UNSPECIFIED |", text)

    def test_traffic_types_are_explicit_and_no_model_results_are_invented(self):
        for kind, expected in (("TIA", "建成后交通影响"), ("施工导改", "施工期导改"), ("不做施工导改", "UNSPECIFIED")):
            with self.subTest(kind=kind):
                text = draft("traffic", "研究名称：路口A；研究类型：" + kind + "；流量文件：调查.csv；流量：850辆/小时；仿真软件：用户软件")
                self.assertIn("本记录任务类型：" + expected, text)
                self.assertIn("调查.csv", section(text, "3 调查数据与来源文件"))
                self.assertIn("| 饱和度 | UNSPECIFIED |", text)
                self.assertIn("| 平均延误 | UNSPECIFIED |", text)

    def test_design_coord_problem_and_decision_do_not_share_deadlines(self):
        text = draft("design-coord", "问题编号：Q1；问题：管线穿梁；责任专业：机电；期限：周五\n问题编号：Q2；问题：门口净高；决议：建议修改梁位")
        first, second = text.split("# 独立材料记录 2", 1)
        self.assertIn("管线穿梁", first)
        self.assertIn("周五", first)
        self.assertNotIn("周五", second)
        self.assertIn("| 已议定事项 | UNSPECIFIED |", second)
        self.assertIn("| 待定事项 | 建议修改梁位 |", second)
        self.assertNotIn("APPBCA-2026-12", second)

    def test_jurisdictions_have_independent_sources_and_interfaces(self):
        text = draft("port", "辖区：DUAL；CN依据：用户CN文件；CN版本：版本甲；CN接口：部门甲；SG依据：用户SG文件；SG版本：版本乙；SG接口：部门乙")
        self.assertIn("| CN | 用户CN文件 | 版本甲 | UNSPECIFIED | 部门甲 | unverified |", text)
        self.assertIn("| SG | 用户SG文件 | 版本乙 | UNSPECIFIED | 部门乙 | unverified |", text)
        unresolved = draft("port", "辖区：DUAL；适用依据：范围待核文件；依据版本：用户版本")
        self.assertIn("| 辖区A待指定 | UNSPECIFIED | UNSPECIFIED |", unresolved)
        self.assertNotIn("| CN |", unresolved)
        self.assertNotIn("JTS", draft("port", "辖区：SG"))


class InfrastructureRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="civil-infrastructure-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for context in (
            patch.object(expert_turn, "_OUT", self.root),
            patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_JOB_ROOT": "", "CIVIL_SANDBOX": "workspace-write"}),
            patch("packing_assistant.runtime.memory.assemble_context", return_value={}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def test_six_posts_have_real_markdown_and_excel_with_literal_values(self):
        import openpyxl

        for post, profile in PROFILES.items():
            with self.subTest(post=post):
                request = profile.identity.split("|", 1)[0] + "：=对象A|B < 10"
                result = expert_turn.run_named_exclusive(profile.tool, {"text": request, "confirm_ok": True, "session_id": post})
                self.assertTrue(result["wrote"], result)
                self.assertTrue(result["submit_blocked"])
                markdown = next(Path(f["path"]) for f in result["files"] if f["path"].endswith(".md"))
                self.assertIn("=对象A&#124;B &lt; 10", markdown.read_text(encoding="utf-8"))
                workbook = openpyxl.load_workbook(next(f["path"] for f in result["files"] if f["path"].endswith(".xlsx")))
                try:
                    cells = [cell for sheet in workbook for row in sheet for cell in row]
                    self.assertIn("=对象A|B < 10", [cell.value for cell in cells])
                    self.assertFalse(any(cell.data_type == "f" for cell in cells))
                finally:
                    workbook.close()

    def test_chat_and_high_risk_confirmation_are_enforced(self):
        for post, profile in PROFILES.items():
            with self.subTest(post=post):
                chat = expert_turn.run_expert_turn("这岗位做什么", post, force_intent="chat", session_id="chat-" + post)
                self.assertFalse(chat["wrote"])
                if get_expert(post).risk == "high":
                    result = expert_turn.run_named_exclusive(profile.tool, {"text": "写一份提纲", "confirm_ok": "false", "session_id": "blocked-" + post})
                    self.assertTrue(result["hitl_pending"])
                    self.assertFalse(result["files"])
        self.assertFalse(list(self.root.rglob("*.md")))

    def test_compact_table_and_suffix_records_reach_real_excel_cells(self):
        import openpyxl

        inputs = (
            ("compact", "|桥名|跨径|\n|---|---|\n||40m|", ["UNSPECIFIED", "40m"]),
            ("suffix", "跨径：30m；桥名：一桥；跨径：40m；桥名：二桥", ["一桥", "二桥", "30m", "40m"]),
            ("entities", "|桥名|跨径|\n|---|---|\n|=A&#124;B &lt; 10|字面&amp;lt;|", ["=A|B < 10", "字面&lt;"]),
        )
        for sid, request, expected in inputs:
            with self.subTest(sid=sid):
                result = expert_turn.run_named_exclusive("bridge__outline", {"text": request, "confirm_ok": True, "session_id": sid})
                self.assertTrue(result["wrote"], result)
                workbook = openpyxl.load_workbook(next(f["path"] for f in result["files"] if f["path"].endswith(".xlsx")))
                try:
                    cells = [cell for sheet in workbook for row in sheet for cell in row]
                    for value in expected:
                        self.assertIn(value, [cell.value for cell in cells])
                    self.assertFalse(any(cell.data_type == "f" for cell in cells))
                finally:
                    workbook.close()


if __name__ == "__main__":
    unittest.main()
