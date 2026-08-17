#!/usr/bin/env python3
"""
只跑「过不去」的题：同一票货 baseline → 针对性 retune → 对照是否变好。

规则：
- can_fit is False 一律算失败（不再把「pipeline 没崩」当 pass）
- 不改货物尺寸/数量来刷绿（禁止 scale_down / qty_cap）
- 缺维题：修好 = 仍然拒装；装进去算回归
- 货源：仓库里的 t30/t80/非标夹具，不是 BPP 小样循环

用法:
  python scripts/run_hard_fail_cases.py --smoke
  python scripts/run_hard_fail_cases.py
  python scripts/run_hard_fail_cases.py --skip-t80
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")
os.environ.setdefault("PACKING_LLM_TOOLCALL", "0")

OUT_DIR = ROOT / "output" / "hard_fail_cases"
SIM = ROOT / "test" / "sim_materials"

# 40HQ payload ~28.6t；1 柜装不下 30t，2 柜装不下 80t
HQ_PAYLOAD_KG = 28610.0


def _load_payload(rel_or_abs: str) -> Dict[str, Any]:
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        p = SIM / rel_or_abs / "materials.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _mats(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return deepcopy(list(payload.get("materials") or []))


def _net_kg(mats: List[Dict[str, Any]]) -> float:
    s = 0.0
    for m in mats:
        if m.get("total_weight_kg") is not None:
            s += float(m["total_weight_kg"])
        else:
            s += float(m.get("weight_kg") or 0) * float(m.get("quantity") or m.get("qty") or 1)
    return s


def _base_opts(**kw: Any) -> Dict[str, Any]:
    o = {
        "standard_boxes": False,
        "dense_mode": False,
        "mix_mode": False,
        "prefer_stack": True,
        "prefer_single_row": False,
        "prefer_two_row": False,
        "crate_passthrough": False,
        "max_box_net_kg": 3200,
    }
    o.update(kw)
    return o


def snapshot(st: Dict[str, Any], err: Optional[str], dt_s: float) -> Dict[str, Any]:
    plan = st.get("container_plan") or {}
    feas = st.get("cargo_feasibility") or {}
    booking = st.get("booking") or {}
    unpacked = plan.get("unpacked_box_ids") or plan.get("unpacked") or []
    can_fit = plan.get("can_fit")
    ship_ok = st.get("ship_ok")
    missing = bool(st.get("materials_incomplete"))
    phase = st.get("phase")
    errors = [str(e) for e in (st.get("errors") or [])][:6]
    refused = (
        can_fit is False
        or ship_ok is False
        or missing
        or feas.get("ok") is False
        or bool(unpacked)
        or phase in ("error",)
        or bool(err)
    )
    return {
        "error": err,
        "dt_s": round(dt_s, 3),
        "phase": phase,
        "can_fit": can_fit,
        "ship_ok": ship_ok,
        "materials_incomplete": missing,
        "feas_ok": feas.get("ok"),
        "n_boxes": len(st.get("boxes") or []),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0") or booking.get("n0"),
        "unpacked_n": len(unpacked) if isinstance(unpacked, (list, tuple)) else int(bool(unpacked)),
        "booking_util": plan.get("booking_volume_utilization"),
        "outer_util": plan.get("outer_space_utilization") or plan.get("space_utilization"),
        "weight_util": plan.get("weight_utilization"),
        "errors": errors,
        "entry": "packing_assistant.harness.run_agent_pipeline",
        # 几何题/重量题的硬失败
        "hard_fail": (can_fit is False) or bool(err) or missing,
        "refused": refused,
    }


def run_pipeline(
    *,
    case_id: str,
    tag: str,
    user_input: str,
    materials: List[Dict[str, Any]],
    packing_options: Dict[str, Any],
    max_containers: int,
    container_type: str = "40HQ",
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    err = None
    st: Dict[str, Any] = {}
    try:
        st = run_agent_pipeline(
            user_input,
            materials=deepcopy(materials),
            container_type=container_type,
            max_containers=int(max_containers or 0),
            enable_auto_confirm=True,
            packing_options=deepcopy(packing_options),
            session_id=f"hardfail-{case_id}-{tag}",
            save_artifacts=False,
            agent_mode="steps",
        )
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    snap = snapshot(st, err, dt)
    snap["max_containers"] = max_containers
    snap["opts"] = {
        k: packing_options.get(k)
        for k in (
            "dense_mode",
            "standard_boxes",
            "prefer_single_row",
            "prefer_two_row",
            "crate_passthrough",
            "max_box_net_kg",
            "lock_max_containers",
        )
        if k in packing_options or packing_options.get(k) is not None
    }
    return snap


def judge(case: Dict[str, Any], before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> str:
    """Honest verdict. missing_dims: refuse is success; inventing fit is regression."""
    family = case["family"]
    if family == "missing_dims":
        b_ok = before.get("refused") and before.get("can_fit") is not True
        if after is None:
            return "expected_refuse" if b_ok else "unexpected_fit"
        a_fit = after.get("can_fit") is True and after.get("ship_ok") is True
        if a_fit:
            return "regression_invented_fit"
        if after.get("refused"):
            return "expected_refuse"
        return "unclear"

    if not before.get("hard_fail") and before.get("can_fit") is True:
        return "already_ok"

    if after is None:
        return "fail_no_retune"

    b_fit = before.get("can_fit") is True
    a_fit = after.get("can_fit") is True
    if (not b_fit) and a_fit:
        return "improved"
    if b_fit and not a_fit:
        return "worse"
    if (not b_fit) and (not a_fit):
        return "unchanged_still_fail"
    return "unchanged_still_ok"


def build_bank(*, skip_t80: bool, smoke: bool) -> List[Dict[str, Any]]:
    """Real-cargo / real-fixture cases. Each has baseline + targeted retune."""
    cases: List[Dict[str, Any]] = []

    # 1) 超宽：柜内宽 2352，件宽 2800
    ovw = _load_payload("ns_over_container_width")
    cases.append(
        {
            "id": "geo_over_width",
            "family": "oversize",
            "source": "test/sim_materials/ns_over_container_width",
            "story": "超宽底座 2800mm > 40HQ 内宽 2352，几何装不进",
            "user_input": "超宽设备不要硬塞",
            "materials": _mats(ovw),
            "baseline": {"opts": _base_opts(), "max_containers": 2},
            "retune": {
                "why": "加柜/密装改不了单件超宽；对照证明 options 救不了几何超尺",
                "opts": _base_opts(dense_mode=True, crate_passthrough=True),
                "max_containers": 4,
            },
        }
    )

    # 2) 超长：从真实 t30 超长混装抽出若干杆，把一根改到 14m
    t30o = _load_payload("t30_oversized_mix_s6")
    long_mats = _mats(t30o)[:12]
    if long_mats:
        long_mats[0] = deepcopy(long_mats[0])
        long_mats[0]["length_mm"] = 14000.0
        long_mats[0]["name"] = str(long_mats[0].get("name") or "超长杆") + "-14m"
        long_mats[0]["note"] = "derived from t30_oversized_mix_s6; L=14000 > 40HQ inner 12032"
    cases.append(
        {
            "id": "geo_over_length_from_t30",
            "family": "oversize",
            "source": "t30_oversized_mix_s6 (one bar stretched to 14m)",
            "story": "真实 30t 超长混装派生：一根 14m 超过 40HQ 内长",
            "user_input": "超长杆件按真实尺寸装",
            "materials": long_mats,
            "baseline": {"opts": _base_opts(crate_passthrough=True), "max_containers": 3},
            "retune": {
                "why": "超长单件不能靠 densify 变短",
                "opts": _base_opts(dense_mode=True, crate_passthrough=True, prefer_two_row=True),
                "max_containers": 6,
            },
        }
    )

    # 3) 超重锁 1 柜：4×16t
    ow = _load_payload("overweight_risk")
    cases.append(
        {
            "id": "overweight_64t_lock1",
            "family": "overweight",
            "source": "test/sim_materials/overweight_risk",
            "story": "64t 重块锁 1×40HQ（payload≈28.6t）应 can_fit=false",
            "user_input": "超重只准 1 个 40HQ",
            "materials": _mats(ow),
            "baseline": {
                "opts": _base_opts(
                    lock_max_containers=True,
                    crate_passthrough=True,
                    max_box_net_kg=20000,
                ),
                "max_containers": 1,
            },
            "retune": {
                "why": "同一票 4×16t 不改尺寸，只放开柜数到重量下界（64t/28.6t≈3）",
                "opts": _base_opts(
                    dense_mode=True,
                    crate_passthrough=True,
                    lock_max_containers=False,
                    max_box_net_kg=20000,
                ),
                "max_containers": 5,
            },
        }
    )

    # 4) 缺维：混缺宽/缺三维
    md = _load_payload("ns_missing_dims_mix")
    cases.append(
        {
            "id": "missing_dims_mix",
            "family": "missing_dims",
            "source": "test/sim_materials/ns_missing_dims_mix",
            "story": "缺宽 + 缺三维，不许编造尺寸装进去",
            "user_input": "缺尺寸不要编造",
            "materials": _mats(md),
            "baseline": {"opts": _base_opts(), "max_containers": 2},
            "retune": {
                "why": "只拧 packing_options，不得补尺寸；仍应拒装",
                "opts": _base_opts(dense_mode=True, mix_mode=True),
                "max_containers": 4,
            },
        }
    )

    # 5) 一排/两排：真实托盘 20×1100mm，锁 1 柜。
    # 单排沿柜长约 22m>12m 应装不下；两排约 11m 且重量 22t<payload。
    pal = _load_payload("t30_pallet_like_s5")
    row_mats = _mats(pal)[:20]
    cases.append(
        {
            "id": "row_conflict_t30_pallets",
            "family": "row_conflict",
            "source": "t30_pallet_like_s5 (first 20 pallets)",
            "story": "真实 30t 托盘抽 20 件锁 1 柜：强制一排超柜长，改两排对照",
            "user_input": "这些托盘要一排装进一个柜",
            "materials": row_mats,
            "baseline": {
                "opts": _base_opts(
                    prefer_single_row=True,
                    prefer_two_row=False,
                    crate_passthrough=True,
                    lock_max_containers=True,
                ),
                "max_containers": 1,
            },
            "retune": {
                "why": "同一票货、仍锁 1 柜，只改 prefer_two_row（不再改尺寸/数量）",
                "opts": _base_opts(
                    prefer_single_row=False,
                    prefer_two_row=True,
                    dense_mode=True,
                    crate_passthrough=True,
                    lock_max_containers=True,
                ),
                "max_containers": 1,
            },
        }
    )

    # 6) 真实 30t 锁 1 柜
    t30_full = _load_payload("t30_oversized_mix_s6")
    cases.append(
        {
            "id": "t30_oversized_lock1",
            "family": "real_t30",
            "source": "t30_oversized_mix_s6",
            "story": f"真实 ~{t30_full.get('net_t')}t / {t30_full.get('n_lines')} 行，锁 1 柜应超 payload",
            "user_input": "30t 超长混装只准 1 个 40HQ",
            "materials": _mats(t30_full),
            "baseline": {
                "opts": _base_opts(crate_passthrough=True, lock_max_containers=True),
                "max_containers": 1,
            },
            "retune": {
                "why": "放开到 ≥2 柜（30t/28.6t）+ 密装",
                "opts": _base_opts(dense_mode=True, crate_passthrough=True, lock_max_containers=False),
                "max_containers": 6,
            },
        }
    )

    if not skip_t80:
        t80 = _load_payload("t80_long_mix_s297883")
        cases.append(
            {
                "id": "t80_long_mix_lock2",
                "family": "real_t80",
                "source": "t80_long_mix_s297883",
                "story": f"真实 ~{t80.get('net_t')}t / {t80.get('n_lines')} 行，锁 2 柜（约 57t payload）应超重",
                "user_input": "80t 长票混装最多 2 个 40HQ",
                "materials": _mats(t80),
                "baseline": {
                    "opts": _base_opts(crate_passthrough=True, lock_max_containers=True, max_box_net_kg=5000),
                    "max_containers": 2,
                },
                "retune": {
                    "why": "放开到重量下界（80t/28.6t≈3）以上 + 密装",
                    "opts": _base_opts(
                        dense_mode=True,
                        crate_passthrough=True,
                        lock_max_containers=False,
                        max_box_net_kg=5000,
                    ),
                    "max_containers": 8,
                },
            }
        )

    if smoke:
        return [c for c in cases if c["id"] in ("missing_dims_mix", "overweight_64t_lock1")]
    return cases


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    mats = case["materials"]
    net = _net_kg(mats)
    print(
        f"\n== {case['id']} family={case['family']} lines={len(mats)} net_t={net/1000:.2f} ==",
        flush=True,
    )
    print(f"   {case['story']}", flush=True)

    before = run_pipeline(
        case_id=case["id"],
        tag="before",
        user_input=case["user_input"],
        materials=mats,
        packing_options=case["baseline"]["opts"],
        max_containers=case["baseline"]["max_containers"],
    )
    print(
        f"   BEFORE can_fit={before.get('can_fit')} ship_ok={before.get('ship_ok')} "
        f"used={before.get('containers_used')} n0={before.get('n0')} "
        f"boxes={before.get('n_boxes')} hard_fail={before.get('hard_fail')} "
        f"phase={before.get('phase')} {before.get('dt_s')}s"
        + (f" err={before.get('error')}" if before.get("error") else ""),
        flush=True,
    )

    after: Optional[Dict[str, Any]] = None
    did_retune = True
    # already_ok on non-missing: still retune? User asked only fail cases.
    # We still run retune for missing_dims (must stay refuse) and for hard_fail.
    # Skip retune only when already can_fit=true on a fit-expected family.
    if case["family"] != "missing_dims" and before.get("can_fit") is True and not before.get("hard_fail"):
        did_retune = False
        print("   SKIP retune (already can_fit=true)", flush=True)
    else:
        rt = case["retune"]
        after = run_pipeline(
            case_id=case["id"],
            tag="after",
            user_input=case["user_input"] + " | retune",
            materials=mats,  # SAME cargo
            packing_options=rt["opts"],
            max_containers=rt["max_containers"],
        )
        print(
            f"   AFTER  can_fit={after.get('can_fit')} ship_ok={after.get('ship_ok')} "
            f"used={after.get('containers_used')} n0={after.get('n0')} "
            f"boxes={after.get('n_boxes')} {after.get('dt_s')}s",
            flush=True,
        )
        print(f"   retune: {rt['why']}", flush=True)

    verdict = judge(case, before, after)
    print(f"   VERDICT {verdict}", flush=True)
    return {
        "id": case["id"],
        "family": case["family"],
        "source": case["source"],
        "story": case["story"],
        "n_lines": len(mats),
        "net_kg": round(net, 1),
        "net_t": round(net / 1000.0, 3),
        "retune_why": case["retune"]["why"],
        "did_retune": did_retune,
        "before": before,
        "after": after,
        "verdict": verdict,
        "same_materials": True,
    }


def write_rollup(rows: List[Dict[str, Any]], *, skip_t80: bool, smoke: bool) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    improved = counts.get("improved", 0)
    still_fail = counts.get("unchanged_still_fail", 0)
    expected_refuse = counts.get("expected_refuse", 0)
    regression = counts.get("regression_invented_fit", 0)
    already = counts.get("already_ok", 0)

    roll = {
        "title": "hard_fail_cases",
        "finished_at": datetime.now().isoformat(),
        "entry": "packing_assistant.harness.run_agent_pipeline",
        "rule": "can_fit=false is fail; same cargo before/after; no scale_down/qty_cap",
        "smoke": smoke,
        "skip_t80": skip_t80,
        "n_cases": len(rows),
        "verdict_counts": counts,
        "n_improved": improved,
        "n_still_fail": still_fail,
        "n_expected_refuse": expected_refuse,
        "n_regression": regression,
        "n_already_ok": already,
        "cases": rows,
    }
    jp = OUT_DIR / "rollup.json"
    jp.write_text(json.dumps(roll, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Hard-fail cases (same cargo, before → after)",
        "",
        f"- finished: {roll['finished_at']}",
        f"- entry: `{roll['entry']}`",
        f"- rule: {roll['rule']}",
        f"- cases: **{len(rows)}**",
        f"- improved: **{improved}** · still_fail: **{still_fail}** · expected_refuse: **{expected_refuse}**",
        f"- already_ok: {already} · regression_invented_fit: {regression}",
        "",
        "| id | family | net_t | before can_fit | after can_fit | used b→a | verdict |",
        "|----|--------|-------|----------------|---------------|----------|---------|",
    ]
    for r in rows:
        b = r["before"]
        a = r.get("after") or {}
        md.append(
            f"| {r['id']} | {r['family']} | {r['net_t']} | {b.get('can_fit')} | "
            f"{a.get('can_fit') if r.get('did_retune') else '—'} | "
            f"{b.get('containers_used')}→{a.get('containers_used') if r.get('did_retune') else '—'} | "
            f"**{r['verdict']}** |"
        )
    md.extend(["", "## Notes", ""])
    for r in rows:
        md.append(f"- **{r['id']}**: {r['story']} — retune: {r['retune_why']}")
    mp = OUT_DIR / "rollup.md"
    mp.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nROLLUP {jp}")
    print(
        f"SUMMARY improved={improved} still_fail={still_fail} "
        f"expected_refuse={expected_refuse} already_ok={already} regression={regression}"
    )
    return jp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="only missing_dims + overweight lock")
    ap.add_argument("--skip-t80", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated case ids")
    args = ap.parse_args()

    bank = build_bank(skip_t80=args.skip_t80, smoke=args.smoke)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        bank = [c for c in bank if c["id"] in want]
        if not bank:
            print("no cases match --only", want)
            return 2

    print(f"bank={len(bank)} smoke={args.smoke} skip_t80={args.skip_t80}", flush=True)
    rows = [run_case(c) for c in bank]
    write_rollup(rows, skip_t80=args.skip_t80, smoke=args.smoke)

    # Smoke / gate: missing dims must refuse; at least one weight/lock case should improve OR still fail honestly
    bad = [r for r in rows if r["verdict"] == "regression_invented_fit"]
    if bad:
        print("GATE FAIL: missing-dims invented a fit", [r["id"] for r in bad])
        return 1
    if not rows:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
