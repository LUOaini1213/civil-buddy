#!/usr/bin/env python3
"""T043: record isolation, truthful BIM limits, and actual Markdown/Excel output."""

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
from packing_assistant.post_drafts.bim import DISCLAIMER, build_draft
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import default_engine

TOOLS = {"bim-coord": "bim-coord__clash", "bim-qto": "bim-qto__rules", "bim-deliver": "bim-deliver__lod"}


def chapter(markdown: str, heading: str) -> str:
    return markdown.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def table_rows(markdown: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.strip().removeprefix("|").removesuffix("|").split("|")]
            for line in markdown.splitlines() if line.startswith("| ") and not re.fullmatch(r"[| \-:]+", line)]


def draft(post: str, text: str = "写一份内部讨论草稿") -> str:
    return build_draft(post, TOOLS[post], text)


class BIMBuilderTests(unittest.TestCase):
    def test_exact_tools_and_dedicated_body_boundaries(self):
        self.assertIsNone(build_draft("bim-coord", "bim-qto__rules", ""))
        self.assertIsNone(build_draft("structure", "structure__draft", ""))
        docs = {post: draft(post) for post in TOOLS}
        for markdown in docs.values():
            self.assertIn(DISCLAIMER, markdown)
            self.assertIn("submit_blocked=true", markdown)
            self.assertIn("- 辖区：UNSPECIFIED", markdown)
            self.assertNotIn("## 用户原文", markdown)
            self.assertNotRegex(markdown, r"第[一二三四五六七八九十\d]+条")
        self.assertIn("## 5 用户问题清单", docs["bim-coord"])
        self.assertNotIn("## 5 用户问题清单", docs["bim-qto"])
        self.assertIn("## 4 用户数量登记表", docs["bim-qto"])
        self.assertIn("## 4 LOD 与信息需求矩阵", docs["bim-deliver"])

    def test_compact_model_rows_keep_empty_cells_in_their_column(self):
        # A row's own pipes are its column borders; an adjacent pipe is an empty cell.
        head = "|模型名称|专业|模型版本|\n|---|---|---|\n|A1|结构|V1|\n"
        spaced = "| 模型名称 | 专业 | 模型版本 |\n| --- | --- | --- |\n| A1 | 结构 | V1 |\n|  | 暖通 | M2 |"
        self.assertEqual(draft("bim-coord", head + "||暖通|M2|"), draft("bim-coord", spaced))
        for row, expected in (
            ("||暖通|M2|", ["UNSPECIFIED", "暖通", "M2"]),
            ("|B1|暖通||", ["B1", "暖通", "UNSPECIFIED"]),
            ("|B1|", ["B1", "UNSPECIFIED", "UNSPECIFIED"]),
            ("|||", ["UNSPECIFIED", "UNSPECIFIED", "UNSPECIFIED"]),
            ("|", ["UNSPECIFIED", "UNSPECIFIED", "UNSPECIFIED"]),
        ):
            with self.subTest(row=row):
                models = [cells for cells in table_rows(chapter(draft("bim-coord", head + row), "1 项目与合成模型登记"))
                          if len(cells) == 9]
                self.assertEqual(models[1][:3], ["A1", "结构", "V1"])
                self.assertEqual(models[2][:3], expected)

    def test_empty_coordination_has_unknown_issues_and_no_invented_check(self):
        markdown = draft("bim-coord", "生成协调纪要，没有模型，帮我估计碰撞数量")
        self.assertIn("未执行碰撞检查", markdown)
        issues = table_rows(chapter(markdown, "5 用户问题清单"))
        self.assertEqual(issues[1][:-1], ["UNSPECIFIED"] * 12)
        self.assertEqual(issues[1][-1], "未核验")
        types = chapter(markdown, "4 碰撞类型分类栏")
        for label in ("硬碰撞", "间隙不足", "预留洞未做", "4D / 工序冲突"):
            self.assertIn(f"| {label} |", types)
        self.assertNotRegex(markdown, r"共发现\s*\d+|\d+\s*mm|\d+\s*处")
        self.assertIn("| 容差 | UNSPECIFIED | 未执行 |", chapter(markdown, "3 检查范围、容差与过滤"))

    def test_multiple_models_keep_each_version_and_config_separate(self):
        markdown = draft("bim-coord", "项目名称：协调测试项目\n模型名称：结构A.ifc；专业：结构；版本：R3；模型单位：mm\n模型名称：机电B.ifc；专业：机电；模型范围：二层\n测试集：结构对机电；专业对：结构×机电；检查范围：二层东区；容差：用户设定7mm")
        models = table_rows(chapter(markdown, "1 项目与合成模型登记"))
        row_a = next(row for row in models if row[0] == "结构A.ifc")
        row_b = next(row for row in models if row[0] == "机电B.ifc")
        self.assertEqual(row_a[1:3], ["结构", "R3"])
        self.assertEqual(row_b[1:3], ["机电", "UNSPECIFIED"])
        self.assertEqual(row_b[4], "二层")
        coordinates = table_rows(chapter(markdown, "2 合成前提与坐标核对"))
        self.assertEqual(next(row for row in coordinates if row[0] == "结构A.ifc")[4], "mm")
        self.assertEqual(next(row for row in coordinates if row[0] == "机电B.ifc")[4], "UNSPECIFIED")
        config = chapter(markdown, "3 检查范围、容差与过滤")
        self.assertIn("| 测试集 | 结构对机电 | 未执行 |", config)
        self.assertIn("| 检查范围 | 二层东区 | 未执行 |", config)
        self.assertIn("| 容差 | 用户设定7mm | 未执行 |", config)

    def test_missing_record_identifiers_do_not_merge_the_following_facts(self):
        markdown = draft("bim-deliver", "模型名称：模型A；版本：V1\n模型名称：待填；版本：V2；模型阶段：施工深化")
        rows = table_rows(chapter(markdown, "1 项目、阶段与模型登记"))
        self.assertEqual(next(row for row in rows if row[0] == "模型A")[2], "V1")
        unknown = next(row for row in rows if row[0] == "UNSPECIFIED" and len(row) == 9)
        self.assertEqual(unknown[2], "V2")
        self.assertEqual(unknown[6], "施工深化")
        qto = draft("bim-qto", "构件类别：墙；工程量：10\n构件类别：待填；工程量：25")
        rows = table_rows(chapter(qto, "4 用户数量登记表"))
        self.assertEqual([row[0] for row in rows[1:]], ["墙", "UNSPECIFIED"])
        self.assertEqual([row[4] for row in rows[1:]], ["10", "25"])

    def test_markdown_table_kind_uses_headers_even_when_model_name_is_missing(self):
        markdown = draft("bim-coord", "| 模型名称 | 专业 | 版本 |\n| --- | --- | --- |\n| 模型A | 结构 | V1 |\n| | 暖通 | M2 |")
        rows = table_rows(chapter(markdown, "1 项目与合成模型登记"))
        self.assertTrue(any(row[:3] == ["UNSPECIFIED", "暖通", "M2"] for row in rows))
        self.assertNotIn("M2", chapter(markdown, "5 用户问题清单"))

    def test_multiple_user_issues_reach_rows_without_claiming_closed(self):
        markdown = draft("bim-coord", "问题编号：BCF-01；关联模型：结构A.ifc；位置：二层A轴；碰撞类型：硬碰撞；问题描述：风管与梁几何相交待复核；构件A：梁L1；构件B：风管F1；责任专业：暖通；状态：关闭；截止日期：2026-10-01；BCF链接：bcf/01\n问题编号：BCF-02；位置：三层B轴；碰撞类型：间隙不足；问题描述：用户指出检修空间待核；责任专业：电气；状态：进行中")
        rows = table_rows(chapter(markdown, "5 用户问题清单"))
        one, two = rows[1:]
        self.assertEqual(one[:4], ["BCF-01", "结构A.ifc", "二层A轴", "硬碰撞"])
        self.assertEqual(one[5:9], ["梁L1", "风管F1", "暖通", "关闭"])
        self.assertEqual(one[-2:], ["UNSPECIFIED", "未核验"])
        self.assertEqual(two[0], "BCF-02")
        self.assertEqual(two[5:7], ["UNSPECIFIED", "UNSPECIFIED"])
        self.assertEqual(two[9:12], ["UNSPECIFIED"] * 3)
        self.assertNotIn("已全部消项", markdown)

    def test_issue_and_professional_interface_tables_are_independent(self):
        markdown = draft("bim-coord", "问题编号：P-1；问题描述：接口待复核；责任专业：结构\n接口编号：J-1；提资方：结构；接收专业：暖通；提资内容：梁底标高表；格式：XLSX；截止日期：2026-10-02；关联模型：结构A\n接口编号：J-2；提资方：电气；接收专业：建筑；提资内容：桥架检修需求")
        rows = table_rows(chapter(markdown, "6 专业提资接口"))
        self.assertEqual(rows[1][:6], ["J-1", "结构", "暖通", "梁底标高表", "XLSX", "2026-10-02"])
        self.assertEqual(rows[2][:4], ["J-2", "电气", "建筑", "桥架检修需求"])
        self.assertEqual(rows[2][4:7], ["UNSPECIFIED"] * 3)
        self.assertNotIn("梁底标高表", chapter(markdown, "5 用户问题清单"))

    def test_issue_markdown_table_preserves_each_problem_with_model_reference(self):
        markdown = draft("bim-coord", "| 问题编号 | 模型名称 | 位置 | 问题描述 | 状态 | 关闭依据 |\n| --- | --- | --- | --- | --- | --- |\n| P-1 | M1 | 一层 | 洞口未建 | 关闭 | 用户会议记录 |\n| P-2 | M2 | 二层 | 通行空间待核 | 新建 | |")
        rows = table_rows(chapter(markdown, "5 用户问题清单"))
        self.assertEqual(rows[1][:3], ["P-1", "M1", "一层"])
        self.assertEqual(rows[1][-2:], ["用户会议记录", "未核验"])
        self.assertEqual(rows[2][:3], ["P-2", "M2", "二层"])
        self.assertEqual(rows[2][-2:], ["UNSPECIFIED", "未核验"])

    def test_qto_missing_model_or_dimensions_never_generate_quantities(self):
        markdown = draft("bim-qto", "写算量说明；构件类别：混凝土梁；计量规则：从几何量取体积；梁长10m宽1m高2m；请估计数量和单价")
        rows = table_rows(chapter(markdown, "4 用户数量登记表"))
        self.assertEqual(rows[1][4:6], ["UNSPECIFIED", "UNSPECIFIED"])
        self.assertEqual(rows[1][8:10], ["TBD", "TBD"])
        self.assertNotIn("20", rows[1][4])
        self.assertIn("未运行几何算量", markdown)
        source_rows = table_rows(chapter(markdown, "5 属性路径与来源校核"))
        self.assertEqual(source_rows[1][2:6], ["UNSPECIFIED"] * 4)

    def test_qto_multiple_items_keep_filters_deductions_and_given_quantities(self):
        markdown = draft("bim-qto", "项目名称：算量测试；提量目的：月进度核对\n模型名称：结构R1.ifc；专业：结构；版本：R1\n构件类别：混凝土墙；关联模型：结构R1.ifc；材质：用户混凝土；楼层：二层；包含项：主体墙；排除项：临时体量；计量规则：用户净体积口径；扣洞规则：按用户清单处理；重叠处理：节点单列；重复处理：同GUID只留一次；工程量：123.40；计量单位：m3；来源：用户导出表；属性路径：用户指定Volume；校核来源：收方表A\n构件类别：钢构件；关联模型：钢构R2.ifc；包含项：屋面钢柱；计量规则：用户重量口径；计量单位：t")
        filters = table_rows(chapter(markdown, "2 工程分类与构件过滤"))
        self.assertEqual(filters[1][:2], ["混凝土墙", "结构R1.ifc"])
        self.assertEqual(filters[1][3:5], ["用户混凝土", "二层"])
        self.assertEqual(filters[2][3:5], ["UNSPECIFIED", "UNSPECIFIED"])
        rules = table_rows(chapter(markdown, "3 计量口径、重复与扣减"))
        self.assertEqual(rules[1][3:6], ["按用户清单处理", "节点单列", "同GUID只留一次"])
        quantities = table_rows(chapter(markdown, "4 用户数量登记表"))
        self.assertEqual(quantities[1][4:6], ["123.40", "m3"])
        self.assertEqual(quantities[2][4:6], ["UNSPECIFIED", "t"])
        self.assertEqual(quantities[1][6], "用户明确给值；未核算")
        paths = table_rows(chapter(markdown, "5 属性路径与来源校核"))
        self.assertEqual(paths[1][2:5], ["用户指定Volume", "UNSPECIFIED", "收方表A"])
        self.assertEqual(paths[2][2:5], ["UNSPECIFIED"] * 3)

    def test_qto_numeric_zero_is_preserved_but_expressions_not_evaluated(self):
        markdown = draft("bim-qto", "构件类别：门窗；工程量：0；计量单位：樘\n构件类别：墙；工程量：10*20；计量单位：m2\n构件类别：楼板；工程量：约25.5m3")
        rows = table_rows(chapter(markdown, "4 用户数量登记表"))
        self.assertEqual(rows[1][4], "0")
        self.assertEqual(rows[2][4], "UNSPECIFIED")
        self.assertEqual(rows[2][-1], "10*20")
        self.assertEqual(rows[3][4], "约25.5m3")
        self.assertNotIn("200", rows[2])

    def test_qto_markdown_rows_preserve_model_references_and_distinct_rules(self):
        markdown = draft("bim-qto", "| 模型名称 | 构件类别 | 计量规则 | 工程量 | 单位 |\n| --- | --- | --- | --- | --- |\n| M1 | 墙 | 毛面积口径 | 110 | m2 |\n| M1 | 墙 | 用户净面积口径 | 97 | m2 |\n| M2 | 板 | 待核口径 | | m3 |")
        rows = table_rows(chapter(markdown, "4 用户数量登记表"))
        self.assertEqual([row[1] for row in rows[1:]], ["M1", "M1", "M2"])
        self.assertEqual([row[4] for row in rows[1:]], ["110", "97", "UNSPECIFIED"])
        self.assertEqual([row[3] for row in rows[1:]], ["毛面积口径", "用户净面积口径", "待核口径"])
        self.assertNotIn("207", chapter(markdown, "4 用户数量登记表"))

    def test_delivery_missing_requirements_does_not_invent_lod_or_file_names(self):
        markdown = draft("bim-deliver", "写一份 BIM 交付清单，暂无模型和合同要求")
        rows = table_rows(chapter(markdown, "4 LOD 与信息需求矩阵"))
        self.assertEqual(rows[1], ["UNSPECIFIED"] * 9)
        names = table_rows(chapter(markdown, "3 拆分与命名规则"))
        self.assertEqual(names[1][:-1], ["UNSPECIFIED"] * 6)
        checklist = table_rows(chapter(markdown, "8 交付检查与未交清单"))
        self.assertEqual(checklist[1], ["UNSPECIFIED"] * 7)
        self.assertNotRegex(markdown, r"LOD\s*(?:100|200|300|350|400|500)|[\w-]+\.(?:ifc|rvt|nwd)")

    def test_delivery_multiple_models_keep_lod_naming_and_versions_independent(self):
        markdown = draft("bim-deliver", "项目名称：交付测试；接收方：业主测试组\n模型名称：结构模型；专业：结构；版本：V2；前版：V1；版本变更：按用户变更单更新；LOD：350；几何要求：节点接口；属性要求：材料代码；文档要求：用户图纸目录；交付目的：接口协调；拆分规则：按单体；命名规则：用户命名制度；文件名：USR-STR-V2.ifc；模型单位：mm；坐标系：项目坐标；北向：用户约定北向\n模型名称：机电模型；专业：机电；版本：M3；LOD：用户自定义细度B；交付目的：运维字段核对；属性要求：设备编号")
        matrix = table_rows(chapter(markdown, "4 LOD 与信息需求矩阵"))
        self.assertEqual(matrix[1][3:8], ["接口协调", "350", "节点接口", "材料代码", "用户图纸目录"])
        self.assertEqual(matrix[2][3:8], ["运维字段核对", "用户自定义细度B", "UNSPECIFIED", "设备编号", "UNSPECIFIED"])
        self.assertEqual(matrix[1][-1], "UNSPECIFIED")
        names = table_rows(chapter(markdown, "3 拆分与命名规则"))
        self.assertEqual(names[1][1], "按单体")
        self.assertEqual(names[1][4:6], ["用户命名制度", "USR-STR-V2.ifc"])
        self.assertEqual(names[2][1:6], ["UNSPECIFIED"] * 5)
        versions = table_rows(chapter(markdown, "6 版本与发布记录"))
        self.assertEqual(versions[1][1:4], ["V2", "V1", "按用户变更单更新"])
        self.assertEqual(versions[2][1:4], ["M3", "UNSPECIFIED", "UNSPECIFIED"])

    def test_delivery_outputs_and_reported_acceptance_are_not_certified(self):
        markdown = draft("bim-deliver", "模型名称：结构模型；碰撞状态：用户称已检查；验收状态：用户称已验收；容器状态：Published；缺项：机房设备尚未建模\n交付物：结构交换文件；关联模型：结构模型；格式：IFC；版本：R2；是否必交：用户合同要求；交付日期：2026-10-03；接收方：项目业主\n交付物：协调纪要；格式：PDF")
        outputs = table_rows(chapter(markdown, "5 交付物与格式清单"))
        self.assertEqual(outputs[1], ["结构交换文件", "结构模型", "IFC", "R2", "用户合同要求", "2026-10-03", "项目业主", "UNSPECIFIED"])
        self.assertEqual(outputs[2][1:4], ["UNSPECIFIED", "PDF", "UNSPECIFIED"])
        checks = table_rows(chapter(markdown, "8 交付检查与未交清单"))
        self.assertEqual(checks[1][3], "用户称已检查")
        self.assertEqual(checks[1][5:7], ["用户称已验收", "UNSPECIFIED"])
        self.assertIn("机房设备尚未建模", chapter(markdown, "8 交付检查与未交清单"))

    def test_global_coordinates_are_preserved_without_filling_each_model(self):
        markdown = draft("bim-deliver", "坐标系：用户公共坐标；单位：m\n模型名称：模型A；版本：V1\n模型名称：模型B；模型单位：mm")
        rows = table_rows(chapter(markdown, "2 坐标系与单位"))
        self.assertEqual(rows[1][0:2], ["全局约定（用户提供）", "用户公共坐标"])
        self.assertEqual(rows[1][4], "m")
        self.assertEqual(rows[2][1:5], ["UNSPECIFIED"] * 4)
        self.assertEqual(rows[3][4], "mm")

    def test_delivery_model_matrix_markdown_and_exchange_fields(self):
        markdown = draft("bim-deliver", "辖区：EU\n| 模型名称 | 专业 | LOD | 几何要求 | 属性要求 | 文档要求 |\n| --- | --- | --- | --- | --- | --- |\n| 模型A | 建筑 | 用户LOD-A | 用户几何A | 用户属性A | 用户文档A |\n| 模型B | 机电 | 用户LOD-B | | 用户属性B | |")
        rows = table_rows(chapter(markdown, "4 LOD 与信息需求矩阵"))
        self.assertEqual(rows[1][4:8], ["用户LOD-A", "用户几何A", "用户属性A", "用户文档A"])
        self.assertEqual(rows[2][4:8], ["用户LOD-B", "UNSPECIFIED", "用户属性B", "UNSPECIFIED"])
        self.assertIn("- 辖区：EU", markdown)
        exchange = draft("bim-deliver", "模型名称：用户模型；IFC版本：用户指定版本；导出视图：用户视图；导出设置：用户设置；交换抽检记录：用户抽检单")
        rows = table_rows(chapter(exchange, "7 交换与接收抽检"))
        self.assertEqual(rows[1], ["用户模型", "用户指定版本", "用户视图", "用户设置", "用户抽检单", "未执行"])

    def test_user_markup_is_escaped_once_without_breaking_table_columns(self):
        markdown = draft("bim-qto", "构件类别：用户构件；包含项：长度<10且区域A|B；来源：<b>用户摘录</b>")
        rows = table_rows(chapter(markdown, "4 用户数量登记表"))
        self.assertEqual(len(rows[1]), 11)
        self.assertEqual(rows[1][2], "长度&lt;10且区域A&#124;B")
        self.assertEqual(rows[1][7], "&lt;b&gt;用户摘录&lt;/b&gt;")
        self.assertNotIn("&amp;lt;", markdown)
        self.assertNotIn("<b>", markdown)


class BIMRuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="civil-bim-")
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

    def _artifacts(self, result: dict, expected: list[str]) -> str:
        self.assertTrue(result.get("wrote"), result)
        self.assertTrue(result["submit_blocked"])
        md = next(Path(item["path"]) for item in result["files"] if item["path"].endswith(".md"))
        text = md.read_text(encoding="utf-8")
        xlsx = next(Path(item["path"]) for item in result["files"] if item["path"].endswith(".xlsx"))
        import openpyxl
        book = openpyxl.load_workbook(xlsx, data_only=False)
        try:
            values = [str(cell.value) for sheet in book for row in sheet for cell in row if cell.value is not None]
            for value in expected:
                self.assertIn(value, values)
            self.assertFalse(any(cell.data_type == "f" for sheet in book for row in sheet for cell in row))
        finally:
            book.close()
        return text

    def test_named_coordination_exports_multiple_issues_and_interfaces(self):
        result = expert_turn.run_named_exclusive("bim-coord__clash", {"text": "问题编号：BCF-A；问题描述：导出碰撞甲\n问题编号：BCF-B；问题描述：导出碰撞乙\n提资项：导出提资表；提资方：结构", "session_id": "bim-named"})
        text = self._artifacts(result, ["BCF-A", "导出碰撞甲", "BCF-B", "导出碰撞乙", "导出提资表"])
        self.assertIn("导出碰撞甲", chapter(text, "5 用户问题清单"))

    def test_tool_engine_exports_qto_rows_with_unknowns_and_no_calculation(self):
        result = default_engine().execute("bim-qto__rules", {"text": "构件类别：用户墙量；工程量：123.50；单位：m3\n构件类别：用户钢量；单位：t", "session_id": "bim-engine"}, expert_id="bim-qto", intent="run")
        self.assertTrue(result["ok"], result)
        text = self._artifacts(result, ["用户墙量", "用户钢量", "123.50", "UNSPECIFIED", "TBD"])
        rows = table_rows(chapter(text, "4 用户数量登记表"))
        self.assertEqual([row[4] for row in rows[1:]], ["123.50", "UNSPECIFIED"])

    def test_expert_turn_exports_multiple_delivery_models(self):
        result = expert_turn.run_expert_turn("写一份 BIM 交付清单\n模型名称：导出模型A；版本：V7；LOD：用户细度7\n模型名称：导出模型B；版本：R9；属性要求：用户资产字段", "bim-deliver", session_id="bim-turn")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "done")
        text = self._artifacts(result, ["导出模型A", "V7", "用户细度7", "导出模型B", "R9", "用户资产字段"])
        rows = table_rows(chapter(text, "4 LOD 与信息需求矩阵"))
        self.assertEqual(rows[1][4], "用户细度7")
        self.assertEqual(rows[2][4], "UNSPECIFIED")

    def test_all_bim_chat_paths_and_wrong_expert_are_write_denied(self):
        engine = default_engine()
        for post, tool in TOOLS.items():
            with self.subTest(post=post):
                result = expert_turn.run_expert_turn("怎么理解这个岗位的资料要求？", post, session_id=f"chat-{post}")
                self.assertFalse(result["wrote"])
                self.assertEqual(result["files"], [])
                denied = engine.execute(tool, {"text": "写一份草稿"}, expert_id=post, intent="chat")
                self.assertFalse(denied["ok"])
                self.assertEqual(denied["error_code"], "permission_denied")
                sibling = engine.execute(tool, {"text": "写一份草稿"}, expert_id="hr-labor", intent="run")
                self.assertFalse(sibling["ok"])
        self.assertFalse(list(self.root.rglob("*.md")))
        self.assertFalse(list(self.root.rglob("*.xlsx")))

    def test_post_forbidden_claim_still_fails_in_common_scan(self):
        result = expert_turn.run_expert_turn("写一份 BIM 交付清单；模型名称：可以开工", "bim-deliver", session_id="bim-reject")
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["error_code"], "forbidden_content")
        self.assertFalse(result["files"])
        self.assertFalse(list(self.root.rglob("*.md")))

    def test_excel_keeps_original_comparison_and_pipe_as_text(self):
        result = expert_turn.run_named_exclusive("bim-deliver__lod", {"text": "模型名称：=2+3；命名规则：x<10 && A|B", "session_id": "bim-text"})
        text = self._artifacts(result, ["=2+3", "x<10 && A|B"])
        self.assertIn("x&lt;10 &amp;&amp; A&#124;B", text)


if __name__ == "__main__":
    unittest.main()
