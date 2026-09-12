#!/usr/bin/env python3
"""T046 specialties: independent records, missing inputs, and real Markdown/Excel gates."""
from __future__ import annotations

import html
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")

from packing_assistant import expert_turn
from packing_assistant.post_drafts.design_specialties import TOOLS, build_draft
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import default_engine


def draft(post: str, text: str = "写一份本岗草稿") -> str:
    result = build_draft(post, TOOLS[post], text)
    assert isinstance(result, str)
    return result


def chapter(markdown: str, heading: str) -> str:
    return markdown.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def rows(markdown: str) -> list[list[str]]:
    return [[html.unescape(cell.strip()) for cell in line.strip().strip("|").split("|")]
            for line in markdown.splitlines() if line.startswith("| ") and not line.startswith("| ---")]


class DesignContentTests(unittest.TestCase):
    def test_only_matching_post_and_tool_are_rendered(self):
        self.assertIsNone(build_draft("unknown", "unknown__memo", ""))
        for post in TOOLS:
            with self.subTest(post=post):
                self.assertIsNone(build_draft(post, "other__tool", ""))

    def test_missing_inputs_keep_unknown_jurisdiction_and_distinct_professional_sections(self):
        expected = {
            "landscape": ("软硬景分区", "软景与苗木", "顶板覆土", "消防交通"),
            "interior": ("房间功能与饰面", "防水、防潮与隔声", "外窗界面", "门窗五金"),
            "intel-weak": ("子系统", "桥架路由", "供电、UPS", "公共安全接口"),
            "civil-defense": ("防护单元", "口部", "防化通风", "柴油电站"),
            "hydraulic": ("水文成果", "地质、地下水", "水闸、泵站", "度汛"),
        }
        for post, headings in expected.items():
            with self.subTest(post=post):
                text = draft(post)
                self.assertIn("- 辖区：UNSPECIFIED", text)
                self.assertIn("submit_blocked=true", text)
                self.assertIn("缺项、复核与交付目录", text)
                for heading in headings:
                    self.assertIn(heading, text)
                self.assertNotRegex(text, r"\d+\s*(?:mm|m²|m3|MPa|kW|像素|天存储|度设防)")

    def test_landscape_zones_keep_vertical_soil_and_fire_interfaces_separate(self):
        text = draft("landscape", "项目：景观测试\n分区编号：L-A；分区：入口区；分区类型：硬景；红线：东侧红线；室内标高：5.2m；室外标高：5.1m；标高基准：用户基准；排水坡向：南侧雨水沟；无障碍：衔接门厅；消防车道：用户总图待核\n分区编号：L-B；分区：屋顶花园；分区类型：软景；覆土厚度：450mm；顶板荷载：结构提资待核；灌溉：用户滴灌；土壤条件：用户改良种植土")
        zoning = rows(chapter(text, "2 范围红线与软硬景分区"))
        self.assertEqual(zoning[1][:3], ["L-A", "入口区", "硬景"])
        self.assertEqual(zoning[2][5], "UNSPECIFIED")
        vertical = rows(chapter(text, "3 竖向、无障碍与排水"))
        self.assertEqual(vertical[1][1:5], ["用户基准", "5.2m", "5.1m", "UNSPECIFIED"])
        self.assertEqual(vertical[2][1:5], ["UNSPECIFIED"] * 4)
        soil = rows(chapter(text, "6 土壤、顶板覆土与灌排"))
        self.assertEqual(soil[1][1:5], ["UNSPECIFIED"] * 4)
        self.assertEqual(soil[2][1:5], ["用户改良种植土", "450mm", "结构提资待核", "用户滴灌"])

    def test_landscape_plants_and_paving_do_not_share_specs_or_quantities(self):
        text = draft("landscape", "苗木：桂花；所属分区：东园；胸径：12cm；冠幅：2m；规格：用户苗木表A；数量：8；单位：株；现状树处理：用户要求保留；来源：甲方苗木表\n苗木：麦冬；所属分区：西园；层次：地被\n铺装：主园路；铺装材质：用户石材；铺装厚度：35mm；铺装纹样：甲方样板；来源：材料表P\n铺装：宅间路；铺装材质：用户透水砖")
        plants = rows(chapter(text, "5 软景与苗木登记"))
        self.assertEqual(plants[1][1:3], ["桂花", "东园"])
        self.assertEqual(plants[1][4:9], ["用户苗木表A", "12cm", "2m", "8", "株"])
        self.assertEqual(plants[2][4:9], ["UNSPECIFIED"] * 5)
        paving = rows(chapter(text, "4 园路与硬景铺装"))
        self.assertEqual(paving[1][3:6], ["用户石材", "35mm", "甲方样板"])
        self.assertEqual(paving[2][3:6], ["用户透水砖", "UNSPECIFIED", "UNSPECIFIED"])
        self.assertNotIn("甲方苗木表", chapter(text, "4 园路与硬景铺装"))

    def test_landscape_water_lighting_and_furniture_remain_user_selected(self):
        text = draft("landscape", "室外设施：入口灯具；设施类型：照明；电源：电气提资A；位置：门厅外\n室外设施：庭院座椅；设施类型：家具；规格：用户样板S")
        facilities = rows(chapter(text, "7 水景、照明与室外设施"))
        self.assertEqual(facilities[1][:4], ["入口灯具", "照明", "门厅外", "电气提资A"])
        self.assertEqual(facilities[2][3:6], ["UNSPECIFIED", "UNSPECIFIED", "用户样板S"])

    def test_interior_rooms_preserve_each_finish_and_waterproof_value(self):
        text = draft("interior", "房间编号：R1；房间：卫生间甲；地面基层：用户找平层；地面：用户地砖；墙面：用户瓷砖；天花：用户吊顶；防水部位：地面及管根；防水材料：用户材料W；防水厚度：1.5mm；防水上翻：300mm；节点图号：JD-1；防潮：用户基层处理\n房间编号：R2；房间：办公室乙；地面：用户地毯；隔声：用户隔声需求")
        finishes = rows(chapter(text, "2 房间功能与饰面做法"))
        self.assertEqual(finishes[1][0:2], ["R1", "卫生间甲"])
        self.assertEqual(finishes[1][3:5], ["用户找平层", "用户地砖"])
        self.assertEqual(finishes[2][3:5], ["UNSPECIFIED", "用户地毯"])
        waterproof = rows(chapter(text, "3 防水、防潮与隔声节点"))
        self.assertEqual(waterproof[1][1:5], ["地面及管根", "用户材料W", "1.5mm", "300mm"])
        self.assertEqual(waterproof[2][1:6], ["UNSPECIFIED"] * 5)
        self.assertEqual(waterproof[2][6], "用户隔声需求")

    def test_interior_interfaces_and_door_hardware_are_associated_to_rooms(self):
        text = draft("interior", "房间：大厅；隔墙：用户轻质隔墙；吊顶净高：3.2m；新增荷载：用户设备荷载单；楼板开洞：洞口D1待核；综合天花：灯风喷淋综合图；窗台收口：装修负责室内侧\n门编号：M1；门窗：大厅门；所属房间：大厅；五金：用户门吸；品牌：用户品牌A；成品保护：用户保护膜\n门编号：M2；门窗：办公室门；所属房间：办公室")
        interfaces = rows(chapter(text, "4 建筑、结构、机电与外窗界面"))
        self.assertEqual(interfaces[1][2:7], ["3.2m", "用户设备荷载单", "洞口D1待核", "灯风喷淋综合图", "装修负责室内侧"])
        doors = rows(chapter(text, "5 门窗五金与成品保护"))
        self.assertEqual(doors[1][4:7], ["用户门吸", "用户品牌A", "用户保护膜"])
        self.assertEqual(doors[2][4:7], ["UNSPECIFIED"] * 3)

    def test_weak_systems_keep_user_brand_pixel_storage_and_power_values(self):
        text = draft("intel-weak", "系统编号：S1；系统：视频安防；覆盖范围：一层；点数：12；品牌：用户品牌V；型号：型号V1；摄像头像素：用户400万；存储天数：用户30天；机房：设备间A；电源：电气电源A；UPS要求：用户UPS条件\n系统编号：S2；系统：综合布线；覆盖范围：二层；点数：0；接地端子：电气端子B")
        systems = rows(chapter(text, "2 子系统与用户功能需求"))
        self.assertEqual(systems[1][4:9], ["12", "用户品牌V", "型号V1", "用户400万", "用户30天"])
        self.assertEqual(systems[2][4:9], ["0", *(["UNSPECIFIED"] * 4)])
        power = rows(chapter(text, "5 供电、UPS、接地与空间提资"))
        self.assertEqual(power[1][3], "电气电源A")
        self.assertEqual(power[2][3:6], ["UNSPECIFIED"] * 3)
        self.assertEqual(power[2][6], "电气端子B")

    def test_weak_routes_points_and_fire_links_are_not_interchanged(self):
        text = draft("intel-weak", "系统：门禁；消防联动接口：用户联动需求待核；网络安全要求：用户隔离需求\n桥架编号：Q1；桥架路由：一层走廊；服务系统：门禁；桥架规格：200x100；强弱电间距：用户300mm；穿越做法：专业穿越节点\n桥架编号：Q2；桥架路由：二层走廊；服务系统：网络\n点位编号：P1；点位：入口读卡器；关联子系统：门禁；位置：东门；数量：2；用户图号：RD1\n点位编号：P2；点位：信息面板；关联子系统：网络")
        routes = rows(chapter(text, "3 机房、弱电井与桥架路由"))
        self.assertEqual(routes[1][4:8], ["200x100", "UNSPECIFIED", "用户300mm", "专业穿越节点"])
        self.assertEqual(routes[2][4:8], ["UNSPECIFIED"] * 4)
        points = rows(chapter(text, "4 点位与系统关联登记"))
        self.assertEqual(points[1][3:7], ["门禁", "东门", "2", "RD1"])
        self.assertEqual(points[2][4:7], ["UNSPECIFIED"] * 3)
        links = rows(chapter(text, "6 消防联动、网络与公共安全接口"))
        self.assertEqual(links[1][1:3], ["用户联动需求待核", "用户隔离需求"])

    def test_defense_units_keep_levels_functions_ventilation_and_missing_dimensions(self):
        text = draft("civil-defense", "辖区：CN\n单元编号：F1；防护单元：单元甲；人防等级：用户六级；平时功能：停车；战时功能：用户人员掩蔽；密闭分区：用户密闭区A；出入口数量：2；防化通风：用户通风条件；滤毒要求：用户设备方案待核；超压：用户50Pa；给水：用户给水资料\n单元编号：F2；防护单元：单元乙；平时功能：储藏")
        units = rows(chapter(text, "2 防护单元、等级与平战功能"))
        self.assertEqual(units[1][3:7], ["用户六级", "停车", "用户人员掩蔽", "用户密闭区A"])
        self.assertEqual(units[2][3:7], ["UNSPECIFIED", "储藏", "UNSPECIFIED", "UNSPECIFIED"])
        vent = rows(chapter(text, "5 防化通风、滤毒与超压"))
        self.assertEqual(vent[1][1:4], ["用户通风条件", "用户设备方案待核", "用户50Pa"])
        self.assertEqual(vent[1][4], "UNSPECIFIED")
        self.assertEqual(vent[2][1:], ["UNSPECIFIED"] * 4)

    def test_defense_mouths_and_equipment_are_explicitly_linked(self):
        text = draft("civil-defense", "口部编号：K1；口部：东口；所属单元：F1；口部类型：用户主要口部；扩散室：用户空间A；防倒塌棚架：方案待核；图号：KF1\n口部编号：K2；口部：西口；所属单元：F2\n设备编号：E1；防护设备：用户防护门；所属单元：F1；所属口部：K1；型号：用户型号X；门樘尺寸：用户1500x2100mm；数量：1；来源：用户设备表\n设备编号：E2；防护设备：用户活门；所属口部：K2")
        mouths = rows(chapter(text, "3 口部、出入口与扩散空间"))
        self.assertEqual(mouths[1][2], "F1")
        self.assertEqual(mouths[2][5:9], ["UNSPECIFIED"] * 4)
        equipment = rows(chapter(text, "4 防护设备与孔口登记"))
        self.assertEqual(equipment[1][2:4], ["F1", "K1"])
        self.assertEqual(equipment[2][2:4], ["UNSPECIFIED", "K2"])
        self.assertEqual(equipment[2][5:9], ["UNSPECIFIED"] * 4)

    def test_hydraulic_water_and_geological_records_keep_each_station_and_borehole(self):
        text = draft("hydraulic", "水文断面：H1；水文报告：报告A；设计洪水位：5.2m；设计流量：125m3/s；设计频率：用户频率；高程基准：基准A\n水文断面：H2；水文报告：报告B\n地勘孔号：Z1；地勘报告：地勘A；地层：用户黏土层；地下水位：2.1m；渗透系数：用户试验值；筑堤材料：用户料场A\n地勘孔号：Z2；地勘报告：地勘B")
        water = rows(chapter(text, "3 水文成果与水位流量登记"))
        self.assertEqual(water[1][1:6], ["H1", "报告A", "UNSPECIFIED", "5.2m", "125m3/s"])
        self.assertEqual(water[2][3:9], ["UNSPECIFIED"] * 6)
        geology = rows(chapter(text, "4 地质、地下水与筑堤材料"))
        self.assertEqual(geology[1][2:6], ["用户黏土层", "2.1m", "用户试验值", "用户料场A"])
        self.assertEqual(geology[2][2:6], ["UNSPECIFIED"] * 4)

    def test_hydraulic_structures_do_not_gain_other_structures_crest_or_pump_selection(self):
        text = draft("hydraulic", "建筑物编号：D1；堤段：左岸堤；工程任务：防洪；关联水文断面：H1；关联勘探孔：Z1；堤顶高程：8.2m；堤顶宽度：4m；坡比：1:3；渗流条件：用户防渗资料；冲刷资料：报告待核\n建筑物编号：P1；泵站：东泵站；工程任务：排涝；扬程：用户12m；设计流量：用户2m3/s；施工导流条件：用户导流资料\n建筑物编号：G1；水闸：西闸；孔数：0")
        section = rows(chapter(text, "5 堤防、护岸与断面原则"))
        self.assertEqual(section[1][1:4], ["8.2m", "4m", "1:3"])
        self.assertEqual(section[2][1:4], ["UNSPECIFIED"] * 3)
        equipment = rows(chapter(text, "6 水闸、泵站与穿堤接口"))
        self.assertEqual(equipment[2][1:5], ["泵站", "UNSPECIFIED", "用户12m", "用户2m3/s"])
        self.assertEqual(equipment[3][1:5], ["水闸", "0", "UNSPECIFIED", "UNSPECIFIED"])
        self.assertIn("未进行水力、渗流、冲刷或边坡稳定计算", text)

    def test_empty_record_anchors_start_new_rows_in_every_specialty(self):
        cases = (
            ("landscape", "苗木", "数量", "5 软景与苗木登记", 1, 7),
            ("interior", "房间", "防水上翻", "3 防水、防潮与隔声节点", 0, 4),
            ("intel-weak", "系统", "点数", "2 子系统与用户功能需求", 1, 4),
            ("civil-defense", "防护单元", "出入口数量", "2 防护单元、等级与平战功能", 1, 8),
            ("hydraulic", "水闸", "孔数", "6 水闸、泵站与穿堤接口", 0, 2),
        )
        for post, label, value_label, heading, name_column, value_column in cases:
            with self.subTest(post=post):
                text = draft(post, f"{label}：A；{value_label}：5\n{label}：待填；{value_label}：7\n{label}：待填；{value_label}：9")
                data = rows(chapter(text, heading))[1:]
                self.assertEqual([row[name_column] for row in data], ["A", "UNSPECIFIED", "UNSPECIFIED"])
                self.assertEqual([row[value_column] for row in data], ["5", "7", "9"])

    def test_markdown_table_rows_do_not_inherit_blank_cells_or_prior_tables(self):
        cases = (
            ("landscape", "苗木", "胸径", "5 软景与苗木登记", 1, 5),
            ("interior", "房间", "地面", "2 房间功能与饰面做法", 1, 4),
            ("intel-weak", "系统", "品牌", "2 子系统与用户功能需求", 1, 5),
            ("civil-defense", "防护单元", "人防等级", "2 防护单元、等级与平战功能", 1, 3),
            ("hydraulic", "水文断面", "设计洪水位", "3 水文成果与水位流量登记", 1, 4),
        )
        for post, label, value_label, heading, name_column, value_column in cases:
            with self.subTest(post=post):
                table = f"| {label} | {value_label} |\n| --- | --- |\n| A | 用户值A |\n| | 用户值B |\n| C | |"
                data = rows(chapter(draft(post, table), heading))[1:]
                self.assertEqual([row[name_column] for row in data], ["A", "UNSPECIFIED", "C"])
                self.assertEqual([row[value_column] for row in data], ["用户值A", "用户值B", "UNSPECIFIED"])

    def test_dual_basis_and_interfaces_have_separate_jurisdiction_columns(self):
        for post in TOOLS:
            with self.subTest(post=post):
                text = draft(post, "辖区：DUAL\n| 辖区 | 依据 |\n| --- | --- |\n| CN | 用户中国依据 |\n| SG | 用户新加坡依据 |\n接口编号：J1；接口名称：围护接口；CN接口：中国接口资料；SG接口：新加坡接口资料；关联对象：对象A\n接口编号：J2；接口名称：机电接口；EU接口：欧盟资料")
                self.assertIn("- 辖区：DUAL", text)
                self.assertIn("| 用户指定文件 | 用户中国依据 | 用户新加坡依据 | UNSPECIFIED | unverified |", text)
                interfaces = rows(chapter(text, "专业提资与辖区接口"))
                self.assertEqual(interfaces[1][6:9], ["中国接口资料", "新加坡接口资料", "UNSPECIFIED"])
                self.assertEqual(interfaces[2][6:9], ["UNSPECIFIED", "UNSPECIFIED", "欧盟资料"])

    def test_compact_table_edge_empty_cells_and_literal_entities_preserve_columns(self):
        cases = (
            ("landscape", "苗木", "胸径", "5 软景与苗木登记", 1, 5),
            ("interior", "房间", "地面", "2 房间功能与饰面做法", 1, 4),
            ("intel-weak", "系统", "品牌", "2 子系统与用户功能需求", 1, 5),
            ("civil-defense", "防护单元", "人防等级", "2 防护单元、等级与平战功能", 1, 3),
            ("hydraulic", "水文断面", "设计洪水位", "3 水文成果与水位流量登记", 1, 4),
        )
        for post, label, value_label, heading, name_column, value_column in cases:
            with self.subTest(post=post):
                table = f"|{label}|{value_label}|\n|---|---|\n||literal &amp;amp;|\n|A&amp;#124;B||\n||&amp;#x3C;|\n|||"
                data = rows(chapter(draft(post, table), heading))[1:]
                self.assertEqual([row[name_column] for row in data], ["UNSPECIFIED", "A&#124;B", "UNSPECIFIED", "UNSPECIFIED"])
                self.assertEqual([row[value_column] for row in data], ["literal &amp;", "UNSPECIFIED", "&#x3C;", "UNSPECIFIED"])

    def test_object_jurisdictions_do_not_inherit_overall_or_sibling_values(self):
        for post, label in (("landscape", "分区"), ("interior", "房间"), ("intel-weak", "系统"), ("civil-defense", "防护单元"), ("hydraulic", "水闸")):
            for payload in (
                f"{label}：A；辖区：CN\n{label}：B\n{label}：C；适用辖区：SG\n{label}：D；辖区：待填\n项目辖区：EU",
                f"总体辖区：EU\n|{label}|辖区|\n|---|---|\n|A|CN|\n|B||\n|C|SG|\n|D|待填|",
            ):
                with self.subTest(post=post, payload=payload):
                    text = draft(post, payload)
                    self.assertIn("- 辖区：DUAL", text)
                    data = rows(text.split("### 对象辖区登记", 1)[1])[1:]
                    self.assertEqual([row[1] for row in data], ["CN", "UNSPECIFIED", "SG", "UNSPECIFIED"])
                    if post == "civil-defense":
                        units = rows(chapter(text, "2 防护单元、等级与平战功能"))[1:]
                        self.assertEqual([row[2] for row in units], ["CN", "UNSPECIFIED", "SG", "UNSPECIFIED"])

    def test_basis_table_after_objects_stays_global_without_reassigning_last_object(self):
        text = draft("civil-defense", "防护单元：A；辖区：CN\n防护单元：B\n|辖区|依据|\n|---|---|\n|SG|用户依据S|")
        data = rows(text.split("### 对象辖区登记", 1)[1])[1:]
        self.assertEqual([row[1] for row in data], ["CN", "UNSPECIFIED"])
        self.assertIn("| 用户指定文件 | UNSPECIFIED | 用户依据S | UNSPECIFIED | unverified |", text)

    def test_direct_basis_labels_and_markup_are_preserved_without_double_escape(self):
        text = draft("interior", "辖区：EU；EU依据：用户规范原文；项目：A&B\n房间：=2+3；地面：x<10 && A|B；墙面：literal &amp; value；天花：<b>用户材料</b>")
        self.assertIn("x&lt;10 &amp;&amp; A&#124;B", text)
        self.assertIn("literal &amp;amp; value", text)
        self.assertNotIn("<b>", text)
        finishes = rows(chapter(text, "2 房间功能与饰面做法"))
        self.assertEqual(len(finishes[1]), len(finishes[0]))
        self.assertEqual(finishes[1][4], "x<10 && A|B")
        self.assertEqual(finishes[1][6], "literal &amp; value")
        self.assertEqual(finishes[1][8], "<b>用户材料</b>")

    def test_attachment_encoded_cells_decode_once_after_table_splitting(self):
        original = ["=2+3", "x<10 && A|B", "literal &amp; value", "<b>用户材料</b>"]
        encoded = [html.escape(value, quote=False).replace("|", "&#124;") for value in original]
        table = "|房间|地面|墙面|天花|\n|---|---|---|---|\n|" + "|".join(encoded) + "|"
        text = draft("interior", table)
        values = rows(chapter(text, "2 房间功能与饰面做法"))[1]
        self.assertEqual([values[index] for index in (1, 4, 6, 8)], original)
        self.assertIn("x&lt;10 &amp;&amp; A&#124;B", text)
        self.assertIn("literal &amp;amp; value", text)


class DesignRuntimeTests(unittest.TestCase):
    def setUp(self):
        output = ROOT / "output"
        output.mkdir(exist_ok=True)
        output.resolve().relative_to(ROOT)
        directory = tempfile.TemporaryDirectory(prefix="design-specialties-", dir=output)
        self.root = Path(directory.name).resolve()
        self.root.relative_to(output.resolve())
        self.addCleanup(directory.cleanup)
        for context in (
            patch.object(expert_turn, "_OUT", self.root),
            patch("packing_assistant.runtime.memory._OUT", self.root),
            patch("packing_assistant.runtime.scheduler.get_scheduler", return_value=Scheduler()),
            patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_JOB_ROOT": "", "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request", "PYTHON_DOTENV_DISABLED": "1"}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def artifacts(self, result: dict, expected: list[str]) -> str:
        self.assertIsNot(result.get("ok"), False, result)
        self.assertTrue(result.get("wrote"), result)
        self.assertTrue(result["submit_blocked"])
        paths = [Path(item["path"]).resolve() for item in result["files"]]
        for path in paths:
            path.relative_to(self.root)
            self.assertGreater(path.stat().st_size, 0)
        md = next(path for path in paths if path.suffix == ".md")
        xlsx = next(path for path in paths if path.suffix == ".xlsx")
        import openpyxl
        book = openpyxl.load_workbook(xlsx, data_only=False)
        try:
            cells = [cell for sheet in book for row in sheet for cell in row if cell.value is not None]
            values = [str(cell.value) for cell in cells]
            for value in expected:
                self.assertIn(value, values)
            self.assertFalse(any(cell.data_type == "f" for cell in cells))
        finally:
            book.close()
        return md.read_text(encoding="utf-8")

    def test_every_post_exports_given_facts_to_actual_markdown_and_excel(self):
        facts = {
            "landscape": "苗木：验收桂花；数量：8；来源：用户苗木表",
            "interior": "房间：验收卫生间；防水材料：用户防水材料；防水上翻：300mm",
            "intel-weak": "系统：验收视频系统；点数：12；桥架：验收桥架；桥架规格：用户规格200",
            "civil-defense": "防护单元：验收单元；人防等级：用户等级；口部：验收口部；所属单元：验收单元",
            "hydraulic": "水闸：验收水闸；孔数：2；水文断面：验收断面；设计洪水位：5.2m",
        }
        expected = {
            "landscape": ["验收桂花", "8", "用户苗木表"],
            "interior": ["验收卫生间", "用户防水材料", "300mm"],
            "intel-weak": ["验收视频系统", "12", "验收桥架", "用户规格200"],
            "civil-defense": ["验收单元", "用户等级", "验收口部"],
            "hydraulic": ["验收水闸", "2", "验收断面", "5.2m"],
        }
        for post, text in facts.items():
            with self.subTest(post=post):
                result = expert_turn.run_expert_turn("写一份本岗草稿\n" + text, post, session_id="draft-" + post, confirm_ok=True)
                self.artifacts(result, expected[post])

    def test_missing_inputs_export_unknowns_for_every_post(self):
        for post in TOOLS:
            with self.subTest(post=post):
                result = expert_turn.run_expert_turn("写一份本岗草稿，缺失内容保持待填", post, session_id="unknown-" + post, confirm_ok=True)
                text = self.artifacts(result, ["UNSPECIFIED"])
                self.assertIn("- 辖区：UNSPECIFIED", text)

    def test_chat_and_sibling_tool_calls_never_write(self):
        engine = default_engine()
        for post, tool in TOOLS.items():
            with self.subTest(post=post):
                result = expert_turn.run_expert_turn("这个岗位需要哪些资料？先别写", post, session_id="chat-" + post)
                self.assertFalse(result["wrote"])
                self.assertFalse(result["files"])
                denied = engine.execute(tool, {"text": "写一份草稿"}, expert_id=post, intent="chat")
                self.assertFalse(denied["ok"])
                self.assertEqual(denied["error_code"], "permission_denied")
                sibling = engine.execute(tool, {"text": "写一份草稿"}, expert_id="hr-labor", intent="run")
                self.assertFalse(sibling["ok"])
        self.assertFalse(list(self.root.rglob("*.md")))
        self.assertFalse(list(self.root.rglob("*.xlsx")))

    def test_both_high_risk_posts_wait_for_confirmation(self):
        for post in ("civil-defense", "hydraulic"):
            with self.subTest(post=post):
                result = expert_turn.run_expert_turn("写一份本岗草稿", post, session_id="gate-" + post, confirm_ok=False)
                self.assertFalse(result["wrote"], result)
                self.assertFalse(result["files"])
                self.assertIn("我明白，将由持证人员签认", str(result))
        self.assertFalse(list(self.root.rglob("*.md")))

    def test_named_export_restores_raw_markup_entities_and_formula_like_text(self):
        result = expert_turn.run_named_exclusive(TOOLS["interior"], {"text": "房间：=2+3；地面：x<10 && A|B；墙面：literal &amp; value；天花：<b>用户材料</b>", "session_id": "escape-interior"})
        text = self.artifacts(result, ["=2+3", "x<10 && A|B", "literal &amp; value", "<b>用户材料</b>"])
        self.assertIn("x&lt;10 &amp;&amp; A&#124;B", text)

    def test_compact_table_exports_keep_blank_edges_and_literal_entities_in_excel(self):
        result = expert_turn.run_named_exclusive(TOOLS["interior"], {"text": "|房间|地面|\n|---|---|\n||literal &amp;amp;|\n|A&amp;#124;B||\n||&amp;#x3C;|", "session_id": "compact-table-interior"})
        text = self.artifacts(result, ["literal &amp;", "A&#124;B", "&#x3C;"])
        finishes = rows(chapter(text, "2 房间功能与饰面做法"))[1:]
        self.assertEqual([row[1] for row in finishes], ["UNSPECIFIED", "A&#124;B", "UNSPECIFIED"])
        self.assertEqual([row[4] for row in finishes], ["literal &amp;", "UNSPECIFIED", "&#x3C;"])

    def test_real_csv_and_xlsx_upload_text_roundtrips_to_draft_excel(self):
        import csv
        from io import BytesIO, StringIO
        import openpyxl
        from demo.uploads import extract_upload

        source_rows = [
            ["房间", "地面", "墙面", "天花"],
            ["=2+3", "x<10 && A|B", "literal &amp; value", "<b>用户材料</b>"],
            ["", "独立空名称房间", "", ""],
        ]
        csv_buffer = StringIO(newline="")
        csv.writer(csv_buffer).writerows(source_rows)
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        for source_row in source_rows:
            sheet.append(source_row)
        sheet["A2"].data_type = "s"
        xlsx_buffer = BytesIO()
        workbook.save(xlsx_buffer)
        workbook.close()
        for extension, content in (("csv", csv_buffer.getvalue().encode("utf-8")), ("xlsx", xlsx_buffer.getvalue())):
            with self.subTest(extension=extension):
                _, extracted, _ = extract_upload("rooms." + extension, content)
                result = expert_turn.run_named_exclusive(TOOLS["interior"], {"text": extracted, "session_id": "upload-interior-" + extension})
                text = self.artifacts(result, source_rows[1] + ["独立空名称房间"])
                finishes = rows(chapter(text, "2 房间功能与饰面做法"))[1:]
                self.assertEqual([finishes[0][index] for index in (1, 4, 6, 8)], source_rows[1])
                self.assertEqual([finishes[1][index] for index in (1, 4, 6, 8)], ["UNSPECIFIED", "独立空名称房间", "UNSPECIFIED", "UNSPECIFIED"])


if __name__ == "__main__":
    unittest.main()
