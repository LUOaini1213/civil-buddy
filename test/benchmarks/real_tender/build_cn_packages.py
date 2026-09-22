#!/usr/bin/env python3
"""Held-out G: a government purchase in two PACKAGES (采购包) with a correction notice (更正公告) - written after the rules
for lots and addenda were frozen on cn_multilot, in other words: 包 not 标段, 更正 / 变更为 / 延期至 not 修改为 / 调整为, a
package table headed 包号, one value per package written "包1：…", a clarification that answers without a change verb.

    python test/benchmarks/real_tender/build_cn_packages.py
    python scripts/eval_real_document.py test/benchmarks/real_tender/cn_packages.md \
        --with test/benchmarks/real_tender/cn_packages.correction1.md --gold test/benchmarks/real_tender/cn_packages.gold.json --word

Run once, first-run number into README.md; whatever is fixed afterwards is a development number.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILLER = "\n\n".join(
    f"{n}.{k} 成交供应商应在收到采购人通知后{4 + n + k}日内书面答复；逾期交付的，每逾期1日按合同金额的{k}‰支付违约金，累计不超过合同金额的{3 + k}%。"
    for n in range(1, 12) for k in range(1, 5))


def tender() -> str:
    return f"""# 松岭县第二人民医院门诊楼修缮及配套设施采购项目竞争性磋商文件

项目编号：SLCG-2029-C-017

目 录

第一章 采购邀请........................................................ 1
第二章 供应商须知...................................................... 5
第三章 评审办法........................................................ 18
第四章 合同草案条款.................................................... 25
第五章 响应文件格式.................................................... 60

第一章 采购邀请

一、项目基本情况

项目编号：SLCG-2029-C-017

项目名称：松岭县第二人民医院门诊楼修缮及配套设施采购项目

采购方式：竞争性磋商

| 包号 | 包名称 | 采购预算 | 最高限价 | 合同履行期限 |
| --- | --- | --- | --- | --- |
| 1 | 门诊楼外立面及屋面修缮 | 386万元 | 380万元 | 100日历天 |
| 2 | 门诊楼电梯更新 | 142万元 | 139.5万元 | 75日历天 |

本项目（ 否 ）接受联合体。

二、申请人的资格要求：

1.满足《中华人民共和国政府采购法》第二十二条规定；

3.本项目的特定资格要求：

包1

供应商须具备建筑装修装饰工程专业承包贰级及以上资质，并具有有效的安全生产许可证。

包2

供应商须具备特种设备安装改造维修许可证（电梯）。

四、响应文件提交

截止时间：2029年5月14日 09:00（北京时间）

地点：松岭县公共资源交易中心二楼磋商室

第二章 供应商须知

供应商须知资料表

| 条款号 | 条目 | 内容 |
| --- | --- | --- |
| 1.1 | 采购人 | 名称：松岭县第二人民医院；地址：松岭县健康路12号 |
| 10.1 | 磋商保证金 | 包1：7万元；包2：2.5万元；形式：银行转账、保函 |
| 12.1 | 响应有效期 | 自响应文件提交截止之日起 90 日历天 |
| 14.3 | 响应文件份数 | 每包正本1份、副本3份 |
| 20.2 | 履约保证金 | 包1：合同金额的5%；包2：合同金额的3% |
| 23.5 | 分包 | ■不允许；□允许 |

一 说明

1.1 本磋商文件适用于本项目两个采购包的磋商活动，供应商可以参加一个或两个采购包。

10.4 未按资料表规定提交磋商保证金的，其响应无效。

12.2 响应有效期少于本文件规定期限的，其响应无效。

14.6 同一供应商对同一采购包提交两份以上响应文件的，该供应商在该包的全部响应按无效响应处理。

第三章 评审办法

本项目采用综合评分法。

| 评分因素 | 分值 |
| --- | --- |
| 施工（安装）方案 | 35分 |
| 项目团队 | 15分 |
| 业绩与信誉 | 10分 |
| 响应报价 | 40分 |

第四章 合同草案条款

{FILLER}

第五章 响应文件格式

目录

一、响应函

二、报价一览表

三、资格证明文件

四、施工（安装）方案
"""


def correction() -> str:
    return """# 松岭县第二人民医院门诊楼修缮及配套设施采购项目更正公告（第一次）

一、项目基本情况

原公告的采购项目编号：SLCG-2029-C-017

二、更正信息

更正事项：采购文件

更正内容：

1. 响应文件提交截止时间延期至2029年5月21日 09:00，磋商地点不变。

2. 包2最高限价变更为135万元。

3. 供应商须知资料表第10.1条中包1磋商保证金由7万元变更为5万元。

三、澄清

问：包2合同履行期限75日历天是否含设备订货周期？

答：包2合同履行期限为90日历天，含设备订货周期，以此为准。

问：包1是否接受联合体？

答：不接受联合体。

四、其他补充事宜

其他内容不变。
"""


GOLD = {
    "fields": [
        {"label": "项目名称", "expect": "松岭县第二人民医院门诊楼修缮及配套设施采购项目"},
        {"label": "招标人", "expect": "松岭县第二人民医院"},
        {"label": "招标编号", "expect": "SLCG-2029-C-017"},
        {"label": "工期（包1）", "expect": "100日历天"},
        {"label": "工期（包2）", "expect": "90日历天"},
        {"label": "工期（包2）", "expect": "75日历天"},
        {"label": "最高限价（包1）", "expect": "380万元"},
        {"label": "最高限价（包2）", "expect": "135万元"},
        {"label": "最高限价（包2）", "expect": "139.5万元"},
        {"label": "采购预算（包1）", "expect": "386万元"},
        {"label": "采购预算（包2）", "expect": "142万元"},
        {"label": "投标保证金（包1）", "expect": "5万元"},
        {"label": "投标保证金（包1）", "expect": "7万元"},
        {"label": "投标保证金（包2）", "expect": "2.5万元"},
        {"label": "履约担保（包1）", "expect": "合同金额的5%"},
        {"label": "履约担保（包2）", "expect": "合同金额的3%"},
        {"label": "资质（包1）", "expect": "建筑装修装饰工程专业承包贰级及以上资质"},
        {"label": "资质（包2）", "expect": "特种设备安装改造维修许可证"},
        {"label": "投标截止", "expect": "2029年5月21日 09:00"},
        {"label": "投标截止", "expect": "2029年5月14日 09:00"},
        {"label": "投标有效期", "expect": "90 日历天"},
        {"label": "联合体投标", "expect": "否"},
        {"label": "分包", "expect": "不允许"},
        {"label": "评标办法", "expect": "综合评分法"},
    ],
    "amended": [["投标截止", "2029年5月21日 09:00"], ["最高限价（包2）", "135万元"], ["投标保证金（包1）", "5万元"], ["工期（包2）", "90日历天"]],
    "rejections": ["未按资料表规定提交磋商保证金的，其响应无效", "响应有效期少于本文件规定期限的，其响应无效", "按无效响应处理"],
    "scores": [["施工（安装）方案", "35"], ["项目团队", "15"], ["业绩与信誉", "10"], ["响应报价", "40"]],
    "forms": ["响应函", "报价一览表", "资格证明文件", "施工（安装）方案"],
}


def main() -> int:
    (HERE / "cn_packages.md").write_text(tender(), encoding="utf-8")
    (HERE / "cn_packages.correction1.md").write_text(correction(), encoding="utf-8")
    (HERE / "cn_packages.gold.json").write_text(json.dumps(GOLD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"cn_packages.md {len(tender())} chars; correction {len(correction())} chars; gold {len(GOLD['fields'])} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
