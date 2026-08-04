#!/usr/bin/env python3
"""446t：捷径 Tool vs 全 Agent 对照（利用率 / mid50 / 策略决策）。

  python scripts/compare_446t_agent_vs_tool.py
  python scripts/compare_446t_agent_vs_tool.py --full-agent
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

OPTS = {
    "crate_passthrough": True,
    "prefer_stack": True,
    "multi_start": True,
    "cog_aware": True,
    "cog_rebalance": True,
    "standard_boxes": False,
    "dense_mode": True,
}


def _mid(plan: dict) -> float | None:
    from packing_assistant.tools.booking import _plan_worst_mid50

    return _plan_worst_mid50(plan)


def run_tool(mats: list) -> dict:
    from packing_assistant.agents.box_scheme import agent_box_scheme
    from packing_assistant.tools.booking import pack_with_auto_containers

    t0 = time.time()
    out = agent_box_scheme(
        {"materials": mats, "packing_options": dict(OPTS), "messages": []}
    )
    boxes = out.get("boxes") or []
    plan = pack_with_auto_containers(
        boxes,
        container_type="40HQ",
        n_max=50,
        packing_options=dict(OPTS),
    )
    return {
        "path": "tool_shortcut",
        "wall_s": round(time.time() - t0, 1),
        "n_boxes": len(boxes),
        "mode": (out.get("team_a_summary") or {}).get("packing_mode"),
        "can_fit": plan.get("can_fit"),
        "n0": plan.get("n0"),
        "used": plan.get("containers_used"),
        "weight_util": plan.get("weight_utilization"),
        "mid50": _mid(plan),
        "density_mode": plan.get("density_mode"),
        "reference_light_used": plan.get("reference_light_used"),
        "strategy": (plan.get("strategy_decision") or {}).get("chosen"),
        "strategy_reason": (plan.get("strategy_decision") or {}).get("reason"),
        "candidates": (plan.get("strategy_decision") or {}).get("candidates")
        or plan.get("strategy_candidates"),
        "explain": plan.get("multi_container_explain"),
        "light_ship_forbidden": plan.get("density_mode")
        not in ("light_lb_fallback", "min_bins_light")
        or bool((plan.get("strategy_decision") or {}).get("chosen") not in (
            "min_bins_light",
            "light_lb_fallback",
        )),
    }


def run_full(mats: list) -> dict:
    from packing_assistant.harness import run_agent_pipeline, public_response

    t0 = time.time()
    st = run_agent_pipeline(
        "case_446t_full_agent",
        materials=mats,
        packing_options=dict(OPTS),
        max_containers=0,
        enable_auto_confirm=True,
        session_id="compare-446t-full-agent",
        save_artifacts=True,
    )
    plan = st.get("container_plan") or {}
    pub = public_response(st) or {}
    sd = pub.get("strategy_decision") or plan.get("strategy_decision") or {}
    return {
        "path": "full_agent_pipeline",
        "wall_s": round(time.time() - t0, 1),
        "phase": st.get("phase"),
        "n_boxes": len(st.get("boxes") or []),
        "mode": (st.get("team_a_summary") or {}).get("packing_mode"),
        "can_fit": plan.get("can_fit"),
        "n0": plan.get("n0"),
        "used": plan.get("containers_used"),
        "weight_util": plan.get("weight_utilization"),
        "mid50": _mid(plan),
        "density_mode": plan.get("density_mode"),
        "reference_light_used": plan.get("reference_light_used"),
        "strategy": sd.get("chosen") or (plan.get("strategy_decision") or {}).get("chosen"),
        "strategy_reason": sd.get("reason")
        or (plan.get("strategy_decision") or {}).get("reason"),
        "candidates": sd.get("candidates")
        or (plan.get("strategy_decision") or {}).get("candidates"),
        "explain": plan.get("multi_container_explain"),
        "verdict": (st.get("verdict") or {}).get("level")
        if isinstance(st.get("verdict"), dict)
        else None,
        "strategy_public_show": bool(sd.get("show") or sd.get("chosen")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-agent", action="store_true", help="也跑全 Agent（~2–3min）")
    ap.add_argument("--tool-only", action="store_true", help="只跑 Tool 捷径")
    args = ap.parse_args()

    mats_path = ROOT / "output" / "cases_446t" / "materials.json"
    mats = json.loads(mats_path.read_text(encoding="utf-8"))
    if isinstance(mats, dict):
        mats = mats.get("materials") or []

    rows = []
    print("=== tool shortcut ===")
    tool = run_tool(mats)
    rows.append(tool)
    print(json.dumps(tool, ensure_ascii=False, indent=2))

    if args.full_agent and not args.tool_only:
        print("=== full agent ===")
        full = run_full(mats)
        rows.append(full)
        print(json.dumps(full, ensure_ascii=False, indent=2))

    out = {
        "rows": rows,
        "baseline_old": {"used": 29, "weight_util": 0.5948},
        "baseline_shortcut_prev": {"used": 21, "weight_util": 0.766},
        "baseline_full_prev": {"used": 24, "weight_util": 0.7187, "mid50": 0.16},
    }
    path = ROOT / "output" / "cases_446t" / "result_compare_live.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", path)

    # 硬断言：不得 light 直接 ship
    for r in rows:
        dm = r.get("density_mode")
        st = r.get("strategy")
        if dm in ("light_lb_fallback",) or st in ("min_bins_light", "light_lb_fallback"):
            # strategy chosen light is fail
            if st in ("min_bins_light", "light_lb_fallback"):
                print("FAIL: light strategy chosen as ship", r.get("path"))
                return 1
        if r.get("path") == "tool_shortcut" and not r.get("strategy"):
            print("WARN: no strategy_decision on tool path")
    print("OK compare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
