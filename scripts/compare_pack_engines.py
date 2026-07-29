#!/usr/bin/env python3
"""装载引擎 A/B 对照：python-laff-3d vs 可选 skjolber。

用法:
  python scripts/compare_pack_engines.py
  python scripts/compare_pack_engines.py --cases case_a_small_cartons_20gp,case_b_long_frames_40hq
  python scripts/compare_pack_engines.py --out output/engine_ab_report.json

输出: 利用率 / can_fit / 用时 / 引擎可用性。skjolber 未启动时仅跑 laff 并标注 unavailable。
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


def _load_cases(only: Optional[List[str]]) -> List[Path]:
    bench = ROOT / "test" / "benchmarks"
    paths = sorted(bench.glob("*.json"))
    paths = [p for p in paths if p.name != "INDEX.json"]
    if only:
        want = set(only)
        paths = [p for p in paths if p.stem in want]
    return paths


def _expand(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    from scripts.convert_bpp_to_cases import expand_boxes_api

    return expand_boxes_api(case)


def _run_laff(boxes: List[Dict[str, Any]], ctype: str, max_c: int) -> Dict[str, Any]:
    from packing_assistant.tools.bin3d import CONTAINER_INNER, pack_boxes_api

    # 保持默认柜；自定义柜已在 case 中 type 对应
    t0 = time.perf_counter()
    plan = pack_boxes_api(boxes, container_type=ctype, max_containers=max_c)
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "engine": plan.get("engine") or "python-laff-3d",
        "ok": True,
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "space_utilization": plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "unpacked": len(plan.get("unpacked_box_ids") or []),
        "layout_n": len(plan.get("layout") or []),
        "ms": ms,
        "error": None,
        "container_inner": CONTAINER_INNER.get(ctype),
    }


def _run_skjolber(boxes: List[Dict[str, Any]], ctype: str, max_c: int) -> Dict[str, Any]:
    from packing_assistant.skjolber_client import (
        health_check,
        is_skjolber_configured,
        pack_via_skjolber,
    )

    if not is_skjolber_configured():
        return {
            "engine": "skjolber",
            "ok": False,
            "available": False,
            "error": "SKJOLBER_URL 未配置",
            "ms": 0,
        }
    try:
        h = health_check(timeout=1.5)
        if not h.get("ok"):
            return {
                "engine": "skjolber",
                "ok": False,
                "available": False,
                "error": h.get("reason") or "health not ok",
                "ms": 0,
            }
    except Exception as e:
        return {
            "engine": "skjolber",
            "ok": False,
            "available": False,
            "error": str(e),
            "ms": 0,
        }

    t0 = time.perf_counter()
    try:
        plan = pack_via_skjolber(boxes, container_type=ctype, max_containers=max_c)
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "engine": plan.get("engine") or "skjolber",
            "ok": True,
            "available": True,
            "can_fit": plan.get("can_fit"),
            "containers_used": plan.get("containers_used"),
            "space_utilization": plan.get("space_utilization"),
            "weight_utilization": plan.get("weight_utilization"),
            "unpacked": len(plan.get("unpacked_box_ids") or []),
            "layout_n": len(plan.get("layout") or []),
            "ms": ms,
            "error": None,
        }
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "engine": "skjolber",
            "ok": False,
            "available": True,
            "error": str(e),
            "ms": ms,
        }


def _diff_row(laff: Dict[str, Any], skj: Dict[str, Any]) -> Dict[str, Any]:
    if not skj.get("ok"):
        return {
            "space_delta": None,
            "containers_delta": None,
            "note": skj.get("error") or "skjolber unavailable",
        }
    su_l = float(laff.get("space_utilization") or 0)
    su_s = float(skj.get("space_utilization") or 0)
    cu_l = int(laff.get("containers_used") or 0)
    cu_s = int(skj.get("containers_used") or 0)
    return {
        "space_delta": round(su_s - su_l, 4),
        "containers_delta": cu_s - cu_l,
        "faster": "laff" if (laff.get("ms") or 0) <= (skj.get("ms") or 0) else "skjolber",
        "note": "positive space_delta ⇒ skjolber 外廓摆柜率更高",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="python-laff-3d vs skjolber A/B")
    ap.add_argument("--cases", default="", help="逗号分隔 case stem，默认全部 benchmarks")
    ap.add_argument(
        "--out",
        default=str(ROOT / "output" / "engine_ab_report.json"),
        help="JSON 报告路径",
    )
    args = ap.parse_args()
    only = [x.strip() for x in args.cases.split(",") if x.strip()] or None
    paths = _load_cases(only)
    if not paths:
        print("无用例", file=sys.stderr)
        return 2

    rows: List[Dict[str, Any]] = []
    for path in paths:
        case = json.loads(path.read_text(encoding="utf-8"))
        c = case.get("container") or {}
        ctype = str(c.get("type") or "40HQ")
        max_c = int(c.get("max_containers") or 1)
        boxes = _expand(case)
        # 自定义柜内尺寸
        if c.get("inner_length_mm"):
            from packing_assistant.tools.bin3d import CONTAINER_INNER

            CONTAINER_INNER[ctype] = {
                "L": float(c.get("inner_length_mm") or 12032),
                "W": float(c.get("inner_width_mm") or 2352),
                "H": float(c.get("inner_height_mm") or 2698),
                "max_load_kg": float(c.get("max_payload_kg") or 26000),
            }
        laff = _run_laff(boxes, ctype, max_c)
        skj = _run_skjolber(boxes, ctype, max_c)
        row = {
            "name": case.get("name") or path.stem,
            "source": case.get("source"),
            "container_type": ctype,
            "max_containers": max_c,
            "n_boxes": len(boxes),
            "python_laff_3d": laff,
            "skjolber": skj,
            "diff": _diff_row(laff, skj),
        }
        rows.append(row)
        status = "OK" if laff.get("ok") else "FAIL"
        skj_s = (
            f"skj space={skj.get('space_utilization')} used={skj.get('containers_used')}"
            if skj.get("ok")
            else f"skj n/a ({skj.get('error')})"
        )
        print(
            f"[{status}] {row['name']}: laff space={laff.get('space_utilization')} "
            f"used={laff.get('containers_used')} ms={laff.get('ms')} | {skj_s}"
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "harness": "packing-agent engine A/B",
        "note": (
            "外廓摆柜率 space_utilization 仅布局松紧；订柜看 booking_volume。"
            "skjolber 需 SKJOLBER_URL + 服务健康。"
        ),
        "cases": rows,
        "summary": {
            "n_cases": len(rows),
            "laff_ok": sum(1 for r in rows if r["python_laff_3d"].get("ok")),
            "skjolber_ok": sum(1 for r in rows if r["skjolber"].get("ok")),
            "skjolber_available": any(
                r["skjolber"].get("available") or r["skjolber"].get("ok") for r in rows
            ),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告 → {out}")
    print(
        f"summary: laff_ok={report['summary']['laff_ok']}/{report['summary']['n_cases']} "
        f"skjolber_ok={report['summary']['skjolber_ok']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
