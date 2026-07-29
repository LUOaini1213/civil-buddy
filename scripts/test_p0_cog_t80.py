#!/usr/bin/env python3
"""P0 合规验收：t80 worst mid50≥0.55，lat≤0.08，can_fit + ship_ok。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASE = ROOT / "test" / "sim_materials" / "t80_random_mixed_s20260729" / "materials.json"


def main() -> int:
    from packing_assistant.agents.box_scheme import agent_box_scheme
    from packing_assistant.agents.risk_compliance import agent_risk_compliance
    from packing_assistant.tools.bin3d import pack_boxes_api

    if not CASE.exists():
        print("SKIP missing", CASE)
        return 0

    mats = json.loads(CASE.read_text(encoding="utf-8")).get("materials") or []
    boxes = agent_box_scheme(
        {
            "materials": mats,
            "packing_options": {"crate_passthrough": True},
            "container_type": "40HQ",
        }
    )["boxes"]
    print(f"boxes={len(boxes)} packing…")
    t0 = time.time()
    plan = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=12,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r0_r1": True,
            "r2_slab": True,
            "r4_repair": True,
            "lns_worst": True,
            "lateral_repair": True,
            "r4_target_mid50": 0.55,
            "lat_threshold": 0.08,
            "clearance_mm": 30,
        },
    )
    ms = int((time.time() - t0) * 1000)
    cog = plan.get("cog") or {}
    mid = float(plan.get("worst_mid50") or 0)
    lat = float(cog.get("lateral_eccentricity") or 0)
    can_fit = bool(plan.get("can_fit"))
    unp = len(plan.get("unpacked_box_ids") or [])

    risk = agent_risk_compliance(
        {
            "boxes": boxes,
            "container_plan": plan,
            "evaluation": {},
            "packing_options": {"export_strict": False},
        }
    )
    ship_ok = bool(risk.get("ship_ok") or (risk.get("risk_report") or {}).get("ship_ok"))
    decision = (risk.get("risk_report") or {}).get("decision")

    print(
        f"can_fit={can_fit} used={plan.get('containers_used')} unpacked={unp} "
        f"worst_mid50={mid:.4f} lat={lat:.4f} ship_ok={ship_ok} risk={decision} ms={ms}"
    )
    st = plan.get("stacking") or {}
    print(
        "stack",
        {
            k: st.get(k)
            for k in (
                "lns_applied",
                "lns_mid50_after",
                "lateral_repair_applied",
                "lat_after",
                "multi_start_winner",
                "multi_start_n",
            )
        },
    )

    ok = (
        can_fit
        and unp == 0
        and mid + 1e-9 >= 0.55
        and lat <= 0.08 + 1e-9
        and ship_ok
    )
    print("---", "PASS" if ok else "FAIL")
    if not ok:
        if mid < 0.55:
            print("  FAIL mid50", mid)
        if lat > 0.08:
            print("  FAIL lat", lat)
        if not can_fit or unp:
            print("  FAIL fit", can_fit, unp)
        if not ship_ok:
            print("  FAIL ship_ok", decision, (risk.get("risk_report") or {}).get("blockers")[:3])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
