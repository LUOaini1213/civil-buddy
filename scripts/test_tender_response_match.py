#!/usr/bin/env python3
"""招标要求 ↔ 投标响应对照：一条原文一行、数值只做算术、响应永远不变成要求。

匹配质量（精确率 / 召回率）由 scripts/eval_tender_response_match.py 对基准打分；
这里钉的是行为契约：去重、展开、单位、状态码、偏移量，以及整条流程里的呈现。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.tools.tender_parse import parse_tender_text  # noqa: E402
from packing_assistant.tools.tender_response_match import _compare_quantities, compare_responses  # noqa: E402

TENDER = "★投标人须提供营业执照复印件。\n技术方案评分20分，须编制施工专项方案。\n工期60日历天。\n"
RESPONSE = "已附营业执照复印件。\n施工方案资料待补。\n供应商自述工期999日历天。\n"


def _sources(tender=TENDER, response=RESPONSE):
    rows = [{"source_id": "tender-1", "title": "招标资料", "text": tender, "start": 100, "role": "tender"}]
    if response is not None:
        rows.append({"source_id": "response-1", "title": "投标响应", "text": response, "start": 300, "role": "response"})
    return rows


def _compare(tender=TENDER, response=RESPONSE):
    return compare_responses(parse_tender_text(tender)["requirements"], _sources(tender, response))


def main() -> int:
    # 1. 同一句招标原文只出一行（此前这份样例出 5 行，其中「施工专项方案」3 行）
    rows = _compare()
    assert [r["requirement_ref"] for r in rows] == ["L3", "L2", "L1"], rows
    plan_row = next(r for r in rows if r["requirement_ref"] == "L2")
    assert {"theme", "scoring_point", "special"} <= set(plan_row["kinds"]), plan_row

    # 2. theme 命中的每一句都进对照表，ref 与句子一一对应（此前只有第一句进表）
    many = "投标人须具备建筑工程施工总承包二级及以上资质。\n须提供近三年类似项目业绩不少于2项。\n须提供有效的安全生产许可证。\n"
    refs = {r["requirement"]: r["requirement_ref"] for r in _compare(many, "安全生产许可证见附件4。\n")}
    assert refs == {"投标人须具备建筑工程施工总承包二级及以上资质。": "L1", "须提供近三年类似项目业绩不少于2项。": "L2",
                    "须提供有效的安全生产许可证。": "L3"}, refs

    # 3. 数值只做算术：方向取招标原文里的比较词，没有才用该主题的默认方向
    for requirement, response, want in (
        ("工期60日历天。", "供应商自述工期999日历天。", ("duration", "max")),
        ("工期90日历天。", "计划工期85日历天，分三个阶段实施。", None),
        ("★质保期不少于24个月。", "质保期2年，自验收合格之日起计算。", None),            # 2 年 = 24 个月
        ("★投标有效期不少于90天。", "投标有效期60天。", ("validity", "min")),
        ("★投标有效期不少于90天。", "投标有效期3个月。", None),                        # 天与月不换算，留给人看
        ("★投标保证金人民币20万元，须在投标截止前到账。", "投标保证金10万元已于9月1日汇出。", ("bond", "equal")),
        ("★投标保证金人民币5万元。", "投标保证金5万元已缴纳，回单见附件。", None),
        ("单件货载不得超过25吨。", "最重单件货载为28吨的变压器底座。", ("payload", "max")),
        ("须采用40HQ集装箱海运。", "全部货物装入3个40HQ集装箱。", None),                # 40HQ 不是数值要求
        ("★交货期：合同签订后45天内到货。", "交货期为合同签订后60天。", ("delivery", "max")),
        ("须提供近三年类似项目业绩不少于3项。", "类似项目业绩2项：A小区、B厂房。", ("track_record", "min")),
        ("The Works shall be completed within 60 calendar days.", "We propose to complete the Works in 75 calendar days.", ("duration", "max")),
        ("★ The defects liability period shall be not less than 12 months.", "We have 12 full-time engineers.", None),
        # 日期不是数量
        ("总工期不超过3个月。", "计划于2026年12月31日前完工。", None),
        ("★交货期：合同签订后45天内到货。", "交货期：9月1日前到货。", None),
        ("The Works shall be completed within 60 calendar days.", "Completion by 31 December 2026.", None),
        ("总工期不超过3个月。", "总工期4个月，计划2026年12月31日完工。", ("duration", "max")),
    ):
        found = [(c["topic"], c["direction"]) for c in _compare_quantities(requirement, response)]
        assert found == ([want] if want else []), (requirement, response, found)
    # 总工期与节点工期按出现顺序配对，只报真正对不上的那个
    two = _compare_quantities("总工期180日历天，其中主体结构封顶不超过90日历天。", "我司计划总工期175日历天，主体结构封顶100日历天。")
    assert [(c["required"], c["offered"]) for c in two] == [("90日历天", "100日历天")], two
    # 个数对不上就不配对
    assert _compare_quantities("总工期180日历天，其中主体结构封顶不超过90日历天。", "总工期200日历天。") == []

    # 4. 状态码与措辞：只陈述、不裁决
    by_ref = {r["requirement_ref"]: r for r in rows}
    assert by_ref["L3"]["status"] == "conflict_requires_review", by_ref["L3"]
    note = by_ref["L3"]["conflicts"][0]["note"]
    assert "999日历天" in note and "60日历天" in note and note.endswith("待人工核验"), note
    assert not any(word in note for word in ("不合格", "废标", "无效", "否决")), note
    assert by_ref["L1"]["status"] == "candidate_requires_review", by_ref["L1"]
    assert all(r["verified"] is False for r in rows)
    assert all(r["status"] == "not_provided" and not r["response_evidence"] for r in _compare(TENDER, None))
    assert all(r["status"] == "not_matched" for r in _compare(TENDER, "感谢贵司邀请，我司将全力配合。\n"))

    # 5. 偏移量逐字可回溯到响应原文
    for row in rows:
        for ev in row["response_evidence"]:
            assert RESPONSE[ev["start"] - 300:ev["end"] - 300] == ev["quote"], ev
            assert ev["matched_by"], ev

    # 6. 整条流程：冲突进汇总，响应里的 999 永远不变成招标要求
    from packing_assistant.runtime.tender_workflow import run_tender_workflow

    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tender-response-match-", dir=output) as td:
        result = run_tender_workflow(TENDER, session_id="response-match", output_root=Path(td), sources=_sources())
        assert result["ok"] and result["submit_blocked"], result
        comparison = result["review"]["response_comparison"]
        assert len(comparison) == 3, comparison
        assert any("999日历天" in c["note"] and c["status"] == "needs_review" for c in result["review"]["conflicts"]), result["review"]["conflicts"]
        assert result["quality"]["conflicts"] >= 1, result["quality"]
        directory = Path(result["directory"])
        compliance = (directory / "worker-bid-compliance" / "bid-compliance.md").read_text(encoding="utf-8")
        assert "conflict_requires_review" in compliance and "999日历天" in compliance, compliance[-600:]
        assert compliance.count("| 技术方案评分20分，须编制施工专项方案") == 1, "同一句招标原文在对照表里重复出现"
        summary = (directory / "collaboration-review.md").read_text(encoding="utf-8")
        assert "响应 999日历天 超过招标 60日历天" in summary, summary
        handoff = json.loads((directory / "handoff.json").read_text(encoding="utf-8"))
        assert handoff["handoff"].get("duration_days") == 60, handoff["handoff"]
        assert "999" not in json.dumps(handoff["matrix"], ensure_ascii=False)

    print(f"PASS tender_response_match rows={len(rows)} conflict={by_ref['L3']['conflicts'][0]['topic']} "
          f"statuses={sorted({r['status'] for r in rows})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
