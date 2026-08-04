#!/usr/bin/env python3
"""多柜诊断表：N0* / used / 末柜 / 成箱模式。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")


def _run(name: str, mats: list, opts: dict | None = None, maxc: int = 0) -> dict:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    st = run_agent_pipeline(
        name,
        materials=mats,
        packing_options=opts
        or {
            "standard_boxes": True,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
        max_containers=maxc,
        enable_auto_confirm=True,
        session_id=f"diag-mc-{name[:24]}",
        save_artifacts=False,
    )
    plan = st.get("container_plan") or {}
    book = plan.get("booking") or st.get("booking") or {}
    last = plan.get("last_container_stats") or {}
    ta = st.get("team_a_summary") or {}
    return {
        "name": name,
        "ms": int((time.time() - t0) * 1000),
        "n_boxes": len(st.get("boxes") or []),
        "mode": ta.get("packing_mode") or ta.get("multi_risk"),
        "can_fit": plan.get("can_fit"),
        "n0": plan.get("n0") or book.get("n0"),
        "n0_note": plan.get("n0_note") or book.get("n0_note"),
        "used": plan.get("containers_used"),
        "n0_gap": plan.get("n0_gap"),
        "merged_ok": plan.get("merged_ok"),
        "residual": plan.get("residual_last_container"),
        "last_boxes": last.get("n_boxes"),
        "last_floor": last.get("floor_utilization"),
        "explain": plan.get("multi_container_explain"),
        "comps": plan.get("n0_components") or book.get("n0_components"),
    }


def main() -> int:
    rows = []
    # 1) 模块 8 件 — 应当量直通，used≤2
    mats = [
        {
            "id": f"M{i}",
            "name": f"模块{i}",
            "quantity": 1,
            "length_mm": 2800,
            "width_mm": 1100,
            "height_mm": 1000,
            "total_weight_kg": 2800,
            "weight_kg": 2800,
        }
        for i in range(8)
    ]
    rows.append(_run("modules_8_std_default", mats))
    rows.append(
        _run(
            "modules_8_dense",
            mats,
            {"standard_boxes": False, "dense_mode": True, "prefer_stack": True},
        )
    )

    # 2) near_payload
    p = ROOT / "test" / "sim_materials" / "near_payload" / "materials.json"
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        mats2 = data if isinstance(data, list) else data.get("materials") or []
        rows.append(_run("near_payload", mats2))

    # 3) weight_bound sample
    p2 = ROOT / "test" / "sim_materials" / "weight_bound_32t" / "materials.json"
    if p2.is_file():
        data = json.loads(p2.read_text(encoding="utf-8"))
        mats3 = data if isinstance(data, list) else data.get("materials") or []
        rows.append(_run("weight_bound_32t", mats3[:80] if len(mats3) > 80 else mats3))

    print(
        f"{'name':22} {'boxes':>5} {'mode':16} {'fit':4} {'N0*':>4} {'used':>4} "
        f"{'gap':>4} {'lastB':>5} {'merge':5} ms"
    )
    for r in rows:
        print(
            f"{r['name'][:22]:22} {r['n_boxes']:5} {str(r.get('mode') or '-')[:16]:16} "
            f"{str(r['can_fit']):4} {str(r['n0']):>4} {str(r['used']):>4} "
            f"{str(r.get('n0_gap')):>4} {str(r.get('last_boxes')):>5} "
            f"{str(r.get('merged_ok')):5} {r['ms']}"
        )
        if r.get("explain"):
            print(f"  → {r['explain']}")
        if r.get("comps"):
            print(f"  → comps {r['comps']}")

    out = ROOT / "output" / "multi_container_diag.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JSON", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
