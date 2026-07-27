#!/usr/bin/env python
"""
Agent 闭环自检 demo：五条能力可指着输出。

  python scripts/demo_agent_closed_loop.py
  python scripts/demo_agent_closed_loop.py --tiny

输出：
  - stdout 五条自检表
  - output/runs/<run_id>/ 全套落盘
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _tiny_materials():
    return [
        {
            "id": "M001",
            "name": "H型钢柱",
            "spec": "H400",
            "length_mm": 3800,
            "width_mm": 400,
            "height_mm": 200,
            "weight_kg": 85,
            "quantity": 4,
            "total_weight_kg": 340,
            "category": "普通件",
        },
        {
            "id": "M002",
            "name": "钢梁",
            "spec": "H350",
            "length_mm": 4200,
            "width_mm": 350,
            "height_mm": 175,
            "weight_kg": 55,
            "quantity": 6,
            "total_weight_kg": 330,
            "category": "超长件",
        },
        {
            "id": "M003",
            "name": "连接板",
            "spec": "套件",
            "length_mm": 800,
            "width_mm": 600,
            "height_mm": 400,
            "weight_kg": 12,
            "quantity": 20,
            "total_weight_kg": 240,
            "category": "普通件",
        },
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiny", action="store_true", help="用内置小清单")
    ap.add_argument(
        "--goal",
        default="deliver_valid_pack_plan",
        choices=["deliver_valid_pack_plan", "minimize_containers", "safe_to_ship"],
    )
    args = ap.parse_args()

    from packing_assistant.harness import run_agent_pipeline

    mats = _tiny_materials() if args.tiny else _tiny_materials()
    print("=" * 60)
    print("Agent 闭环：感知 → 规划 → 工具 → 行动 → 目标")
    print("=" * 60)

    state = run_agent_pipeline(
        "demo_agent_closed_loop",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        goal=args.goal,
        save_artifacts=True,
    )

    steps = state.get("agent_steps") or []
    paths = state.get("artifact_paths") or {}
    perc = state.get("perception") or {}
    reasons = (state.get("plan") or {}).get("planning_reasons") or []
    gs = state.get("goal_status") or {}
    rr = state.get("risk_report") or {}

    print("\n## 1 感知（材料摘要）")
    print(perc.get("summary_text") or perc or state.get("materials_summary"))

    print("\n## 2 规划（N0 理由）")
    for i, r in enumerate(reasons, 1):
        print(f"  ({i}) {r}")
    if not reasons:
        print("  (无 planning_reasons — 检查 planner)")

    print("\n## 3 工具轨迹（tools_used）")
    for s in steps:
        tools = s.get("tools_used") or []
        if tools:
            print(f"  [{s.get('node')}] {', '.join(tools)}")
            msg = (s.get("message") or "")[:120]
            if msg:
                print(f"         {msg}...")

    print("\n## 4 行动（落盘）")
    print(f"  run_dir: {paths.get('run_dir')}")
    for k in ("perception", "plan", "risk_md", "finalize_md", "trace", "views"):
        if paths.get(k):
            print(f"  {k}: {paths[k]}")

    print("\n## 5 目标（finalize 裁决）")
    print(f"  goal={gs.get('goal')} achieved={gs.get('achieved')}")
    print(f"  verdict={gs.get('verdict')}")
    print(f"  ship_ok={state.get('ship_ok')} risk={rr.get('decision')}")
    if rr.get("suggested_actions"):
        print("  suggested_actions:")
        for a in rr["suggested_actions"][:4]:
            print(f"    - {a}")

    print("\n## 自检表")
    checks = [
        ("感知", bool(perc or state.get("materials_summary"))),
        ("规划", bool(reasons)),
        ("工具", any((s.get("tools_used") or []) for s in steps)),
        ("行动", bool(paths.get("run_dir"))),
        ("目标", bool(gs.get("verdict") or state.get("final_response"))),
    ]
    ok_all = True
    for name, ok in checks:
        mark = "OK" if ok else "MISS"
        if not ok:
            ok_all = False
        print(f"  [{mark}] {name}")

    out_sum = ROOT / "output" / "agent_closed_loop_summary.json"
    out_sum.parent.mkdir(parents=True, exist_ok=True)
    out_sum.write_text(
        json.dumps(
            {
                "run_id": state.get("run_id"),
                "goal_status": gs,
                "artifact_paths": paths,
                "planning_reasons": reasons,
                "perception": perc,
                "steps_tools": [
                    {"node": s.get("node"), "tools_used": s.get("tools_used")}
                    for s in steps
                ],
                "checks": {n: ok for n, ok in checks},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nsummary → {out_sum}")
    print("=" * 60)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
