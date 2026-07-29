#!/usr/bin/env python3
"""高利用率演示：用足够物料压实 40HQ，打印双口径利用率。

用法:
  python scripts/run_high_util_demo.py
  python scripts/run_high_util_demo.py --case crate24
  python scripts/run_high_util_demo.py --save   # 落盘 + 可给前端 session
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def mats_modules(n: int, L: int, W: int, H: int, kg: float, prefix: str = "D") -> List[Dict[str, Any]]:
    out = []
    for i in range(1, n + 1):
        out.append(
            {
                "id": f"{prefix}{i:03d}",
                "name": f"密实模块-{i}",
                "spec": "整包模块",
                "quantity": 1,
                "weight_kg": kg,
                "total_weight_kg": kg,
                "length_mm": L,
                "width_mm": W,
                "height_mm": H,
                "category": "重件" if kg >= 500 else "普通件",
            }
        )
    return out


def mats_steel_fill() -> List[Dict[str, Any]]:
    """长件 + 大量板垛，演示钢结构也可用密实模式抬利用率。"""
    steel: List[Dict[str, Any]] = [
        {
            "id": "L1",
            "name": "H型长梁",
            "spec": "H350×175",
            "quantity": 10,
            "weight_kg": 95,
            "total_weight_kg": 950,
            "length_mm": 5800,
            "width_mm": 350,
            "height_mm": 175,
            "category": "超长件",
        },
        {
            "id": "L2",
            "name": "H型柱段",
            "spec": "H400×200",
            "quantity": 8,
            "weight_kg": 110,
            "total_weight_kg": 880,
            "length_mm": 3200,
            "width_mm": 400,
            "height_mm": 200,
            "category": "普通件",
        },
    ]
    for i in range(1, 45):
        steel.append(
            {
                "id": f"F{i:03d}",
                "name": f"厚板垛-{i}",
                "spec": "板材打包",
                "quantity": 1,
                "weight_kg": 480,
                "total_weight_kg": 480,
                "length_mm": 2000,
                "width_mm": 1000,
                "height_mm": 450,
                "category": "重件",
            }
        )
    return steel


def mats_demo_full() -> List[Dict[str, Any]]:
    """推荐演示：接近满载（重量）+ 外廓可看满。"""
    # 24× 约 1t 模块 ≈ 24t 净重 → 40HQ 重量利用率高
    return mats_modules(24, 2000, 1100, 1100, 1000.0, prefix="M")


CASES: Dict[str, Tuple[List[Dict[str, Any]], Dict[str, Any], str]] = {
    "demo_full": (
        mats_demo_full(),
        {
            "standard_boxes": False,
            "dense_mode": True,
            "crate_passthrough": True,
            "max_box_net_kg": 2500,
        },
        "推荐演示：24×1t 密实模块，crate 直通 + dense",
    ),
    "crate24": (
        mats_modules(24, 2000, 1100, 1100, 1000.0),
        {
            "standard_boxes": False,
            "crate_passthrough": True,
            "max_box_net_kg": 2500,
        },
        "24 箱当量直通",
    ),
    "dense30": (
        mats_modules(30, 1200, 1000, 1100, 800.0),
        {
            "standard_boxes": False,
            "dense_mode": True,
            "max_box_net_kg": 2000,
        },
        "30 模块 dense 合箱",
    ),
    "steel_fill": (
        mats_steel_fill(),
        {
            "standard_boxes": False,
            "dense_mode": True,
            "max_box_net_kg": 2500,
        },
        "长件+板垛密实合箱",
    ),
    "weight32": (
        [],  # load later
        {"standard_boxes": True, "mix_mode": True, "max_box_net_kg": 2500},
        "已有 weight_bound_32t 仿真票",
    ),
}


def load_weight32() -> List[Dict[str, Any]]:
    p = ROOT / "test" / "sim_materials" / "weight_bound_32t" / "materials.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("materials") or [])


def run_one(case: str, *, save: bool) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    if case not in CASES:
        raise SystemExit(f"unknown case {case}; choose {list(CASES)}")
    mats, opts, story = CASES[case]
    if case == "weight32":
        mats = load_weight32()
    print(f"\n=== {case}: {story} ===")
    print(f"materials lines={len(mats)} net_kg≈{sum(float(m.get('total_weight_kg') or m.get('weight_kg') or 0) for m in mats):.0f}")
    print(f"packing_options={opts}")

    st = run_agent_pipeline(
        f"高利用率演示 {case}",
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id=f"high-util-{case}",
        save_artifacts=save,
        packing_options=opts,
    )
    p = st.get("container_plan") or {}
    b = st.get("booking") or (st.get("plan") or {}).get("booking") or {}
    book = p.get("booking_volume_utilization")
    outer = p.get("outer_space_utilization") or p.get("space_utilization")
    wt = p.get("weight_utilization")
    print(
        f"boxes={len(st.get('boxes') or [])}  used={p.get('containers_used')}  n0={p.get('n0') or b.get('n0')}  "
        f"binding={b.get('binding_constraint')}"
    )
    print(
        f"订柜有效体积率={_pct(book)}  外廓摆柜率={_pct(outer)}  重量利用率={_pct(wt)}  "
        f"can_fit={p.get('can_fit')}  engine={p.get('engine')}"
    )
    if save:
        paths = st.get("artifact_paths") or {}
        print(f"artifacts run_id={st.get('run_id')} dir={paths.get('run_dir')}")
    # 写一份给前端/API 复用
    out_dir = ROOT / "output" / "high_util_demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case": case,
        "story": story,
        "materials": mats,
        "packing_options": opts,
        "metrics": {
            "boxes": len(st.get("boxes") or []),
            "containers_used": p.get("containers_used"),
            "n0": p.get("n0") or b.get("n0"),
            "booking_volume_utilization": book,
            "outer_space_utilization": outer,
            "weight_utilization": wt,
            "can_fit": p.get("can_fit"),
            "binding": b.get("binding_constraint"),
            "engine": p.get("engine"),
        },
        "session_id": f"high-util-{case}",
        "run_id": st.get("run_id"),
    }
    (out_dir / f"{case}_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (out_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"wrote {out_dir / f'{case}_result.json'}")
    return payload


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    return f"{float(v) * 100:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--case",
        default="demo_full",
        choices=list(CASES.keys()) + ["all"],
    )
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    cases = list(CASES.keys()) if args.case == "all" else [args.case]
    best = None
    for c in cases:
        payload = run_one(c, save=args.save or c == "demo_full")
        m = payload["metrics"]
        score = (
            float(m.get("weight_utilization") or 0)
            + float(m.get("outer_space_utilization") or 0)
            + float(m.get("booking_volume_utilization") or 0)
        )
        if best is None or score > best[0]:
            best = (score, c, m)
    if best:
        print("\n--- BEST ---")
        print(best[1], best[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
