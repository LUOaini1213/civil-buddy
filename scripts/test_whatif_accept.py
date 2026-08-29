#!/usr/bin/env python3
"""验收：What-if + plan_diff + 侧视图工单标注 + 单Team 标记。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import run_agent_pipeline
    from packing_assistant.whatif import list_whatif_scenarios, run_whatif
    from packing_assistant.tools.visualize import draw_layout_multi
    from packing_assistant.tools.secure_work_order import build_secure_work_order

    mats = [
        {
            "id": f"H{i}",
            "name": f"铁架-{i}",
            "spec": "13—铁件",
            "quantity": 1,
            "weight_kg": 500 + i * 20,
            "total_weight_kg": 500 + i * 20,
            "length_mm": 2000,
            "width_mm": 1100,
            "height_mm": 1100,
            "note": "crate_equiv_est",
        }
        for i in range(8)
    ] + [
        {
            "id": f"L{i}",
            "name": f"轻箱-{i}",
            "spec": "杂项",
            "quantity": 1,
            "weight_kg": 60,
            "total_weight_kg": 60,
            "length_mm": 1000,
            "width_mm": 800,
            "height_mm": 600,
            "note": "crate=",
        }
        for i in range(12)
    ]

    base = run_agent_pipeline(
        "whatif accept baseline",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id="whatif-accept-base",
        packing_options={
            "crate_passthrough": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
    )
    # 66 岗重塑后统一为大 Team A/B 闭环（曾为 single_closed_loop）
    assert base.get("team_mode") in ("big_team_a_b", "single_closed_loop"), base.get("team_mode")
    plan = base.get("container_plan") or {}
    assert plan.get("can_fit") is True
    used = int(plan.get("containers_used") or 1)
    print("base used=", used, "n0=", plan.get("n0"), "ship_ok=", base.get("ship_ok"))

    # 侧视图 + 工单标注
    swo = build_secure_work_order(plan, base.get("boxes") or [])
    plan2 = dict(plan)
    plan2["secure_work_order"] = swo
    multi = draw_layout_multi(plan2, container_type="40HQ", output_dir="output", prefix="whatif_accept")
    assert multi.get("primary_path") or multi.get("per_container"), multi
    print("PASS side annotate", multi.get("primary_path") or multi.get("overview_path"))

    # What-if：锁柜 = 当前 used
    r = run_whatif(
        base,
        scenario="lock_containers",
        max_containers=used,
        session_id="whatif-accept",
    )
    assert r.get("ok"), r
    assert r.get("plan_diff"), r
    assert "narrative" in r["plan_diff"]
    print("PASS whatif lock", r["plan_diff"].get("narrative", "")[:200])

    r2 = run_whatif(base, scenario="strict_mid50", session_id="whatif-accept")
    assert r2.get("ok")
    print(
        "PASS whatif strict_mid50",
        "mid",
        (r2.get("before") or {}).get("worst_mid50"),
        "→",
        (r2.get("after") or {}).get("worst_mid50"),
    )

    assert len(list_whatif_scenarios()) >= 5
    print("ALL PASS whatif accept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
