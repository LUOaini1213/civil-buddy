#!/usr/bin/env python3
"""
联网评估优化循环 · 跑到本地 14:00（+08）为止。

结构：
1) 启动时拉公开装货/BPP 资料
2) 每 batch：16 路并行 × R 轮，调用 shipped run_agent_pipeline
3) 按 can_fit 弱结果中途 retune packing_options / materials
4) 墙钟 ≥ 今日 14:00 本地时间则停，写出 session rollup

用法:
  python scripts/netopt_until2.py --smoke-one
  python scripts/netopt_until2.py --end-hour 14 --workers 16 --rounds-per-batch 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")
os.environ.setdefault("PACKING_LLM_TOOLCALL", "0")

# Reuse netopt128 building blocks (load by path — scripts/ is not always a package)
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "netopt128_online_iter", ROOT / "scripts" / "netopt128_online_iter.py"
)
_n128 = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_n128)
base_opts = _n128.base_opts
fetch_online = _n128.fetch_online
load_material_bank = _n128.load_material_bank
retune_opts = _n128.retune_opts
run_one_round = _n128.run_one_round
NETOPT_EXT = _n128.EXT_DIR

OUT_DIR = ROOT / "output" / "netopt_until2"
EXT_DIR = ROOT / "data" / "external" / "netopt_until2"


def _log(msg: str) -> None:
    print(msg, flush=True)


def end_timestamp(end_hour: int = 14, end_minute: int = 0) -> datetime:
    """Local machine wall clock (host is +08)."""
    now = datetime.now()
    return now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)


def run_lane_batch(
    args: Tuple[int, List[Dict[str, Any]], int, Dict[str, Any], int],
) -> Dict[str, Any]:
    """lane_id, materials, n_rounds, start_opts, batch_id"""
    lane_id, materials0, n_rounds, start_opts, batch_id = args
    opts = deepcopy(start_opts or base_opts())
    mats = deepcopy(materials0)
    rounds_out: List[Dict[str, Any]] = []
    retunes: List[Dict[str, Any]] = []
    research_step = 0

    for r in range(1, n_rounds + 1):
        rec = run_one_round(
            {
                "lane_id": lane_id,
                "round_id": r + batch_id * 100,  # unique session id space
                "materials": mats,
                "opts": opts,
            }
        )
        # tag batch
        rec["batch_id"] = batch_id
        rounds_out.append(rec)

        need = (not rec["pass"]) or (rec.get("can_fit") is False)
        exploratory = (r == max(1, n_rounds // 2)) and (len(retunes) == 0)
        if (need or exploratory) and r < n_rounds:
            research_step += 1
            if exploratory and not need:
                opts = deepcopy(opts)
                opts["dense_mode"] = True
                opts["mix_mode"] = True
                opts["prefer_single_row"] = False
                ev = {
                    "batch_id": batch_id,
                    "after_round": r,
                    "lane_id": lane_id,
                    "reason": "exploratory_mid_batch_research_retune",
                    "knobs": ["dense_mode=True", "mix_mode=True", "prefer_single_row=False"],
                }
                retunes.append(ev)
            else:
                opts, mats, ev = retune_opts(opts, mats, rec, research_step=research_step)
                ev["batch_id"] = batch_id
                if ev.get("knobs"):
                    retunes.append(ev)

    n_pass = sum(1 for x in rounds_out if x["pass"])
    n_q = sum(1 for x in rounds_out if x.get("quality_can_fit"))
    return {
        "lane_id": lane_id,
        "batch_id": batch_id,
        "rounds": rounds_out,
        "n_rounds": len(rounds_out),
        "n_pass": n_pass,
        "n_fail": len(rounds_out) - n_pass,
        "n_quality_can_fit": n_q,
        "retunes": retunes,
        "n_retunes": len(retunes),
        "final_opts": opts,
    }


def write_progress(session: Dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "progress.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end-hour", type=int, default=14)
    ap.add_argument("--end-minute", type=int, default=0)
    ap.add_argument("--lanes", type=int, default=16)
    ap.add_argument("--rounds-per-batch", type=int, default=2)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--smoke-one", action="store_true")
    ap.add_argument("--max-batches", type=int, default=0, help="0=until deadline")
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end_ts = end_timestamp(args.end_hour, args.end_minute)
    now0 = datetime.now()
    deadline_already_past = now0 >= end_ts

    session: Dict[str, Any] = {
        "title": "netopt_until2",
        "started_at": now0.isoformat(),
        "end_ts": end_ts.isoformat(),
        "deadline_already_past": deadline_already_past,
        "end_reason": None,
        "batches": [],
        "total_attempts": 0,
        "total_pass": 0,
        "total_fail": 0,
        "total_retunes": 0,
        "total_quality_can_fit": 0,
        "optimize_knobs": [],
        "fetch": None,
        "entry": "packing_assistant.harness.run_agent_pipeline",
    }

    # fetch once at start (+ refresh every N batches)
    if args.skip_fetch:
        fetch_meta = {
            "skipped": True,
            "ok_count": 0,
            "items": [],
            "network_any_ok": False,
            "total_urls": 0,
            "research_notes": [],
        }
        for p in list(EXT_DIR.glob("*")) + list((ROOT / "data" / "external").glob("sample_data_*.txt")) + list(
            NETOPT_EXT.glob("*")
        ):
            if p.is_file():
                fetch_meta["items"].append(
                    {"name": p.name, "path": str(p), "ok": True, "bytes": p.stat().st_size, "url": "local"}
                )
                fetch_meta["ok_count"] += 1
    else:
        fetch_meta = fetch_online(EXT_DIR)

    session["fetch"] = {
        "ok_count": fetch_meta.get("ok_count"),
        "network_any_ok": fetch_meta.get("network_any_ok"),
        "research_notes": fetch_meta.get("research_notes"),
    }
    (OUT_DIR / "fetch_meta.json").write_text(
        json.dumps(fetch_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(
        f"START end_ts={end_ts.isoformat()} now={now0.isoformat()} "
        f"deadline_already_past={deadline_already_past} fetch_ok={fetch_meta.get('ok_count')}"
    )

    bank = load_material_bank(fetch_meta, n_lanes=args.lanes)

    if args.smoke_one:
        rec = run_one_round(
            {"lane_id": 0, "round_id": 1, "materials": bank[0], "opts": base_opts()}
        )
        _, _, ev = retune_opts(base_opts(), bank[0], rec, research_step=1)
        print(json.dumps({"rec": rec, "sample_retune": ev}, ensure_ascii=False, indent=2))
        return 0 if rec.get("pass") else 1

    batch_id = 0
    shared_opts = base_opts()
    knobs_all: List[str] = []

    # At least one full batch if deadline already past
    while True:
        now = datetime.now()
        if not deadline_already_past and now >= end_ts:
            session["end_reason"] = "deadline"
            _log(f"STOP deadline reached now={now.isoformat()}")
            break
        if deadline_already_past and batch_id >= 1:
            session["end_reason"] = "deadline_already_past"
            _log("STOP deadline_already_past after one batch")
            break
        if args.max_batches and batch_id >= args.max_batches:
            session["end_reason"] = "max_batches"
            break

        batch_id += 1
        t_batch = time.time()
        _log(
            f"BATCH {batch_id} start={datetime.now().isoformat()} "
            f"lanes={args.lanes} rounds={args.rounds_per_batch} workers={args.workers}"
        )

        # refresh materials bank every 3 batches (re-fetch optional light)
        if batch_id > 1 and batch_id % 3 == 1 and not args.skip_fetch:
            try:
                fetch_meta = fetch_online(EXT_DIR)
                bank = load_material_bank(fetch_meta, n_lanes=args.lanes)
                session["fetch"]["ok_count"] = fetch_meta.get("ok_count")
                session["fetch"]["network_any_ok"] = fetch_meta.get("network_any_ok") or session["fetch"].get(
                    "network_any_ok"
                )
                _log(f"REFETCH ok_count={fetch_meta.get('ok_count')}")
            except Exception as e:
                _log(f"REFETCH_FAIL {e}")

        lane_results: List[Dict[str, Any]] = []
        workers = max(1, min(args.workers, args.lanes))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {
                ex.submit(
                    run_lane_batch,
                    (i, bank[i % len(bank)], args.rounds_per_batch, shared_opts, batch_id),
                ): i
                for i in range(args.lanes)
            }
            for fut in as_completed(futs):
                try:
                    lane_results.append(fut.result())
                except Exception as e:
                    lid = futs[fut]
                    lane_results.append(
                        {
                            "lane_id": lid,
                            "batch_id": batch_id,
                            "rounds": [],
                            "n_rounds": 0,
                            "n_pass": 0,
                            "n_fail": args.rounds_per_batch,
                            "n_quality_can_fit": 0,
                            "retunes": [],
                            "n_retunes": 0,
                            "error": str(e),
                        }
                    )

        lane_results.sort(key=lambda x: x.get("lane_id", 0))
        b_att = sum(int(x.get("n_rounds") or 0) for x in lane_results)
        b_pass = sum(int(x.get("n_pass") or 0) for x in lane_results)
        b_fail = sum(int(x.get("n_fail") or 0) for x in lane_results)
        b_q = sum(int(x.get("n_quality_can_fit") or 0) for x in lane_results)
        b_ret = sum(int(x.get("n_retunes") or 0) for x in lane_results)
        for x in lane_results:
            for ev in x.get("retunes") or []:
                knobs_all.extend(ev.get("knobs") or [])
            # carry best densify forward as shared_opts seed
            fo = x.get("final_opts") or {}
            if fo.get("dense_mode"):
                shared_opts["dense_mode"] = True
            if fo.get("mix_mode"):
                shared_opts["mix_mode"] = True

        batch_rec = {
            "batch_id": batch_id,
            "wall_s": round(time.time() - t_batch, 2),
            "attempts": b_att,
            "pass": b_pass,
            "fail": b_fail,
            "quality_can_fit": b_q,
            "retunes": b_ret,
            "shared_opts_after": deepcopy(shared_opts),
            "lanes": [
                {
                    "lane_id": x["lane_id"],
                    "n_pass": x.get("n_pass"),
                    "n_fail": x.get("n_fail"),
                    "n_retunes": x.get("n_retunes"),
                    "n_quality_can_fit": x.get("n_quality_can_fit"),
                }
                for x in lane_results
            ],
            # keep last batch round details compact: only fail can_fit samples
            "sample_retunes": [
                ev for x in lane_results for ev in (x.get("retunes") or [])
            ][:20],
        }
        session["batches"].append(batch_rec)
        session["total_attempts"] += b_att
        session["total_pass"] += b_pass
        session["total_fail"] += b_fail
        session["total_retunes"] += b_ret
        session["total_quality_can_fit"] += b_q
        session["optimize_knobs"] = sorted(set(knobs_all))
        session["updated_at"] = datetime.now().isoformat()
        write_progress(session)

        _log(
            f"BATCH {batch_id} done attempts={b_att} pass={b_pass} fail={b_fail} "
            f"quality={b_q} retunes={b_ret} wall_s={batch_rec['wall_s']} "
            f"cum_attempts={session['total_attempts']}"
        )

        if deadline_already_past:
            session["end_reason"] = "deadline_already_past"
            break

        # brief pause so wall clock can advance cleanly between batches
        time.sleep(1)

        if datetime.now() >= end_ts:
            session["end_reason"] = "deadline"
            break

    if not session.get("end_reason"):
        session["end_reason"] = "completed_loop"

    session["finished_at"] = datetime.now().isoformat()
    session["all_green"] = session["total_fail"] == 0 and session["total_attempts"] > 0
    session["optimize"] = {
        "enabled": True,
        "n_retune_events": session["total_retunes"],
        "knobs_applied": session["optimize_knobs"],
        "policy": "per-lane mid-batch retune on can_fit false + exploratory mid-batch",
    }

    rollup_path = OUT_DIR / "rollup.json"
    rollup_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# Netopt until 14:00",
        "",
        f"- started: {session['started_at']}",
        f"- finished: {session['finished_at']}",
        f"- end_ts: {session['end_ts']}",
        f"- end_reason: **{session['end_reason']}**",
        f"- batches: **{len(session['batches'])}**",
        f"- attempts: **{session['total_attempts']}** pass: **{session['total_pass']}** fail: **{session['total_fail']}**",
        f"- quality_can_fit: **{session['total_quality_can_fit']}**",
        f"- retunes: **{session['total_retunes']}** knobs: {', '.join(session['optimize_knobs']) or '(none)'}",
        f"- fetch_ok: {session.get('fetch', {}).get('ok_count')} network: {session.get('fetch', {}).get('network_any_ok')}",
        f"- entry: `{session['entry']}`",
        "",
        "| batch | attempts | pass | fail | quality | retunes | wall_s |",
        "|-------|----------|------|------|---------|---------|--------|",
    ]
    for b in session["batches"]:
        md.append(
            f"| {b['batch_id']} | {b['attempts']} | {b['pass']} | {b['fail']} | "
            f"{b['quality_can_fit']} | {b['retunes']} | {b['wall_s']} |"
        )
    (OUT_DIR / "rollup.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    write_progress(session)

    _log(f"ROLLUP {rollup_path}")
    _log(
        f"FINAL end_reason={session['end_reason']} batches={len(session['batches'])} "
        f"attempts={session['total_attempts']} pass={session['total_pass']} "
        f"retunes={session['total_retunes']} all_green={session['all_green']}"
    )
    return 0 if session["total_attempts"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
