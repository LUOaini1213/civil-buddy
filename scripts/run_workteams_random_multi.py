#!/usr/bin/env python3
"""Teams 随机物料多轮测试（steps 主路径 + 可选 llm 影子）。

用法:
  python scripts/run_workteams_random_multi.py
  python scripts/run_workteams_random_multi.py --rounds 12 --seed 20260805
  python scripts/run_workteams_random_multi.py --rounds 6 --shadow
  python scripts/run_workteams_random_multi.py --rounds 8 --families steel_mix,long_heavy,module_plate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

from gen_random_materials import FAMILIES, gen_case  # noqa: E402

OUT_DIR = ROOT / "output" / "workteams_random"


def _default_opts(family: str) -> Dict[str, Any]:
    base = {
        "prefer_stack": True,
        "multi_start": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "r4_repair": True,
        "r4_target_mid50": 0.60,
        "dense_mode": True,
        "crate_passthrough": family in ("module_plate", "long_heavy"),
        "standard_boxes": family not in ("module_plate", "long_heavy", "junk_edge"),
        "mix_mode": family == "steel_mix",
    }
    return base


def _mid50(st: Dict[str, Any]) -> Optional[float]:
    plan = st.get("container_plan") or {}
    if plan.get("worst_mid50") is not None:
        try:
            return float(plan["worst_mid50"])
        except Exception:
            pass
    try:
        from packing_assistant.tools.booking import _plan_worst_mid50

        return _plan_worst_mid50(plan)
    except Exception:
        return None


def _illegal(st: Dict[str, Any]) -> int:
    try:
        from packing_assistant.workteam_kpi import compute_kpis

        return int(compute_kpis(st).get("illegal_tool_calls") or 0)
    except Exception:
        return 0


def _ns_summary(st: Dict[str, Any]) -> Dict[str, Any]:
    ns = st.get("nonstandard_summary") or {}
    if not ns.get("overall"):
        rep = st.get("nonstandard_report") or {}
        if rep.get("overall"):
            try:
                from packing_assistant.tools.nonstandard_inspect import public_summary

                ns = public_summary(rep)
            except Exception:
                ns = {
                    "overall": rep.get("overall"),
                    "summary": rep.get("summary"),
                    "dashboard": rep.get("dashboard"),
                }
    if not ns.get("overall"):
        # 管线若未挂上，补跑一次
        try:
            from packing_assistant.tools.nonstandard_inspect import (
                inspect_nonstandard,
                public_summary,
            )

            full = inspect_nonstandard(
                materials=st.get("materials") or [],
                boxes=st.get("boxes") or [],
                container_type=str(st.get("container_type") or "40HQ"),
                packing_options=st.get("packing_options") or {},
            )
            ns = public_summary(full)
        except Exception:
            ns = {}
    dash = ns.get("dashboard") or {}
    ui = dash.get("counts_for_ui") or {}
    sm = ns.get("summary") or {}
    return {
        "overall": ns.get("overall"),
        "n_ns": sm.get("n_nonstandard_materials"),
        "n_fail": sm.get("n_fail"),
        "overlength": ui.get("overlength"),
        "heavy": ui.get("heavy"),
        "struct_pending": ui.get("struct_pending"),
        "custom_shape": ui.get("custom_shape"),
    }


def _has_tool(st: Dict[str, Any], needle: str) -> bool:
    for step in st.get("agent_steps") or []:
        tools = step.get("tools_used") or step.get("tools") or []
        if isinstance(tools, str):
            tools = [tools]
        for t in tools:
            if needle in str(t):
                return True
        msg = str(step.get("message") or step.get("title") or "")
        if needle in msg:
            return True
    # kpi tool sequence
    try:
        from packing_assistant.workteam_kpi import compute_kpis

        seq = compute_kpis(st).get("tool_sequence") or []
        return any(needle in str(t) for t in seq)
    except Exception:
        return False


def run_pipeline(
    *,
    case_id: str,
    materials: List[Dict[str, Any]],
    opts: Dict[str, Any],
    agent_mode: str,
    session_id: str,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    err = ""
    st: Dict[str, Any] = {}
    try:
        st = run_agent_pipeline(
            f"workteams_random:{case_id}:{agent_mode}",
            materials=materials,
            packing_options=dict(opts),
            container_type="40HQ",
            max_containers=0,
            enable_auto_confirm=True,
            session_id=session_id[:80],
            save_artifacts=False,
            agent_mode=agent_mode,
            max_llm_rounds=12,
        )
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        st = {
            "status": "error",
            "errors": [err, traceback.format_exc()[-1200:]],
            "container_plan": {},
            "agent_steps": [],
            "materials": materials,
            "packing_options": opts,
        }
    ms = int((time.time() - t0) * 1000)
    plan = st.get("container_plan") or {}
    illegal = _illegal(st)
    ns = _ns_summary(st)
    mid = _mid50(st)
    hard = bool(
        st.get("status") == "error"
        or illegal > 0
        or any("Traceback" in str(x) for x in (st.get("errors") or []))
    )
    # 成功标准：不崩、无非法工具；能装则 mid50 不惨（多柜≥2 时 mid≥0.50 或 ship 讨论）
    can = plan.get("can_fit")
    used = plan.get("containers_used")
    ship = st.get("ship_ok")
    soft_ok = True
    if can is True and used is not None and int(used) >= 2 and mid is not None:
        if float(mid) < 0.45 and ship is True:
            soft_ok = False  # 假出运过松
    pass_round = (not hard) and soft_ok and st.get("status") != "error"
    # junk_edge 缺尺寸预期 can_fit 假/无箱 —— 不硬 fail
    if "junk" in case_id and not can:
        pass_round = not hard

    return {
        "case_id": case_id,
        "agent_mode": agent_mode,
        "agent_style": st.get("agent_style") or "",
        "team_mode": st.get("team_mode") or "",
        "phase": st.get("phase"),
        "status": st.get("status"),
        "n_materials": len(materials),
        "n_boxes": len(st.get("boxes") or []),
        "can_fit": can,
        "containers_used": used,
        "n0": plan.get("n0"),
        "ship_ok": ship,
        "mid50": mid,
        "weight_util": plan.get("weight_utilization"),
        "strategy": (plan.get("strategy_decision") or {}).get("chosen"),
        "illegal": illegal,
        "n_steps": len(st.get("agent_steps") or []),
        "has_nonstandard_tool": _has_tool(st, "nonstandard"),
        "ns": ns,
        "hard_fail": hard,
        "pass": pass_round,
        "ms": ms,
        "error": err[:400] if err else "",
    }


def pick_families(rounds: int, names: Optional[Sequence[str]] = None) -> List[str]:
    pool = list(names) if names else list(FAMILIES)
    if not pool:
        pool = list(FAMILIES)
    out = []
    for i in range(rounds):
        out.append(pool[i % len(pool)])
    return out


def write_report(rows: List[Dict[str, Any]], meta: Dict[str, Any], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = out_dir / f"workteams_random_{ts}.json"
    mp = out_dir / "WORKTEAMS_RANDOM_REPORT.md"
    latest = out_dir / "latest.json"

    n = len(rows)
    n_pass = sum(1 for r in rows if r.get("pass"))
    n_hard = sum(1 for r in rows if r.get("hard_fail"))
    n_fit = sum(1 for r in rows if r.get("can_fit") is True)
    n_ship = sum(1 for r in rows if r.get("ship_ok") is True)
    n_illegal = sum(int(r.get("illegal") or 0) for r in rows)
    n_ns_tool = sum(1 for r in rows if r.get("has_nonstandard_tool"))
    by_fam: Dict[str, Dict[str, int]] = {}
    for r in rows:
        fam = (r.get("family") or "?")
        by_fam.setdefault(fam, {"n": 0, "pass": 0, "hard": 0, "fit": 0})
        by_fam[fam]["n"] += 1
        if r.get("pass"):
            by_fam[fam]["pass"] += 1
        if r.get("hard_fail"):
            by_fam[fam]["hard"] += 1
        if r.get("can_fit"):
            by_fam[fam]["fit"] += 1

    ns_levels: Dict[str, int] = {}
    for r in rows:
        lv = ((r.get("ns") or {}).get("overall")) or "—"
        ns_levels[lv] = ns_levels.get(lv, 0) + 1

    payload = {
        "meta": meta,
        "summary": {
            "n": n,
            "pass": n_pass,
            "pass_rate": round(n_pass / max(n, 1), 3),
            "hard_fail": n_hard,
            "can_fit": n_fit,
            "ship_ok": n_ship,
            "illegal_total": n_illegal,
            "nonstandard_tool_hits": n_ns_tool,
            "by_family": by_fam,
            "ns_levels": ns_levels,
            "ok": n_hard == 0 and n_illegal == 0 and n_pass >= max(1, int(0.7 * n)),
        },
        "rows": rows,
    }
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Workteams 随机多轮报告",
        "",
        f"- 生成: {meta.get('ts')}",
        f"- seed: **{meta.get('seed')}** · rounds: **{n}** · shadow: {meta.get('shadow')}",
        f"- pass: **{n_pass}/{n}** ({payload['summary']['pass_rate']:.0%}) · hard_fail: {n_hard} · illegal: {n_illegal}",
        f"- can_fit: {n_fit} · ship_ok: {n_ship} · nonstandard.tool 命中: {n_ns_tool}",
        f"- 总判定 ok: **{payload['summary']['ok']}**",
        "",
        "## 家族汇总",
        "",
        "| family | n | pass | fit | hard |",
        "|--------|--:|-----:|----:|-----:|",
    ]
    for fam, d in sorted(by_fam.items()):
        lines.append(f"| {fam} | {d['n']} | {d['pass']} | {d['fit']} | {d['hard']} |")
    lines += [
        "",
        "## 非标 overall 分布",
        "",
        "| overall | count |",
        "|---------|------:|",
    ]
    for k, v in sorted(ns_levels.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## 明细",
        "",
        "| # | case | family | fit | used | mid50 | ship | ns | toolNS | pass | ms |",
        "|--:|------|--------|:---:|-----:|------:|:----:|----|:------:|:----:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        mid = r.get("mid50")
        mid_s = f"{float(mid):.0%}" if mid is not None else "—"
        lines.append(
            f"| {i} | `{r.get('case_id')}` | {r.get('family')} | {r.get('can_fit')} | "
            f"{r.get('containers_used')} | {mid_s} | {r.get('ship_ok')} | "
            f"{(r.get('ns') or {}).get('overall')} | "
            f"{'Y' if r.get('has_nonstandard_tool') else '·'} | "
            f"{'✓' if r.get('pass') else '✗'} | {r.get('ms')} |"
        )
    fails = [r for r in rows if not r.get("pass")]
    if fails:
        lines += ["", "## 失败/关注票", ""]
        for r in fails:
            lines.append(
                f"- `{r.get('case_id')}` hard={r.get('hard_fail')} err={r.get('error') or '—'} "
                f"ns={(r.get('ns') or {}).get('overall')} fit={r.get('can_fit')}"
            )
    try:
        jp_disp = str(jp.relative_to(ROOT))
    except ValueError:
        jp_disp = str(jp)
    lines += [
        "",
        f"JSON: `{jp_disp}`",
        "",
    ]
    # shadow 对照表
    steps = [r for r in rows if r.get("path") == "steps"]
    llms = {r.get("case_id"): r for r in rows if r.get("path") == "llm_toolcall"}
    if llms:
        lines += [
            "## steps vs llm_toolcall 对照",
            "",
            "| case | steps used | llm used | fit 一致 | used差≤1 | agree | llm style |",
            "|------|----------:|---------:|:--------:|:--------:|:-----:|-----------|",
        ]
        for s in steps:
            cid = s.get("case_id")
            l = llms.get(cid) or {}
            su, lu = s.get("containers_used"), l.get("containers_used")
            fit_ok = s.get("can_fit") == l.get("can_fit")
            try:
                used_ok = abs(int(su or 0) - int(lu or 0)) <= 1
            except Exception:
                used_ok = False
            agree = l.get("agree_with_steps")
            if agree is None:
                agree = fit_ok and used_ok
            lines.append(
                f"| `{cid}` | {su} | {lu} | {'Y' if fit_ok else 'N'} | "
                f"{'Y' if used_ok else 'N'} | {'Y' if agree else 'N'} | {l.get('agent_style') or '—'} |"
            )
        n_agree = sum(
            1
            for s in steps
            if (llms.get(s.get("case_id")) or {}).get("agree_with_steps")
            or (
                s.get("can_fit") == (llms.get(s.get("case_id")) or {}).get("can_fit")
                and abs(
                    int(s.get("containers_used") or 0)
                    - int((llms.get(s.get("case_id")) or {}).get("containers_used") or 0)
                )
                <= 1
            )
        )
        lines += ["", f"影子一致率: **{n_agree}/{len(steps)}**", ""]
    mp.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", mp)
    print("wrote", jp)
    return mp


def main() -> int:
    ap = argparse.ArgumentParser(description="Workteams 随机多轮")
    ap.add_argument("--rounds", type=int, default=12, help="轮数（默认 12）")
    ap.add_argument("--seed", type=int, default=20260805)
    ap.add_argument(
        "--families",
        type=str,
        default="",
        help="逗号分隔家族，空=轮换 FAMILIES",
    )
    ap.add_argument("--shadow", action="store_true", help="每票再跑 llm_toolcall 影子（更慢）")
    ap.add_argument("--out-dir", type=str, default=str(OUT_DIR))
    args = ap.parse_args()

    fam_filter = [x.strip() for x in (args.families or "").split(",") if x.strip()] or None
    families = pick_families(args.rounds, fam_filter)
    out_dir = Path(args.out_dir)
    rows: List[Dict[str, Any]] = []
    t_all = time.time()

    print(
        f"== workteams random multi rounds={args.rounds} seed={args.seed} "
        f"shadow={args.shadow} =="
    )
    for i, family in enumerate(families):
        seed_i = int(args.seed) + i * 17
        case = gen_case(seed_i, family)
        mats = list(case.get("materials") or [])
        case_id = f"r{i:02d}_{family}_s{seed_i}"
        opts = _default_opts(family)
        print(f"--- [{i+1}/{args.rounds}] {case_id} mats={len(mats)} ---")
        steps = run_pipeline(
            case_id=case_id,
            materials=mats,
            opts=opts,
            agent_mode="steps",
            session_id=f"wtrnd-{case_id}-steps",
        )
        steps["family"] = family
        steps["seed"] = seed_i
        steps["path"] = "steps"
        flag = "PASS" if steps.get("pass") else "FAIL"
        print(
            f"  {flag} fit={steps.get('can_fit')} used={steps.get('containers_used')} "
            f"mid={steps.get('mid50')} ns={((steps.get('ns') or {}).get('overall'))} "
            f"illegal={steps.get('illegal')} ms={steps.get('ms')}"
        )
        rows.append(steps)

        if args.shadow:
            llm = run_pipeline(
                case_id=case_id,
                materials=mats,
                opts=opts,
                agent_mode="llm_toolcall",
                session_id=f"wtrnd-{case_id}-llm",
            )
            llm["family"] = family
            llm["seed"] = seed_i
            llm["path"] = "llm_toolcall"
            # 影子一致性
            agree = (steps.get("can_fit") == llm.get("can_fit")) and (
                abs(int(steps.get("containers_used") or 0) - int(llm.get("containers_used") or 0))
                <= 1
                if steps.get("containers_used") is not None
                and llm.get("containers_used") is not None
                else True
            )
            llm["agree_with_steps"] = agree
            llm["pass"] = bool(llm.get("pass") and agree)
            print(
                f"  SHADOW fit={llm.get('can_fit')} used={llm.get('containers_used')} "
                f"agree={agree} style={llm.get('agent_style')} ms={llm.get('ms')}"
            )
            rows.append(llm)

    meta = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "rounds": args.rounds,
        "shadow": bool(args.shadow),
        "families": families,
        "wall_s": round(time.time() - t_all, 1),
    }
    write_report(rows, meta, out_dir)
    # summary only steps for pass_rate gate when shadow doubles rows
    steps_rows = [r for r in rows if r.get("path") == "steps"]
    if not steps_rows:
        steps_rows = rows
    n_pass = sum(1 for r in steps_rows if r.get("pass"))
    n_hard = sum(1 for r in steps_rows if r.get("hard_fail"))
    illegal = sum(int(r.get("illegal") or 0) for r in steps_rows)
    rate = n_pass / max(len(steps_rows), 1)
    print(
        f"SUMMARY steps_pass={n_pass}/{len(steps_rows)} rate={rate:.0%} "
        f"hard={n_hard} illegal={illegal} wall={meta['wall_s']}s"
    )
    ok = n_hard == 0 and illegal == 0 and rate >= 0.70
    print("WORKTEAMS_RANDOM", "OK" if ok else "CHECK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
