#!/usr/bin/env python3
"""Held-out document F: a competitive-selection file (公开比选) for construction SUPERVISION.

Written 2026-09-21 with every rule frozen at commit f7a7e39, before it was run. Its purpose is one number: on a
vocabulary the rejection list has not met, how many of the fatal clauses reach the reader at all - on the list,
or in the weak-signal net under it. The words are a fourth set: 比选人 / 比选申请人 / 比选申请文件 / 比选保证金 /
中选 / 总监理工程师 / 监理服务期; the fatal clauses say 将被拒绝, 恕不接受, 视为自动放弃, 作废标处理, 判定其不合格,
按不响应处理.

Synthetic: every name and number is invented. Deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).resolve().parent
PROJECT = "柳溪镇中心卫生院迁建工程施工监理"
OWNER = "柳溪镇人民政府"
NUMBER = "LXBX-2026-JL-031"

Block = Tuple


def table(header: List[str], rows: List[List[str]]) -> Block:
    return ("table", header, rows)


FRONT: List[List[str]] = [
    ["1", "项目名称", PROJECT],
    ["2", "比选人", f"{OWNER}；联系人：邬主任；电话：0573-5550661"],
    ["3", "项目概况", "新建门诊医技综合楼、住院楼及附属用房，总建筑面积23800平方米，框架结构，工程总投资约1.42亿元"],
    ["4", "监理服务期", "自开工之日起至缺陷责任期满；其中施工阶段480日历天"],
    ["5", "监理费最高限价", "186万元；报价高于最高限价的作废标处理"],
    ["6", "比选申请人资质要求", "具备房屋建筑工程监理乙级及以上资质"],
    ["7", "总监理工程师要求", "具有国家注册监理工程师执业资格（房屋建筑工程专业），且同时担任总监的在建项目不超过2个"],
    ["8", "是否接受联合体", "不接受"],
    ["9", "比选保证金", "2万元；未按时足额到账的，视为自动放弃比选资格"],
    ["10", "比选申请有效期", "60日历天"],
    ["11", "比选申请文件递交截止时间", "2027年1月12日10:00"],
    ["12", "比选申请文件份数", "正本1份、副本2份"],
    ["13", "装订与密封", "比选申请文件须装订成册并密封；未装订成册或存在缺页的，评审委员会可判定其不合格"],
    ["14", "评审办法", "综合评估法"],
    ["15", "履约保证金", "中选金额的10%"],
    ["16", "答疑", "比选申请人如有疑问，应于2027年1月5日16:00前书面提出"],
]

SCORES: List[List[str]] = [
    ["监理报价", "报价得分", "20", "以有效报价的算术平均值为基准价，每高1%扣0.5分，每低1%扣0.3分"],
    ["监理大纲", "质量控制措施", "15", "措施全面、针对医疗建筑特点的得12-15分；一般的得6-11分"],
    ["监理大纲", "进度与投资控制", "10", "方法具体可行的得8-10分；一般的得4-7分"],
    ["监理大纲", "安全监理与旁站方案", "15", "对深基坑、高支模、洁净工程旁站安排明确的得12-15分；一般的得6-11分"],
    ["人员", "总监理工程师业绩", "15", "近五年担任过医院类项目总监的，每项得5分，最高15分"],
    ["人员", "专业监理工程师配备", "15", "土建、机电、洁净、造价专业齐全的得15分，每缺一个专业扣4分"],
    ["信誉", "企业业绩与信誉", "10", "近三年获得市级及以上优秀监理项目的每项得2分，最高10分"],
]


def document() -> List[Block]:
    blocks: List[Block] = [
        ("h1", "第一章 比选公告"),
        ("p", f"{OWNER}现对{PROJECT}进行公开比选，择优选定监理单位。项目编号：{NUMBER}。"),
        ("p", "一、比选申请人资格：具备房屋建筑工程监理乙级及以上资质；拟派总监理工程师须具有国家注册监理工程师执业资格。以他人名义参选或者出借资质的，"
              "一经查实，没收其比选保证金并上报行业主管部门。"),
        ("p", "二、比选文件的获取：2026年12月28日至2027年1月4日在柳溪镇公共资源交易站领取。"),
        ("p", "三、比选申请文件的递交：递交截止时间为2027年1月12日10:00，地点为柳溪镇公共资源交易站。逾期送达的比选申请文件恕不接受。"),
        ("h1", "第二章 比选申请人须知"),
        ("h2", "比选申请人须知前附表"),
        table(["序号", "条款名称", "编列内容"], FRONT),
        ("h2", "一、比选申请文件的编制"),
        ("p", "1. 比选申请文件由下列部分组成：（1）比选申请函；（2）法定代表人身份证明及授权委托书；（3）监理报价表；（4）资格证明材料；（5）监理大纲；"
              "（6）项目监理机构人员配备表；（7）总监理工程师承诺书；（8）比选保证金交纳凭证。"),
        ("p", "2. 比选申请人应承诺总监理工程师每周驻场不少于4天，未承诺的按不响应处理。"),
        ("p", "3. 比选申请文件应由法定代表人或其委托代理人签字并加盖单位公章。"),
        ("h2", "二、比选申请文件的拒绝"),
        ("p", "4. 比选申请人有下列情形之一的，其比选申请文件将被拒绝："),
        ("p", "1）未按比选文件规定的格式填写，内容不全或关键字迹模糊、无法辨认的；"),
        ("p", "2）比选申请文件无单位公章或无法定代表人（或其委托代理人）签字的；"),
        ("p", "3）同一比选申请人递交两份或多份内容不同的比选申请文件的；"),
        ("p", "4）比选申请人名称与资格证明材料不一致的；"),
        ("p", "5）监理服务期、比选申请有效期不满足比选文件要求的；"),
        ("p", "6）拟派总监理工程师不满足前附表要求的。"),
        ("p", "5. 同一总监理工程师同时在两个及以上比选项目中被拟派的，不予通过符合性审查。"),
        ("h1", "第三章 评审办法"),
        ("p", "一、本项目采用综合评估法评审。评审委员会由5人组成。"),
        ("p", "二、评审程序：资格审查、符合性审查、详细评审。未通过资格审查的比选申请人不进入下一阶段评审。"),
        ("p", "三、评分细则"),
        table(["评审项目", "评审内容", "分值", "评分标准"], SCORES),
        ("p", "四、中选候选人的推荐：按得分由高到低推荐2名中选候选人。中选人无正当理由更换总监理工程师的，取消其中选资格。"),
        ("h1", "第四章 监理合同主要条款"),
    ]
    lines = ["监理人应在收到施工组织设计后{a}日内完成审查并提出书面意见；逾期未提出的，视为无异议。",
             "委托人应在收到监理人的付款申请后{b}日内支付当期监理酬金；逾期支付的，按日万分之{c}计付违约金。",
             "监理人更换专业监理工程师的，应提前{a}日书面通知委托人；擅自更换的，每人次扣减监理酬金{d}元。",
             "因监理人过失造成工程质量事故的，监理人应按事故直接损失的{e}%承担赔偿责任，累计不超过监理酬金总额。",
             "监理月报应于次月{f}日前报送委托人；监理日志、旁站记录应当日完成，不得事后补记。"]
    for index in range(1, 11):
        blocks.append(("h2", f"第{index}条"))
        for sub in range(1, 7):
            k = index * 7 + sub * 3
            blocks.append(("p", f"{index}.{sub} " + lines[(index + sub) % len(lines)].format(
                a=(3, 7, 14)[k % 3], b=(14, 28)[k % 2], c=(3, 5)[(k + 1) % 2], d=(1000, 2000, 5000)[k % 3], e=(5, 10)[k % 2], f=(3, 5)[(k + 1) % 2])))
            blocks.append(("p", f"{index}.{sub}.1 本款未尽事宜，按国家有关监理规范及本合同通用条件执行；双方另有书面约定的，从其约定。"
                                "一方变更联系人或送达地址的，应在变更后3日内书面通知对方，未通知的，按原地址送达视为有效送达。"))
    blocks += [
        ("h1", "第五章 监理任务书"),
        ("p", "一、监理范围：施工准备阶段、施工阶段、竣工验收及缺陷责任期的监理服务。"),
        ("p", "二、★总监理工程师须在基坑开挖、主体结构封顶、洁净手术部验收等关键节点到场，并留存影像记录。"),
        ("p", "三、★监理机构须配备不少于1名具有洁净工程监理经验的专业监理工程师。"),
        ("p", "四、旁站范围包括：深基坑土方开挖（开挖深度5.6米）、地下室防水、梁柱节点混凝土浇筑、高支模搭设（搭设高度8.4米）。"),
        ("h1", "第六章 比选申请文件格式"),
        ("p", "一、比选申请函"),
        ("p", f"致：{OWNER}。我方已仔细阅读{PROJECT}比选文件，愿以人民币________元的监理报价参加比选，监理服务期____日历天，比选申请有效期____日历天。"),
        ("p", "二、授权委托书"),
        ("p", "三、监理报价表"),
        ("p", "四、总监理工程师承诺书"),
    ]
    return blocks


def markdown(blocks: List[Block]) -> str:
    out: List[str] = []
    for block in blocks:
        if block[0] == "h1":
            out += [f"# {block[1]}", ""]
        elif block[0] == "h2":
            out += [f"## {block[1]}", ""]
        elif block[0] == "p":
            out += [block[1], ""]
        else:
            _kind, header, rows = block
            out.append("| " + " | ".join(header) + " |")
            out.append("| " + " | ".join("---" for _ in header) + " |")
            out += ["| " + " | ".join(cell.replace("|", "／") for cell in row) + " |" for row in rows]
            out.append("")
    return "\n".join(out)


def gold() -> Dict:
    fields = {
        "project": (PROJECT, "1", "项目名称|工程名称"),
        "owner": (OWNER, "2", "招标人|采购人|比选人|建设单位"),
        "tender_no": (NUMBER, "第一章", "招标编号|项目编号"),
        "duration": ("480日历天", "4", "工期|服务期|监理服务期"),
        "price_cap": ("186万元", "5", "最高限价|限价|控制价"),
        "qualification": ("房屋建筑工程监理乙级及以上", "6", "资质|资格"),
        "pm": ("国家注册监理工程师", "7", "项目经理|项目负责人|总监理工程师|总监"),
        "consortium": ("不接受", "8", "联合体"),
        "bond": ("2万元", "9", "投标保证金|比选保证金|保证金"),
        "validity": ("60日历天", "10", "投标有效期|比选申请有效期|有效期"),
        "deadline_bid": ("2027年1月12日10:00", "11", "投标截止|递交截止|截止"),
        "copies": ("正本1份、副本2份", "12", "投标文件份数|比选申请文件份数|份数"),
        "eval_method": ("综合评估法", "14", "评标办法|评标方法|评审方法|评审办法"),
        "performance_bond": ("10%", "15", "履约担保|履约保证"),
        "deadline_query": ("2027年1月5日16:00", "16", "答疑|澄清|提问|质疑"),
    }
    wrong = {"duration": ["60日历天", "3日", "7日", "14日"], "price_cap": ["1.42亿元"], "bond": ["186万元"], "validity": ["480日历天"]}
    rejections = [
        ("R01", "没收其比选保证金并上报行业主管部门", "第一章 一"),
        ("R02", "逾期送达的比选申请文件恕不接受", "第一章 三"),
        ("R03", "报价高于最高限价的作废标处理", "前附表 5"),
        ("R04", "未按时足额到账的，视为自动放弃比选资格", "前附表 9"),
        ("R05", "未装订成册或存在缺页的，评审委员会可判定其不合格", "前附表 13"),
        ("R06", "未承诺的按不响应处理", "第二章 2"),
        ("R07", "其比选申请文件将被拒绝", "第二章 4"),
        ("R08", "未按比选文件规定的格式填写，内容不全或关键字迹模糊、无法辨认的", "第二章 4 1)"),
        ("R09", "比选申请文件无单位公章或无法定代表人（或其委托代理人）签字的", "第二章 4 2)"),
        ("R10", "同一比选申请人递交两份或多份内容不同的比选申请文件的", "第二章 4 3)"),
        ("R11", "比选申请人名称与资格证明材料不一致的", "第二章 4 4)"),
        ("R12", "监理服务期、比选申请有效期不满足比选文件要求的", "第二章 4 5)"),
        ("R13", "拟派总监理工程师不满足前附表要求的", "第二章 4 6)"),
        ("R14", "不予通过符合性审查", "第二章 5"),
        ("R15", "未通过资格审查的比选申请人不进入下一阶段评审", "第三章 二"),
        ("R16", "取消其中选资格", "第三章 四"),
        ("R17", "总监理工程师须在基坑开挖、主体结构封顶、洁净手术部验收等关键节点到场", "第五章 二"),
        ("R18", "监理机构须配备不少于1名具有洁净工程监理经验的专业监理工程师", "第五章 三"),
    ]
    scores = [(row[1], row[2]) for row in SCORES]
    forms = ["比选申请函", "法定代表人身份证明及授权委托书", "监理报价表", "资格证明材料", "监理大纲", "项目监理机构人员配备表", "总监理工程师承诺书", "比选保证金交纳凭证"]
    return {
        "_note": "Gold for cn_selection.md, held-out document F. Written 2026-09-21 with every rule frozen at commit f7a7e39, before the document "
                 "was run. A public competitive selection for construction supervision: a fourth vocabulary. Synthetic.",
        "fields": {key: {"value": value, "clause": clause, "row": row} for key, (value, clause, row) in fields.items()},
        "wrong": wrong,
        "rejections": [{"id": rid, "text": text, "clause": clause} for rid, text, clause in rejections],
        "scores": [{"name": name, "score": score} for name, score in scores],
        "specials": [],
        "forms": forms,
    }


def main() -> None:
    text = markdown(document())
    (HERE / "cn_selection.md").write_bytes(text.encode("utf-8"))
    g = gold()
    (HERE / "cn_selection.gold.json").write_bytes((json.dumps(g, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for key, item in g["fields"].items():
        assert item["value"] in text, key
    for item in g["rejections"]:
        assert item["text"] in text, item["id"]
    for name in g["forms"]:
        assert name in text, name
    print(f"cn_selection.md: {len(text)} chars; gold: {len(g['fields'])} fields, {len(g['rejections'])} rejection clauses, "
          f"{len(g['scores'])} scoring rows, {len(g['forms'])} forms")


if __name__ == "__main__":
    main()
