#!/usr/bin/env python3
"""P1-1: bid-parse writes tender.handoff.json; compliance 3-col; tech uses scores."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SAMPLE = """一、投标人须具备建筑工程施工资质。
二、货物须铁架包装。
三、未实质性响应作废标。
四、交货期 90 个日历天。
五、技术标评分：施工组织设计 25 分、项目管理机构 10 分。
六、★深基坑专项方案须编制。
"""


def main() -> int:
    from packing_assistant.expert_turn import run_expert_turn
    from packing_assistant.runtime.session_handoff import handoff_path, load_handoff

    sid = "handoff-p1"
    parse = run_expert_turn(SAMPLE, "bid-parse", session_id=sid, force_intent="run")
    assert parse["wrote"] is True
    assert parse.get("submit_blocked") is True
    assert "tender.handoff" in (parse.get("tools_run") or [])
    p = handoff_path(sid)
    assert p.is_file(), p
    ho = json.loads(p.read_text(encoding="utf-8"))
    assert ho.get("schema") == "tender.handoff.v1"
    assert ho.get("p0_reject_scan", {}).get("human_confirm_required") is True
    assert load_handoff(sid)

    comp = run_expert_turn("出一份废标检查对照", "bid-compliance", session_id=sid, force_intent="run")
    assert comp["wrote"] is True
    assert "bid-compliance__gaps" in (comp.get("tools_run") or [])
    gaps = Path(comp["files"][0]["path"]).read_text(encoding="utf-8")
    assert "已响应" in gaps and "未响应" in gaps and "招标未提供" in gaps
    assert "可以投标" not in gaps

    tech = run_expert_turn("出一份技术标目录", "bid-tech", session_id=sid, force_intent="run")
    assert tech["wrote"] is True
    outline = tech.get("tech_outline") or {}
    assert outline.get("from_extracted_scores") is True
    md = Path(tech["files"][0]["path"]).read_text(encoding="utf-8")
    assert "施工组织设计" in md or "评分" in md
    assert "可以开工" not in md

    empty = run_expert_turn("出一份技术标目录", "bid-tech", session_id="handoff-empty", force_intent="run")
    o2 = empty.get("tech_outline") or {}
    assert o2.get("from_extracted_scores") is False
    md2 = Path(empty["files"][0]["path"]).read_text(encoding="utf-8")
    assert "禁止套上个项目" in md2 or "未检出评分点" in (empty.get("reply") or "")

    print("PASS tender_handoff parse+compliance+tech")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
