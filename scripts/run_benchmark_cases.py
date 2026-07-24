#!/usr/bin/env python3
"""
跑 test/benchmarks 公开 BPP / 拼柜用例（第二阶段：已装箱 → 装柜）。

用法:
  python scripts/convert_bpp_to_cases.py
  python scripts/run_benchmark_cases.py
  python scripts/run_benchmark_cases.py --only sample_data_1,case_b
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_case(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expand_boxes(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    from scripts.convert_bpp_to_cases import expand_boxes_api

    return expand_boxes_api(case)


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.tools.bin3d import CONTAINER_INNER, pack_boxes_api

    c = case.get("container") or {}
    ctype = str(c.get("type") or "40HQ")
    # 注册自定义柜
    CONTAINER_INNER[ctype] = {
        "L": float(c.get("inner_length_mm") or CONTAINER_INNER.get("40HQ", {}).get("L", 12032)),
        "W": float(c.get("inner_width_mm") or 2352),
        "H": float(c.get("inner_height_mm") or 2698),
        "max_load_kg": float(c.get("max_payload_kg") or 26000),
    }
    boxes = expand_boxes(case)
    max_c = int(c.get("max_containers") or 1)
    t0 = time.time()
    plan = pack_boxes_api(boxes, container_type=ctype, max_containers=max_c)
    ms = int((time.time() - t0) * 1000)

    # 理论容积（全部货 / 单柜容积）
    cont_vol = (
        CONTAINER_INNER[ctype]["L"]
        * CONTAINER_INNER[ctype]["W"]
        * CONTAINER_INNER[ctype]["H"]
    )
    cargo_vol = sum(
        float(b["outer_size_mm"]["length"])
        * float(b["outer_size_mm"]["width"])
        * float(b["outer_size_mm"]["height"])
        for b in boxes
    )
    theo = cargo_vol / cont_vol if cont_vol else 0

    return {
        "name": case.get("name"),
        "description": case.get("description"),
        "source": case.get("source"),
        "container_type": ctype,
        "n_boxes": len(boxes),
        "max_containers": max_c,
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "space_utilization": plan.get("space_utilization"),
        "space_best": plan.get("space_utilization_best_container"),
        "weight_utilization": plan.get("weight_utilization"),
        "unpacked": len(plan.get("unpacked_box_ids") or []),
        "theo_vol_vs_one_bin": round(theo, 4),
        "ms": ms,
        "engine": plan.get("engine"),
        "metrics_note": plan.get("metrics_note"),
        "layout_n": len(plan.get("layout") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "test" / "benchmarks"))
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    d = Path(args.dir)
    if not d.is_absolute():
        d = ROOT / d
    if not d.exists():
        print("先运行: python scripts/convert_bpp_to_cases.py")
        return 1

    files = sorted(d.glob("*.json"))
    files = [f for f in files if f.name not in ("INDEX.json",)]
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]
        files = [f for f in files if any(k in f.stem for k in keys)]

    out_dir = ROOT / "output" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    print("=" * 64)
    print(f"Benchmark cases n={len(files)}")
    for f in files:
        case = load_case(f)
        print("-" * 64)
        print(f"CASE {case.get('name') or f.stem}")
        try:
            # expand via local to avoid import path issues
            r = _run_case_local(case)
            r["file"] = f.name
            r["ok"] = True
        except Exception as e:
            r = {"file": f.name, "name": case.get("name"), "ok": False, "error": str(e)}
            import traceback

            traceback.print_exc()
        results.append(r)
        if r.get("ok"):
            print(
                f"  boxes={r['n_boxes']} fit={r['can_fit']} used={r['containers_used']} "
                f"vol={r['space_utilization']} best={r.get('space_best')} "
                f"wt={r['weight_utilization']} unpacked={r['unpacked']} "
                f"theo1={r['theo_vol_vs_one_bin']} {r['ms']}ms"
            )
        else:
            print("  FAIL", r.get("error"))

    summary = {
        "results": results,
        "ok": sum(1 for x in results if x.get("ok")),
        "fail": sum(1 for x in results if not x.get("ok")),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rows = []
    for r in results:
        if not r.get("ok"):
            rows.append(
                f"<tr class='fail'><td>{r.get('file')}</td><td colspan='8'>{r.get('error')}</td></tr>"
            )
            continue
        rows.append(
            "<tr>"
            f"<td>{r.get('name')}</td><td>{r.get('container_type')}</td>"
            f"<td>{r.get('n_boxes')}</td><td>{r.get('can_fit')}</td>"
            f"<td>{r.get('containers_used')}</td><td>{r.get('space_utilization')}</td>"
            f"<td>{r.get('space_best')}</td><td>{r.get('weight_utilization')}</td>"
            f"<td>{r.get('unpacked')}</td><td>{r.get('ms')}</td></tr>"
        )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>BPP 基准</title>
<style>
body{{font-family:Microsoft YaHei,sans-serif;margin:24px;background:#0f1419;color:#e7ecf3}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border:1px solid #2a3a52;padding:6px}} th{{background:#1a2332;color:#93c5fd}}
.note{{background:#1e293b;padding:12px;border-radius:8px;line-height:1.5}}
.fail{{color:#fca5a5}}
</style></head><body>
<h1>公开 3D-BPP 拼柜基准 ok={summary['ok']} fail={summary['fail']}</h1>
<div class="note">
<strong>用途分层：</strong>D-Wave/Case A → 算法冒烟；Case B/40HQ style → 长件风格；
Case C/overweight → 限重风险；<b>业务正确性仍以 test/excel 远东数据为准</b>。
结构计算勿用这些通用箱当真。
</div>
<table><thead><tr>
<th>用例</th><th>柜型</th><th>箱数</th><th>can_fit</th><th>用柜</th>
<th>容积率</th><th>最满柜</th><th>重量率</th><th>未装</th><th>ms</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    print("=" * 64)
    print(f"DONE ok={summary['ok']} fail={summary['fail']}")
    print(f"  {out_dir / 'summary.json'}")
    print(f"  {out_dir / 'report.html'}")
    return 0 if summary["fail"] == 0 else 1


def _run_case_local(case: Dict[str, Any]) -> Dict[str, Any]:
    """不依赖 scripts 包导入。"""
    from packing_assistant.tools.bin3d import CONTAINER_INNER, pack_boxes_api

    c = case.get("container") or {}
    ctype = str(c.get("type") or "40HQ")
    CONTAINER_INNER[ctype] = {
        "L": float(c.get("inner_length_mm") or 12032),
        "W": float(c.get("inner_width_mm") or 2352),
        "H": float(c.get("inner_height_mm") or 2698),
        "max_load_kg": float(c.get("max_payload_kg") or 26000),
    }
    boxes: List[Dict[str, Any]] = []
    for b in case.get("boxes") or []:
        q = int(b.get("quantity") or 1)
        for i in range(q):
            bid = b.get("box_id") or "B"
            boxes.append(
                {
                    "box_id": f"{bid}-{i+1:03d}" if q > 1 else str(bid),
                    "outer_size_mm": {
                        "length": b["length_mm"],
                        "width": b["width_mm"],
                        "height": b["height_mm"],
                    },
                    "gross_weight_kg": float(b.get("weight_kg") or 0),
                    "allowRotate": bool(b.get("allow_rotate", True)),
                    "special_attributes": list(b.get("special_attributes") or []),
                }
            )
    max_c = int(c.get("max_containers") or 1)
    t0 = time.time()
    plan = pack_boxes_api(boxes, container_type=ctype, max_containers=max_c)
    ms = int((time.time() - t0) * 1000)
    cont_vol = (
        CONTAINER_INNER[ctype]["L"]
        * CONTAINER_INNER[ctype]["W"]
        * CONTAINER_INNER[ctype]["H"]
    )
    cargo_vol = sum(
        float(b["outer_size_mm"]["length"])
        * float(b["outer_size_mm"]["width"])
        * float(b["outer_size_mm"]["height"])
        for b in boxes
    )
    return {
        "name": case.get("name"),
        "description": case.get("description"),
        "source": case.get("source"),
        "container_type": ctype,
        "n_boxes": len(boxes),
        "max_containers": max_c,
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "space_utilization": plan.get("space_utilization"),
        "space_best": plan.get("space_utilization_best_container"),
        "weight_utilization": plan.get("weight_utilization"),
        "unpacked": len(plan.get("unpacked_box_ids") or []),
        "theo_vol_vs_one_bin": round(cargo_vol / cont_vol, 4) if cont_vol else 0,
        "ms": ms,
        "engine": plan.get("engine"),
        "metrics_note": plan.get("metrics_note"),
        "layout_n": len(plan.get("layout") or []),
    }


if __name__ == "__main__":
    sys.exit(main())
