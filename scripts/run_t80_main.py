#!/usr/bin/env python3
"""跑 t80 主用例全流程 pipeline。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASE = ROOT / "test" / "sim_materials" / "t80_random_mixed_s20260729" / "materials.json"
OUT = ROOT / "output" / "t80_main_run.json"
SID = "t80-main"


def main() -> int:
    if not CASE.exists():
        print("missing", CASE)
        print("run: python scripts/gen_80t_materials.py --seed 20260729")
        return 1

    data = json.loads(CASE.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    print(
        f"case={data.get('case_id')} net={data.get('net_t')}t "
        f"lines={len(mats)} → pipeline…"
    )

    from packing_assistant.harness import public_response, run_agent_pipeline
    from packing_assistant.session_store import save_session

    st = run_agent_pipeline(
        "随机80t主用例装柜 t80_random_mixed_s20260729",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id=SID,
        save_artifacts=True,
        packing_options={
            "prefer_stack": True,
            "dense_mode": True,
            "crate_passthrough": True,  # 80t 仿真：避免结构校核卡死，直通成箱
            "standard_boxes": False,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r1_shift": True,
            "r4_repair": True,
            "r4_target_mid50": 0.55,
            "lns_worst": True,
            "lateral_repair": True,
            "lat_threshold": 0.08,
            "clearance_mm": 30,
            "max_box_net_kg": 5000,
            "export_strict": False,
        },
    )
    save_session(SID, st)
    pub = public_response(st)

    plan = pub.get("container_plan") or {}
    vs = pub.get("volume_summary") or {}
    pp = pub.get("packing_plan") or {}
    cog = pub.get("cog") or plan.get("cog") or (pp.get("cog") if isinstance(pp, dict) else {}) or {}
    if not isinstance(cog, dict):
        cog = {}
    stak = plan.get("stacking") or (pp.get("stacking") if isinstance(pp, dict) else {}) or {}
    lq = plan.get("layout_quality") or {}
    ev = pub.get("evaluation") or {}
    rr = pub.get("risk_report") or {}
    seq = pub.get("load_sequence") or {}
    vgm = pub.get("vgm_draft") or {}
    gates = pub.get("hitl_gates") or {}

    summary = {
        "case": data.get("case_id"),
        "net_t": data.get("net_t"),
        "n_material_lines": len(mats),
        "boxes": len(pub.get("boxes") or []),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0") or vs.get("n0"),
        "can_fit": plan.get("can_fit"),
        "engine": plan.get("engine"),
        "booking_volume_utilization": vs.get("booking_volume_utilization")
        or plan.get("booking_volume_utilization"),
        "outer_space_utilization": vs.get("outer_space_utilization")
        or plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization") or vs.get("weight_utilization"),
        "stacking": stak,
        "r1_shift": plan.get("r1_shift"),
        "worst_mid50": plan.get("worst_mid50") or pub.get("worst_mid50"),
        "cog": {
            "mass_in_mid50_ratio": cog.get("mass_in_mid50_ratio"),
            "mid50_ok": cog.get("mid50_ok"),
            "longitudinal_position": cog.get("longitudinal_position"),
            "lateral_eccentricity": cog.get("lateral_eccentricity"),
            "height_ratio": cog.get("height_ratio"),
            "balance": cog.get("balance"),
        },
        "layout_quality": {
            "max_horizontal_gap_mm": lq.get("max_horizontal_gap_mm"),
            "gaps_over_limit": lq.get("gaps_over_limit"),
            "stackable_floor_only": lq.get("stackable_floor_only"),
            "concentrated_n": len(lq.get("concentrated_load_flags") or []),
        },
        "evaluation": {
            "score": ev.get("score"),
            "decision": ev.get("decision"),
            "need_replan": ev.get("need_replan"),
            "passed": ev.get("passed"),
        },
        "risk": {
            "decision": rr.get("decision"),
            "level": rr.get("level"),
            "blockers": (rr.get("blockers") or [])[:8],
        },
        "hitl_gates": {
            "require_hitl": gates.get("require_hitl"),
            "can_auto_confirm": gates.get("can_auto_confirm"),
            "summary": gates.get("summary"),
        },
        "load_sequence_steps": len(seq.get("steps") or []),
        "vgm_status": vgm.get("status"),
        "vgm_totals": vgm.get("totals"),
        "packing_plan_id": pp.get("plan_id"),
        "packing_plan_version": pp.get("version"),
        "ship_ok": pub.get("ship_ok"),
        "phase": pub.get("phase"),
        "goal_status": pub.get("goal_status"),
        "session_id": SID,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- RESULT ---")
    print(f"boxes={summary['boxes']} used={summary['containers_used']} n0={summary['n0']} can_fit={summary['can_fit']}")
    print(f"engine={summary['engine']}")
    print(
        f"booking={summary['booking_volume_utilization']} "
        f"outer={summary['outer_space_utilization']} weight={summary['weight_utilization']}"
    )
    print(
        f"stack={stak.get('stacked_placements')} max_z={stak.get('max_z_mm')} "
        f"winner={stak.get('multi_start_winner')}"
    )
    print(
        f"cog mid50={summary['cog'].get('mass_in_mid50_ratio')} "
        f"worst_mid50={summary.get('worst_mid50')} "
        f"long={summary['cog'].get('longitudinal_position')} bal={summary['cog'].get('balance')}"
    )
    r1 = summary.get("r1_shift") or {}
    if r1:
        print(f"R1 shifts={r1.get('per_container')}")
    print(
        f"gap={summary['layout_quality'].get('max_horizontal_gap_mm')} "
        f"eval={summary['evaluation']} risk={summary['risk']}"
    )
    print(
        f"load_steps={summary['load_sequence_steps']} vgm={summary['vgm_status']} "
        f"ship_ok={summary['ship_ok']} phase={summary['phase']}"
    )
    print(f"session={SID}")
    print(f"summary → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
