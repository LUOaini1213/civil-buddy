#!/usr/bin/env python3
"""
VMU1 工地当量箱 → 9 智能体（crate_passthrough，禁止二次标准箱撑外廓）。

期望：N0≈2、3D can_fit 接近 2，结构默认通过。

  python scripts/demo_vmu1_nine_passthrough.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_vmu1_site_only as site  # type: ignore
from packing_assistant.harness import apply_user_confirmation, make_initial_state
from packing_assistant.agents import (
    agent_box_scheme,
    agent_evaluator,
    agent_finalize,
    agent_loader,
    agent_material_parser,
    agent_orchestrator,
    agent_planner,
    agent_present_team_a,
    agent_risk_compliance,
    agent_structure,
    agent_visualizer,
)


def main() -> int:
    if not site.SITE_XLSX.exists():
        print("MISSING", site.SITE_XLSX)
        return 1
    rows = site.load_site_rows(site.SITE_XLSX)
    mats, _ = site.to_materials(rows)
    print(f"materials={len(mats)} net≈{sum(m['total_weight_kg'] for m in mats):.0f}kg")

    state = make_initial_state(
        user_input="VMU1 工地当量直通 9智能体 自主定柜",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        max_containers=0,
        session_id="vmu1-passthrough-nine",
    )
    # 关键：当量直通
    state["packing_options"] = {
        "crate_passthrough": True,
        "standard_boxes": False,
        "mix_mode": False,
    }

    agents = [
        ("orchestrator", agent_orchestrator),
        ("material_parser", agent_material_parser),
        ("structure", agent_structure),
        ("box_scheme", agent_box_scheme),
        ("present_team_a", agent_present_team_a),
        ("planner", agent_planner),
        ("loader", agent_loader),
        ("evaluator", agent_evaluator),
        ("risk_compliance", agent_risk_compliance),
        ("visualizer", agent_visualizer),
        ("finalize", agent_finalize),
    ]
    steps = []
    t0 = time.time()
    for name, fn in agents:
        upd = fn(state) or {}
        for k, v in upd.items():
            if k in ("messages", "traces", "errors", "validation_warnings") and isinstance(
                v, list
            ):
                state[k] = list(state.get(k) or []) + v
            else:
                state[k] = v
        if name == "present_team_a":
            state = apply_user_confirmation(
                state, action="confirm", container_type="40HQ", max_containers=0
            )
        last = ""
        for m in reversed(state.get("messages") or []):
            if m.get("content"):
                last = str(m["content"])
                break
        print(f"[{name}] {last[:120]}")
        steps.append({"agent": name, "message": last[:400]})

    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    summary = {
        "mode": "crate_passthrough+9agents",
        "materials": len(mats),
        "boxes": len(state.get("boxes") or []),
        "n0": book.get("n0") or plan.get("n0"),
        "n_weight": book.get("containers_by_weight"),
        "n_volume": book.get("containers_by_volume"),
        "binding": book.get("binding_constraint"),
        "containers_used": plan.get("containers_used"),
        "can_fit": plan.get("can_fit"),
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "risk": (state.get("risk_report") or {}).get("decision"),
        "ms": int((time.time() - t0) * 1000),
    }
    print("SUMMARY", json.dumps(summary, ensure_ascii=False))
    # 验收：N0 应约为 2，3D 不宜再飙到 9
    n0 = int(summary.get("n0") or 0)
    used = int(summary.get("containers_used") or 0)
    if n0 > 3 or used > 4:
        print("WARN: N0/used 仍偏高，请查当量直通是否生效")
    else:
        print("OK: Agent 路径柜数与订舱同量级")

    out = ROOT / "output" / "vmu1_nine_passthrough.json"
    out.write_text(
        json.dumps({"summary": summary, "steps": steps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
