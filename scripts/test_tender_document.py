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
        # who may bid at all: a consortium's bid would be thrown out, so the sentence stands among the rejection clauses
        self.assertIn("2.2 本次招标不接受联合体投标。", [r.piece.text for r in td.rejections(doc)])
        self.assertNotIn("2.2 本次招标不接受联合体投标。", [p.text for p in td.obligations(doc)], "and not twice")
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


REAL_SHAPED = """目 录

第一章 采购邀请........................................................ 1
第二章 供应商须知...................................................... 5
第三章 评审办法（综合评分法）.......................................... 19
第四章 合同条款及格式.................................................. 38
第五章 技术标准和要求.................................................. 96

第一章 采购邀请

东湖泵站电气改造项目竞争性磋商公告

四、响应文件提交

截止时间：2028 年 6 月 12 日 09 点 30 分（北京时间）

地点：东湖市公共资源交易中心三层第二开标室

五、开启

时间：2028 年 6 月 12 日 09 点 30 分（北京时间）

地点：东湖市公共资源交易中心三层第二开标室

本项目（ 否 ）接受联合体投标。

第二章 供应商须知

供应商须知前附表

| 条款号 | 条款名称 | 编列内容 |
| --- | --- | --- |
| 1.1.2 | 采购人 | 名称：东湖市排水管理处；地址：东湖市环湖路18号 |
| 1.1.4 | 项目名称 | 东湖泵站电气改造项目 |
| 1.3.3 | 质量要求 | 日常维护执行国家及本文件规定的标准；专项验收的质量评定：达到行业规范规定的合格等级 |
| 1.4.1 | 供应商资格要求 | 1.满足《中华人民共和国政府采购法》第二十二条规定；2.落实政府采购政策需满足的资格要求：■本项目不专门面向中小企业预留采购份额；□本项目专门面向中小企业采购；3.3.1 具备机电工程施工总承包叁级及以上资质；3.3.2 拟派项目经理资格条件：具备机电工程专业贰级注册建造师执业资格；3.3.3 对列入失信被执行人名单的供应商，将拒绝其参与本次采购活动 |
| 1.4.2 | 是否接受联合体 | ■不接受；□接受 |
| 1.11 | 分包 | □不允许；☑允许，允许分包的专项工程：自控系统；对分包人的资格要求：具备电子与智能化工程专业承包贰级资质 |
| 3.3.1 | 响应文件有效期 | 90 天 |
| 3.4.1 | 磋商保证金 | 本项目不适用 |
| 3.6 | 是否允许提交备选投标/响应方案 | ■不允许；□允许 |
| 4.1.2 | 封套上写明 | 采购人名称：（填写采购人名称）；采购人地址：（填写采购人地址） |
| 5.1 | 开标形式和开标时间、地点 | 开标形式：线下开标；第一个信封（商务及技术文件）开标时间：同递交截止时间；第一个信封（商务及技术文件）开标地点：三层第二开标室。第二个信封（报价文件）开标时间：2028年6月13日10时00分 |

1. 总则

1.4.3 供应商不得存在下列情形之一：

（1）为采购人不具有独立法人资格的附属机构；

（2）被责令停业的。

2.1 磋商文件的组成

本磋商文件包括：（1）采购邀请；（2）供应商须知；（3）评审办法。

3.1.1 响应文件应包括下列内容：（1）响应函；（2）法定代表人身份证明；（3）施工组织设计。

3.3.2 供应商拒绝延长的，其响应失效，但有权收回其磋商保证金。

3.4.4 有下列情形之一的，磋商保证金将不予退还：

（1）供应商在规定的响应有效期内撤销或修改其响应文件；

报价修正应当符合第五章“技术标准和要求”中的有关规定，此修改须符合本章第 4.3 款的要求。

第三章 评审办法（综合评分法）

| 评审因素 | 评审标准 |
| --- | --- |
| 形式评审标准 | 供应商名称 | 与营业执照、资质证书一致 |
| 形式评审标准 | 响应函签字盖章 | 符合第六章的要求 |
| 资格评审标准 | （1）供应商具备有效的营业执照。（2）供应商的资质等级符合磋商文件规定。（3）供应商的信誉符合磋商文件规定。 |

| 评分因素 | 分值分配 |
| --- | --- |
| 技术部分 | 45 分 |
| 商务部分 | 25 分 |

| 评分项目 | 评分标准 | 分值 |
| --- | --- | --- |
| 工程业绩 | 有 1 项类似业绩得 2 分，满分 10 分 | 10 |

| 条款号 | 评分因素与评分标准 |
| --- | --- |
| 2.2.4（2） | 主要人员 | 5分 | 满足最低要求得3分 | 3-5分 |

第四章 合同条款及格式

某市泵站运行考核办法

第一章 总则

第二章 月度考核

| 考核项目 | 分值 |
| --- | --- |
| 设备完好率 | 30分 |

合同文件的组成：（1）合同协议书；（2）中标通知书。

第五章 技术标准和要求

12.6 材料不符合合同约定的，监理人可拒收此类材料。

投标报价不得包含本章未列明的设备，否则按无效响应处理。
""" + "\n\n" + FILLER


class RealShaped(unittest.TestCase):
    """One test per family of thing that went wrong when two real tenders (165 and 751 pages) were read for the first
    time - on a made-up document that has the same shapes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = td.read(REAL_SHAPED)
        cls.facts = tf.extract(REAL_SHAPED)

    def values(self, topic: str) -> list:
        return [m.value for m in self.facts.of(topic) if m.side == "tender"]

    def test_the_contents_page_a_cross_reference_and_a_bound_in_regulation_make_no_chapters(self) -> None:
        chapters = []
        for p in self.doc.pieces:
            if p.chapter and p.chapter not in chapters:
                chapters.append(p.chapter)
        self.assertEqual(chapters, ["第一章 采购邀请", "第二章 供应商须知", "第三章 评审办法（综合评分法）", "第四章 合同条款及格式", "第五章 技术标准和要求"])
        self.assertFalse(any("....." in p.text for p in self.doc.pieces), "a line of the contents page lays nothing down")

    def test_tick_boxes_lay_down_what_is_ticked(self) -> None:
        self.assertEqual(self.values("consortium"), ["不接受"], "and 否 in the notice is the same answer, not a contradiction")
        self.assertEqual(self.values("subcontract"), ["允许，允许分包的专项工程：自控系统"], "□不允许 was NOT chosen")
        self.assertEqual(self.values("alternative"), ["不允许"], "是否允许提交备选投标/响应方案 is the 备选投标方案 row")

    def test_what_is_not_a_value_is_not_shown_as_one(self) -> None:
        self.assertEqual(self.values("owner"), ["东湖市排水管理处"], "（填写采购人名称） on the envelope row is a blank to fill in")
        self.assertFalse(any("电子与智能化" in v for v in self.values("qualification")), "对分包人的资格要求 is not the bidder's")
        self.assertFalse(any("专门面向" in v for v in self.values("qualification")), "a policy note names no qualification")
        self.assertTrue(any("机电工程施工总承包叁级" in v for v in self.values("qualification")))
        self.assertTrue(any("贰级注册建造师" in v for v in self.values("pm")), "拟派项目经理资格条件 is about the 项目经理")

    def test_no_amount_is_still_what_is_laid_down(self) -> None:
        self.assertEqual(self.values("bond"), ["本项目不适用"])

    def test_a_part_whose_label_names_the_rows_own_field_is_kept(self) -> None:
        self.assertTrue(any("合格等级" in v for v in self.values("quality")))

    def test_the_notice_format_labels_under_their_headings(self) -> None:
        self.assertEqual(self.values("deadline_bid"), ["2028 年 6 月 12 日 09 点 30 分"])
        self.assertIn("东湖市公共资源交易中心三层第二开标室", self.values("submit_place"))

    def test_two_envelopes_two_opening_times_told_apart(self) -> None:
        opens = {m.role: m.value for m in self.facts.of("deadline_open") if m.side == "tender" and m.ref and "前附表" in m.ref}
        self.assertEqual(opens, {"第一个信封（商务及技术文件）": "同递交截止时间", "第二个信封（报价文件）": "2028年6月13日10时00分"})
        self.assertFalse(any("不一致" in (m.origin or "") for m in self.facts.of("deadline_open")), "同…截止时间 IS the notice's date")

    def test_rejections_are_about_the_bid(self) -> None:
        listed = [r.piece.text for r in td.rejections(self.doc)]
        for wanted in ("将拒绝其参与本次采购活动", "其响应失效", "供应商不得存在下列情形之一", "否则按无效响应处理"):
            self.assertTrue(any(wanted in text for text in listed), wanted)
        self.assertFalse(any("拒收此类材料" in text for text in listed), "the technical chapter rejects a delivery, not a tender")
        self.assertFalse(any("拒收此类材料" in p.text for p in td.rejection_candidates(self.doc)))

    def test_review_standards_a_row_each_or_a_numbered_list_in_one_cell(self) -> None:
        found = [(group, factor, standard) for group, factor, standard, _ in td.review_standards(self.doc)]
        self.assertIn(("形式评审标准", "供应商名称", "与营业执照、资质证书一致"), found)
        self.assertEqual([s for g, _, s in found if g == "资格评审标准"],
                         ["（1）供应商具备有效的营业执照。", "（2）供应商的资质等级符合磋商文件规定。", "（3）供应商的信誉符合磋商文件规定。"])

    def test_scores_come_from_the_evaluation_chapter_and_are_named_by_the_cell_before_the_rule(self) -> None:
        found = {name: value for name, value, _ in td.scores(self.doc)}
        self.assertEqual(found, {"技术部分": "45 分", "商务部分": "25 分", "工程业绩": "10分", "主要人员": "5分"},
                         "not 设备完好率 (the contract scores the contractor's performance), not the sentence that says how points are won")

    def test_forms_are_what_the_bid_must_hold(self) -> None:
        self.assertEqual([name for name, _ in td.forms(self.doc)], ["响应函", "法定代表人身份证明", "施工组织设计"],
                         "not 磋商文件的组成 (the buyer's), not 合同文件的组成, not the list of 3.4.4")

    def test_the_table_of_a_document_holds_no_keyword_lines(self) -> None:
        from packing_assistant.tools.tender_tables import extract_table

        table = extract_table(parse_tender_text(REAL_SHAPED))
        self.assertNotRegex(table, r"\| 评分点 L\d+|\| 专项 L\d+", "a line that merely holds 分 or 专项 is no scoring point of a document")
        self.assertIn("## 10A 初步评审标准（逐项）", table)
        self.assertIn("| 开标·第二个信封（报价文件） | 2028年6月13日10时00分 |", table)


NEGOTIATION = """青石中学

实验楼屋面防水翻修项目

竞争性谈判文件

项目编号：青中-2711

采 购 人：青石中学

第一章 竞争性谈判公告

一、项目基本情况

1.项目编号：青中-2711

2.项目名称：青石中学实验楼屋面防水翻修项目

4.预算金额：318000.00 元，最高限价：318000 元

5.3 工期：45 日历天。

6.本项目（不允许）接受联合体投标。

二、申请人的资格要求：

1.满足《中华人民共和国政府采购法》第二十二条规定；

2.3 供应商具有行政主管部门核发的防水防腐保温工程专业承包贰级及以上资质，并具有有效的安全生产许可证；

2.4 供应商拟派项目经理具有建筑工程专业贰级及以上注册建造师资格证书。

三、获取谈判文件

1.时间：2029 年 03 月 02 日至 2029 年 03 月 06 日。

四、响应文件提交

1.截止时间：2029-03-12 10:00:00（北京时间）

五、响应文件开启

1.开启时间：2029-03-12 10:00:00（北京时间）

八、凡对本次采购提出询问，请按以下方式联系。

1.采购人信息

名    称：青石中学 地    址：青石市学苑路 9 号

第二章 供应商须知

| 序号 | 项目 | 内容 |
| --- | --- | --- |
| 1 | 采购人 | 名称：青石中学；地址：青石市学苑路 9 号 |
| 5 | 资质要求 | 同谈判公告 |
| 8 | 工期 | 45 日历天。 |
| 10 | 质量保修期 | 工程验收合格后防水工程 5 年，其他工程 2 年。 |
| 11 | 服务完成期限 | 自合同签订之日起，于当年11 月之前完成全部工作。 |
| 15 | 谈判保证金 | 谈判保证金金额：6000元，人民币陆仟元整；保证金形式：银行转账 |
| 16 | 谈判有效期 | 自首次响应文件提交截止时间起 60 日历日 |
| 18 | 响应文件装订要求 | 响应文件的正本与副本应分别装订成册，并编制目录。左侧胶装，不得采用活页装订。 |
| 28 | 履约担保 | 1、履约保证金为成交价的 5%。2、投标最高限价 318000元，超过的为无效响应。 |
| 29 | 项目负责人的资格要求 | 同谈判公告 |

附表：校内施工时段表

| 序号 | 时段 | 说明 |
| --- | --- | --- |
| 1 | 周末 | 全天可施工 |

1. 总则

1.1 适用范围：本谈判文件仅适用于本项目。

第三章 评审方法

评审方法：最低评标价法

1.资格评审

| 序号 | 评审因素 | 评审标准 |
| --- | --- | --- |
| 1 | 资格证明文件 | 符合第二章“供应商须知”第 24 条规定。 |

2.形式评审

| 序号 | 评审因素 | 评审标准 |
| --- | --- | --- |
| 1 | 供应商名称 | 与营业执照一致。 |

| 评分项目 | 分值区间 | 评分办法 |
| --- | --- | --- |
| 需求理解 | 0~20 | 根据理解的准确性酌情打分。 |

| 条款号 | 评分因素与评分标准 |
| --- | --- |
| 2.2.4（1） | 施工组织设计 | 28.0分 | 总体施工布置及规划 | 4.0分 | 优得2-4分，差得0-1分。 |

第四章 合同条款及格式

合同条款略。
""" + "\n\n" + FILLER

TWO_COLUMN = """第一章 竞争性磋商公告

项目名称：河湾街道居民满意度调查服务项目

第二章 响应方须知

前附表

| 序号 | 内容及要求 |
| --- | --- |
| 1 | 项目名称及数量：详见《竞争性磋商采购公告》 |
| 6 | 投标保证金金额：12,000 元；开户银行：河湾农商银行 |
| 9 | 转包与分包：否；联合投标：不允许。 |
| 17 | 磋商响应文件有效期为 90 天 |

一、总 则

（一）适用范围：仅适用于本次磋商。

第三章 评审办法及评审标准

综合评分法

第四章 合同条款

""" + FILLER + "\n\n" + FILLER.replace("承包人", "成交供应商")


class HeldOutShapes(unittest.TestCase):
    """What four real tenders nobody had fitted a rule to showed on their first run: three of them had a front table
    the reader did not know for one, none had its review standards listed, and the notice's lines held more than one
    label each. Made-up documents of the same shapes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = td.read(NEGOTIATION)
        cls.facts = tf.extract(NEGOTIATION)

    def values(self, topic: str, facts=None) -> list:
        return [m.value for m in (facts or self.facts).of(topic) if m.side == "tender"]

    def test_the_table_a_instructions_chapter_opens_with_is_its_front_table_whatever_its_columns_are_called(self) -> None:
        rows = td.front_rows(self.doc)
        self.assertEqual([r.number for r in rows if "评标办法" not in r.piece.table], ["1", "5", "8", "10", "11", "15", "16", "18", "28", "29"],
                         "序号 | 项目 | 内容 - and not the appendix table behind it, headed the same way")
        self.assertEqual(self.values("validity"), ["60 日历日"])

    def test_a_front_table_of_two_columns_names_its_rows_in_the_cell(self) -> None:
        facts = tf.extract(TWO_COLUMN)
        self.assertEqual(self.values("bond", facts), ["12,000 元"])
        self.assertEqual(self.values("validity", facts), ["90 天"], "磋商响应文件有效期为 90 天 - no colon at all")
        self.assertEqual(self.values("subcontract", facts), ["否"])
        self.assertEqual(self.values("eval_method", facts), ["综合评分法"])
        self.assertEqual(self.values("project", facts), ["河湾街道居民满意度调查服务项目"], "详见《竞争性磋商采购公告》 lays no name down")

    def test_see_the_notice_is_no_value_and_the_notice_is_read(self) -> None:
        self.assertTrue(all("同谈判公告" not in v for v in self.values("qualification") + self.values("pm")))
        self.assertTrue(any("防水防腐保温工程专业承包贰级及以上资质" in v for v in self.values("qualification")), "a sentence under 申请人的资格要求：")
        self.assertTrue(any("贰级及以上注册建造师" in v for v in self.values("pm")), "项目负责人的资格要求 is about the 项目经理, not the bidder's 资质")

    def test_one_notice_line_holds_several_labels(self) -> None:
        self.assertEqual(self.values("budget"), ["318000.00 元"])
        self.assertEqual({v.replace(" ", "") for v in self.values("price_cap")}, {"318000元"}, "the notice's and the row's are one value")
        self.assertEqual(self.values("owner"), ["青石中学"], "名    称：青石中学 地    址：… - spaced out, and the address is not the name")
        self.assertEqual(self.values("tender_no"), ["青中-2711"], "a number with Chinese in it, once (the cover says the same)")
        self.assertEqual(self.values("consortium"), ["不允许"])

    def test_clock_seconds_a_date_to_finish_by_and_two_periods(self) -> None:
        self.assertEqual(self.values("deadline_bid"), ["2029-03-12 10:00:00"])
        self.assertEqual(self.values("deadline_open"), ["2029-03-12 10:00:00"], "开启时间")
        self.assertTrue(any("防水工程 5 年，其他工程 2 年" in v for v in self.values("warranty")), "the first period alone would mislead")
        self.assertTrue(all(v != "11 月" for v in self.values("duration")), "于当年11 月之前完成 is no duration of eleven months")

    def test_a_part_that_holds_the_rows_own_name_is_the_rows_field(self) -> None:
        self.assertEqual(self.values("bond"), ["6000元"], "谈判保证金金额：… under 谈判保证金")
        self.assertTrue(any("左侧胶装" in v for v in self.values("binding")), "how a bid is bound is the whole cell")

    def test_the_cap_inside_another_row_and_the_method_the_chapter_names(self) -> None:
        self.assertIn("318000元", [v.replace(" ", "") for v in self.values("price_cap")])
        self.assertEqual(self.values("eval_method"), ["最低评标价法"])

    def test_review_standards_under_a_heading_and_scores_of_every_shape(self) -> None:
        found = [(group, factor) for group, factor, _, _ in td.review_standards(self.doc)]
        self.assertEqual(found, [("资格评审", "资格证明文件"), ("形式评审", "供应商名称")])
        scores = {name: value for name, value, _ in td.scores(self.doc)}
        self.assertEqual(scores, {"需求理解": "0~20分", "施工组织设计": "28.0分", "总体施工布置及规划": "4.0分"})

    def test_rejections_of_the_new_wordings(self) -> None:
        # in the instructions chapter - behind the contract chapter they would be the contract's, and left out
        more = NEGOTIATION.replace("1.1 适用范围：", "14.2 采购人拒绝接受通过电子交易平台以外任何形式提交的响应文件。\n\n3.5 本项目不接受联合体响应。\n\n1.1 适用范围：")
        listed = [r.piece.text for r in td.rejections(td.read(more))]
        self.assertTrue(any("拒绝接受" in t for t in listed) and any("不接受联合体响应" in t for t in listed))


PARTS = """栖霞学院实训楼配电改造工程

竞争性磋商文件

第一部分  采购公告

第二部分  竞争性磋商前附表

第三部分  磋商人须知

第四部分  响应文件格式

第五部分  合同条款格式

第六部分  评审标准和方法

第一部分  采购公告

一、项目基本情况

项目编号：栖院-2806

预算金额：86(万元)

本项目不接受联合体报名。

三、递交投标登记文件

时间：2030年3月4日至2030年3月6日

地点：栖霞市文汇路 12 号青桐招标有限公司

四、磋商文件发售

时间：另行通知

第二部分  竞争性磋商前附表

| 项号 | 内容 | 说明及要求 |
| --- | --- | --- |
| 1 | 项目名称 | 栖霞学院实训楼配电改造工程 |
| 8 | 响应文件份数及装订要求 | 正本壹份，副本叁份，电子版 1 份，同时密封于一个包封内。 |
| 9 | 磋商有效期 | 为90日历天（从磋商截止之日算起） |
| 12 | 现场踏勘 | □√不组织；□组织，踏勘时间：踏勘集中地点： |
| 15 | 响应文件提交地点及截止时间 | 提交地点：栖霞市文汇路 12 号青桐招标有限公司会议室；截止时间：2030年3月18日14时00分 |
| 17 | 评审标准和方法 | 详见本磋商文件第六部分 |
| 21 | 是否允许磋商人分包 | 否 |
| 33 | 预付款保证金 | 成交供应商在签订合同后 / 个工作日内提供 / %的预付款保函。 |

第三部分  磋商人须知

1. 总则

1.1 适用范围：本磋商文件仅适用于本项目。

5.4 经磋商提交最后报价的磋商人，由磋商小组采用综合评分法对其响应文件进行综合评分。

5.5 磋商人试图对评审施加影响，都可能导致其磋商被拒绝。

5.6 如未提供，磋商小组有权拒绝其响应文件。

5.7 供应商如提交备选方案，响应文件将被判定为无效。

第四部分  响应文件格式

一、磋商函

资格审查必要合格条件标准

| 序号 | 项目内容 | 合格条件 | 备注 | 是否合格及相关情况 |
| --- | --- | --- | --- | --- |
| 1 | 营业执照 | 具有独立承担民事责任的能力 | 复印件盖公章 |  |
| 2 | 资质证书 | 具有电力工程施工总承包叁级及以上资质 | 复印件盖公章 |  |
| 结论 | 是否通过 |

符合性评审表

| 序号 | 评审内容 | 是否满足要求 |
| --- | --- | --- |
| 1 | 磋商人名称是否与营业执照一致 |  |
| 2 | 磋商保证金是否按磋商文件要求缴纳 |  |
| 结论 | 是否通过 |

综合评分法评分标准

| 序号 | 项目 | 评分标准 |
| --- | --- | --- |
| 1 | 报价（60分） | 满足磋商文件要求且最终报价最低的为磋商基准价，其价格分为满分。 |
| 2 | 施工方案及技术措施（10分） | 针对性很强的得10分；较强的得7分；一般的得3分。 |
| 3 | 资信（7 分） | 进货渠道（3 分）售后网点（4 分） | 提供证明材料。 |
| 4 | 施工组织设计（20分） | 主要施工方案与技术措 | 施工方案（含工程特点） |
|  |  | 施；（0-4 分） | 总体安排合理。2＜得分≤4 |
|  |  | 服务承诺（0-6 分） | 优（5-6分）；良（3-4分）；一般（0-2分） |

第一部分  合同协议书            编号：

第五部分 技术标准和要求专用部分

""" + FILLER


class SecondRoundShapes(unittest.TestCase):
    """The second round of real tenders nobody had fitted a rule to (first run: fields 52/70, scores 1/40): a tender in
    部分 whose contents page has no leaders and whose last parts are headed only there, points written inside the name
    cell, review tables headed otherwise, a row named for two things. Made-up documents of the same shapes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = td.read(PARTS)
        cls.facts = tf.extract(PARTS)

    def values(self, topic: str) -> list:
        return [m.value for m in self.facts.of(topic) if m.side == "tender"]

    def test_parts_are_chapters_and_a_contents_page_without_leaders_lays_nothing_down(self) -> None:
        chapters = []
        for p in self.doc.pieces:
            if p.chapter and p.chapter not in chapters:
                chapters.append(p.chapter)
        self.assertEqual(chapters, ["第一部分 采购公告", "第二部分 竞争性磋商前附表", "第三部分 磋商人须知", "第四部分 响应文件格式"],
                         "not the two parts only the contents page heads, not the contract's own 第五部分")
        self.assertEqual(self.values("project"), ["栖霞学院实训楼配电改造工程"])

    def test_a_row_named_for_two_things_gives_both_and_registering_is_not_handing_in(self) -> None:
        self.assertEqual(self.values("deadline_bid"), ["2030年3月18日14时00分"])
        self.assertEqual(self.values("submit_place"), ["栖霞市文汇路 12 号青桐招标有限公司会议室"], "not the address under 三、递交投标登记文件")

    def test_row_names_and_values_of_the_second_round(self) -> None:
        self.assertTrue(any("副本叁份" in v for v in self.values("copies")), "响应文件份数及装订要求 - the whole cell")
        self.assertEqual(self.values("subcontract"), ["否"], "是否允许磋商人分包")
        self.assertEqual(self.values("deadline_visit"), ["不组织"], "the ticked box, and no date is what is laid down")
        self.assertEqual(self.values("bond"), [], "预付款保证金 is the contract's guarantee")
        self.assertEqual(self.values("budget"), ["86(万元)"])
        self.assertEqual(self.values("consortium"), ["不接受联合体报名"])
        self.assertEqual(self.values("eval_method"), ["综合评分法"], "no heading names it: what the document says it uses")

    def test_the_copies_statement_under_a_row_called_otherwise(self) -> None:
        other = PARTS.replace("| 8 | 响应文件份数及装订要求 | 正本壹份，副本叁份，电子版 1 份，同时密封于一个包封内。 |",
                              "| 8 | 响应文件组成和封装 | 1）正本1 份；副本2份。副本为正本的复印件。2）响应文件装订成册。 |")
        self.assertEqual([m.value for m in tf.extract(other).of("copies")], ["正本1 份；副本2份"])

    def test_a_one_cell_row_is_named_by_how_it_begins(self) -> None:
        text = TWO_COLUMN.replace("| 17 | 磋商响应文件有效期为 90 天 |", "| 17 | 磋商响应文件有效期为 90 天 |\n| 18 | 在成交通知书发出前，采购人将成交候选人的信息予以公示。 |")
        facts = tf.extract(text)
        self.assertEqual([m.value for m in facts.of("owner")], [], "采购人 after the first clause: the cell is about the notice of award")
        self.assertEqual([m.value for m in facts.of("validity")], ["90 天"])

    def test_points_inside_the_name_cell(self) -> None:
        scores = {name: value for name, value, _ in td.scores(self.doc)}
        self.assertEqual(scores, {"报价": "60分", "施工方案及技术措施": "10分", "资信": "7分", "进货渠道": "3分", "售后网点": "4分",
                                  "施工组织设计": "20分", "主要施工方案与技术措施": "0-4分", "服务承诺": "0-6分"},
                         "known by the table's own header (no chapter says 评审); two items run into one cell; a name the page cut; "
                         "a grade's band is no item")

    def test_review_tables_headed_otherwise(self) -> None:
        found = [(group, factor, standard) for group, factor, standard, _ in td.review_standards(self.doc)]
        self.assertEqual(found, [("资格审查必要合格条件标准", "营业执照", "具有独立承担民事责任的能力"),
                                 ("资格审查必要合格条件标准", "资质证书", "具有电力工程施工总承包叁级及以上资质"),
                                 ("符合性评审表", "", "磋商人名称是否与营业执照一致"),
                                 ("符合性评审表", "", "磋商保证金是否按磋商文件要求缴纳")])

    def test_the_clause_that_lists_the_tenders_chapters_heads_none(self) -> None:
        text = ("第一章 招标公告\n\n项目名称：临溪镇文化站修缮工程\n\n第二章 投标人须知\n\n1. 总则\n\n1.1 适用范围：仅适用于本项目。\n\n2.1 招标文件包括：\n\n"
                "第一章 招标公告\n\n第二章 投标人须知\n\n第三章 评标办法\n\n第四章 合同条款及格式\n\n"
                "2.2 投标人不按要求提交投标保证金的，其投标将被否决。\n\n第三章 评标办法\n\n综合评估法\n\n第四章 合同条款及格式\n\n" + FILLER)
        doc = td.read(text)
        clause = next(p for p in doc.pieces if "其投标将被否决" in p.text)
        self.assertEqual(clause.chapter, "第二章 投标人须知", "read as headings, the listing made this clause 第四章's")
        self.assertEqual([p.text for p in doc.pieces if p.kind == "heading" and p.text.startswith("第")],
                         ["第一章 招标公告", "第二章 投标人须知", "第三章 评标办法", "第四章 合同条款及格式"])

    def test_the_next_clause_is_no_list_item_and_cancelling_the_procurement_throws_no_bid_out(self) -> None:
        more = PARTS.replace("5.5 磋商人试图", "4.2 磋商人不得存在下列情形之一：\n\n（1）为本项目提供过设计服务的；\n\n4.3 本次磋商是否允许联合体，详见前附表。\n\n"
                             "28.1 出现下列情形之一的，应对采购项目予以废标：\n\n（1）有效供应商不足三家的；\n\n28.2 废标后，采购代理机构应当发布公告。\n\n"
                             "★附件 1：\n\n磋商函\n\n5.5 磋商人试图")
        listed = [r.piece.text for r in td.rejections(td.read(more))]
        self.assertIn("（1）为本项目提供过设计服务的；", listed)
        self.assertFalse(any("4.3 本次磋商" in t for t in listed), "4.3 is the next clause, not item 4. of the list under 4.2")
        self.assertFalse(any("废标" in t or "不足三家" in t for t in listed), "the procurement is cancelled; no bid is thrown out")
        self.assertIn("★附件 1：磋商函", listed, "a starred label takes the title on the next line")

    def test_the_lot_this_document_is_for_is_read_off_its_cover(self) -> None:
        text = ("使用说明\n\n一、本标准文件适用于公路养护项目，各标段分别编制招标文件。\n\n临溪县农村公路日常养护（一、二、三标段）\n\n（项目名称）养护二标段施工招标\n\n招标文件\n\n"
                "第一章 招标公告\n\n1. 招标条件\n\n1.1 本项目共划分 3 个标段，一标段为北线，二标段为南线，三标段为环线。\n\n"
                "第二章 投标人须知\n\n| 条款号 | 条款名称 | 编列内容 |\n| --- | --- | --- |\n| 1.3.2 | 计划工期 | 一标段：300日历天；二标段：365日历天 |\n\n"
                "1. 总则\n\n1.1 适用范围：仅适用于本项目。\n\n第三章 评标办法\n\n综合评估法\n\n第四章 合同条款及格式\n\n" + FILLER + "\n\n" + FILLER.replace("承包人", "中标人"))
        doc = td.read(text)
        lot, piece = td.document_lot(doc)
        self.assertEqual((lot, piece.text), ("二标段", "（项目名称）养护二标段施工招标"), "not 三标段 out of 一、二、三标段, not the sentence that splits the project")
        from packing_assistant.tools import tender_tables
        table = tender_tables.extract_table(parse_tender_text(text), project_name="x")
        self.assertRegex(table, r"\| 本文件所属标段 \| 二标段 \|")
        self.assertRegex(table, r"\| 工期（一标段） \| 300日历天 \|[^\n]*其他标段的值（本文件为二标段）")
        self.assertNotRegex(table, r"\| 工期（二标段） \|[^\n]*其他标段")
        self.assertIsNone(td.document_lot(td.read("第一章 招标公告\n\n1.本次招标共 1 包：\n\n第二章 投标人须知\n\n" + FILLER)), "how many there are names none")

    def test_a_correction_notice_as_a_table_as_a_block_and_what_it_leaves_to_an_attachment(self) -> None:
        tender = ("### 招标文件.docx\n\n第一章 招标公告\n\n项目名称：临溪镇文化站修缮工程\n\n第二章 投标人须知\n\n| 条款号 | 条款名称 | 编列内容 |\n| --- | --- | --- |\n"
                  "| 3.3.1 | 投标有效期 | 90日历天 |\n| 3.4.1 | 投标保证金 | 金额：8万元；形式：银行转账 |\n| 4.2.1 | 递交投标文件截止时间 | 2030年5月6日9时30分 |\n\n"
                  "1. 总则\n\n1.1 适用范围：仅适用于本项目。\n\n第三章 评标办法\n\n综合评估法\n\n第四章 合同条款及格式\n\n" + FILLER + "\n\n" + FILLER.replace("承包人", "中标人"))
        notice = ("\n\n### 更正公告第1号.docx\n\n更正公告\n\n| 序号 | 原招标文件内容 | 修改后内容 |\n| --- | --- | --- |\n"
                  "| 1 | 第二章前附表 3.3.1 投标有效期：90日历天 | 投标有效期：120日历天 |\n| 2 | 3.4.1 投标保证金金额：8万元 | 3.4.1 投标保证金金额：6万元 |\n\n"
                  "原文：4.2.1 递交投标文件截止时间 2030年5月6日9时30分\n\n现修改为：4.2.1 递交投标文件截止时间 2030年5月13日9时30分\n\n"
                  "工程量清单有调整，详见附件 2。\n\n第五章“工程量清单”整体替换，以重新上传的文件为准。\n")
        facts = tf.extract(tender + notice)

        def changed(topic: str) -> list:
            return [m.value for m in facts.of(topic) if m.origin]

        self.assertEqual(changed("validity"), ["120日历天"], "序号 | 原招标文件内容 | 修改后内容")
        self.assertEqual(changed("bond"), ["6万元"])
        self.assertEqual(changed("deadline_bid"), ["2030年5月13日9时30分"], "现修改为：4.2.1 … - the field is named after the verb")
        self.assertEqual([c["text"] for c in facts.addenda_unread], ["工程量清单有调整，详见附件 2。", "第五章“工程量清单”整体替换，以重新上传的文件为准。"])
        from packing_assistant.tools import tender_tables
        table = tender_tables.extract_table(parse_tender_text(tender + notice), project_name="x")
        self.assertRegex(table, r"\| 补遗里没读出的改动 1 \| 工程量清单有调整，详见附件 2。 \|[^\n]*未读出")
        self.assertRegex(table, r"\| 投标有效期 \| 90日历天 \|[^\n]*已被更正公告第1号修改")

    def test_rejections_of_the_second_round_wordings(self) -> None:
        listed = [r.piece.text for r in td.rejections(self.doc)]
        for words in ("导致其磋商被拒绝", "有权拒绝其响应文件", "将被判定为无效"):
            self.assertTrue(any(words in t for t in listed), words)


if __name__ == "__main__":
    unittest.main(verbosity=1)
