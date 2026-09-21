#!/usr/bin/env python3
"""tools/tender_document.py: a tender DOCUMENT is read by its structure; our own bid files are read field by field.

Small documents written for these tests - other names, numbers and wording than the benchmark documents of
test/benchmarks/real_tender, so that a rule fitted to a benchmark sentence does not pass here by accident.
One test per family of thing that went wrong on a real-shaped tender.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools import tender_document as td  # noqa: E402
from packing_assistant.tools import tender_facts as tf  # noqa: E402
from packing_assistant.tools.tender_parse import parse_tender_text  # noqa: E402

FILLER = "\n\n".join(f"{n}.1 承包人应在收到监理人指示后{7 + n}天内提交书面报告，监理人应在{14 + n}天内答复；因承包人原因造成工期延误的，每延误1天支付违约金{500 * n}元。"
                     for n in range(1, 16))

TENDER = f"""第一章 招标公告

1. 招标条件

本招标项目河西污水处理厂提标改造工程已批准建设，招标人为河西水务有限公司。招标编号：HXSW-2027-SG-009。

2. 项目概况

2.1 计划工期：300日历天。

2.2 本次招标不接受联合体投标。

5.1 投标文件递交的截止时间为2027年3月9日10时00分。

5.2 逾期送达的投标文件，招标人不予受理。

第二章 投标人须知

投标人须知前附表

| 条款号 | 条款名称 | 编列内容 |
| --- | --- | --- |
| 1.1.2 | 招标人 | 名称：河西水务有限公司；地址：河西区清源路2号；联系人：白工 |
| 1.1.4 | 项目名称 | 河西污水处理厂提标改造工程 |
| 1.3.2 | 计划工期 | 计划工期：300日历天；计划开工日期：2027年4月1日 |
| 1.10.3 | 招标人书面澄清的时间 | 投标截止时间15天前 |
| 3.2.3 | 最高投标限价 | 9,860万元；超过最高投标限价的投标将被否决 |
| 3.3.1 | 投标有效期 | 120日历天 |
| 3.4.1 | 投标保证金 | 金额：50万元；形式：银行保函；递交截止时间：同投标截止时间 |
| 3.7.5 | 装订要求 | 须采用胶装，不得使用活页夹 |
| 7.3.1 | 履约担保 | 履约担保的形式：银行保函；履约担保的金额：签约合同价的10% |
| 10 | 需要补充的其他内容 | 10.2 缺陷责任期：12个月 |

3.4 投标保证金

3.4.1 投标人应按前附表规定递交投标保证金。3.4.2 未按要求提交投标保证金的，其投标文件作否决投标处理。

8. 重新招标

8.1 经评标委员会评审后否决所有投标的，招标人将重新招标。

四、无效投标情形

投标文件有下列情形之一的，按无效投标处理：

（1）未按规定签字盖章的；

（2）投标报价超过最高投标限价的；

第三章 评标办法（经评审的最低投标价法）

评分标准

| 评审项目 | 评审内容 | 分值 | 评分标准 |
| --- | --- | --- | --- |
| 技术部分 | 工艺调试方案 | 12 | 方案完整得9-12分 |
| 商务部分 | 类似业绩 | 8 | 每项得4分 |

第四章 合同条款及格式

{FILLER}

第七章 技术标准和要求

本工程生化池基坑开挖深度7.5米，投标人须编制深基坑专项施工方案。★投标人须承诺出水水质达到一级A标准，未承诺的其投标将被否决。

第八章 投标文件格式

一、投标函

二、授权委托书
"""


def values(facts: tf.TenderFacts, topic: str):
    return [(m.value, m.ref) for m in facts.of(topic)]


class Structure(unittest.TestCase):
    def test_a_typed_request_or_a_pasted_page_is_not_a_document(self) -> None:
        self.assertTrue(td.is_document(TENDER))
        self.assertFalse(td.is_document("招标文件要求工期300日历天、投标保证金50万，我们投标函写的是320日历天。"))
        self.assertFalse(td.is_document("第一章 投标人须知\n★工期60日历天。\n★投标保证金人民币20万元。\n" * 3))

    def test_fields_come_from_the_front_table_with_the_clause_they_stand_in(self) -> None:
        facts = tf.extract(TENDER)
        self.assertEqual(values(facts, "owner"), [("河西水务有限公司", "第二章 前附表 1.1.2")])
        self.assertEqual(values(facts, "duration"), [("300日历天", "第二章 前附表 1.3.2")])
        self.assertEqual(values(facts, "price_cap"), [("9,860万元", "第二章 前附表 3.2.3")])
        self.assertEqual(values(facts, "validity"), [("120日历天", "第二章 前附表 3.3.1")])
        self.assertEqual(values(facts, "bond"), [("50万元", "第二章 前附表 3.4.1")])
        self.assertEqual(values(facts, "warranty"), [("12个月", "第二章 前附表 10.2")], "the number inside the content is the better locator")
        self.assertEqual(values(facts, "tender_no"), [("HXSW-2027-SG-009", "第一章 1")], "what the table lacks comes from the notice")
        self.assertEqual(facts.jurisdiction, "UNSPECIFIED", "SG inside a tender number is 施工, not Singapore - and no country is a default")

    def test_running_text_next_to_a_field_word_is_not_the_field(self) -> None:
        facts = tf.extract(TENDER)
        self.assertEqual(len(facts.of("owner")), 1, "招标人不予受理 / 招标人书面澄清的时间 / 招标人将重新招标 are not the 招标人")
        self.assertEqual([m.value for m in facts.of("duration")], ["300日历天"], "the contract's 7天 / 14天 / 1天 are nobody's 工期")
        self.assertEqual([m.value for m in facts.of("deadline_bid")], ["2027年3月9日10时00分"], "the bond row's 递交截止时间 is the bond's")

    def test_two_parts_of_one_row_are_told_apart(self) -> None:
        facts = tf.extract(TENDER)
        self.assertEqual([(m.role, m.value) for m in facts.of("performance_bond")], [("形式", "银行保函"), ("金额", "签约合同价的10%")])

    def test_a_front_table_numbered_by_row_keeps_its_row_number(self) -> None:
        local = TENDER.replace("| 条款号 | 条款名称 | 编列内容 |", "| 序号 | 条款名称 | 内容及要求 |").replace("| 1.3.2 | 计划工期 |", "| 5 | 工期要求 |")
        self.assertEqual(values(tf.extract(local), "duration"), [("300日历天", "第二章 前附表 5")])

    def test_the_notice_disagreeing_with_the_table_is_said_not_settled(self) -> None:
        facts = tf.extract(TENDER.replace("2.1 计划工期：300日历天。", "2.1 计划工期：280日历天。"))
        self.assertEqual([(m.value, m.origin) for m in facts.of("duration")], [("300日历天", ""), ("280日历天", "招标公告，与前附表不一致")])


class Rejections(unittest.TestCase):
    def setUp(self) -> None:
        self.found = td.rejections(td.read(TENDER))
        self.texts = [r.piece.text for r in self.found]

    def test_every_rejecting_sentence_is_a_row_with_its_clause(self) -> None:
        by_text = {r.piece.text: r.piece.ref for r in self.found}
        self.assertEqual(by_text["3.4.2 未按要求提交投标保证金的，其投标文件作否决投标处理。"], "第二章 3.4.2")
        self.assertEqual(by_text["5.2 逾期送达的投标文件，招标人不予受理。"], "第一章 5.2")
        self.assertIn("超过最高投标限价的投标将被否决", self.texts, "a rejection inside a front-table cell")

    def test_a_list_announced_by_a_sentence_is_read_item_by_item(self) -> None:
        self.assertIn("（1）未按规定签字盖章的；", self.texts)
        self.assertIn("（2）投标报价超过最高投标限价的；", self.texts)

    def test_rejecting_all_bids_is_not_about_a_bidder_and_stars_count(self) -> None:
        self.assertFalse(any("否决所有投标" in t for t in self.texts))
        star = [r for r in self.found if r.star]
        self.assertEqual(len(star), 1)
        self.assertIn("一级A标准", star[0].piece.text)

    def test_the_parser_lists_them_one_by_one(self) -> None:
        parsed = parse_tender_text(TENDER)
        clauses = parsed["handoff"]["rejection_clauses"]
        self.assertGreaterEqual(len(clauses), 6)
        self.assertTrue(all(c["locator"] for c in clauses))
        self.assertEqual(parsed["handoff"]["document"]["chapters"], 6)
        kinds = {r["item_kind"] for r in parsed["requirements"]}
        self.assertTrue({"reject_clause", "obligation"} <= kinds, kinds)


class TheRest(unittest.TestCase):
    def test_obligations_scores_specials_forms(self) -> None:
        doc = td.read(TENDER)
        self.assertIn("须采用胶装，不得使用活页夹", [p.text for p in td.obligations(doc)])
        self.assertIn("2.2 本次招标不接受联合体投标。", [p.text for p in td.obligations(doc)])
        self.assertEqual([(n, s) for n, s, _p in td.scores(doc)], [("工艺调试方案", "12分"), ("类似业绩", "8分")], "a points column of bare numbers")
        self.assertEqual([(n, d) for n, d, _p in td.specials(doc)], [("深基坑专项施工方案", "开挖深度7.5米")], "the figure stands in the clause before")
        self.assertEqual([n for n, _p in td.forms(doc)], ["投标函", "授权委托书"])


class OurFiles(unittest.TestCase):
    LETTER = ("# 投标函\n\n我方愿意以人民币玖仟伍佰万元整（¥9,500.00万元）的投标总报价，工期300日历天，工程质量达到合格。\n\n"
              "随同本投标函提交投标保证金一份，金额为人民币50万元。\n\n| 序号 | 条款名称 | 约定内容 |\n| --- | --- | --- |\n| 1 | 项目经理 | 邵文斌 |\n")
    METHOD = "# 施工组织设计\n\n总工期控制在330日历天以内，其中土建阶段150日历天。项目经理邵文彬负责全面管理。\n"
    PRICES = "| 项目名称 | 投标总报价（元） | 工期（日历天） |\n| --- | --- | --- |\n| 河西提标改造 | 95,000,000.00 | 300 |\n"

    def said(self, text: str, title: str):
        return [(m.topic, m.value) for m in td.response_values(text, title)]

    def test_a_value_counts_in_the_clause_of_its_field_word(self) -> None:
        self.assertEqual(self.said(self.LETTER, "投标函"), [("our_price", "9,500.00万元"), ("quality", "合格"), ("duration", "300日历天"),
                                                        ("bond", "50万元"), ("pm", "邵文斌")])
        self.assertEqual(self.said(self.METHOD, "施组"), [("duration", "330日历天"), ("pm", "邵文彬")], "150日历天 is a stage")
        self.assertEqual(self.said(self.PRICES, "报价表"), [("our_price", "95,000,000.00元"), ("duration", "300日历天")],
                         "the field words are the column names, the unit stands in the column name")

    def test_what_our_files_do_not_agree_on(self) -> None:
        mentions = [m for text, title in ((self.LETTER, "投标函"), (self.METHOD, "施组"), (self.PRICES, "报价表")) for m in td.response_values(text, title)]
        rows = {row["label"]: row for row in td.consistency(mentions)}
        self.assertFalse(rows["工期"]["same"])
        self.assertFalse(rows["项目经理"]["same"], "邵文斌 / 邵文彬: one character")
        self.assertTrue(rows["我方报价"]["same"], "9,500.00万元 and 95,000,000.00元 are one amount")
        self.assertNotIn("质量标准", rows, "only one file speaks of it")


class WordNumbering(unittest.TestCase):
    """A clause number that Word generates is a list number, not text. Extracted without numbering.xml the
    paragraph "8. 投标文件有下列情形之一的…" has lost its "8." - and the clause its locator."""

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def paragraph(self, text: str, num: str = "", level: int = 0) -> str:
        props = f'<w:pPr><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="{num}"/></w:numPr></w:pPr>' if num else ""
        return f"<w:p>{props}<w:r><w:t>{text}</w:t></w:r></w:p>"

    def test_list_numbers_come_back_as_text(self) -> None:
        from xml.etree import ElementTree as ET

        from packing_assistant.document_text import docx_document_text

        body = "".join([self.paragraph("投标文件", "1"), self.paragraph("投标文件的组成", "1", 1), self.paragraph("投标报价", "1", 1),
                        self.paragraph("投标", "1"), self.paragraph("密封和标记", "1", 1), self.paragraph("无效投标情形", "2"),
                        self.paragraph("未按规定签字盖章的", "3"), self.paragraph("报价超过限价的", "3"), self.paragraph("普通段落"),
                        self.paragraph("", "3"), self.paragraph("项目符号", "4")])
        document = ET.fromstring(f'<w:document xmlns:w="{self.W}"><w:body>{body}</w:body></w:document>')
        numbering = ET.fromstring(f'''<w:numbering xmlns:w="{self.W}">
            <w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="3"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>
              <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl></w:abstractNum>
            <w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="4"/><w:numFmt w:val="chineseCounting"/><w:lvlText w:val="%1、"/></w:lvl></w:abstractNum>
            <w:abstractNum w:abstractNumId="2"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="（%1）"/></w:lvl></w:abstractNum>
            <w:abstractNum w:abstractNumId="3"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="●"/></w:lvl></w:abstractNum>
            <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
            <w:num w:numId="3"><w:abstractNumId w:val="2"/></w:num><w:num w:numId="4"><w:abstractNumId w:val="3"/></w:num>
        </w:numbering>''')
        lines = [line for line in docx_document_text(document, 10_000, numbering).splitlines() if line]
        self.assertEqual(lines, ["3. 投标文件", "3.1 投标文件的组成", "3.2 投标报价", "4. 投标", "4.1 密封和标记", "四、 无效投标情形",
                                 "（1） 未按规定签字盖章的", "（2） 报价超过限价的", "普通段落", "项目符号"],
                         "a deeper level restarts under a new parent; an empty paragraph takes no number; a bullet is no number")
        plain = [line for line in docx_document_text(document, 10_000).splitlines() if line]
        self.assertEqual(plain[0], "投标文件", "without numbering.xml the text is what it was")


class PdfLayout(unittest.TestCase):
    """What pypdf gives back for a page - lines cut at the page width, table cells one to a line, the header
    repeated on the next page, a page number - put together again."""

    PAGES = ["第 1 页\n第二章 投标人须知\n投标人须知前附表\n条款号\n条款名称\n编列内容\n1.3.2\n计划工期\n计划工期：300日历天；计划开工日期：2027年4月1\n日\n"
             "1.10.2\n投标人提出问题的截止\n时间\n2027年2月20日17时00分前\n3.3.1\n投标有效期",
             "第 2 页\n条款号\n条款名称\n编列内容\n120日历天\n10\n需要补充的其他内容\n10.1 本项目采用综合评估法评标；10.2 缺陷责任期：12个月\n1. 总则\n"
             "1.1 本招标项目已具备招标条件，现对本标段施工进行招标，投标人应当仔细阅读招标文件的全部内\n容。未按要求提交投标保证金的，其投标文件作否\n决投标处理。",
             "第 3 页\n序号\n项目\n技术要求\n备注\n1\n沥青面层\n★采用SBS改性沥青\n不满足的为无效投标\n二、其他要求\n本节无。"]

    def setUp(self) -> None:
        from packing_assistant.tools.pdf_layout import pages_text

        self.text = pages_text(self.PAGES)
        self.lines = [line for line in self.text.splitlines() if line]

    def test_a_table_drawn_cell_by_cell_is_a_table_again(self) -> None:
        self.assertIn("| 条款号 | 条款名称 | 编列内容 |", self.lines)
        self.assertEqual(self.lines.count("| 条款号 | 条款名称 | 编列内容 |"), 1, "the header repeated on page 2 is the same table")
        self.assertIn("| 1.3.2 | 计划工期 | 计划工期：300日历天；计划开工日期：2027年4月1日 |", self.lines)
        self.assertIn("| 1.10.2 | 投标人提出问题的截止时间 | 2027年2月20日17时00分前 |", self.lines, "a name that filled its column runs on")
        self.assertIn("| 3.3.1 | 投标有效期 | 120日历天 |", self.lines, "a row cut by the page break")
        self.assertIn("| 10 | 需要补充的其他内容 | 10.1 本项目采用综合评估法评标；10.2 缺陷责任期：12个月 |", self.lines, "10.1 is row 10's own content")

    def test_the_text_after_the_table_is_text_and_a_cut_sentence_is_whole(self) -> None:
        self.assertIn("1. 总则", self.lines)
        joined = [line for line in self.lines if "否决投标处理" in line]
        self.assertEqual(len(joined), 1)
        self.assertIn("未按要求提交投标保证金的，其投标文件作否决投标处理。", joined[0])
        self.assertFalse(any(line.startswith("第 ") and line.endswith(" 页") for line in self.lines), "page numbers are dropped")
        self.assertEqual([line for line in self.lines if line.startswith("〔第")], ["〔第1页〕", "〔第2页〕", "〔第3页〕"])

    def test_a_remark_column_and_a_chinese_heading_after_a_numbered_table(self) -> None:
        self.assertIn("| 1 | 沥青面层 | ★采用SBS改性沥青 | 不满足的为无效投标 |", self.lines)
        self.assertIn("二、其他要求", self.lines)

    def test_the_document_reader_knows_the_page(self) -> None:
        facts = tf.extract("第一章 招标公告\n\n" + "占位。" * 600 + "\n\n" + self.text)
        self.assertEqual([(m.value, m.ref) for m in facts.of("duration")], [("300日历天", "第二章 前附表 1.3.2（第1页）")])
        self.assertEqual([(m.value, m.ref) for m in facts.of("validity")], [("120日历天", "第二章 前附表 3.3.1（第1页）")])


class OcrLines(unittest.TestCase):
    """Recognised boxes as the lines a text layer would give: a table's cells one to a line, a paragraph's boxes joined."""

    def test_boxes_in_columns_become_cells(self) -> None:
        from packing_assistant.tools.ocr import lines_from_boxes

        def box(x, y, text, w=60):
            return (float(x), float(y), float(x + w), float(y + 30), text)

        boxes = [box(170, 100, "投标人须知前附表", 300),
                 box(170, 160, "条款号"), box(345, 160, "条款名称"), box(660, 162, "编列内容"),
                 box(170, 220, "1.3.2"), box(345, 218, "计划工期"), box(660, 221, "计划工期：300日历天；计划开工日期：2027年4月1", 700), box(660, 258, "日"),
                 box(170, 320, "1.10.2"), box(345, 320, "投标人提出问题的截止"), box(660, 321, "2027年2月20日17时前", 300), box(345, 356, "时间"),
                 box(170, 430, "1.总则", 120), box(170, 490, "1.1本招标项目已具备招标条件，现对本标段施工进行招标。", 1100)]
        lines = lines_from_boxes(boxes)
        self.assertEqual(lines[:4], ["投标人须知前附表", "条款号", "条款名称", "编列内容"])
        self.assertEqual(lines[4:7], ["1.3.2", "计划工期", "计划工期：300日历天；计划开工日期：2027年4月1日"])
        self.assertEqual(lines[7:10], ["1.10.2", "投标人提出问题的截止时间", "2027年2月20日17时前"], "a cell's second line joins its own column")
        self.assertEqual(lines[10:], ["1.总则", "1.1本招标项目已具备招标条件，现对本标段施工进行招标。"], "a line across the columns ends the table")


class ScanReadings(unittest.TestCase):
    """What an OCR reading does to a number. The one thing worse than showing no value is showing a wrong one as
    if it had been read: "3，268.50万元" must never come out as "268.50万元"."""

    def table(self, *rows: str) -> str:
        body = "\n".join(f"| {n} | {name} | {content} |" for n, (name, content) in enumerate((r.split("=", 1) for r in rows), 1))
        return ("第一章 投标邀请\n\n" + "占位。" * 600 + "\n\n第二章 投标人须知\n\n投标人须知前附表\n\n| 序号 | 条款名称 | 内容及要求 |\n| --- | --- | --- |\n" + body + "\n")

    def test_a_thousands_separator_read_as_a_full_width_comma(self) -> None:
        facts = tf.extract(self.table("最高限价=人民币3，268.50万元", "投标保证金=人民币贰拾万元整（￥200，000.00）；银行转账"))
        self.assertEqual([m.value for m in facts.of("price_cap")], ["3，268.50万元"])
        self.assertEqual([m.value for m in facts.of("bond")], ["￥200，000.00"])
        typed = tf.extract("招标文件要求最高限价3,268.50万元、投标保证金200，000元。")
        self.assertEqual([m.value for m in typed.of("price_cap")], ["3,268.50万元"])
        self.assertEqual([m.value for m in typed.of("bond")], ["200，000元"])

    def test_a_date_glued_to_its_time_is_a_date_not_a_label(self) -> None:
        facts = tf.extract(self.table("投标截止时间及地点=2027-03-0909：00：河西区公共资源交易中心", "答疑=应于2027-02-2017：00前提出"))
        self.assertEqual([m.value for m in facts.of("deadline_bid")], ["2027-03-0909：00"])
        self.assertEqual([m.value for m in facts.of("deadline_query")], ["2027-02-2017：00"])

    def test_a_semicolon_read_as_a_colon_still_separates_two_labels(self) -> None:
        facts = tf.extract(self.table("投标人资质条件=资质条件：市政公用工程施工总承包二级：项目经理资格：市政公用工程专业一级注册建造师",
                                      "履约担保=履约担保的形式：银行保函：履约担保的金额：签约合同价的10%"))
        self.assertEqual([m.value for m in facts.of("qualification")], ["市政公用工程施工总承包二级"])
        self.assertEqual([m.value for m in facts.of("pm")], ["市政公用工程专业一级注册建造师"])
        self.assertEqual([(m.role, m.value) for m in facts.of("performance_bond")], [("形式", "银行保函"), ("金额", "签约合同价的10%")])

    def test_a_clause_number_with_no_space_after_it(self) -> None:
        doc = td.read("第一章 招标公告\n\n" + "占位。" * 600 + "\n\n第二章 投标人须知\n\n3.4.2投标人不按要求提交投标保证金的，其投标文件作否决投标处理。\n\n"
                      "基坑开挖深度3.5米以上的须编制专项方案，逾期送达的投标文件不予受理。")
        refs = {r.piece.text[:8]: r.piece.ref for r in td.rejections(doc)}
        self.assertEqual(refs["3.4.2投标人"], "第二章 3.4.2")
        self.assertEqual(refs["基坑开挖深度3."], "第二章 3.4.2", "3.5米 is a depth, not clause 3.5: the sentence stays under the clause before it")


class NoticeFormat(unittest.TestCase):
    """The national format of a government-procurement notice: fixed headings over labelled lines. Read as somebody
    talking, a real one gave 招标人 = "信息" (from 采购人信息) and 招标范围 = "内" (from 不在本次招标范围内)."""

    NOTICE = ("石门镇2027年排水设施养护项目公开招标公告\n\n项目概况\n\n石门镇2027年排水设施养护项目的潜在投标人应在市政府采购网获取招标文件，并于2027年3月18日 09:30（北京时间）前递交投标文件。\n\n"
              "一、项目基本情况\n\n项目编号：330482202703001-886\n\n项目名称：石门镇2027年排水设施养护项目\n\n预算金额（元）： 第1包3200000元,第2包2750000元\n\n"
              "最高限价（元）： 5800000.00元\n\n采购需求：零星维修之外的大修不在本次招标范围内。\n\n合同履约期限： 本项目服务期限为2年。\n\n本项目（ 否 ）接受联合体投标。\n\n"
              "二、申请人的资格要求：\n\n1.满足《中华人民共和国政府采购法》第二十二条规定；\n\n3.本项目的特定资格要求：具备市政公用工程施工总承包三级及以上资质。\n\n"
              "四、提交投标文件截止时间、开标时间和地点\n\n提交（上传）投标文件截止时间（开标时间）：2027年3月18日 09:30（北京时间）\n\n五、公告期限\n\n自本公告发布之日起5个工作日。\n\n"
              "七、对本次采购提出询问，请按以下方式联系\n\n1.采购人信息\n\n名 称：石门镇人民政府\n\n地 址：石门镇政通路1号\n\n2.采购代理机构信息\n\n名 称：嘉禾招标代理有限公司\n")

    def test_a_short_notice_in_the_national_format_is_a_document(self) -> None:
        self.assertTrue(td.is_document(self.NOTICE), "two thousand characters, no chapters - and still a form, not a request")
        facts = tf.extract(self.NOTICE)
        first = {topic: [m.value for m in facts.of(topic)] for topic in ("owner", "tender_no", "project", "price_cap", "duration", "consortium",
                                                                         "deadline_bid", "qualification", "scope")}
        self.assertEqual(first["owner"], ["石门镇人民政府"], "名 称 under 采购人信息 - not 信息, and not the agency's 名称")
        self.assertEqual(first["tender_no"], ["330482202703001-886"], "a number made of digits only")
        self.assertEqual(first["project"], ["石门镇2027年排水设施养护项目"])
        self.assertEqual(first["price_cap"], ["5800000.00元"])
        self.assertEqual(first["duration"], ["2年"])
        self.assertEqual(first["consortium"], ["否"])
        self.assertEqual(first["deadline_bid"], ["2027年3月18日 09:30"])
        self.assertEqual(first["qualification"], ["具备市政公用工程施工总承包三级及以上资质"])
        self.assertEqual(first["scope"], [], "不在本次招标范围内 says nothing about the scope")

    def test_one_figure_per_lot_is_shown_whole(self) -> None:
        budget = [m.value for m in tf.extract(self.NOTICE).of("budget")]
        self.assertEqual(budget, ["第1包3200000元,第2包2750000元"], "the first lot's figure alone would read as the total")


class JurisdictionToken(unittest.TestCase):
    def test_a_code_inside_a_document_number_is_not_a_code(self) -> None:
        from packing_assistant.jurisdiction import infer_jurisdiction

        self.assertEqual(infer_jurisdiction("招标编号：LJZB-2026-SG-0418，执行GB 50300-2013"), "CN", "SG is 施工")
        self.assertEqual(infer_jurisdiction("辖区：CN/SG"), "DUAL", "two codes side by side are two codes")
        self.assertEqual(infer_jurisdiction("写一份核算检查 2026-08\nSG"), "SG", "a code on the line after a date ($ matches before a final newline)")


if __name__ == "__main__":
    unittest.main(verbosity=1)
