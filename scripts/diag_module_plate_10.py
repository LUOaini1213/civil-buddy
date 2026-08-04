#!/usr/bin/env python3
"""诊断：连续 10 个 module_plate 随机票，看 cannot_fit 卡在哪。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

from gen_random_materials import gen_case  # noqa: E402


def _opts() -> Dict[str, Any]:
    return {
        "standard_boxes": True,
        "dense_mode": True,
        "prefer_stack": True,
        "multi_start": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "r4_target_mid50": 0.60,
        "mix_mode": True,
    }


def _summarize_mats(mats: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(mats)
    Ls, Ws, Hs, wts = [], [], [], []
    missing = 0
    for m in mats:
        L = m.get("length_mm")
        W = m.get("width_mm")
        H = m.get("height_mm")
        if L is None or W is None or H is None:
            missing += 1
            continue
        Ls.append(float(L))
        Ws.append(float(W))
        Hs.append(float(H))
        wts.append(float(m.get("total_weight_kg") or 0))
    vol = sum((a * b * c) / 1e9 for a, b, c in zip(Ls, Ws, Hs))
    return {
        "n_lines": n,
        "missing_dims": missing,
        "L_mm": {"min": min(Ls) if Ls else None, "max": max(Ls) if Ls else None, "avg": sum(Ls) / len(Ls) if Ls else None},
        "W_mm": {"min": min(Ws) if Ws else None, "max": max(Ws) if Ws else None},
        "H_mm": {"min": min(Hs) if Hs else None, "max": max(Hs) if Hs else None},
        "weight_t": round(sum(wts) / 1000.0, 3),
        "solid_vol_m3": round(vol, 3),
        "n_module_like": sum(1 for h in Hs if h >= 400),
        "n_plate_like": sum(1 for h in Hs if h < 100),
    }


def main() -> int:
    import argparse

    from packing_assistant.harness import run_agent_pipeline

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-seed", type=int, default=20260734)
    ap.add_argument("--n", type=int, default=10)
    # 默认从失败种子附近开始：20260734 是 round20 失败票
    args = ap.parse_args()

    out_dir = ROOT / "output" / "round20" / "module_plate_diag"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"== module_plate x{args.n} base_seed={args.base_seed} ==")
    for i in range(args.n):
        seed = int(args.base_seed) + i
        data = gen_case(seed, "module_plate")
        mats = data["materials"]
        mat_sum = _summarize_mats(mats)
        (out_dir / f"s{seed}_materials.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        t0 = time.time()
        st = run_agent_pipeline(
            f"diag module_plate seed={seed}",
            materials=mats,
            session_id=f"diag-mp-{seed}",
            enable_auto_confirm=True,
            save_artifacts=False,
            packing_options=_opts(),
            container_type="40HQ",
            agent_mode="steps",
        )
        ms = int((time.time() - t0) * 1000)
        plan = st.get("container_plan") or {}
        boxes = st.get("boxes") or []
        feas = st.get("cargo_feasibility") or {}
        unpack = plan.get("unpacked_box_ids") or []
        layout = plan.get("layout") or []
        # box outer stats
        oL = []
        for b in boxes:
            o = b.get("outer_size_mm") or {}
            if isinstance(o, dict):
                oL.append(
                    (
                        float(o.get("length") or 0),
                        float(o.get("width") or 0),
                        float(o.get("height") or 0),
                        float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0),
                    )
                )
        row = {
            "seed": seed,
            "case_id": data["case_id"],
            "materials": mat_sum,
            "n_boxes": len(boxes),
            "can_fit": plan.get("can_fit"),
            "containers_used": plan.get("containers_used"),
            "n0": plan.get("n0") or (st.get("plan") or {}).get("n0"),
            "unpacked": len(unpack) if isinstance(unpack, list) else unpack,
            "unpacked_ids": (unpack[:8] if isinstance(unpack, list) else []),
            "layout_n": len(layout),
            "engine": plan.get("engine"),
            "feas_ok": feas.get("ok"),
            "feas_class": feas.get("failure_class") or feas.get("reason"),
            "ship_ok": st.get("ship_ok"),
            "phase": st.get("phase"),
            "outer_util": plan.get("outer_space_utilization") or plan.get("space_utilization"),
            "book_util": plan.get("booking_volume_utilization"),
            "weight_util": plan.get("weight_utilization"),
            "mid50": plan.get("worst_mid50"),
            "ms": ms,
            "box_outer_max_L": max((x[0] for x in oL), default=None),
            "box_outer_max_H": max((x[2] for x in oL), default=None),
            "box_max_kg": max((x[3] for x in oL), default=None),
            "errors": (st.get("errors") or [])[:2],
        }
        rows.append(row)
        flag = "PASS" if plan.get("can_fit") is True else "FAIL"
        print(
            f"{flag} seed={seed} mats={mat_sum['n_lines']} "
            f"vol={mat_sum['solid_vol_m3']}m3 wt={mat_sum['weight_t']}t "
            f"boxes={len(boxes)} can_fit={plan.get('can_fit')} used={plan.get('containers_used')} "
            f"n0={row['n0']} unpack={row['unpacked']} feas={feas.get('ok')} "
            f"maxH={row['box_outer_max_H']} ms={ms}"
        )

    n_ok = sum(1 for r in rows if r.get("can_fit") is True)
    fails = [r for r in rows if r.get("can_fit") is not True]
    summary = {
        "base_seed": args.base_seed,
        "n": len(rows),
        "can_fit_ok": n_ok,
        "can_fit_fail": len(fails),
        "rate": round(n_ok / len(rows), 3) if rows else 0,
        "cases": rows,
        "fail_seeds": [r["seed"] for r in fails],
        "hypothesis": [],
    }
    # 简单归因
    for r in fails:
        reasons = []
        if r.get("feas_ok") is False:
            reasons.append("cargo_feasibility_block")
        if r.get("n_boxes", 0) == 0:
            reasons.append("no_boxes")
        if (r.get("unpacked") or 0) and int(r.get("unpacked") or 0) > 0:
            reasons.append("unpacked_boxes")
        if r.get("box_outer_max_H") and float(r["box_outer_max_H"]) > 2690:
            reasons.append("box_taller_than_40HQ")
        if r.get("box_outer_max_L") and float(r["box_outer_max_L"]) > 12000:
            reasons.append("box_longer_than_40HQ")
        if r.get("materials", {}).get("solid_vol_m3", 0) > 70:
            reasons.append("cargo_volume_huge")
        if r.get("materials", {}).get("weight_t", 0) > 28:
            reasons.append("weight_over_payload_band")
        if not reasons:
            reasons.append("bin3d_cannot_fit_or_cap")
        r["diag_reasons"] = reasons
        summary["hypothesis"].extend(reasons)

    from collections import Counter

    summary["reason_counts"] = dict(Counter(summary["hypothesis"]))
    out_json = out_dir / "diag_module_plate_10.json"
    out_md = out_dir / "DIAG_MODULE_PLATE_10.md"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Module/Plate ×10 诊断",
        "",
        f"- base_seed: {args.base_seed}",
        f"- can_fit: **{n_ok}/{len(rows)}** ({summary['rate']:.0%})",
        f"- fail_seeds: {summary['fail_seeds']}",
        f"- reason_counts: `{summary['reason_counts']}`",
        "",
        "| seed | mats | vol_m3 | wt_t | boxes | can_fit | used | n0 | unpack | maxH | ms | reasons |",
        "|------|------|--------|------|-------|---------|------|----|--------|------|-----|---------|",
    ]
    for r in rows:
        m = r.get("materials") or {}
        lines.append(
            f"| {r['seed']} | {m.get('n_lines')} | {m.get('solid_vol_m3')} | {m.get('weight_t')} | "
            f"{r.get('n_boxes')} | {r.get('can_fit')} | {r.get('containers_used')} | {r.get('n0')} | "
            f"{r.get('unpacked')} | {r.get('box_outer_max_H')} | {r.get('ms')} | "
            f"{','.join(r.get('diag_reasons') or []) or 'ok'} |"
        )
    lines += ["", "## 解读", ""]
    if not fails:
        lines.append("- 10/10 全 can_fit，问题可能已随生成器收紧消失。")
    else:
        lines.append("- 失败集中原因见 reason_counts。")
        lines.append("- `unpacked_boxes`：3D 放不下剩余箱。")
        lines.append("- `box_taller_than_40HQ`：成箱外高超柜内高。")
        lines.append("- `cargo_volume_huge` / `weight_over_payload_band`：货量/重量本身过满。")
        lines.append("- `bin3d_cannot_fit_or_cap`：搜索上限内仍装不下（策略/柜数）。")
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print("SUMMARY", json.dumps({k: summary[k] for k in ("can_fit_ok", "can_fit_fail", "rate", "fail_seeds", "reason_counts")}, ensure_ascii=False))
    print("MD", out_md)
    print("JSON", out_json)
    return 0 if n_ok >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
