#!/usr/bin/env python3
"""What someone typed about a tender: whose number, which lot, which field - and what the parser makes of it.

Each case here is a behaviour that was reproduced failing before packing_assistant/tools/tender_facts.py
existed: the bidder's own 999 日历天 reported as the tender's duration when it was mentioned first, the
second lot's numbers filed under the first, the second scoring point on a line dropped because two
clauses shared one id, a 补遗 ignored, "须提供财务报表" at risk of being read as our side speaking.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools import tender_facts as tf  # noqa: E402
from packing_assistant.tools.tender_parse import parse_tender_text  # noqa: E402


def found(facts: tf.TenderFacts, topic: str, side: str, lot: str = "") -> list[str]:
    return [m.value for m in facts.of(topic, side=side, lot=lot)]


class WhoseNumber(unittest.TestCase):
    def test_a_number_is_the_tenders_unless_our_side_speaks_before_it(self) -> None:
        facts = tf.extract("招标文件要求投标保证金85万、工期365日历天、投标有效期120天，我们投标函草稿工期写成了380日历天，保函还没开。")
        self.assertEqual(found(facts, "duration", "tender"), ["365日历天"])
        self.assertEqual(found(facts, "duration", "ours"), ["380日历天"])
        self.assertEqual(found(facts, "bond", "tender"), ["85万"])
        self.assertEqual(found(facts, "validity", "tender"), ["120天"])
        statement = facts.of("bond", side="ours")
        self.assertEqual([(m.value, m.note) for m in statement], [("", "保函还没开")])

    def test_our_number_mentioned_first_is_still_ours(self) -> None:
        facts = tf.extract("我们投标函草稿里工期先写了999日历天，经营部说不对，招标文件要求的工期是60日历天。")
        self.assertEqual(found(facts, "duration", "ours"), ["999日历天"])
        self.assertEqual(found(facts, "duration", "tender"), ["60日历天"])

    def test_one_clause_can_hold_the_requirement_and_what_we_did_about_it(self) -> None:
        facts = tf.extract("工期要求300天投标函照着写的，三标保证金68万保函已经开好了。")
        self.assertEqual(found(facts, "duration", "tender"), ["300天"])
        self.assertEqual([m.value for m in facts.of("duration", side="ours")], [""])
        self.assertEqual(found(facts, "bond", "tender"), ["68万"], "68万 belongs to 保证金 once, not again to 保函")

    def test_a_number_before_its_keyword(self) -> None:
        facts = tf.extract("保证金：要求75万银行保函，我方保函已开")
        self.assertEqual(found(facts, "bond", "tender"), ["75万"])

    def test_a_named_person_is_ours_and_a_grade_is_the_tenders(self) -> None:
        facts = tf.extract("项目经理：要求一级市政，拟派陈海峰\n技术负责人 周海燕\n责任人：商务部王丽娟")
        self.assertEqual(found(facts, "pm", "tender"), ["一级市政"])
        self.assertEqual(found(facts, "pm", "ours"), ["陈海峰"])
        self.assertEqual(found(facts, "tech_lead", "ours"), ["周海燕"])
        self.assertEqual(found(facts, "owner_person", "none"), ["王丽娟"], "商务部 is a department, not the name")

    def test_a_pronoun_keeps_speaking_of_our_man(self) -> None:
        facts = tf.extract("项目经理须具备一级注册建造师资格，我们拟派周建国，他是二级的。")
        self.assertEqual(found(facts, "pm", "tender"), ["一级注册建造师资格"])
        self.assertEqual([(m.value, m.note) for m in facts.of("pm", side="ours")], [("周建国", "我们拟派周建国"), ("", "他是二级的")])

    def test_price_cap_is_theirs_and_our_price_is_ours(self) -> None:
        facts = tf.extract("最高限价：3860万\n我方报价：3792.6万\n报价分 60分")
        self.assertEqual(found(facts, "price_cap", "tender"), ["3860万"])
        self.assertEqual(found(facts, "our_price", "ours"), ["3792.6万"])
        self.assertEqual([(s.name, s.score) for s in facts.scores], [("报价分", "60分")], "报价分 is a scoring point, not a price")


class WhichLot(unittest.TestCase):
    TEXT = ("一标保证金要45万，财务只转了38.5万说明天补，工期要求300天投标函照着写的。三标保证金68万保函已经开好了，"
            "但工期要求270天，我们施组里排的是285天。项目经理一标报的刘志强，三标还没定人。三标的缺口让赵倩跟，一标谁跟还没说。")

    def test_each_value_stays_with_its_lot(self) -> None:
        facts = tf.extract(self.TEXT)
        self.assertEqual(facts.lots, ["一标段", "三标段"])
        self.assertEqual(found(facts, "bond", "tender", "一标段"), ["45万"])
        self.assertEqual(found(facts, "bond", "ours", "一标段"), ["38.5万"], "a clause with no keyword continues the topic before it")
        self.assertEqual(found(facts, "bond", "tender", "三标段"), ["68万"])
        self.assertEqual(found(facts, "duration", "tender", "三标段"), ["270天"])
        self.assertEqual(found(facts, "duration", "ours", "三标段"), ["285天"])

    def test_a_lot_named_in_the_middle_of_a_clause(self) -> None:
        facts = tf.extract(self.TEXT)
        self.assertEqual(found(facts, "pm", "ours", "一标段"), ["刘志强"])
        self.assertEqual([m.note for m in facts.of("pm", side="ours", lot="三标段")], ["三标还没定人"])

    def test_who_follows_up_and_who_is_not_named_yet(self) -> None:
        facts = tf.extract(self.TEXT)
        self.assertEqual(found(facts, "owner_person", "none", "三标段"), ["赵倩"])
        open_one = facts.of("owner_person", lot="一标段")
        self.assertTrue(open_one and open_one[0].not_given and not open_one[0].value)

    def test_all_lots_resets_and_one_lot_alone_is_not_a_split(self) -> None:
        facts = tf.extract("一标段工期180日历天，限价2860万；二标段是泵站土建，工期270天，限价还没公布。两个标段投标截止都是2026-10-22。")
        self.assertEqual(found(facts, "deadline_bid", "tender", ""), ["2026-10-22"])
        self.assertEqual(facts.lot_scopes, {"二标段": "泵站土建"})
        absent = facts.of("price_cap", lot="二标段")
        self.assertTrue(absent and absent[0].not_given, "限价还没公布 is the tender not having given it, not us not having acted")
        single = tf.extract("滨江路雨污分流改造工程二标段，工期240日历天，投标保证金75万元。")
        self.assertEqual(single.lots, ["二标段"])
        self.assertEqual(found(single, "duration", "tender", ""), ["240日历天"])

    def test_二标段_is_a_lot_not_two_lots(self) -> None:
        facts = tf.extract("一标段工期180日历天；二标段工期270日历天。")
        self.assertEqual(found(facts, "duration", "tender", "二标段"), ["270日历天"])


class Fields(unittest.TestCase):
    def test_a_running_sentence(self) -> None:
        facts = tf.extract("帮我出一份招标解析表，滨江路雨污分流改造工程二标段，招标人是临港城建投资有限公司，工期240日历天，质量标准合格，"
                           "资质要求市政公用工程施工总承包二级及以上，最高限价3865.42万元，投标保证金75万元，投标截止2026-10-16上午9点半，"
                           "评标办法里施工组织设计占35分。")
        self.assertEqual(found(facts, "project", "tender"), ["滨江路雨污分流改造工程"])
        self.assertEqual(found(facts, "owner", "tender"), ["临港城建投资有限公司"])
        self.assertEqual(found(facts, "quality", "tender"), ["合格"])
        self.assertEqual(found(facts, "qualification", "tender"), ["市政公用工程施工总承包二级及以上"])
        self.assertEqual(found(facts, "deadline_bid", "tender"), ["2026-10-16上午9点半"])
        self.assertEqual(found(facts, "eval_method", "tender"), [], "评标办法里…占35分 names no method")
        self.assertEqual([(s.name, s.score) for s in facts.scores], [("施工组织设计", "35分")])

    def test_labelled_lines_of_every_kind(self) -> None:
        facts = tf.extract("项目名称：石桥镇中心小学教学综合楼新建工程\n招标人：石桥镇人民政府\n计划工期：420日历天\n"
                           "类似业绩：近5年单项合同额2000万元以上房建工程\n评标办法：综合评估法\n开标时间：2026-11-03 10:00\n"
                           "已有证据：同类学校业绩一项，合同和竣工验收备案表都在\n授权委托书：还没盖公章")
        self.assertEqual(found(facts, "owner", "tender"), ["石桥镇人民政府"])
        self.assertEqual(found(facts, "track_record", "tender"), ["近5年单项合同额2000万元以上房建工程"])
        self.assertEqual(found(facts, "eval_method", "tender"), ["综合评估法"])
        self.assertEqual(found(facts, "deadline_open", "tender"), ["2026-11-03 10:00"])
        self.assertEqual(found(facts, "evidence", "ours"), ["同类学校业绩一项", "合同和竣工验收备案表都在"],
                         "the label governs the line: 业绩 inside it is not a tender requirement")
        self.assertEqual([(m.side, m.note) for m in facts.of("poa")], [("ours", "授权委托书：还没盖公章")])

    def test_scoring_points_and_named_specials(self) -> None:
        facts = tf.extract("技术标评分：施工组织设计 25 分、项目管理机构 10 分。施工方案那块最重，占18.5分。\n"
                           "招标点名要编深基坑专项，挖深11.8米。\n点名专项：报告厅高支模，支模高度9.6m")
        self.assertEqual([(s.name, s.score) for s in facts.scores],
                         [("施工组织设计", "25分"), ("项目管理机构", "10分"), ("施工方案", "18.5分")])
        self.assertEqual([(s.name, s.detail) for s in facts.specials],
                         [("深基坑专项", "挖深11.8米"), ("报告厅高支模", "支模高度9.6m")])

    def test_structure_written_as_a_value(self) -> None:
        facts = tf.extract("总建筑面积38600平，地上十八层剪力墙结构，质量目标：市级优质结构")
        self.assertEqual(found(facts, "structure", "tender"), ["剪力墙结构"])
        self.assertEqual(found(facts, "area", "tender"), ["38600平"])
        self.assertEqual(found(facts, "quality", "tender"), ["市级优质结构"])

    def test_an_addendum_keeps_both_values_and_says_which_is_which(self) -> None:
        facts = tf.extract("招标正文写计划工期420日历天、投标保证金50万元；昨天发的补遗1号只把计划工期改成了450日历天，保证金和资质没提。")
        self.assertEqual([(m.value, m.origin) for m in facts.of("duration", side="tender")], [("420日历天", ""), ("450日历天", "补遗1号")])
        untouched = [m for m in facts.of("bond") if m.origin]
        self.assertTrue(untouched and untouched[0].not_given and not untouched[0].value)
        self.assertEqual(found(facts, "qualification", "tender"), [""], "没提 is not a qualification")

    def test_every_value_is_a_literal_stretch_of_the_text(self) -> None:
        for text in (WhichLot.TEXT, "招标文件要求投标保证金85万、工期365日历天，我们投标函草稿工期写成了380日历天，拟派周建国。"):
            facts = tf.extract(text)
            for mention in facts.mentions:
                self.assertIn(mention.value, text)
                self.assertIn(mention.note, text)

    def test_a_number_nobody_placed_is_returned_not_dropped(self) -> None:
        facts = tf.extract("现场离搅拌站大概12公里，工期240日历天。")
        self.assertEqual(facts.unplaced, ["现场离搅拌站大概12公里"])


class PastedDocument(unittest.TestCase):
    DOC = ("1. 投标人拟派项目经理须具备一级注册建造师资格，且未担任其他在建项目的项目经理。\n"
           "2. 投标人已经取得安全生产许可证的，须提供复印件并加盖公章。\n"
           "3. 投标人应当承诺按期完工，承诺工期不得超过365日历天。\n"
           "4. 投标保证金：人民币80万元，未按时到账的按否决投标处理。\n"
           "5. ★投标人须提供近三年经审计的财务报表。")

    def test_nothing_in_a_document_is_our_side(self) -> None:
        facts = tf.extract(self.DOC)
        self.assertEqual([m for m in facts.mentions if m.side == "ours"], [])
        self.assertEqual(found(facts, "pm", "tender"), ["一级注册建造师资格"])
        self.assertEqual(found(facts, "duration", "tender"), ["365日历天"])
        self.assertEqual(tf.split_sides(self.DOC)[1], "")
        self.assertEqual(facts.unplaced, [], "a clause number is not a number somebody failed to place")

    def test_the_parser_keeps_every_clause_of_a_document(self) -> None:
        parsed = parse_tender_text(self.DOC)
        quoted = "\n".join(str(r["exact_text"]) for r in parsed["requirements"])
        for needle in ("已经取得安全生产许可证", "财务报表", "一级注册建造师"):
            self.assertIn(needle, quoted)

    def test_a_keyword_at_the_end_of_a_requirement(self) -> None:
        facts = tf.extract("一、投标人须具备建筑工程施工总承包二级及以上资质。\n二、货物须铁架包装。")
        self.assertEqual(found(facts, "qualification", "tender"), ["建筑工程施工总承包二级及以上资质"])

    def test_declared_tender_text_is_never_split(self) -> None:
        text = "我们已经确认：投标人须在投标截止前缴纳保证金80万元。"
        self.assertEqual(tf.split_sides(text, sides="none"), (text, ""))
        self.assertEqual([m.side for m in tf.extract(text, sides="none").mentions], ["tender"])


class Parser(unittest.TestCase):
    def test_two_clauses_of_a_kind_on_one_line_are_two_requirements(self) -> None:
        parsed = parse_tender_text("施工组织设计评分35分。进度计划与保障措施评分12.5分。")
        ids = [r["id"] for r in parsed["requirements"] if r["item_kind"] == "scoring_point"]
        self.assertEqual(ids, ["score_L1", "score_L1_2"], "the first keeps the id it always had")
        self.assertEqual(len(parsed["handoff"]["scoring_points"]), 2)

    def test_whose_duration(self) -> None:
        cases = [
            ("我们投标函草稿里工期先写了999日历天，招标文件要求的工期是60日历天。", 60),
            ("招标文件要求工期60日历天，我们投标函写了999日历天。", 60),
            ("我们投标函写了999日历天，招标文件我还没看。", None),
            ("招标正文写计划工期420日历天；补遗1号只把计划工期改成了450日历天。", 450),
            ("一标段工期180日历天；二标段工期270日历天。", None),
            ("一标段工期180日历天；二标段工期180日历天。", 180),
            ("四、交货期 90 个日历天。", 90),
        ]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_tender_text(text)["duration_days"], want)

    def test_our_sentence_never_becomes_a_requirement(self) -> None:
        text = "招标文件要求工期60日历天、投标有效期90天，我们投标函写了999日历天，投标有效期写了60天。"
        parsed = parse_tender_text(text)
        for requirement in parsed["requirements"]:
            for quote in [requirement["exact_text"], *requirement["snippets"]]:
                self.assertIn(quote, text, "a requirement quotes the source literally")
                self.assertNotIn("999", quote)
                self.assertNotIn("写了60天", quote)

    def test_construction_clauses_without_a_star_are_requirements_now(self) -> None:
        parsed = parse_tender_text("项目经理须具备一级注册建造师资格。\n投标有效期90天。\n最高投标限价3865.42万元。\n"
                                   "质量标准：合格。\n缺陷责任期24个月。\n预付款为签约合同价的10%。")
        self.assertEqual([r["id"] for r in parsed["requirements"]],
                         ["bid_validity", "personnel", "price_cap", "quality_standard", "warranty", "payment"])
        p0 = {item["req_id"] for item in parsed["handoff"]["p0_reject_scan"]["items"]}
        self.assertTrue({"bid_validity", "personnel", "price_cap"} <= p0, "missing any of these gets a bid rejected")

    def test_facts_travel_with_the_parse(self) -> None:
        parsed = parse_tender_text("一标段工期180日历天；二标段工期270日历天。")
        self.assertEqual(parsed["facts"]["schema"], "tender.facts.v1")
        self.assertEqual(parsed["facts"]["lots"], ["一标段", "二标段"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
