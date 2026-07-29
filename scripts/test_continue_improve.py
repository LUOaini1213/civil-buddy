#!/usr/bin/env python3
"""继续改进验收：profiles + por_manifest + whatif apply + gap x_m。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import public_response, run_agent_pipeline
    from packing_assistant.packing_profiles import apply_profile, list_profiles
    from packing_assistant.tools.por_manifest import build_por_manifest
    from packing_assistant.whatif import run_whatif

    assert len(list_profiles()) >= 4
    opts = apply_profile({}, "strict_mid50")
    assert opts.get("r4_target_mid50") == 0.60
    assert opts.get("profile_id") == "strict_mid50"
    print("PASS profiles", opts.get("profile_id"))

    mats = []
    for i in range(6):
        mats.append(
            {
                "id": f"A{i}",
                "name": f"铁架{i}",
                "spec": "铁件",
                "part_no": f"FST{i:04d}",
                "quantity": 1,
                "weight_kg": 600,
                "total_weight_kg": 600,
                "length_mm": 1800,
                "width_mm": 1100,
                "height_mm": 1100,
                "note": "crate_equiv_est",
            }
        )
    for i in range(10):
        mats.append(
            {
                "id": f"B{i}",
                "name": f"轻箱{i}",
                "part_no": "BBF0001",
                "quantity": 1,
                "weight_kg": 50,
                "total_weight_kg": 50,
                "length_mm": 800,
                "width_mm": 600,
                "height_mm": 500,
                "note": "crate=",
            }
        )

    st = run_agent_pipeline(
        "continue improve",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id="cont-improve",
        packing_options=apply_profile(
            {"crate_passthrough": True, "multi_start": True, "cog_aware": True},
            "balanced",
        ),
    )
    pub = public_response(st)
    plan = pub.get("container_plan") or {}
    assert plan.get("can_fit") is True
    assert pub.get("team_mode") == "single_closed_loop"

    pm = pub.get("por_manifest") or build_por_manifest(
        plan, st.get("boxes") or [], mats
    )
    assert pm.get("by_part"), pm
    assert pm.get("by_container"), pm
    print("PASS por_manifest", pm.get("summary"))

    # gap sample 应带 x_m（若有空隙）
    lq = plan.get("layout_quality") or {}
    for g in lq.get("gap_samples") or []:
        if g.get("axis") == "x" and g.get("gap_mm", 0) > 150:
            assert "x_m" in g or "x_mm" in g
            print("PASS gap coords", g.get("x_m"), g.get("gap_mm"))
            break
    else:
        print("NOTE no large x-gap samples (ok for dense pack)")

    # whatif + 模拟 apply：result session 有 state
    r = run_whatif(st, scenario="strict_mid50", session_id="cont-improve")
    assert r.get("ok") and r.get("plan_diff")
    after = r.get("state")
    assert after is not None
    print("PASS whatif", r.get("scenario"), "narrative ok")

    print("ALL PASS continue improve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
