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
        matrix_to_csv,
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
    # M4: excerpts come from real in-repo files, not invented clause numbers
    with_ex = [r for r in matrix["rows"] if r.get("knowledge_excerpt")]
    assert with_ex, matrix["rows"][0]
    assert "条款第" not in with_ex[0]["knowledge_excerpt"]
    # M4 light: matrix rows cite 08_tender_delivery knowledge paths
    assert all(r.get("knowledge_ref") for r in matrix["rows"]), matrix["rows"][0]
    assert any(
        "08_tender_delivery" in str(r.get("knowledge_ref")) for r in matrix["rows"]
    )
    # markdown export usable for client handoff
    from packing_assistant.tools.tender_parse import matrix_to_markdown

    md2 = matrix_to_markdown(matrix)
    assert md2.count("|") >= 10
    csv = matrix_to_csv(matrix)
    assert csv.startswith("req_id,")
    assert "owner" in csv.splitlines()[0]
    assert csv.count("\n") >= 2
    assert pipe.get("matrix_csv") and pipe["matrix_csv"].startswith("req_id,")
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

    # v1.1 item-level + handoff (AutoRFP / P0): drive shipped parse, do not invent days
    rich = """
项目：Harbourline Facade DEMO
一、投标人须具备建筑工程施工资质及类似幕墙业绩。BCA workhead CW01。
二、货物须妥善包装，采用铁架防护。
三、采用海运整柜 40HQ。
四、重心与绑扎须符合 CTU。
五、交货期：合同签订后 90 个日历天内到港。
六、未实质性响应招标文件的作废标处理。
七、技术标评分：施工组织设计 25 分、项目管理机构 10 分。
八、★深基坑专项方案须编制，不满足即废标。
九、采用两信封：技术标与报价分投。投标截止 2026-09-01 15:00。
"""
    rich_parsed = parse_tender_text(rich, source="unit-rich")
    assert rich_parsed.get("duration_days") == 90, rich_parsed.get("duration_days")
    ho = rich_parsed.get("handoff") or {}
    assert ho.get("schema") == "tender.handoff.v1"
    assert ho.get("duration_days") == 90
    stars = ho.get("star_items") or []
    assert any("深基坑" in str(s.get("text") or "") for s in stars), stars
    scores = ho.get("scoring_points") or []
    assert any("25 分" in str(s.get("text") or "") or "25分" in str(s.get("text") or "") for s in scores), scores
    assert "CW01" in (ho.get("workheads") or [])
    assert ho.get("envelope") == "two"
    # eval method only when verbatim
    pqm = parse_tender_text("评标采用综合评估法。包装木箱。", source="eval")
    assert (pqm.get("handoff") or {}).get("eval_method") == "综合评估法"
    none_m = parse_tender_text("包装木箱防护。", source="no-eval")
    assert (none_m.get("handoff") or {}).get("eval_method") is None
    blind = parse_tender_text("技术标为暗标。包装木箱。", source="blind")
    assert (blind.get("handoff") or {}).get("envelope") == "blind_tech"
    p0b = (blind.get("handoff") or {}).get("p0_reject_scan") or {}
    assert any(i.get("req_id") == "blind_identity" for i in (p0b.get("items") or []))
    assert ho.get("bid_decision") == "human_required"
    dls = ho.get("deadlines") or []
    assert any(d.get("label") == "投标截止" and "2026" in str(d.get("when")) for d in dls), dls
    # no invented extra deadline
    assert all(d.get("source") == "verbatim" for d in dls)
    assert "bid-tech" in (ho.get("next_experts") or [])
    assert "bid-compliance" in (ho.get("next_experts") or [])
    p0 = ho.get("p0_reject_scan") or {}
    assert p0.get("human_confirm_required") is True
    assert int(p0.get("n") or 0) >= 1
    # exact buyer text copied, not rewritten
    star_req = next(r for r in rich_parsed["requirements"] if r.get("item_kind") == "star")
    assert "深基坑" in (star_req.get("exact_text") or "")
    assert star_req.get("requirement_type") == "mandatory"
    assert star_req.get("risk") == "critical"
    # no invented BCA grade / price / days
    assert "CW02" not in str(ho.get("workheads"))
    assert rich_parsed.get("duration_days") != 180

    rich_pipe = run_tender_pipeline(rich)
    assert rich_pipe.get("submit_blocked") is True
    assert rich_pipe.get("p0_confirmed") is False
    assert "unconfirmed" in (rich_pipe.get("bidbook_markdown") or "")
    noted = run_tender_pipeline(rich, p0_confirmed=True)
    assert noted.get("submit_blocked") is True
    assert noted.get("p0_confirmed") is True
    assert "仍是 AI 草稿" in str(noted.get("submit_block_reason") or "")
    assert "P0 noted" in (noted.get("bidbook_markdown") or "")
    assert rich_pipe.get("handoff", {}).get("duration_days") == 90
    outline = rich_pipe.get("tech_outline") or {}
    assert outline.get("schema") == "tender.tech_outline.v1"
    assert outline.get("from_extracted_scores") is True
    assert outline.get("n_chapters", 0) >= 1
    assert "25 分" in (outline.get("markdown") or "") or "施工组织设计" in (outline.get("markdown") or "")
    assert "已论证通过" not in (outline.get("markdown") or "")
    assert "可以开工" not in (outline.get("markdown") or "")
    assert "禁止写已论证" in (outline.get("markdown") or "")
    assert "经营岗交接" in (rich_pipe.get("export_markdown") or "")
    table = rich_pipe.get("extract_table_markdown") or ""
    assert "招标解析表" in table
    assert "90 日历天" in table
    assert "未在原文检出" in table or "CW01" in table
    assert "365 天" not in table
    bb = rich_pipe.get("bidbook_markdown") or ""
    assert "Scoring-point map" in bb
    assert "25 分" in bb or "施工组织设计" in bb
    assert "40%–60%" not in bb

    # can_fit=false is fail: transport/packaging stay gap (not covered)
    fail_mx = build_response_matrix(
        rich_parsed["requirements"],
        packing_summary={"can_fit": False, "containers_used": 0, "n0": 2, "ship_ok": False},
    )
    pack_rows = [
        r
        for r in fail_mx["rows"]
        if r.get("category") in ("transport", "packaging") and r.get("item_kind") == "theme"
    ]
    assert pack_rows, fail_mx["rows"]
    assert all(r.get("status") == "gap" for r in pack_rows), pack_rows
    cog = [r for r in fail_mx["rows"] if r.get("req_id") == "cog_lashing"]
    if cog:
        assert cog[0].get("status") == "gap"
        assert "CTU Code" in str(cog[0].get("public_ref") or "")
        assert "clause" not in str(cog[0].get("public_ref") or "").lower()

    bond = parse_tender_text("投标保证金为投标报价的 2%。包装用木箱。", source="bond")
    ho_b = bond.get("handoff") or {}
    assert (ho_b.get("bid_bond") or {}).get("mentioned") is True
    assert (ho_b.get("bid_bond") or {}).get("amount_verbatim") == "2%"
    bare = parse_tender_text("包装用木箱防护。", source="no-bond")
    assert (bare.get("handoff") or {}).get("bid_bond", {}).get("mentioned") is False
    assert (bare.get("handoff") or {}).get("bid_bond", {}).get("amount_verbatim") is None

    ebid = parse_tender_text(
        "采用电子投标，投标文件须加密并持 CA 锁开标解密。包装用木箱。",
        source="ebid",
    )
    ebid_items = [r for r in ebid["requirements"] if r.get("item_kind") == "ebid"]
    assert ebid_items, ebid["requirements"]
    assert "CA" in (ebid_items[0].get("exact_text") or "")
    assert "契约锁" not in str(ebid)

    empty_days = parse_tender_text("仅包装要求：木箱防护。", source="no-days")
    assert empty_days.get("duration_days") is None
    assert (empty_days.get("handoff") or {}).get("envelope") is None
    assert (empty_days.get("handoff") or {}).get("deadlines") == []
    assert (empty_days.get("handoff") or {}).get("bid_decision") == "human_required"

    # workbench sidecar shares the same shipped parse
    import json
    import subprocess

    sidecar = ROOT / "workbench" / "scripts" / "run_packing_sidecar.py"
    payload = json.dumps({"mode": "tender_parse", "tender_text": rich}, ensure_ascii=False)
    proc = subprocess.run(
        [sys.executable, str(sidecar)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        env={**__import__("os").environ, "PACKING_AGENT_ROOT": str(ROOT)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    side = json.loads(proc.stdout.strip().splitlines()[-1])
    assert side.get("ok") is True
    assert side.get("mode") == "tender_parse"
    assert (side.get("handoff") or {}).get("duration_days") == 90
    assert (side.get("handoff") or {}).get("envelope") == "two"
    assert side.get("submit_blocked") is True
    assert "招标解析表" in str(side.get("extract_table_markdown") or "")

    print(
        "PASS tender_parse",
        f"n_req={len(reqs)}",
        f"covered={matrix['summary']['covered']}",
        f"readiness={pipe['matrix']['summary'].get('readiness_score')}",
        f"critical={parsed['summary'].get('critical_n')}",
        f"open={pkg.get('n_open')}",
        f"owners={parsed['summary'].get('owners')}",
        f"cats={sorted(cats)}",
        f"rich_days={rich_parsed.get('duration_days')}",
        f"stars={len(stars)}",
        f"scores={len(scores)}",
        f"outline={outline.get('n_chapters')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
