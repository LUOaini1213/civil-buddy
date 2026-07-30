#!/usr/bin/env python3
"""20 轮：10 实际夹具 + 10 随机物料，steps 全流程评分报告。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

sys.path.insert(0, str(ROOT / "scripts"))
from gen_random_materials import FAMILIES, gen_case  # noqa: E402

SIM = ROOT / "test" / "sim_materials"
OUT_DIR = ROOT / "output" / "round20"

# 10 实际票（按优先级，缺失则跳过并补 INDEX 替代）
REAL_PREFERRED = [
    "tiny",
    "small_one_container",
    "mixed_realistic",
    "long_frames",
    "glass_category",
    "near_payload",
    "weight_bound_32t",
    "volume_bound_light",
    "t30_mixed_short_s4",
    "t80_long_mix_s297883",
]

REAL_FALLBACK = [
    "t30_steel_tubes_s1",
    "t30_heavy_modules_s2",
    "t30_plates_beams_s3",
    "t80_random_mixed_s297832",
    "hollow_crate_lines",
    "overweight_risk",
]


def _load_materials_file(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta: Dict[str, Any] = {}
    if isinstance(data, list):
        return data, meta
    mats = data.get("materials") or []
    meta = {
        "expect": data.get("expect") or {},
        "story": data.get("story") or "",
        "packing_options_hint": data.get("packing_options_hint"),
    }
    return list(mats), meta


def _resolve_real_ids(n: int = 10) -> List[str]:
    chosen: List[str] = []
    for cid in REAL_PREFERRED:
        p = SIM / cid / "materials.json"
        if p.is_file() and cid not in chosen:
            chosen.append(cid)
        if len(chosen) >= n:
            return chosen
    for cid in REAL_FALLBACK:
        p = SIM / cid / "materials.json"
        if p.is_file() and cid not in chosen:
            chosen.append(cid)
        if len(chosen) >= n:
            break
    # INDEX 扫尾
    idx = SIM / "INDEX.json"
    if len(chosen) < n and idx.is_file():
        data = json.loads(idx.read_text(encoding="utf-8"))
        for cid in (data.get("cases") or {}):
            if cid in chosen:
                continue
            if (SIM / cid / "materials.json").is_file():
                chosen.append(cid)
            if len(chosen) >= n:
                break
    return chosen[:n]


def _default_opts(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    o = {
        "standard_boxes": True,
        "prefer_stack": True,
        "multi_start": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "r4_repair": True,
        "r4_target_mid50": 0.60,
        "mix_mode": True,
    }
    if extra:
        o.update(extra)
    return o


def _illegal(st: Dict[str, Any]) -> int:
    try:
        from packing_assistant.workteam_kpi import compute_kpis

        return int(compute_kpis(st).get("illegal_tool_calls") or 0)
    except Exception:
        return 0


def _mid50(st: Dict[str, Any]) -> Optional[float]:
    plan = st.get("container_plan") or {}
    if plan.get("worst_mid50") is not None:
        return float(plan["worst_mid50"])
    cog = plan.get("cog") or st.get("cog") or {}
    if isinstance(cog, dict):
        if cog.get("mass_in_mid50_ratio") is not None:
            return float(cog["mass_in_mid50_ratio"])
        p = cog.get("primary") or {}
        if p.get("mass_in_mid50_ratio") is not None:
            return float(p["mass_in_mid50_ratio"])
    return None


def run_one(
    *,
    case_id: str,
    materials: List[Dict[str, Any]],
    user_input: str,
    packing_options: Dict[str, Any],
    max_containers: int,
    expect: Dict[str, Any],
    tags: List[str],
    story: str,
    source: str,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline
    from packing_assistant.phase0_benchmark import Phase0Case, classify_failure, score_run
    from packing_assistant.verdict import build_verdict

    case = Phase0Case(
        id=case_id,
        materials=materials,
        user_input=user_input,
        packing_options=packing_options,
        max_containers=max_containers,
        tags=tags,
        expect=expect,
        story=story,
    )
    t0 = time.time()
    err_msg = ""
    st: Dict[str, Any] = {}
    try:
        st = run_agent_pipeline(
            user_input,
            materials=materials,
            session_id=f"r20-{case_id}"[:80],
            enable_auto_confirm=True,
            save_artifacts=False,
            packing_options=packing_options,
            max_containers=max_containers,
            container_type="40HQ",
            agent_mode="steps",
        )
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        st = {
            "status": "error",
            "errors": [err_msg, traceback.format_exc()[-1500:]],
            "container_plan": {},
            "agent_steps": [],
        }
    ms = int((time.time() - t0) * 1000)
    scored = score_run(st, case, ms=ms)
    try:
        verdict = build_verdict(st)
    except Exception:
        verdict = {}
    illegal = _illegal(st)
    hard_fail = bool(
        st.get("status") == "error"
        or illegal > 0
        or any("Traceback" in str(e) for e in (st.get("errors") or []))
    )
    total = float(scored.get("total_score") or 0)
    task = float((scored.get("dimensions") or {}).get("task_success") or 0)
    soft = bool(expect.get("allow_soft_fail") or expect.get("allow_cannot_fit"))
    win = (total >= 0.75 and task >= 0.80) or (soft and not hard_fail and total >= 0.55)
    fm = classify_failure(st, scored, case)
    if hard_fail:
        fm = "hard_error"
    plan = st.get("container_plan") or {}
    return {
        "id": case_id,
        "source": source,
        "tags": tags,
        "story": story,
        "n_materials": len(materials),
        "pass": bool(win and not hard_fail),
        "hard_fail": hard_fail,
        "failure_mode": fm,
        "total_score": total,
        "task_success": task,
        "dimensions": scored.get("dimensions"),
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "ship_ok": st.get("ship_ok"),
        "mid50": _mid50(st),
        "verdict_level": (verdict or {}).get("level"),
        "illegal": illegal,
        "ms": ms,
        "error": err_msg[:300] if err_msg else "",
        "n_steps": scored.get("n_steps"),
    }


def build_suite(seed: int) -> List[Dict[str, Any]]:
    suite: List[Dict[str, Any]] = []
    # real
    for cid in _resolve_real_ids(10):
        path = SIM / cid / "materials.json"
        mats, meta = _load_materials_file(path)
        expect = dict(meta.get("expect") or {})
        # 边界票允许 cannot_fit 软过
        if any(k in cid for k in ("overweight", "near_payload", "weight_bound")):
            expect.setdefault("allow_cannot_fit", True)
        hint = meta.get("packing_options_hint")
        opts = _default_opts(hint if isinstance(hint, dict) else None)
        # 长票/板件密装提示
        if any(k in cid for k in ("plate", "module", "long_mix", "t80")):
            opts.setdefault("dense_mode", True)
        suite.append(
            {
                "case_id": f"real:{cid}",
                "materials": mats,
                "user_input": meta.get("story") or f"实际夹具 {cid}",
                "packing_options": opts,
                "max_containers": 0,
                "expect": expect,
                "tags": ["real", cid],
                "story": meta.get("story") or cid,
                "source": f"test/sim_materials/{cid}",
            }
        )
    # random 10
    for i in range(10):
        s = int(seed) + i
        fam = FAMILIES[i % len(FAMILIES)]
        data = gen_case(s, fam)
        opts = _default_opts()
        if fam in ("module_plate", "light_volume"):
            opts["dense_mode"] = True
            opts["standard_boxes"] = fam != "light_volume"
        max_c = 0
        expect = dict(data.get("expect") or {})
        if fam == "junk_edge":
            expect["allow_soft_fail"] = True
            expect["allow_cannot_fit"] = True
        # 1 票硬锁柜
        if i == 7:
            max_c = 1
            opts["lock_max_containers"] = True
            opts["container_budget"] = 1
            opts["meeting_cap"] = True
            expect["allow_cannot_fit"] = True
            expect["allow_soft_fail"] = True
        suite.append(
            {
                "case_id": data["case_id"],
                "materials": data["materials"],
                "user_input": data.get("story") or data["case_id"],
                "packing_options": opts,
                "max_containers": max_c,
                "expect": expect,
                "tags": ["random", fam, f"seed{s}"],
                "story": data.get("story") or "",
                "source": f"generated:{fam}:s{s}",
            }
        )
        # 落盘 case 物料
        case_dir = OUT_DIR / "cases" / data["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "materials.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return suite[:20]


def render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Round-20 Materials Report",
        "",
        f"- seed: **{report.get('seed')}**",
        f"- harness: `{report.get('harness_version')}`",
        f"- n: **{report.get('n')}** · pass: **{report.get('n_pass')}** · "
        f"pass_rate: **{report.get('pass_rate'):.3f}** · hard_fail: **{report.get('n_hard_fail')}**",
        f"- avg_score: **{report.get('avg_score'):.4f}**",
        f"- win_line: total≥0.75 & task≥0.80（soft_fail 票可放宽）",
        f"- suite_pass (≥18/20 & hard=0): **{report.get('suite_pass')}**",
        "",
        "## By source",
        "",
        f"- real: {report.get('real_pass')}/{report.get('real_n')} · "
        f"random: {report.get('random_pass')}/{report.get('random_n')}",
        "",
        "## Dimension averages",
        "",
        "| dim | avg |",
        "|-----|-----|",
    ]
    for k, v in (report.get("dimension_averages") or {}).items():
        lines.append(f"| {k} | {v:.4f} |")
    lines += ["", "## Cases", "", "| id | src | pass | score | task | can_fit | mid50 | ms | mode |", "|----|-----|------|-------|------|---------|-------|-----|------|"]
    for c in report.get("cases") or []:
        lines.append(
            f"| {c.get('id')} | {c.get('source','')[:24]} | {c.get('pass')} | "
            f"{c.get('total_score')} | {c.get('task_success')} | {c.get('can_fit')} | "
            f"{c.get('mid50')} | {c.get('ms')} | {c.get('failure_mode')} |"
        )
    fails = [c for c in (report.get("cases") or []) if not c.get("pass") or c.get("hard_fail")]
    lines += ["", "## Failure ledger", ""]
    if not fails:
        lines.append("- none")
    else:
        for c in fails:
            lines.append(
                f"- **{c.get('id')}**: mode={c.get('failure_mode')} "
                f"score={c.get('total_score')} err={c.get('error') or '—'}"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="20-round real+random materials test")
    ap.add_argument("--seed", type=int, default=20260730)
    ap.add_argument("--only-real", action="store_true")
    ap.add_argument("--only-random", action="store_true")
    args = ap.parse_args()

    from packing_assistant.config import HARNESS_VERSION
    from packing_assistant.phase0_benchmark import load_success_criteria

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suite = build_suite(args.seed)
    if args.only_real:
        suite = [c for c in suite if str(c["case_id"]).startswith("real:")]
    if args.only_random:
        suite = [c for c in suite if not str(c["case_id"]).startswith("real:")]

    print(f"ROUND20 n={len(suite)} seed={args.seed}")
    rows: List[Dict[str, Any]] = []
    for i, spec in enumerate(suite, 1):
        print(f"RUN [{i}/{len(suite)}] {spec['case_id']} n_mat={len(spec['materials'])}")
        row = run_one(
            case_id=spec["case_id"],
            materials=spec["materials"],
            user_input=spec["user_input"],
            packing_options=spec["packing_options"],
            max_containers=int(spec.get("max_containers") or 0),
            expect=spec.get("expect") or {},
            tags=list(spec.get("tags") or []),
            story=str(spec.get("story") or ""),
            source=str(spec.get("source") or ""),
        )
        print(
            f"  -> pass={row['pass']} score={row['total_score']} "
            f"can_fit={row['can_fit']} mid50={row['mid50']} ms={row['ms']} mode={row['failure_mode']}"
        )
        rows.append(row)

    n = len(rows)
    n_pass = sum(1 for r in rows if r.get("pass"))
    n_hard = sum(1 for r in rows if r.get("hard_fail"))
    scores = [float(r.get("total_score") or 0) for r in rows]
    avg = sum(scores) / n if n else 0.0
    dim_acc: Dict[str, List[float]] = {}
    for r in rows:
        for k, v in (r.get("dimensions") or {}).items():
            dim_acc.setdefault(k, []).append(float(v))
    dim_avg = {k: sum(v) / len(v) for k, v in dim_acc.items()}
    real_rows = [r for r in rows if str(r.get("id", "")).startswith("real:")]
    rnd_rows = [r for r in rows if not str(r.get("id", "")).startswith("real:")]
    suite_pass = n_hard == 0 and n_pass >= min(18, max(1, int(n * 0.9)))

    report = {
        "version": "round20-v1",
        "seed": args.seed,
        "harness_version": HARNESS_VERSION,
        "criteria": load_success_criteria(),
        "n": n,
        "n_pass": n_pass,
        "n_hard_fail": n_hard,
        "pass_rate": round(n_pass / n, 4) if n else 0.0,
        "avg_score": round(avg, 4),
        "dimension_averages": {k: round(v, 4) for k, v in dim_avg.items()},
        "real_n": len(real_rows),
        "real_pass": sum(1 for r in real_rows if r.get("pass")),
        "random_n": len(rnd_rows),
        "random_pass": sum(1 for r in rnd_rows if r.get("pass")),
        "suite_pass": suite_pass,
        "cases": rows,
        "ts": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }
    ts = report["ts"]
    jp = OUT_DIR / f"round20_{ts}.json"
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = render_md(report)
    (OUT_DIR / "ROUND20_REPORT.md").write_text(md, encoding="utf-8")
    print(
        f"DONE pass={n_pass}/{n} rate={report['pass_rate']} avg={avg:.4f} "
        f"hard={n_hard} suite_pass={suite_pass}"
    )
    print("JSON", jp)
    print("MD", OUT_DIR / "ROUND20_REPORT.md")
    return 0 if suite_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
