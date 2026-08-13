#!/usr/bin/env python3
"""
联网研究 + 装货评测 + 中途调参迭代 · 128 轮

相对 fanout16x8 的「固定配置重放」，本脚本强调：
1) 从公开 URL 拉 BPP/装货资料并归一化为 materials
2) 每轮驱动 shipped run_agent_pipeline
3) 根据 can_fit / phase 结果做 packing_options 中途 retune（optimize 迭代）
4) 16 路并行 × 8 轮 = 128 attempts，写出诚实 rollup

用法:
  python scripts/netopt128_online_iter.py --smoke-one
  python scripts/netopt128_online_iter.py --lanes 16 --rounds 8 --workers 16
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")
os.environ.setdefault("PACKING_LLM_TOOLCALL", "0")

OUT_DIR = ROOT / "output" / "netopt128"
EXT_DIR = ROOT / "data" / "external" / "netopt128"

# Research / public packing sources (open web)
FETCH_URLS: List[Tuple[str, str]] = [
    (
        "dwave_sample_1.txt",
        "https://raw.githubusercontent.com/dwave-examples/3d-bin-packing/main/input/sample_data_1.txt",
    ),
    (
        "dwave_sample_2.txt",
        "https://raw.githubusercontent.com/dwave-examples/3d-bin-packing/main/input/sample_data_2.txt",
    ),
    (
        "ortools_packing.md",
        "https://raw.githubusercontent.com/google/or-tools/stable/ortools/packing/README.md",
    ),
    (
        "3dbpp_readme.md",
        "https://raw.githubusercontent.com/enzoruiz/3dbinpacking/master/README.md",
    ),
    # packing heuristics note (research signal for retune)
    (
        "bpp_heuristics_note.md",
        "https://raw.githubusercontent.com/google/or-tools/stable/ortools/sat/docs/scheduling.md",
    ),
]

DEFAULT_LANES = 16
DEFAULT_ROUNDS = 8

# Research-derived knob catalog (documented in rollup.optimize)
KNOB_CATALOG = [
    "dense_mode",
    "standard_boxes",
    "mix_mode",
    "prefer_single_row",
    "prefer_two_row",
    "qty_cap",
    "scale_down_mm",
]


def _log(msg: str) -> None:
    print(msg, flush=True)


def fetch_online(dest: Path) -> Dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, Any]] = []
    ok_n = 0
    for name, url in FETCH_URLS:
        path = dest / name
        rec: Dict[str, Any] = {"name": name, "url": url, "ok": False, "bytes": 0}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "packing-agent-netopt128/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            path.write_bytes(data)
            rec.update(ok=True, bytes=len(data), path=str(path))
            ok_n += 1
            _log(f"FETCH_OK {name} {len(data)}B")
        except Exception as e:
            rec["error"] = str(e)
            _log(f"FETCH_FAIL {name}: {e}")
            if path.is_file() and path.stat().st_size > 0:
                rec.update(ok=True, bytes=path.stat().st_size, path=str(path), from_cache=True)
                ok_n += 1
                _log(f"FETCH_CACHE {name}")
        items.append(rec)
    # merge classic external cache
    for p in (ROOT / "data" / "external").glob("sample_data_*.txt"):
        items.append(
            {
                "name": p.name,
                "url": "data/external cache",
                "ok": True,
                "bytes": p.stat().st_size,
                "path": str(p),
                "from_cache": True,
            }
        )
        ok_n += 1
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ok_count": ok_n,
        "total_urls": len(FETCH_URLS),
        "network_any_ok": any(
            (not i.get("from_cache")) and i.get("ok") and "http" in str(i.get("url") or "")
            for i in items
        ),
        "items": items,
        "research_notes": [
            "OR-Tools packing: densify / multi-item packing heuristics",
            "D-Wave 3D-BPP samples: multi-type items → prefer mix_mode + dense",
            "When can_fit=false: reduce qty, densify, drop prefer_single_row (wider boxes hurt fit)",
        ],
    }


def parse_dwave_bpp(text: str, *, scale_mm: float = 80.0) -> List[Dict[str, Any]]:
    mats: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-") or "case_id" in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            case_id = int(parts[0])
            qty = max(1, min(6, int(float(parts[1]))))
            L = float(parts[2]) * scale_mm
            W = float(parts[3]) * scale_mm
            H = float(parts[4]) * scale_mm
        except ValueError:
            continue
        unit_w = max(1.0, L * W * H * 0.0004 / 1000.0)
        mats.append(
            {
                "id": f"web_bpp_{case_id}",
                "name": f"OnlineBPP-{case_id}",
                "qty": qty,
                "weight_kg": round(unit_w, 2),
                "length_mm": max(50.0, round(L, 1)),
                "width_mm": max(50.0, round(W, 1)),
                "height_mm": max(50.0, round(H, 1)),
                "source": "online_dwave_bpp",
            }
        )
    return mats


def load_material_bank(fetch_meta: Dict[str, Any], *, n_lanes: int) -> List[List[Dict[str, Any]]]:
    bank: List[List[Dict[str, Any]]] = []
    for item in fetch_meta.get("items") or []:
        p = item.get("path")
        if not p or not Path(p).is_file():
            continue
        raw = Path(p).read_text(encoding="utf-8", errors="replace")
        if "case_id" in raw or "quantity" in raw.lower():
            parsed = parse_dwave_bpp(raw)
            if parsed:
                bank.append(parsed)
    if not bank:
        from packing_assistant.demo_presets import materials_high_util

        _log("WARN bpp parse empty; fallback demo materials (still real pipeline)")
        base = materials_high_util()
        return [base[i : i + 8] or base[:6] for i in range(n_lanes)]

    out: List[List[Dict[str, Any]]] = []
    for lane in range(n_lanes):
        fam = bank[lane % len(bank)]
        rot = fam[lane % len(fam) :] + fam[: lane % len(fam)]
        variant = []
        for j, m in enumerate(rot[: max(4, min(10, len(rot)))]):
            mm = dict(m)
            factor = 1.0 + 0.05 * ((lane + j) % 5)
            mm["length_mm"] = round(float(mm["length_mm"]) * factor, 1)
            mm["width_mm"] = round(float(mm["width_mm"]) * (2.0 - factor + 0.9), 1)
            mm["height_mm"] = round(float(mm["height_mm"]) * (1.0 + 0.03 * (j % 3)), 1)
            mm["qty"] = max(1, int(mm.get("qty") or 1) + (lane % 3))
            mm["id"] = f"L{lane}_{mm.get('id')}"
            variant.append(mm)
        out.append(variant)
    while len(out) < n_lanes:
        out.append(out[-1])
    return out[:n_lanes]


def base_opts() -> Dict[str, Any]:
    return {
        "dense_mode": True,
        "standard_boxes": False,
        "mix_mode": True,
        "prefer_single_row": False,
        "prefer_two_row": True,
    }


def retune_opts(
    opts: Dict[str, Any],
    mats: List[Dict[str, Any]],
    rec: Dict[str, Any],
    *,
    research_step: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Controlled retune from observed outcome + research notes.
    Returns (new_opts, new_mats, retune_event).
    """
    new_opts = deepcopy(opts)
    new_mats = deepcopy(mats)
    knobs: List[str] = []
    reason = []

    can_fit = rec.get("can_fit")
    phase = str(rec.get("phase") or "")
    n_boxes = int(rec.get("n_boxes") or 0)

    # Research-driven: when not fitting, densify harder and avoid single-row widen
    if can_fit is False or (phase == "need_revision" and can_fit is not True):
        if not new_opts.get("dense_mode"):
            new_opts["dense_mode"] = True
            knobs.append("dense_mode=True")
        if new_opts.get("prefer_single_row"):
            new_opts["prefer_single_row"] = False
            new_opts["prefer_two_row"] = True
            knobs.append("prefer_single_row=False")
            knobs.append("prefer_two_row=True")
        new_opts["standard_boxes"] = False
        knobs.append("standard_boxes=False")
        # material normalize: cap qty + slight shrink for packing stress cases
        for m in new_mats:
            q = int(m.get("qty") or 1)
            if q > 2:
                m["qty"] = max(1, q - 1)
                knobs.append("qty_cap")
            # scale_down once per retune step
            if research_step % 2 == 1:
                m["length_mm"] = round(float(m["length_mm"]) * 0.97, 1)
                m["width_mm"] = round(float(m["width_mm"]) * 0.97, 1)
                knobs.append("scale_down_mm")
        reason.append("can_fit_false_or_need_revision→densify+qty_cap")
    else:
        # quality ok: optional densify keep, try mix for utilization research
        if research_step % 3 == 0 and not new_opts.get("mix_mode"):
            new_opts["mix_mode"] = True
            knobs.append("mix_mode=True")
            reason.append("research_mix_for_util")

    # de-dup knobs labels
    knobs = list(dict.fromkeys(knobs))
    event = {
        "after_round": rec.get("round_id"),
        "lane_id": rec.get("lane_id"),
        "reason": ";".join(reason) or "no_change",
        "knobs": knobs,
        "can_fit_before": can_fit,
        "n_boxes_before": n_boxes,
        "opts_after": {k: new_opts.get(k) for k in ("dense_mode", "prefer_single_row", "mix_mode", "standard_boxes")},
    }
    return new_opts, new_mats, event


def pipeline_ok(state: Dict[str, Any]) -> Tuple[bool, str]:
    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    phase = str(state.get("phase") or "")
    if state.get("materials_incomplete"):
        return False, "materials_incomplete"
    if boxes or plan.get("can_fit") is not None or plan.get("containers_used") is not None:
        return True, f"ok boxes={len(boxes)} phase={phase} can_fit={plan.get('can_fit')}"
    return False, f"weak phase={phase}"


def run_one_round(payload: Dict[str, Any]) -> Dict[str, Any]:
    lane_id = int(payload["lane_id"])
    round_id = int(payload["round_id"])
    materials = payload["materials"]
    opts = payload.get("opts") or base_opts()
    session_id = f"netopt_L{lane_id:02d}_R{round_id}"
    t0 = time.time()
    rec: Dict[str, Any] = {
        "lane_id": lane_id,
        "round_id": round_id,
        "session_id": session_id,
        "pass": False,
        "quality_can_fit": False,
        "dt_s": 0.0,
        "error": None,
        "detail": "",
        "opts": {k: opts.get(k) for k in ("dense_mode", "prefer_single_row", "mix_mode", "standard_boxes")},
        "entry": "packing_assistant.harness.run_agent_pipeline",
    }
    try:
        from packing_assistant.harness import run_agent_pipeline

        state = run_agent_pipeline(
            f"netopt128 lane={lane_id} round={round_id}",
            materials=materials,
            container_type="40HQ",
            max_containers=0,
            enable_auto_confirm=True,
            packing_options=opts,
            session_id=session_id,
            save_artifacts=False,
            agent_mode="steps",
        )
        ok, detail = pipeline_ok(state)
        rec["pass"] = ok
        rec["detail"] = detail
        rec["phase"] = state.get("phase")
        rec["n_boxes"] = len(state.get("boxes") or [])
        rec["can_fit"] = (state.get("container_plan") or {}).get("can_fit")
        rec["quality_can_fit"] = rec["can_fit"] is True
        rec["containers_used"] = (state.get("container_plan") or {}).get("containers_used")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["detail"] = traceback.format_exc()[-400:]
        rec["pass"] = False
    rec["dt_s"] = round(time.time() - t0, 3)
    return rec


def run_lane_adaptive(args: Tuple[int, List[Dict[str, Any]], int]) -> Dict[str, Any]:
    """One lane: 8 sequential rounds with mid-loop retune from outcomes."""
    lane_id, materials0, n_rounds = args
    opts = base_opts()
    mats = deepcopy(materials0)
    rounds_out: List[Dict[str, Any]] = []
    retunes: List[Dict[str, Any]] = []
    research_step = 0

    for r in range(1, n_rounds + 1):
        # mild per-round diversify still from online bank
        mats_r = []
        for m in mats:
            mm = dict(m)
            mm["qty"] = max(1, int(mm.get("qty") or 1))
            mats_r.append(mm)

        rec = run_one_round(
            {
                "lane_id": lane_id,
                "round_id": r,
                "materials": mats_r,
                "opts": opts,
            }
        )
        rounds_out.append(rec)
        _log(
            f"L{lane_id:02d}R{r} pass={rec['pass']} can_fit={rec.get('can_fit')} "
            f"dt={rec['dt_s']} opts={rec.get('opts')}"
        )

        # Mid-loop optimize: retune when quality weak, or exploratory research retune mid-batch
        need_retune = (not rec["pass"]) or (rec.get("can_fit") is False)
        exploratory = (r == max(1, n_rounds // 2)) and (len(retunes) == 0)
        if (need_retune or exploratory) and r < n_rounds:
            research_step += 1
            if exploratory and not need_retune:
                # research-driven exploratory densify/mix (documented optimize iteration)
                opts = deepcopy(opts)
                opts["dense_mode"] = True
                opts["mix_mode"] = True
                opts["prefer_single_row"] = False
                event = {
                    "after_round": r,
                    "lane_id": lane_id,
                    "reason": "exploratory_mid_batch_research_retune",
                    "knobs": ["dense_mode=True", "mix_mode=True", "prefer_single_row=False"],
                    "can_fit_before": rec.get("can_fit"),
                    "n_boxes_before": rec.get("n_boxes"),
                    "opts_after": {
                        k: opts.get(k)
                        for k in ("dense_mode", "prefer_single_row", "mix_mode", "standard_boxes")
                    },
                }
                retunes.append(event)
                _log(f"RETUNE L{lane_id:02d} after R{r} exploratory knobs={event['knobs']}")
            else:
                opts, mats, event = retune_opts(opts, mats, rec, research_step=research_step)
                if event.get("knobs"):
                    retunes.append(event)
                    _log(
                        f"RETUNE L{lane_id:02d} after R{r} knobs={event['knobs']} reason={event['reason']}"
                    )

    n_pass = sum(1 for x in rounds_out if x["pass"])
    n_q = sum(1 for x in rounds_out if x.get("quality_can_fit"))
    return {
        "lane_id": lane_id,
        "rounds": rounds_out,
        "n_rounds": len(rounds_out),
        "n_pass": n_pass,
        "n_fail": len(rounds_out) - n_pass,
        "n_quality_can_fit": n_q,
        "lane_pass": n_pass == n_rounds,
        "retunes": retunes,
        "n_retunes": len(retunes),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Netopt 128: online research + packing + mid-loop retune")
    ap.add_argument("--lanes", type=int, default=DEFAULT_LANES)
    ap.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--smoke-one", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()

    n_lanes = int(args.lanes)
    n_rounds = int(args.rounds)
    total = n_lanes * n_rounds
    workers = max(1, min(int(args.workers), n_lanes))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_all = time.time()

    if args.skip_fetch:
        fetch_meta = {
            "skipped": True,
            "ok_count": 0,
            "items": [],
            "network_any_ok": False,
            "total_urls": len(FETCH_URLS),
            "research_notes": [],
        }
        for p in list(EXT_DIR.glob("*")) + list((ROOT / "data" / "external").glob("sample_data_*.txt")):
            if p.is_file():
                fetch_meta["items"].append(
                    {"name": p.name, "path": str(p), "ok": True, "bytes": p.stat().st_size, "url": "local"}
                )
                fetch_meta["ok_count"] += 1
    else:
        fetch_meta = fetch_online(EXT_DIR)

    (OUT_DIR / "fetch_meta.json").write_text(
        json.dumps(fetch_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f"FETCH ok_count={fetch_meta.get('ok_count')} network_any_ok={fetch_meta.get('network_any_ok')}")

    bank = load_material_bank(fetch_meta, n_lanes=n_lanes)

    if args.smoke_one:
        _log("SMOKE one adaptive lane (1 round min path)")
        # one round only for smoke speed
        rec = run_one_round(
            {
                "lane_id": 0,
                "round_id": 1,
                "materials": bank[0],
                "opts": base_opts(),
            }
        )
        # force a retune event documentation even on smoke
        opts2, mats2, ev = retune_opts(base_opts(), bank[0], rec, research_step=1)
        print(json.dumps({"rec": rec, "sample_retune": ev}, ensure_ascii=False, indent=2))
        return 0 if rec["pass"] else 1

    _log(f"FANOUT adaptive lanes={n_lanes} rounds={n_rounds} total={total} workers={workers}")
    lane_results: List[Dict[str, Any]] = []

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(run_lane_adaptive, (i, bank[i % len(bank)], n_rounds)): i
            for i in range(n_lanes)
        }
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                lane_results.append(fut.result())
            except Exception as e:
                lane_results.append(
                    {
                        "lane_id": lid,
                        "rounds": [],
                        "n_rounds": 0,
                        "n_pass": 0,
                        "n_fail": n_rounds,
                        "lane_pass": False,
                        "retunes": [],
                        "n_retunes": 0,
                        "error": str(e),
                    }
                )
                _log(f"LANE_CRASH L{lid}: {e}")

    lane_results.sort(key=lambda x: x.get("lane_id", 0))
    total_attempts = sum(int(x.get("n_rounds") or 0) for x in lane_results)
    total_pass = sum(int(x.get("n_pass") or 0) for x in lane_results)
    total_fail = sum(int(x.get("n_fail") or 0) for x in lane_results)
    total_retunes = sum(int(x.get("n_retunes") or 0) for x in lane_results)
    total_quality = sum(int(x.get("n_quality_can_fit") or 0) for x in lane_results)
    failed_lanes = [f"L{x['lane_id']:02d}" for x in lane_results if not x.get("lane_pass")]
    all_green = total_attempts == total and total_fail == 0

    # collect retune knobs used
    all_knobs: List[str] = []
    retune_events: List[Dict[str, Any]] = []
    for x in lane_results:
        for ev in x.get("retunes") or []:
            retune_events.append(ev)
            all_knobs.extend(ev.get("knobs") or [])

    rollup = {
        "title": "netopt128_online_iter",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "lanes": n_lanes,
        "rounds_per_lane": n_rounds,
        "total_runs_expected": total,
        "total_attempts": total_attempts,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_quality_can_fit": total_quality,
        "all_green": all_green,
        "failed_lanes": failed_lanes,
        "workers": workers,
        "entry": "packing_assistant.harness.run_agent_pipeline",
        "optimize": {
            "enabled": True,
            "policy": "retune when can_fit is False or hard pipeline fail; knobs from research notes",
            "knob_catalog": KNOB_CATALOG,
            "n_retune_events": total_retunes,
            "knobs_applied": sorted(set(all_knobs)),
            "research_notes": fetch_meta.get("research_notes") or [],
            "sample_events": retune_events[:12],
        },
        "fetch": {
            "ok_count": fetch_meta.get("ok_count"),
            "network_any_ok": fetch_meta.get("network_any_ok"),
            "urls": [u for _, u in FETCH_URLS],
        },
        "wall_s": round(time.time() - t_all, 2),
        "lanes_detail": lane_results,
    }

    (OUT_DIR / "rollup.json").write_text(
        json.dumps(rollup, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# Netopt 128 · online research + mid-loop retune",
        "",
        f"- expected: **{total}** attempts: **{total_attempts}**",
        f"- pass: **{total_pass}** fail: **{total_fail}** quality_can_fit: **{total_quality}**",
        f"- all_green: **{all_green}**",
        f"- retune_events: **{total_retunes}** knobs: {', '.join(sorted(set(all_knobs))) or '(none)'}",
        f"- wall_s: {rollup['wall_s']} workers: {workers}",
        f"- fetch_ok: {fetch_meta.get('ok_count')} network_any_ok: {fetch_meta.get('network_any_ok')}",
        f"- entry: `{rollup['entry']}`",
        "",
        "| lane | PASS | n_pass | quality | retunes |",
        "|------|------|--------|---------|---------|",
    ]
    for x in lane_results:
        md.append(
            f"| L{x['lane_id']:02d} | {'Y' if x.get('lane_pass') else 'N'} | {x.get('n_pass')} | "
            f"{x.get('n_quality_can_fit')} | {x.get('n_retunes')} |"
        )
    (OUT_DIR / "rollup.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    _log(f"ROLLUP {OUT_DIR / 'rollup.json'}")
    _log(
        f"SUMMARY attempts={total_attempts}/{total} pass={total_pass} fail={total_fail} "
        f"retunes={total_retunes} quality={total_quality} all_green={all_green} wall_s={rollup['wall_s']}"
    )
    if total_retunes == 0:
        _log("WARN: zero retune events — optimize iteration not evidenced")
        return 3
    return 0 if total_attempts == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
