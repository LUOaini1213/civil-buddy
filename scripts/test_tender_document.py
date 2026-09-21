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


if __name__ == "__main__":
    unittest.main(verbosity=1)
