#!/usr/bin/env python3
"""Drive tender.parse / checklist / response_matrix / pipeline (shipped tools)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


SAMPLE = """
一、投标人须具备建筑工程施工资质及类似幕墙业绩。
二、货物须妥善包装，重要构件采用铁架/木箱防护，防潮防损。
三、采用海运整柜，优先 40HQ；超长构件需说明运输方案。
四、严禁超载，单柜不超过货载限制；重心与绑扎须符合 CTU 要求。
五、交货期：合同签订后 90 个日历天内到港。
六、未实质性响应招标文件的作废标处理。
七、须提供 VGM 及保险相关文件。
八、技术分与商务分按评分办法执行。
"""


def main() -> int:
    from packing_assistant.tools.tender_parse import (
        build_checklist,
        build_response_matrix,
        parse_tender_text,
        run_tender_pipeline,
    )

    parsed = parse_tender_text(SAMPLE, source="unit-sample")
    assert parsed["schema"] == "tender.parse.v1"
    reqs = parsed["requirements"]
    assert len(reqs) >= 5, reqs
    cats = {r["category"] for r in reqs}
    assert "packaging" in cats or "transport" in cats, cats
    assert parsed["summary"]["must_respond_n"] >= 2
    # compliance-matrix fields (AutoRFP / Inventive: owner, risk, ref, type)
    for r in reqs:
        assert r.get("owner"), r
        assert r.get("risk"), r
        assert r.get("requirement_ref"), r
        assert r.get("requirement_type") in (
            "mandatory",
            "evaluated",
            "administrative",
            "informational",
        ), r
    assert parsed["summary"].get("critical_n", 0) >= 1
    assert any(r.get("requirement_type") == "mandatory" for r in reqs)

    cl = build_checklist(reqs)
    assert cl["schema"] == "tender.checklist.v1"
    assert cl["n_pending"] == len(reqs)
    assert "owner" in cl["items"][0]

    matrix = build_response_matrix(
        reqs,
        packing_summary={
            "can_fit": True,
            "containers_used": 1,
            "n0": 1,
            "ship_ok": True,
            "mid50": 0.7,
        },
    )
    assert matrix["schema"] == "tender.response_matrix.v1"
    assert matrix["summary"]["n"] == len(reqs)
    assert matrix["summary"]["covered"] >= 1, matrix
    assert "by_owner" in matrix["summary"]

    pipe = run_tender_pipeline(
        SAMPLE,
        packing_summary={"can_fit": True, "containers_used": 1, "n0": 1, "ship_ok": True, "mid50": 0.72},
    )
    assert pipe["ok"] is True
    assert pipe["schema"] == "tender.pipeline.v1"
    assert pipe["matrix"]["summary"]["covered"] >= 1
    assert "readiness_score" in pipe["matrix"]["summary"]
    assert 0.0 <= float(pipe["matrix"]["summary"]["readiness_score"]) <= 1.0
    assert pipe.get("matrix_markdown") and "| 条款 |" in pipe["matrix_markdown"]
    # proposal_location + compliance_label present on rows (compliance matrix practice)
    assert all(r.get("proposal_location") for r in matrix["rows"]), matrix["rows"][0]
    assert all(r.get("compliance_label") for r in matrix["rows"]), matrix["rows"][0]
    covered = [r for r in matrix["rows"] if r.get("status") == "covered"]
    if covered:
        assert covered[0]["compliance_label"] == "compliant"
    # M4 light: matrix rows cite 08_tender_delivery knowledge paths
    assert all(r.get("knowledge_ref") for r in matrix["rows"]), matrix["rows"][0]
    assert any(
        "08_tender_delivery" in str(r.get("knowledge_ref")) for r in matrix["rows"]
    )
    # markdown export usable for client handoff
    from packing_assistant.tools.tender_parse import matrix_to_markdown

    md2 = matrix_to_markdown(matrix)
    assert md2.count("|") >= 10
    # mainline C: response package + open actions
    assert pipe.get("product_mainline") == "C_tender_delivery"
    assert pipe.get("export_markdown") and "交付证据" in pipe["export_markdown"]
    assert pipe.get("bidbook_markdown") and "DRAFT" in pipe["bidbook_markdown"]
    assert "Harbourline Facade" in pipe["bidbook_markdown"]
    assert "1. Cover & Form of Tender" in pipe["bidbook_markdown"]
    assert "open_actions" in pipe
    assert isinstance(pipe["open_actions"], list)
    pkg = pipe.get("response_package") or {}
    assert pkg.get("schema") == "tender.response_package.v1"
    assert pkg.get("n_open", 0) >= 1  # qualification / reject still human

    print(
        "PASS tender_parse",
        f"n_req={len(reqs)}",
        f"covered={matrix['summary']['covered']}",
        f"readiness={pipe['matrix']['summary'].get('readiness_score')}",
        f"critical={parsed['summary'].get('critical_n')}",
        f"open={pkg.get('n_open')}",
        f"owners={parsed['summary'].get('owners')}",
        f"cats={sorted(cats)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
