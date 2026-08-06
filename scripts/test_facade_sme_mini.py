#!/usr/bin/env python3
"""Facade SME mini pipeline: glass note enrich + pack path (competition narrative)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main() -> int:
    from packing_assistant.tools.nl_nonstandard_enrich import enrich_materials
    from packing_assistant.tools.nonstandard_inspect import inspect_nonstandard
    from packing_assistant.teams.big_team import run_big_team

    # 4 架对称 + 少量玻璃备注：既测 enrich，又避免 lat≥15% 硬拦出运
    mats = [
        {
            "name": f"1.1m 铁架 #{i}",
            "length_mm": 1100,
            "width_mm": 1100,
            "height_mm": 1750,
            "weight_kg": 400,
            "quantity": 1,
            "total_weight_kg": 400,
        }
        for i in range(4)
    ] + [
        {
            "name": "中空玻璃 易碎",
            "note": "禁翻 向上",
            "length_mm": 1800,
            "width_mm": 1000,
            "height_mm": 40,
            "weight_kg": 60,
            "quantity": 2,
            "total_weight_kg": 120,
        },
    ]
    en = enrich_materials(mats)
    glass = next(m for m in en if "玻璃" in str(m.get("name") or ""))
    assert glass.get("fragile") is True, glass
    rep = inspect_nonstandard(materials=en, container_type="40HQ", case_id="facade-sme")
    assert rep.get("overall") in ("PASS", "WARN", "NEED_DESIGN", "FAIL")

    st = run_big_team(
        raw_input="幕墙项目物料装柜，玻璃易碎禁翻，尽量 1 柜 40HQ",
        materials=en,
        container_type="40HQ",
        max_containers=2,
        enable_auto_confirm=True,
        session_id="facade-sme-mini",
        save_artifacts=False,
    )
    plan = st.get("container_plan") or {}
    steps = st.get("agent_steps") or []
    nodes = {str(s.get("node")) for s in steps if isinstance(s, dict)}
    assert "box_scheme" in nodes or any("team_a" in n for n in nodes), nodes
    assert "loader" in nodes or any("team_b" in n or "planner" in n for n in nodes), nodes
    # 装下 ≠ 可出运：横向偏心/风险 REJECT 时 phase 可为 need_revision
    assert plan.get("can_fit") is True, plan
    assert len(steps) >= 8, len(steps)
    print(
        "PASS facade_sme_mini",
        "can_fit=", plan.get("can_fit"),
        "used=", plan.get("containers_used"),
        "ship_ok=", st.get("ship_ok"),
        "ns=", rep.get("overall"),
        "n_steps=", len(steps),
        "phase=", st.get("phase"),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
