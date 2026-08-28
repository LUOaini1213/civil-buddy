#!/usr/bin/env python3
"""单 Team 有界闭环：状态标记 + 小票能跑通 pipeline。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import public_response, run_agent_pipeline

    mats = [
        {
            "id": "M1",
            "name": "铁架试块",
            "spec": "13—铁件",
            "quantity": 1,
            "weight_kg": 400,
            "total_weight_kg": 400,
            "length_mm": 2000,
            "width_mm": 1100,
            "height_mm": 1100,
            "note": "crate_equiv_est",
        },
        {
            "id": "M2",
            "name": "五金箱",
            "spec": "23—紧固件",
            "quantity": 1,
            "weight_kg": 80,
            "total_weight_kg": 80,
            "length_mm": 800,
            "width_mm": 600,
            "height_mm": 500,
            "note": "crate=",
        },
    ]
    st = run_agent_pipeline(
        "单Team闭环冒烟",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id="test-single-team",
        packing_options={
            "crate_passthrough": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
    )
    assert st.get("team_mode") == "big_team_a_b", st.get("team_mode")
    pub = public_response(st)
    assert pub.get("team_mode") == "big_team_a_b"
    plan = pub.get("container_plan") or {}
    assert plan.get("can_fit") is True, plan
    # 闭环字段存在
    assert "replan_round" in pub or st.get("replan_round") is not None
    print(
        "PASS single_team_loop",
        "team_mode=",
        st.get("team_mode"),
        "loop_round=",
        st.get("team_loop_round"),
        "can_fit=",
        plan.get("can_fit"),
        "ship_ok=",
        pub.get("ship_ok"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
