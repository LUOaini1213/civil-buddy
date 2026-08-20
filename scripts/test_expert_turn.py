#!/usr/bin/env python3
"""All 66 experts share understand → chat | run. Questions do not write."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.expert_roster import exclusive_tools, get_expert, list_experts
    from packing_assistant.expert_turn import run_expert_turn
    from packing_assistant.understand import understand

    roster = list_experts()
    assert len(roster) == 66, len(roster)
    assert all(e.exclusive for e in roster), [e.id for e in roster if not e.exclusive]
    assert get_expert("finance-tax") and get_expert("method-hazard") and get_expert("pack-ship")

    q = "什么是 GST"
    assert understand(q) == "chat"
    chat = run_expert_turn(q, "finance-tax")
    assert chat["intent"] == "chat" and chat["wrote"] is False
    assert chat["files"] == []
    assert "9%" in chat["reply"]
    assert "可以开工" not in chat["reply"]

    hz = run_expert_turn("临边防护算不算危大？要不要专家论证？", "method-hazard")
    assert hz["intent"] == "chat" and hz["wrote"] is False

    hz_block = run_expert_turn(
        "写一份危大判定书 临边开挖",
        "method-hazard",
        confirm_ok=False,
        force_intent="run",
    )
    assert hz_block["wrote"] is False and hz_block.get("hitl_pending") is True
    hz_ok = run_expert_turn(
        "写一份危大判定书 临边开挖",
        "method-hazard",
        confirm_ok=True,
        force_intent="run",
        session_id="t002-mh-sg",
    )
    assert hz_ok["wrote"] is True
    hz_text = Path(hz_ok["files"][0]["path"]).read_text(encoding="utf-8")
    assert "WSH" in hz_text and "PTW" in hz_text
    assert "37 号令" not in hz_text
    assert "可以开工" not in hz_text
    assert "信息不足" in hz_text
    hz_cn = run_expert_turn(
        "写一份危大判定书 37 号令 基坑",
        "method-hazard",
        confirm_ok=True,
        force_intent="run",
        session_id="t002-mh-cn",
    )
    cn_text = Path(hz_cn["files"][0]["path"]).read_text(encoding="utf-8")
    assert "37 号令" in cn_text
    assert "可以开工" not in cn_text

    cal = run_expert_turn("出一份税务日历", "finance-tax")
    assert cal["intent"] == "run" and cal["wrote"] is True
    assert "finance-tax__calendar" in cal["tools_run"]
    assert cal["files"] and Path(cal["files"][0]["path"]).is_file()
    cal_text = Path(cal["files"][0]["path"]).read_text(encoding="utf-8")
    assert "9%" in cal_text
    assert "空栏" in cal_text or "待按 IRAS" in cal_text
    assert "待填" in cal_text

    cost = run_expert_turn("写一份工程量拆分表 临边栏杆", "cost", session_id="t006-cost")
    assert cost["wrote"] is True
    assert "cost__takeoff" in cost["tools_run"]
    cost_text = Path(cost["files"][0]["path"]).read_text(encoding="utf-8")
    assert "综合单价" in cost_text and "合价" in cost_text
    assert "UNSPECIFIED" in cost_text

    sv_chat = run_expert_turn("测量点号怎么填？", "survey")
    assert sv_chat["intent"] == "chat" and sv_chat["wrote"] is False
    sv_empty = run_expert_turn(
        "写一份测量记录",
        "survey",
        confirm_ok=True,
        force_intent="run",
        session_id="t030-sv-empty",
    )
    assert sv_empty["wrote"] is True
    assert "survey__record" in sv_empty["tools_run"]
    sv_empty_text = Path(sv_empty["files"][0]["path"]).read_text(encoding="utf-8")
    for title in (
        "封面与文件控制",
        "已知起算",
        "放样内容",
        "复测与检核",
        "附录",
    ):
        assert title in sv_empty_text, title
    assert "[A001]" in sv_empty_text
    assert "CP99" not in sv_empty_text
    assert "可以开工" not in sv_empty_text
    sv_ok = run_expert_turn(
        "写一份测量记录 点号 CP01 东 12345.67 北 23456.89",
        "survey",
        confirm_ok=True,
        force_intent="run",
        session_id="t030-sv-cp01",
    )
    sv_ok_text = Path(sv_ok["files"][0]["path"]).read_text(encoding="utf-8")
    assert "CP01" in sv_ok_text
    assert "12345.67" in sv_ok_text
    assert "23456.89" in sv_ok_text

    dp_chat = run_expert_turn("调度日报怎么写？", "dispatch")
    assert dp_chat["intent"] == "chat" and dp_chat["wrote"] is False
    dp = run_expert_turn(
        "写一份调度日报 临边防护 白班",
        "dispatch",
        force_intent="run",
        session_id="t030-dp",
    )
    assert dp["wrote"] is True
    assert "dispatch__daily" in dp["tools_run"]
    dp_text = Path(dp["files"][0]["path"]).read_text(encoding="utf-8")
    for title in (
        "报头",
        "当日实际",
        "危大/高处/临边等敏感作业清单",
        "明日条件与待决策",
        "附件表头",
    ):
        assert title in dp_text, title
    assert "临边" in dp_text
    assert "method-hazard" in dp_text
    assert "可以开工" not in dp_text

    var_chat = run_expert_turn("签证单怎么填？", "variation")
    assert var_chat["intent"] == "chat" and var_chat["wrote"] is False
    var_empty = run_expert_turn(
        "写一份变更签证草稿",
        "variation",
        force_intent="run",
        session_id="t031-var-empty",
    )
    assert var_empty["wrote"] is True
    assert "variation__form" in var_empty["tools_run"]
    ve = Path(var_empty["files"][0]["path"]).read_text(encoding="utf-8")
    for title in ("文件类型判定", "事实栏", "依据栏", "签认栏", "自检"):
        assert title in ve, title
    assert "工程签证" in ve
    assert "变更编号待填" in ve or "待填" in ve
    assert "见图" not in ve
    assert "TBD" in ve
    assert "可以开工" not in ve
    var_no = run_expert_turn(
        "写一份变更签证 临边栏杆 变更编号 VO-12",
        "variation",
        force_intent="run",
        session_id="t031-var-vo",
    )
    vn = Path(var_no["files"][0]["path"]).read_text(encoding="utf-8")
    assert "VO-12" in vn
    assert "见图" not in vn

    cl_chat = run_expert_turn("索赔意向怎么写？", "claim")
    assert cl_chat["intent"] == "chat" and cl_chat["wrote"] is False
    cl_empty = run_expert_turn(
        "写一份索赔意向草稿",
        "claim",
        force_intent="run",
        session_id="t031-cl-empty",
    )
    assert cl_empty["wrote"] is True
    assert "claim__notice" in cl_empty["tools_run"]
    ce = Path(cl_empty["files"][0]["path"]).read_text(encoding="utf-8")
    for title in ("事件识别", "合同时钟", "意向通知必备", "证据清单", "调概专节"):
        assert title in ce, title
    assert "条款原文待贴" in ce
    assert "TBD" in ce
    assert "可以开工" not in ce
    cl_ev = run_expert_turn(
        "写一份索赔意向 图纸迟到 证据：监理通知 NCR-1；停工令 8 月 1 日",
        "claim",
        force_intent="run",
        session_id="t031-cl-ev",
    )
    cv = Path(cl_ev["files"][0]["path"]).read_text(encoding="utf-8")
    assert "监理通知 NCR-1" in cv or "NCR-1" in cv
    assert "停工令" in cv

    sub_chat = run_expert_turn("分包结算怎么填？", "subcontract")
    assert sub_chat["intent"] == "chat" and sub_chat["wrote"] is False
    sub_empty = run_expert_turn(
        "写一份分包结算草稿",
        "subcontract",
        force_intent="run",
        session_id="t031-sub-empty",
    )
    assert sub_empty["wrote"] is True
    assert "subcontract__sheet" in sub_empty["tools_run"]
    se = Path(sub_empty["files"][0]["path"]).read_text(encoding="utf-8")
    for title in ("本期完成", "合同内价款栏", "扣款表头", "农民工工资专节", "会签栏"):
        assert title in se, title
    assert "TBD" in se
    assert "可以开工" not in se
    sub_ok = run_expert_turn(
        "写一份分包结算 模板 120m2；钢筋 2.5t",
        "subcontract",
        force_intent="run",
        session_id="t031-sub-rows",
    )
    so = Path(sub_ok["files"][0]["path"]).read_text(encoding="utf-8")
    assert "模板" in so
    assert "120" in so
    assert "钢筋" in so
    assert "2.5" in so
    assert so.count("TBD") >= 2

    it_chat = run_expert_turn("验工计价怎么填？", "interim")
    assert it_chat["intent"] == "chat" and it_chat["wrote"] is False
    it_empty = run_expert_turn(
        "写一份验工计价草稿",
        "interim",
        force_intent="run",
        session_id="t031-it-empty",
    )
    assert it_empty["wrote"] is True
    assert "interim__measure" in it_empty["tools_run"]
    ie = Path(it_empty["files"][0]["path"]).read_text(encoding="utf-8")
    for title in ("本期范围", "计量草表", "监理审", "业主核", "报审签认"):
        assert title in ie, title
    assert "TBD" in ie
    assert "可以开工" not in ie
    assert "报审通过" not in ie
    it_ok = run_expert_turn(
        "写一份验工计价 模板 120m2",
        "interim",
        force_intent="run",
        session_id="t031-it-row",
    )
    io = Path(it_ok["files"][0]["path"]).read_text(encoding="utf-8")
    assert "模板" in io
    assert "120" in io
    assert "应付合价" in io or "不编应付" in io or "不编本期应付" in io


    high = [e for e in roster if e.risk == "high"][0]
    blocked = run_expert_turn("写一份专项方案讨论提纲", high.id, confirm_ok=False)
    assert blocked["intent"] == "run"
    assert blocked["wrote"] is False and blocked["hitl_pending"] is True
    okh = run_expert_turn("写一份专项方案讨论提纲", high.id, confirm_ok=True)
    assert okh["wrote"] is True

    pack = run_expert_turn("出一份装箱作业单 铁架", "pack-ship")
    assert pack["wrote"] is True
    ev = (pack.get("pack_ship") or {}).get("plan") or {}
    assert ev.get("can_fit") == "UNSPECIFIED"

    n_chat = n_run = 0
    for e in roster:
        c = run_expert_turn("这是什么意思，先别写", e.id)
        assert c["wrote"] is False, e.id
        n_chat += 1
        if e.risk == "high":
            r = run_expert_turn("写一份草稿提纲", e.id, confirm_ok=True, session_id=f"t-{e.id}")
        else:
            r = run_expert_turn("写一份草稿提纲", e.id, session_id=f"t-{e.id}")
        assert r["intent"] == "run", e.id
        assert r["wrote"] is True, e.id
        assert r["tools_run"], e.id
        n_run += 1
    assert n_chat == 66 and n_run == 66

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    listed = client.get("/api/experts")
    assert listed.status_code == 200
    assert listed.json()["n"] == 66
    ids = {e["id"] for e in listed.json()["experts"]}
    assert ids == {e.id for e in roster}
    http = client.post(
        "/api/turn",
        json={"text": "什么是 GST", "expert_id": "finance-tax"},
    )
    assert http.status_code == 200, http.text
    assert http.json().get("intent") == "chat"
    assert http.json().get("wrote") is False
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "expertSel" in index and "66 岗" in index
    assert exclusive_tools("pack-ship")
    print("PASS expert_turn", f"n={len(roster)} chat={n_chat} run={n_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
