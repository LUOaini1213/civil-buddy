#!/usr/bin/env python3
"""生成并跑 60t 随机物料主用例（crate_passthrough + CoG 闭环）。

  python scripts/run_t60_main.py
  python scripts/run_t60_main.py --seed 20260729
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "output" / "t60_main_run.json"
SID = "t60-main"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260760, help="独立种子，避免覆盖 t80 主用例")
    ap.add_argument("--target-t", type=float, default=60.0)
    ap.add_argument("--skip-gen", action="store_true")
    args = ap.parse_args()

    if not args.skip_gen:
        rc = subprocess.call(
            [
                sys.executable,
                str(ROOT / "scripts" / "gen_80t_materials.py"),
                "--only-random",
                "--target-t",
                str(args.target_t),
                "--seed",
                str(args.seed),
            ],
            cwd=str(ROOT),
        )
        if rc != 0:
            return rc

    case_id = f"t80_random_mixed_s{args.seed}"
    case = ROOT / "test" / "sim_materials" / case_id / "materials.json"
    if not case.exists():
        print("missing", case)
        return 1

    data = json.loads(case.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    net_t = data.get("net_t") or sum(float(m.get("total_weight_kg") or 0) for m in mats) / 1000
    print(f"case={case_id} net={net_t}t lines={len(mats)} → pipeline…")

    from packing_assistant.agents.box_scheme import agent_box_scheme
    from packing_assistant.agents.risk_compliance import agent_risk_compliance
    from packing_assistant.harness import public_response, run_agent_pipeline
    from packing_assistant.session_store import save_session
    from packing_assistant.tools.bin3d import pack_boxes_api

    # —— 快速装载门禁（与 t80 P0 同门槛）——
    boxes = agent_box_scheme(
        {
            "materials": mats,
            "packing_options": {"crate_passthrough": True},
            "container_type": "40HQ",
        }
    )["boxes"]
    t0 = time.time()
    pack = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=10,
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
    pack_ms = int((time.time() - t0) * 1000)
    cog_p = pack.get("cog") or {}
    mid_p = float(pack.get("worst_mid50") or 0)
    lat_p = float(cog_p.get("lateral_eccentricity") or 0)
    risk_p = agent_risk_compliance(
        {
            "boxes": boxes,
            "container_plan": pack,
            "evaluation": {},
            "packing_options": {"export_strict": False},
        }
    )
    ship_pack = bool(
        risk_p.get("ship_ok") or (risk_p.get("risk_report") or {}).get("ship_ok")
    )
    print(
        f"[pack] can_fit={pack.get('can_fit')} used={pack.get('containers_used')} "
        f"unpacked={len(pack.get('unpacked_box_ids') or [])} "
        f"mid50={mid_p:.4f} lat={lat_p:.4f} ship_ok={ship_pack} ms={pack_ms}"
    )
    pack_ok = (
        pack.get("can_fit")
        and not pack.get("unpacked_box_ids")
        and mid_p + 1e-9 >= 0.55
        and lat_p <= 0.08 + 1e-9
        and ship_pack
    )
    print("[pack]", "PASS" if pack_ok else "FAIL")

    # —— 9 智能体闭环 ——
    st = run_agent_pipeline(
        f"随机{args.target_t:.0f}t主用例装柜 {case_id}",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id=SID,
        save_artifacts=True,
        packing_options={
            "prefer_stack": True,
            "dense_mode": True,
            "crate_passthrough": True,
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
    cog = pub.get("cog") or plan.get("cog") or {}
    if not isinstance(cog, dict):
        cog = {}
    ev = pub.get("evaluation") or {}
    rr = pub.get("risk_report") or {}
    stak = plan.get("stacking") or {}
    swo = pub.get("secure_work_order") or {}
    pp = pub.get("packing_plan") or {}

    summary = {
        "case": case_id,
        "target_t": args.target_t,
        "net_t": net_t,
        "n_material_lines": len(mats),
        "boxes": len(pub.get("boxes") or []),
        "pack_gate": {
            "can_fit": pack.get("can_fit"),
            "containers_used": pack.get("containers_used"),
            "worst_mid50": mid_p,
            "lat": lat_p,
            "ship_ok": ship_pack,
            "ms": pack_ms,
            "pass": pack_ok,
        },
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
        "worst_mid50": plan.get("worst_mid50") or pub.get("worst_mid50"),
        "cog": {
            "mass_in_mid50_ratio": cog.get("mass_in_mid50_ratio"),
            "lateral_eccentricity": cog.get("lateral_eccentricity"),
            "longitudinal_position": cog.get("longitudinal_position"),
            "balance": cog.get("balance"),
        },
        "stacking": {
            "multi_start_winner": stak.get("multi_start_winner"),
            "lns_applied": stak.get("lns_applied"),
            "lateral_repair_applied": stak.get("lateral_repair_applied"),
            "stacked_placements": stak.get("stacked_placements"),
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
            "blockers": (rr.get("blockers") or [])[:6],
            "ship_ok": rr.get("ship_ok") if rr.get("ship_ok") is not None else pub.get("ship_ok"),
        },
        "secure_work_order_n": len((swo.get("items") or [])),
        "per_cabin_n": len((pp.get("per_cabin_cog") or [])),
        "r_pipeline": [r.get("step") for r in (pp.get("r_pipeline") or [])],
        "ship_ok": pub.get("ship_ok"),
        "phase": pub.get("phase") or st.get("phase"),
        "session_id": SID,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- RESULT ---")
    print(
        f"boxes={summary['boxes']} used={summary['containers_used']} "
        f"n0={summary['n0']} can_fit={summary['can_fit']}"
    )
    print(
        f"booking={summary['booking_volume_utilization']} "
        f"outer={summary['outer_space_utilization']} "
        f"weight={summary['weight_utilization']}"
    )
    print(
        f"cog mid50={summary['worst_mid50']} "
        f"lat={summary['cog'].get('lateral_eccentricity')} "
        f"long={summary['cog'].get('longitudinal_position')} "
        f"bal={summary['cog'].get('balance')}"
    )
    print(
        f"eval={summary['evaluation']} risk={summary['risk']} "
        f"ship_ok={summary['ship_ok']} phase={summary['phase']}"
    )
    print(f"secure_items={summary['secure_work_order_n']} cabins={summary['per_cabin_n']}")
    print("summary →", OUT)

    pipe_ok = (
        summary.get("can_fit")
        and float(summary.get("worst_mid50") or 0) + 1e-9 >= 0.55
        and float((summary.get("cog") or {}).get("lateral_eccentricity") or 0) <= 0.08 + 1e-9
        and summary.get("ship_ok")
    )
    print("---", "PASS" if (pack_ok and pipe_ok) else "FAIL", "(pack+pipeline)")
    return 0 if (pack_ok and pipe_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
