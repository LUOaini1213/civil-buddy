#!/usr/bin/env python3
"""对 t30_* ~30t 物料集做多轮 pipeline 测试。

  python scripts/gen_30t_materials.py --variants 6
  python scripts/run_t30_multi_round.py --rounds 2
  python scripts/run_t30_multi_round.py --rounds 2 --suite full
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "output" / "t30_multi_round"


def load_cases() -> List[Dict[str, Any]]:
    idx = ROOT / "output" / "t30_batches" / "INDEX.json"
    if not idx.exists():
        raise SystemExit("missing output/t30_batches/INDEX.json — run gen_30t_materials.py first")
    data = json.loads(idx.read_text(encoding="utf-8"))
    return list(data.get("cases") or [])


def run_case(case: Dict[str, Any], *, round_i: int, dense: bool) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    path = Path(case["json"])
    if not path.is_absolute():
        path = ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    mats = payload.get("materials") or []
    opts = (
        {
            "standard_boxes": False,
            "dense_mode": True,
            "max_box_net_kg": 2500,
        }
        if dense
        else {
            "standard_boxes": True,
            "mix_mode": True,
            "max_box_net_kg": 2500,
        }
    )
    # pallet_like 优先 crate 直通
    if "pallet" in case["case_id"] or "heavy_modules" in case["case_id"]:
        opts = {
            "standard_boxes": False,
            "dense_mode": True,
            "crate_passthrough": True,
            "max_box_net_kg": 2500,
        }

    t0 = time.perf_counter()
    err = None
    st: Dict[str, Any] = {}
    try:
        st = run_agent_pipeline(
            f"t30 multi-round {case['case_id']} r{round_i}",
            materials=mats,
            container_type="40HQ",
            enable_auto_confirm=True,
            session_id=f"t30-{case['case_id']}-r{round_i}",
            save_artifacts=False,
            packing_options=opts,
        )
    except Exception as e:
        err = str(e)
    ms = int((time.perf_counter() - t0) * 1000)
    p = st.get("container_plan") or {}
    b = st.get("booking") or (st.get("plan") or {}).get("booking") or {}
    ok = err is None and bool(p.get("can_fit") is not False)
    # 软断言：净重约 30t 时重量柜应 ≥2（40HQ payload~26t）
    net = float(case.get("net_kg") or 0)
    used = int(p.get("containers_used") or 0)
    n0 = int(p.get("n0") or b.get("n0") or 0)
    soft_ok = True
    soft_notes = []
    if net >= 28000 and n0 < 2:
        soft_ok = False
        soft_notes.append(f"expect n0>=2 for ~30t got n0={n0}")
    if err:
        ok = False
    return {
        "case_id": case["case_id"],
        "round": round_i,
        "ok": ok and soft_ok,
        "hard_ok": ok,
        "soft_ok": soft_ok,
        "soft_notes": soft_notes,
        "error": err,
        "ms": ms,
        "net_t": case.get("net_t"),
        "n_materials": case.get("n_lines"),
        "n_boxes": len(st.get("boxes") or []),
        "n0": n0,
        "containers_used": used,
        "can_fit": p.get("can_fit"),
        "booking_volume_utilization": p.get("booking_volume_utilization"),
        "outer_space_utilization": p.get("outer_space_utilization")
        or p.get("space_utilization"),
        "weight_utilization": p.get("weight_utilization"),
        "binding": b.get("binding_constraint"),
        "engine": p.get("engine"),
        "phase": st.get("phase"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--dense", action="store_true", default=True)
    ap.add_argument("--no-dense", action="store_true")
    ap.add_argument("--suite", default="pack", help="pack | full (full 额外跑 multi_round smoke)")
    args = ap.parse_args()
    dense = not args.no_dense
    cases = load_cases()
    if not cases:
        raise SystemExit("no t30 cases")

    OUT.mkdir(parents=True, exist_ok=True)
    all_rows: List[Dict[str, Any]] = []
    print(f"cases={len(cases)} rounds={args.rounds} dense={dense}")

    for r in range(1, int(args.rounds) + 1):
        print(f"\n======== ROUND {r}/{args.rounds} ========")
        for c in cases:
            row = run_case(c, round_i=r, dense=dense)
            all_rows.append(row)
            flag = "PASS" if row["ok"] else "FAIL"
            print(
                f"[{flag}] {row['case_id']} r{r}: boxes={row['n_boxes']} "
                f"n0={row['n0']} used={row['containers_used']} "
                f"book={row['booking_volume_utilization']} "
                f"outer={row['outer_space_utilization']} "
                f"wt={row['weight_utilization']} "
                f"ms={row['ms']}"
                + (f" err={row['error']}" if row.get("error") else "")
                + (f" soft={row['soft_notes']}" if row.get("soft_notes") else "")
            )

    # 稳定性：同一 case 多轮 hard_ok 是否一致
    by_case: Dict[str, List[Dict[str, Any]]] = {}
    for row in all_rows:
        by_case.setdefault(row["case_id"], []).append(row)

    stability = []
    for cid, rows in by_case.items():
        oks = [bool(x["ok"]) for x in rows]
        used = [x["containers_used"] for x in rows]
        stable = all(o == oks[0] for o in oks) and all(u == used[0] for u in used)
        stability.append(
            {
                "case_id": cid,
                "stable": stable,
                "ok_all": all(oks),
                "rounds": len(rows),
                "containers_used": used,
                "ok_flags": oks,
            }
        )
        print(
            f"[STABILITY] {cid}: {'STABLE' if stable else 'UNSTABLE'} "
            f"ok={oks} used={used}"
        )

    # optional full suite
    extra = None
    if args.suite == "full":
        import subprocess

        print("\n======== multi_round smoke ×1 ========")
        r = subprocess.run(
            [sys.executable, "scripts/run_multi_round_tests.py", "--suite", "smoke", "--rounds", "1"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        extra = {"returncode": r.returncode, "tail": ((r.stdout or "") + (r.stderr or ""))[-2000:]}
        print(extra["tail"][-800:])

    n_pass = sum(1 for x in all_rows if x["ok"])
    n_stable = sum(1 for x in stability if x["stable"] and x["ok_all"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rounds": args.rounds,
        "dense": dense,
        "suite": args.suite,
        "summary": {
            "case_runs": len(all_rows),
            "pass": n_pass,
            "fail": len(all_rows) - n_pass,
            "stable_ok_cases": n_stable,
            "cases": len(by_case),
        },
        "stability": stability,
        "rows": all_rows,
        "extra": extra,
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT / f"report_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nreport → {out_path}")
    print(
        f"SUMMARY pass={n_pass}/{len(all_rows)} stable_ok_cases={n_stable}/{len(by_case)}"
    )
    # 全部硬通过才 0
    return 0 if n_pass == len(all_rows) and n_stable == len(by_case) else 1


if __name__ == "__main__":
    raise SystemExit(main())
