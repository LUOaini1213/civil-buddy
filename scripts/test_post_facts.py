#!/usr/bin/env python3
"""post_facts: a request taken apart into literal pieces - and nothing that is not in it."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant import post_facts as pf  # noqa: E402

WAREHOUSE = {"inbound": ("入库", "进场", "到货"), "outbound": ("出库", "领用", "领料", "发料"),
             "variance": ("盘点差", "盘亏", "盘盈", "差异"), "counted": ("盘点", "实存")}


class Quantities(unittest.TestCase):
    def test_identifiers_dates_and_codes_are_not_quantities(self):
        text = "3#楼 HRB400 Φ20 C35 DN100 GB 50010 2026-09-18 9月18日 K3+200"
        self.assertEqual([q.text for q in pf.quantities(text)], [])

    def test_numbers_come_back_as_written(self):
        found = pf.quantities("入库 35 吨，单价1,200元，盘点差0.3t，面积 86.5 m²，共计12")
        self.assertEqual([(q.number, q.unit) for q in found],
                         [("35", "吨"), ("1,200", "元"), ("0.3", "t"), ("86.5", "m²"), ("12", "")])

    def test_a_thousands_comma_does_not_split_a_clause(self):
        self.assertEqual(pf.clauses("合同价 1,200,000 元，工期 540 天"), ["合同价 1,200,000 元", "工期 540 天"])


class ColumnQuantities(unittest.TestCase):
    def test_the_longest_keyword_wins_and_a_quantity_is_used_once(self):
        got = pf.column_quantities("盘点差 0.3 吨", WAREHOUSE)
        self.assertEqual({k: q.text for k, q in got.items()}, {"variance": "0.3吨"})
        got = pf.column_quantities("入库 35 吨 出库 12 吨", WAREHOUSE)
        self.assertEqual({k: q.text for k, q in got.items()}, {"inbound": "35吨", "outbound": "12吨"})

    def test_a_quantity_written_before_its_keyword(self):
        got = pf.column_quantities("35吨入库", WAREHOUSE)
        self.assertEqual({k: q.text for k, q in got.items()}, {"inbound": "35吨"})

    def test_a_keyword_without_a_number_yields_nothing(self):
        self.assertEqual(pf.column_quantities("入库单还没签", WAREHOUSE), {})
        self.assertEqual(pf.column_quantities("入库手续办完后另行通知数量约 35 吨", WAREHOUSE), {})


class ObjectRows(unittest.TestCase):
    def test_one_sentence_is_one_row_with_every_column_the_user_gave(self):
        rows = pf.object_rows("帮我写一份仓库收发存台账口径：螺纹钢 HRB400 Φ20 本周入库 35 吨，领用 12 吨，盘点差 0.3 吨，仓管员张伟", WAREHOUSE)
        self.assertEqual([{k: v for k, v in row.items() if k != "source"} for row in rows],
                         [{"name": "螺纹钢", "spec": "HRB400 Φ20", "period": "本周", "inbound": "35吨",
                           "outbound": "12吨", "variance": "0.3吨"}])
        self.assertIn("螺纹钢", rows[0]["source"])

    def test_a_number_stays_with_its_own_object(self):
        rows = pf.object_rows("水泥 P.O 42.5 入库 80 吨，领用 46 吨；中砂进场 120 方，还没领", WAREHOUSE)
        self.assertEqual([(r["name"], r.get("inbound"), r.get("outbound")) for r in rows],
                         [("水泥", "80吨", "46吨"), ("中砂", "120方", None)])

    def test_lines(self):
        rows = pf.object_rows("物资：电缆 YJV-4×95\n入库 600 米\n出库 250 米", WAREHOUSE)
        self.assertEqual(len(rows), 0, "a bare '物资：' line names an object only through labelled(); rows need a column in the clause")
        rows = pf.object_rows("电缆 YJV 入库 600 米\n电缆 YJV 出库 250 米", WAREHOUSE)
        self.assertEqual([(r["name"], r.get("inbound"), r.get("outbound")) for r in rows],
                         [("电缆 YJV", "600米", None), ("电缆 YJV", None, "250米")])

    def test_nothing_is_invented(self):
        text = "钢管 48.3×3.6 入库 900 根，扣件领用 4500 个"
        for row in pf.object_rows(text, WAREHOUSE):
            for value in (v for k, v in row.items() if k != "source"):
                for token in value.split():
                    self.assertIn(token, text.replace(" ", "") + " " + text, value)


class Labelled(unittest.TestCase):
    ALIASES = {"cooling": ("冷负荷",), "fresh_air": ("新风量",), "scope": ("设计范围", "范围"), "unit": ("单体", "部位")}

    def test_lines_running_text_and_connectives(self):
        self.assertEqual(pf.labelled("冷负荷：850 kW\n新风量: 12000 m³/h", self.ALIASES),
                         {"cooling": "850 kW", "fresh_air": "12000 m³/h"})
        self.assertEqual(pf.labelled("3#楼暖通，冷负荷 850kW，新风量为12000 m³/h", self.ALIASES),
                         {"cooling": "850kW", "fresh_air": "12000 m³/h"})

    def test_a_label_at_the_start_of_a_line_keeps_its_commas(self):
        self.assertEqual(pf.labelled("范围：地下室，一层，屋面机房", self.ALIASES), {"scope": "地下室，一层，屋面机房"})
        self.assertEqual(pf.labelled("范围：地下室，一层 冷负荷：850kW", self.ALIASES),
                         {"scope": "地下室，一层", "cooling": "850kW"})

    def test_a_word_that_merely_contains_an_alias_is_not_a_label(self):
        self.assertEqual(pf.labelled("本次不在施工范围内的内容另行商定", self.ALIASES), {})

    def test_first_mention_wins_and_the_longest_alias_claims_the_text(self):
        self.assertEqual(pf.labelled("设计范围：A 区\n范围：B 区", self.ALIASES), {"scope": "A 区"})


class PeopleDatesSpecs(unittest.TestCase):
    def test_person_for(self):
        self.assertEqual(pf.person_for("盘点差 0.3 吨，仓管员张伟", ("仓管", "仓管员", "保管员")), "张伟")
        self.assertEqual(pf.person_for("负责人：李工，明天复查", ("负责人",)), "李工")
        self.assertEqual(pf.person_for("王建国（质检员）到场", ("质检员",)), "王建国")
        self.assertEqual(pf.person_for("仓管员今天请假", ("仓管员",)), "")

    def test_dates_periods_specs(self):
        self.assertEqual(pf.dates("2026-09-18 浇筑，9月20日拆模，2026年10月交付"), ["2026-09-18", "9月20日", "2026年10月"])
        self.assertEqual(pf.periods("本周入库，下周盘点"), ["本周", "下周"])
        self.assertEqual(pf.specs("螺纹钢 HRB400 Φ20，混凝土 C35，钢管 48.3×3.6"), ["HRB400", "Φ20", "C35", "48.3×3.6"])

    def test_strip_command(self):
        self.assertEqual(pf.strip_command("帮我写一份仓库收发存台账口径：螺纹钢入库 35 吨"), "螺纹钢入库 35 吨")
        self.assertEqual(pf.strip_command("螺纹钢入库 35 吨"), "螺纹钢入库 35 吨")


if __name__ == "__main__":
    unittest.main()
