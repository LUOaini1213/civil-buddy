#!/usr/bin/env python3
"""A tender in THREE LOTS with an addendum - made up, in the shapes real ones come in.

    python test/benchmarks/real_tender/build_cn_multilot.py

writes cn_multilot.md (the tender), cn_multilot.addendum1.md (补遗书第1号) and cn_multilot.gold.json.

What a bid team needs from such a pair and what reading it as one flat document loses:

  per lot      the lot table of the notice (标段 | 建设内容 | 最高限价 | 工期 | 投标保证金), front-table rows that lay down one
               value per lot ("一标段：20万元；二标段：15万元；三标段：18万元"), and qualification paragraphs per lot
  amended      the addendum changes the deadline for every lot, the bond of ONE lot, and answers a question on the
               duration ("以本答复为准"); what it does not touch stands as it was

Scored with scripts/eval_real_document.py (label / expect, the same gold format as for a real document):

    python scripts/eval_real_document.py test/benchmarks/real_tender/cn_multilot.md \
        --with test/benchmarks/real_tender/cn_multilot.addendum1.md --gold test/benchmarks/real_tender/cn_multilot.gold.json
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

LOTS = (("一标段", "沿江大道（K0+000~K2+300）路面大修", "1860万元", "150日历天", "30万元", "公路工程施工总承包贰级及以上资质"),
        ("二标段", "滨湖路（K0+000~K1+750）路面中修及排水改造", "1240万元", "120日历天", "20万元", "市政公用工程施工总承包叁级及以上资质"),
        ("三标段", "全线交通安全设施更新", "415万元", "90日历天", "8万元", "公路交通工程（公路安全设施）专业承包贰级及以上资质"))

CONTRACT = "\n\n".join(
    f"{n}.{k} 承包人应在收到监理人指示后{5 + n + k}天内提交书面报告；因承包人原因造成工期延误的，每延误1天支付违约金{800 * n + 50 * k}元，"
    f"累计不超过签约合同价的{2 + k}%。发包人应在收到申请后{20 + n}天内完成审核。" for n in range(1, 13) for k in range(1, 5))


def tender() -> str:
    lot_rows = "\n".join(f"| {name} | {scope} | {cap} | {days} | {bond} |" for name, scope, cap, days, bond, _ in LOTS)
    qualification = "\n\n".join(
        f"3.1.{i} {name}\n\n本标段要求投标人须具有独立法人资格，须具备{grade}，并具有有效的安全生产许可证。"
        for i, (name, _, _, _, _, grade) in enumerate(LOTS, 1))
    return f"""# 澄湖市2028年城市道路养护提升工程（一、二、三标段）施工招标文件

招标编号：CHGL-2028-SG-031

目 录

第一章 招标公告........................................................ 1
第二章 投标人须知...................................................... 6
第三章 评标办法（综合评估法）.......................................... 31
第四章 合同条款及格式.................................................. 40
第五章 投标文件格式.................................................... 88

第一章 招标公告

1. 招标条件

本招标项目澄湖市2028年城市道路养护提升工程已由澄湖市发展和改革委员会批准建设，招标人为澄湖市市政设施管理中心，招标代理机构为澄信工程咨询有限公司。

2. 项目概况与招标范围

2.1 标段划分：本项目划分为三个标段，投标人可对多个标段投标，但最多只能中标一个标段。

| 标段 | 建设内容 | 最高投标限价 | 计划工期 | 投标保证金 |
| --- | --- | --- | --- | --- |
{lot_rows}

2.2 质量要求：合格。

3. 投标人资格要求

{qualification}

3.2 本次招标不接受联合体投标。

5. 投标文件的递交

5.1 投标文件递交的截止时间为2028年4月18日09时30分。

5.2 逾期送达的投标文件，招标人不予受理。

第二章 投标人须知

投标人须知前附表

| 条款号 | 条款名称 | 编列内容 |
| --- | --- | --- |
| 1.1.2 | 招标人 | 名称：澄湖市市政设施管理中心；地址：澄湖市环城东路66号 |
| 1.1.4 | 项目名称 | 澄湖市2028年城市道路养护提升工程 |
| 1.3.2 | 计划工期 | 一标段：150日历天；二标段：120日历天；三标段：90日历天 |
| 1.3.3 | 质量要求 | 合格 |
| 1.4.1 | 投标人资质条件 | 见招标公告 |
| 1.4.2 | 是否接受联合体投标 | ☑不接受；□接受 |
| 3.2.4 | 最高投标限价 | 一标段：1860万元；二标段：1240万元；三标段：415万元。投标报价超过所投标段最高投标限价的，其投标将被否决。 |
| 3.3.1 | 投标有效期 | 90日历天 |
| 3.4.1 | 投标保证金 | 一标段：30万元；二标段：20万元；三标段：8万元；形式：银行转账或银行保函 |
| 3.7.4 | 投标文件份数 | 每个标段正本1份、副本4份，按标段分别装订、分别密封 |
| 4.2.2 | 递交投标文件地点 | 澄湖市公共资源交易中心四楼第三开标室 |
| 7.3.1 | 履约担保 | 履约担保的金额：签约合同价的10% |

1. 总则

1.1 本招标项目已具备招标条件，现对各标段的施工进行招标。

3.4.2 投标人不按本章第3.4.1项要求提交投标保证金的，评标委员会将否决其投标。

3.7.5 投标人对多个标段投标的，应当按标段分别编制投标文件；将不同标段的内容装订在同一册的，该投标文件将被否决。

第三章 评标办法（综合评估法）

评标办法前附表

| 条款号 | 评审因素 | 评审标准 |
| --- | --- | --- |
| 2.1.1 | 形式评审标准 | 投标人名称：与营业执照、资质证书、安全生产许可证一致 |
| 2.2.1 | 分值构成（总分100分） | 施工组织设计：30分；项目管理机构：10分；投标报价：55分；其他评分因素：5分 |

3.1.2 投标文件有一项不符合评审标准的，评标委员会应当否决其投标。

第四章 合同条款及格式

{CONTRACT}

第五章 投标文件格式

目录

一、投标函及投标函附录

二、法定代表人身份证明

三、投标保证金

四、已标价工程量清单

五、施工组织设计
"""


def addendum() -> str:
    return """# 澄湖市2028年城市道路养护提升工程（一、二、三标段）施工招标补遗书第1号

各投标人：

现就本项目招标文件作如下补遗、澄清，本补遗书是招标文件的组成部分，与招标文件不一致之处，以本补遗书为准。

一、招标文件修改

1. 投标文件递交的截止时间由2028年4月18日09时30分调整为2028年4月25日09时30分，开标时间相应顺延。

2. 原招标文件第二章投标人须知前附表第3.4.1项中二标段投标保证金“20万元”修改为“12万元”，其余标段不变。

3. 投标人须知前附表第3.3.1项投标有效期修改为120日历天。

二、答疑

问1：一标段计划工期150日历天是否包含雨季停工时间？

答：一标段计划工期调整为165日历天，已包含雨季停工时间，以本答复为准。

问2：三标段是否可以分包？

答：不允许分包。

三、其他内容不变。

澄湖市市政设施管理中心

2028年4月9日
"""


GOLD = {
    "fields": [
        {"label": "项目名称", "expect": "澄湖市2028年城市道路养护提升工程"},
        {"label": "招标人", "expect": "澄湖市市政设施管理中心"},
        {"label": "招标编号", "expect": "CHGL-2028-SG-031"},
        {"label": "工期（一标段）", "expect": "165日历天"},
        {"label": "工期（一标段）", "expect": "150日历天"},
        {"label": "工期（二标段）", "expect": "120日历天"},
        {"label": "工期（三标段）", "expect": "90日历天"},
        {"label": "最高限价（一标段）", "expect": "1860万元"},
        {"label": "最高限价（二标段）", "expect": "1240万元"},
        {"label": "最高限价（三标段）", "expect": "415万元"},
        {"label": "投标保证金（一标段）", "expect": "30万元"},
        {"label": "投标保证金（二标段）", "expect": "12万元"},
        {"label": "投标保证金（二标段）", "expect": "20万元"},
        {"label": "投标保证金（三标段）", "expect": "8万元"},
        {"label": "资质（一标段）", "expect": "公路工程施工总承包贰级及以上资质"},
        {"label": "资质（二标段）", "expect": "市政公用工程施工总承包叁级及以上资质"},
        {"label": "资质（三标段）", "expect": "公路交通工程（公路安全设施）专业承包贰级及以上资质"},
        {"label": "投标截止", "expect": "2028年4月25日09时30分"},
        {"label": "投标截止", "expect": "2028年4月18日09时30分"},
        {"label": "投标有效期", "expect": "120日历天"},
        {"label": "投标有效期", "expect": "90日历天"},
        {"label": "联合体投标", "expect": "不接受"},
        {"label": "质量标准", "expect": "合格"},
        {"label": "分包", "expect": "不允许"},
    ],
    # which of two values stands: the row that shows the addendum's value says so, the original's does not
    "amended": [["工期（一标段）", "165日历天"], ["投标保证金（二标段）", "12万元"], ["投标截止", "2028年4月25日09时30分"], ["投标有效期", "120日历天"]],
    "rejections": ["逾期送达的投标文件，招标人不予受理", "其投标将被否决", "评标委员会将否决其投标", "该投标文件将被否决", "评标委员会应当否决其投标"],
    "scores": [["施工组织设计", "30"], ["项目管理机构", "10"], ["投标报价", "55"], ["其他评分因素", "5"]],
    "forms": ["投标函及投标函附录", "法定代表人身份证明", "投标保证金", "已标价工程量清单", "施工组织设计"],
}


def main() -> int:
    (HERE / "cn_multilot.md").write_text(tender(), encoding="utf-8")
    (HERE / "cn_multilot.addendum1.md").write_text(addendum(), encoding="utf-8")
    (HERE / "cn_multilot.gold.json").write_text(json.dumps(GOLD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"cn_multilot.md {len(tender())} chars; addendum {len(addendum())} chars; gold {len(GOLD['fields'])} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
