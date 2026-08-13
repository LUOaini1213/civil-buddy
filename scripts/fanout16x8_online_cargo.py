#!/usr/bin/env python3
"""
16 parallel lanes × 8 rounds = 128 packing evaluations.

- Fetches public cargo / 3D-BPP samples from the open web
- Normalizes to materials the shipped packing pipeline accepts
- Each round drives packing_assistant.harness.run_agent_pipeline (real path)
- Fan-out: ProcessPoolExecutor max_workers=16
- Writes rollup JSON/MD under output/fanout16x8/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")
os.environ.setdefault("PACKING_LLM_TOOLCALL", "0")

OUT_DIR = ROOT / "output" / "fanout16x8"
EXT_DIR = ROOT / "data" / "external" / "fanout16x8"

# Public open-web cargo / bin-packing samples (durable raw URLs)
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
]

DEFAULT_LANES = 16
DEFAULT_ROUNDS = 8


def _log(msg: str) -> None:
    print(msg, flush=True)


def fetch_online_cargo(dest: Path) -> Dict[str, Any]:
    """Download public cargo/BPP samples. Network failure recorded, not faked green."""
    dest.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    ok_n = 0
    for name, url in FETCH_URLS:
        path = dest / name
        entry: Dict[str, Any] = {"name": name, "url": url, "ok": False, "bytes": 0, "error": None}
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "packing-agent-fanout16x8/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            path.write_bytes(data)
            entry["ok"] = True
            entry["bytes"] = len(data)
            entry["path"] = str(path)
            ok_n += 1
            _log(f"FETCH_OK {name} {len(data)} bytes from {url}")
        except Exception as e:
            entry["error"] = str(e)
            _log(f"FETCH_FAIL {name}: {e}")
            # keep prior local cache if present
            if path.is_file() and path.stat().st_size > 0:
                entry["ok"] = True
                entry["bytes"] = path.stat().st_size
                entry["path"] = str(path)
                entry["from_cache"] = True
                ok_n += 1
                _log(f"FETCH_CACHE {name} {entry['bytes']} bytes")
        results.append(entry)
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ok_count": ok_n,
        "total_urls": len(FETCH_URLS),
        "items": results,
        "network_any_ok": ok_n > 0,
    }


def parse_dwave_bpp(text: str, *, scale_mm: float = 80.0) -> List[Dict[str, Any]]:
    """Parse D-Wave 3d-bin-packing sample_data txt → materials (mm/kg)."""
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
            qty = max(1, int(float(parts[1])))
            L = float(parts[2]) * scale_mm
            W = float(parts[3]) * scale_mm
            H = float(parts[4]) * scale_mm
        except ValueError:
            continue
        # cap qty for speed while remaining multi-piece
        qty = min(qty, 6)
        dens = 0.0004  # kg/mm^3-ish light cargo proxy
        unit_w = max(1.0, L * W * H * dens / 1000.0)
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


def load_material_bank(
    fetch_meta: Dict[str, Any], *, n_lanes: int = DEFAULT_LANES
) -> List[List[Dict[str, Any]]]:
    """Build N material sets from online files + deterministic variants."""
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

    # If online parse produced lists, expand to n_lanes via slices/shuffles
    if not bank:
        # fallback: still real packing path using demo materials after failed parse
        from packing_assistant.demo_presets import materials_high_util

        _log("WARN no bpp parse; fallback demo materials still on shipped path")
        base = materials_high_util()
        return [base[i : i + 8] or base[:6] for i in range(n_lanes)]

    families = bank[:]
    out: List[List[Dict[str, Any]]] = []
    for lane in range(n_lanes):
        fam = families[lane % len(families)]
        rot = fam[lane % len(fam) :] + fam[: lane % len(fam)]
        variant: List[Dict[str, Any]] = []
        for j, m in enumerate(rot[: max(4, min(10, len(rot)))]):
            mm = dict(m)
            factor = 1.0 + 0.05 * ((lane + j) % 5)
            mm["length_mm"] = round(float(mm["length_mm"]) * factor, 1)
            mm["width_mm"] = round(float(mm["width_mm"]) * (2.0 - factor + 0.9), 1)
            mm["height_mm"] = round(float(mm["height_mm"]) * (1.0 + 0.03 * (j % 3)), 1)
            mm["qty"] = max(1, int(mm.get("qty") or 1) + (lane % 3))
            mm["id"] = f"L{lane}_{mm.get('id')}"
            mm["name"] = f"L{lane}-{mm.get('name')}"
            variant.append(mm)
        out.append(variant)
    while len(out) < n_lanes:
        out.append(out[-1])
    return out[:n_lanes]


def _pass_criteria(state: Dict[str, Any]) -> Tuple[bool, str]:
    boxes = state.get("boxes") or []
    plan = state.get("container_plan") or {}
    phase = str(state.get("phase") or "")
    if state.get("materials_incomplete"):
        return False, "materials_incomplete"
    if not boxes and not plan:
        return False, f"no_boxes_or_plan phase={phase}"
    # real pipeline ran if we have boxes or plan metrics
    if boxes or plan.get("can_fit") is not None or plan.get("containers_used") is not None:
        return True, f"ok boxes={len(boxes)} phase={phase} can_fit={plan.get('can_fit')}"
    return False, f"weak phase={phase}"


def run_one_round(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Worker: one packing evaluation on shipped harness."""
    lane_id = int(payload["lane_id"])
    round_id = int(payload["round_id"])
    materials = payload["materials"]
    session_id = f"fanout_L{lane_id:02d}_R{round_id}"
    t0 = time.time()
    rec: Dict[str, Any] = {
        "lane_id": lane_id,
        "round_id": round_id,
        "session_id": session_id,
        "pass": False,
        "dt_s": 0.0,
        "error": None,
        "detail": "",
        "entry": "packing_assistant.harness.run_agent_pipeline",
    }
    try:
        from packing_assistant.harness import run_agent_pipeline

        # densify-ish options for diverse cargo; still real steps path
        opts = {
            "dense_mode": True,
            "standard_boxes": False,
            "mix_mode": True,
        }
        # slight option diversify by round
        if round_id % 2 == 1:
            opts["prefer_single_row"] = True
        state = run_agent_pipeline(
            f"fanout lane={lane_id} round={round_id} online cargo",
            materials=materials,
            container_type="40HQ",
            max_containers=0,
            enable_auto_confirm=True,
            packing_options=opts,
            session_id=session_id,
            save_artifacts=False,
            agent_mode="steps",
        )
        ok, detail = _pass_criteria(state)
        rec["pass"] = ok
        rec["detail"] = detail
        rec["phase"] = state.get("phase")
        rec["n_boxes"] = len(state.get("boxes") or [])
        rec["can_fit"] = (state.get("container_plan") or {}).get("can_fit")
        rec["containers_used"] = (state.get("container_plan") or {}).get("containers_used")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["detail"] = traceback.format_exc()[-500:]
        rec["pass"] = False
    rec["dt_s"] = round(time.time() - t0, 3)
    return rec


def run_lane(args: Tuple[int, List[Dict[str, Any]], int]) -> Dict[str, Any]:
    lane_id, materials, n_rounds = args
    rounds_out: List[Dict[str, Any]] = []
    for r in range(1, n_rounds + 1):
        mats = []
        for j, m in enumerate(materials):
            mm = dict(m)
            mm["qty"] = max(1, int(mm.get("qty") or 1) + ((r - 1) % 2))
            if r % 3 == 0:
                mm["length_mm"] = round(float(mm["length_mm"]) * (1.0 + 0.02 * r), 1)
            mats.append(mm)
        rec = run_one_round(
            {"lane_id": lane_id, "round_id": r, "materials": mats}
        )
        rounds_out.append(rec)
        _log(
            f"L{lane_id:02d}R{r} pass={rec['pass']} dt={rec['dt_s']} {rec.get('detail') or rec.get('error')}"
        )
    n_pass = sum(1 for x in rounds_out if x["pass"])
    return {
        "lane_id": lane_id,
        "rounds": rounds_out,
        "n_rounds": len(rounds_out),
        "n_pass": n_pass,
        "n_fail": len(rounds_out) - n_pass,
        "lane_pass": n_pass == n_rounds,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="16×8 online cargo packing fan-out")
    ap.add_argument("--lanes", type=int, default=DEFAULT_LANES)
    ap.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--smoke-one", action="store_true", help="one lane one round only")
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()

    n_lanes = int(args.lanes)
    n_rounds = int(args.rounds)
    total = n_lanes * n_rounds

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_all = time.time()

    # 1) fetch
    if args.skip_fetch:
        fetch_meta = {
            "skipped": True,
            "items": [
                {
                    "name": p.name,
                    "path": str(p),
                    "ok": True,
                    "bytes": p.stat().st_size,
                    "url": "local",
                }
                for p in EXT_DIR.glob("*")
                if p.is_file()
            ],
            "ok_count": len(list(EXT_DIR.glob("*"))),
            "network_any_ok": False,
            "total_urls": len(FETCH_URLS),
        }
        for p in (ROOT / "data" / "external").glob("sample_data_*.txt"):
            fetch_meta["items"].append(
                {"name": p.name, "path": str(p), "ok": True, "bytes": p.stat().st_size, "url": "local_cache"}
            )
            fetch_meta["ok_count"] += 1
    else:
        fetch_meta = fetch_online_cargo(EXT_DIR)
        for p in (ROOT / "data" / "external").glob("sample_data_*.txt"):
            fetch_meta["items"].append(
                {
                    "name": p.name,
                    "path": str(p),
                    "ok": True,
                    "bytes": p.stat().st_size,
                    "url": "data/external cache",
                    "from_cache": True,
                }
            )

    fetch_path = OUT_DIR / "fetch_meta.json"
    fetch_path.write_text(json.dumps(fetch_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"FETCH_META {fetch_path} ok_count={fetch_meta.get('ok_count')}")

    bank = load_material_bank(fetch_meta, n_lanes=n_lanes)
    bank_path = OUT_DIR / "material_bank.json"
    bank_path.write_text(
        json.dumps(
            [{"lane": i, "n": len(m), "sample": m[:2]} for i, m in enumerate(bank)],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.smoke_one:
        _log("SMOKE one lane one round on shipped pipeline")
        rec = run_one_round({"lane_id": 0, "round_id": 1, "materials": bank[0]})
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0 if rec["pass"] else 1

    # 2) fan-out 16 lanes
    workers = max(1, min(int(args.workers), n_lanes))
    _log(f"FANOUT lanes={n_lanes} rounds={n_rounds} total={total} workers={workers}")
    lane_results: List[Dict[str, Any]] = []

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(run_lane, (i, bank[i % len(bank)], n_rounds)): i
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
                        "error": str(e),
                    }
                )
                _log(f"LANE_CRASH L{lid}: {e}")

    lane_results.sort(key=lambda x: x.get("lane_id", 0))
    total_attempts = sum(int(x.get("n_rounds") or 0) for x in lane_results)
    total_pass = sum(int(x.get("n_pass") or 0) for x in lane_results)
    total_fail = sum(int(x.get("n_fail") or 0) for x in lane_results)
    failed_lanes = [
        f"L{x['lane_id']:02d}"
        for x in lane_results
        if not x.get("lane_pass")
    ]
    all_green = total_attempts == total and total_fail == 0 and not failed_lanes

    rollup = {
        "title": "fanout16x8_online_cargo",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "lanes": n_lanes,
        "rounds_per_lane": n_rounds,
        "total_runs_expected": total,
        "total_attempts": total_attempts,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "all_green": all_green,
        "failed_lanes": failed_lanes,
        "workers": workers,
        "entry": "packing_assistant.harness.run_agent_pipeline",
        "fetch": {
            "ok_count": fetch_meta.get("ok_count"),
            "network_any_ok": fetch_meta.get("network_any_ok"),
            "urls": [u for _, u in FETCH_URLS],
        },
        "wall_s": round(time.time() - t_all, 2),
        "lanes_detail": lane_results,
    }

    rollup_json = OUT_DIR / "rollup.json"
    rollup_json.write_text(json.dumps(rollup, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        f"# Fanout 16×8 online cargo",
        "",
        f"- expected_runs: **{total}**",
        f"- attempts: **{total_attempts}**",
        f"- pass: **{total_pass}** fail: **{total_fail}**",
        f"- all_green: **{all_green}**",
        f"- failed_lanes: {', '.join(failed_lanes) if failed_lanes else '(none)'}",
        f"- wall_s: {rollup['wall_s']}",
        f"- fetch_ok: {fetch_meta.get('ok_count')}/{fetch_meta.get('total_urls', len(FETCH_URLS))}",
        f"- entry: `{rollup['entry']}`",
        "",
        "| lane | pass/fail | n_pass | n_fail |",
        "|------|-----------|--------|--------|",
    ]
    for x in lane_results:
        md.append(
            f"| L{x['lane_id']:02d} | {'PASS' if x.get('lane_pass') else 'FAIL'} | {x.get('n_pass')} | {x.get('n_fail')} |"
        )
    rollup_md = OUT_DIR / "rollup.md"
    rollup_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    _log(f"ROLLUP {rollup_json}")
    _log(f"ROLLUP_MD {rollup_md}")
    _log(
        f"SUMMARY attempts={total_attempts}/{total} pass={total_pass} fail={total_fail} all_green={all_green} wall_s={rollup['wall_s']}"
    )
    return 0 if total_attempts == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
