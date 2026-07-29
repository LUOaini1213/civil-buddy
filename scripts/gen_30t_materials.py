#!/usr/bin/env python3
"""生成多套约 30t（净重）仿真物料，供多轮测试 / 演示。

输出:
  test/sim_materials/t30_<variant>/materials.json
  test/sim_materials/t30_<variant>/materials.xlsx  (若 openpyxl 可用)
  output/t30_batches/INDEX.json

用法:
  python scripts/gen_30t_materials.py
  python scripts/gen_30t_materials.py --variants 6 --target-t 30
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_SIM = ROOT / "test" / "sim_materials"
OUT_IDX = ROOT / "output" / "t30_batches"


def _row(
    i: int,
    *,
    name: str,
    spec: str,
    L: float,
    W: float,
    H: float,
    qty: int,
    unit_kg: float,
    part_no: str,
    note: str,
) -> Dict[str, Any]:
    q = max(1, int(qty))
    w = float(unit_kg)
    return {
        "id": f"T30-{i:04d}",
        "name": name,
        "spec": spec,
        "quantity": q,
        "weight_kg": round(w, 3),
        "total_weight_kg": round(w * q, 3),
        "length_mm": float(L),
        "width_mm": float(W),
        "height_mm": float(H),
        "part_no": part_no,
        "note": note,
        "category": "重件" if w >= 200 or w * q >= 500 else "普通件",
    }


def _net(mats: List[Dict[str, Any]]) -> float:
    return sum(float(m.get("total_weight_kg") or 0) for m in mats)


def variant_steel_tubes(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """镀锌钢通为主，接近 30t。"""
    unit = 125.0 + (seed % 5) * 5  # 125–145 kg
    n = max(1, int(math.ceil(target_kg / unit)))
    mats = []
    for i in range(n):
        mats.append(
            _row(
                i + 1,
                name=f"镀锌钢通-{i+1}",
                spec="13—铁件",
                L=1200 + (i % 7) * 100,
                W=200 + (i % 3) * 50,
                H=200 + (i % 2) * 50,
                qty=1,
                unit_kg=unit,
                part_no=f"SIM-T30-STEEL-{seed}",
                note=f"sim:t30 steel_tubes seed={seed}",
            )
        )
    return mats, "钢通重量主导 ~30t"


def variant_heavy_modules(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """密实模块（便于 dense 高利用率）。"""
    unit = 750.0 + (seed % 4) * 50  # 750–900
    n = max(1, int(math.ceil(target_kg / unit)))
    mats = []
    for i in range(n):
        mats.append(
            _row(
                i + 1,
                name=f"密实模块-{i+1}",
                spec="整包模块",
                L=1200,
                W=1000,
                H=1000 + (i % 3) * 50,
                qty=1,
                unit_kg=unit,
                part_no=f"SIM-T30-MOD-{seed}",
                note=f"sim:t30 heavy_modules seed={seed}",
            )
        )
    return mats, "密实模块 ~30t（dense 友好）"


def variant_plates_beams(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """长梁 + 板垛混装。"""
    mats: List[Dict[str, Any]] = []
    idx = 1
    # 长梁约 4–6t
    beam_n = 8 + seed % 4
    beam_w = 95.0 + seed * 3
    for i in range(beam_n):
        mats.append(
            _row(
                idx,
                name=f"H型长梁-{i+1}",
                spec="H350×175",
                L=5200 + (i % 3) * 200,
                W=350,
                H=175,
                qty=1,
                unit_kg=beam_w,
                part_no=f"SIM-T30-BEAM-{seed}",
                note=f"sim:t30 plates_beams seed={seed}",
            )
        )
        idx += 1
    rest = target_kg - _net(mats)
    plate_w = 420.0 + (seed % 5) * 20
    pn = max(1, int(math.ceil(rest / plate_w)))
    for i in range(pn):
        mats.append(
            _row(
                idx,
                name=f"厚板垛-{i+1}",
                spec="板材打包",
                L=2000,
                W=1000,
                H=400 + (i % 4) * 20,
                qty=1,
                unit_kg=plate_w,
                part_no=f"SIM-T30-PLATE-{seed}",
                note=f"sim:t30 plates_beams seed={seed}",
            )
        )
        idx += 1
    return mats, "长梁+板垛混装 ~30t"


def variant_mixed_short(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """短件堆量到 30t。"""
    mats = []
    unit = 80.0 + (seed % 6) * 10
    n = max(1, int(math.ceil(target_kg / unit)))
    for i in range(n):
        mats.append(
            _row(
                i + 1,
                name=f"短支撑-{i+1}",
                spec="13—铁件",
                L=800 + (i % 5) * 50,
                W=120,
                H=120,
                qty=1,
                unit_kg=unit,
                part_no=f"SIM-T30-SHORT-{seed}",
                note=f"sim:t30 mixed_short seed={seed}",
            )
        )
    return mats, "短件堆量 ~30t"


def variant_pallet_like(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """托盘型（crate 直通友好）。"""
    unit = 1000.0 + (seed % 3) * 50
    n = max(1, int(math.ceil(target_kg / unit)))
    mats = []
    for i in range(n):
        mats.append(
            _row(
                i + 1,
                name=f"托盘整包-{i+1}",
                spec="托盘",
                L=1100 + (i % 2) * 100,
                W=1100,
                H=1100 + (i % 3) * 50,
                qty=1,
                unit_kg=unit,
                part_no=f"SIM-T30-PAL-{seed}",
                note=f"sim:t30 pallet_like seed={seed}",
            )
        )
    return mats, "托盘整包 ~30t"


def variant_oversized_mix(target_kg: float, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """含少量超长 + 重块。"""
    mats: List[Dict[str, Any]] = []
    idx = 1
    for i in range(6 + seed % 3):
        mats.append(
            _row(
                idx,
                name=f"超长杆件-{i+1}",
                spec="超长铁件",
                L=6000 + (i % 2) * 200,
                W=180,
                H=180,
                qty=1,
                unit_kg=160 + seed * 2,
                part_no=f"SIM-T30-LONG-{seed}",
                note=f"sim:t30 oversized_mix seed={seed}",
            )
        )
        idx += 1
    rest = target_kg - _net(mats)
    block = 600.0 + seed * 25
    bn = max(1, int(math.ceil(rest / block)))
    for i in range(bn):
        mats.append(
            _row(
                idx,
                name=f"重块-{i+1}",
                spec="铸铁/配重块",
                L=900,
                W=900,
                H=600,
                qty=1,
                unit_kg=block,
                part_no=f"SIM-T30-BLK-{seed}",
                note=f"sim:t30 oversized_mix seed={seed}",
            )
        )
        idx += 1
    return mats, "超长+重块混装 ~30t"


GENERATORS = [
    ("steel_tubes", variant_steel_tubes),
    ("heavy_modules", variant_heavy_modules),
    ("plates_beams", variant_plates_beams),
    ("mixed_short", variant_mixed_short),
    ("pallet_like", variant_pallet_like),
    ("oversized_mix", variant_oversized_mix),
]


def _trim_to_target(mats: List[Dict[str, Any]], target_kg: float, tol: float = 0.08) -> List[Dict[str, Any]]:
    """微调数量使净重落在 target±tol。"""
    net = _net(mats)
    lo, hi = target_kg * (1 - tol), target_kg * (1 + tol)
    if lo <= net <= hi:
        return mats
    # 过重：从尾部删
    out = list(mats)
    while _net(out) > hi and len(out) > 1:
        out.pop()
    # 过轻：复制末行
    i = 0
    while _net(out) < lo and out:
        base = dict(out[-1])
        i += 1
        base["id"] = f"T30-X{i:04d}"
        base["name"] = f"{base.get('name')}-extra{i}"
        out.append(base)
        if i > 500:
            break
    return out


def write_case(case_id: str, mats: List[Dict[str, Any]], story: str, target_t: float) -> Dict[str, Any]:
    d = OUT_SIM / case_id
    d.mkdir(parents=True, exist_ok=True)
    net = _net(mats)
    payload = {
        "case_id": case_id,
        "story": story,
        "target_net_t": target_t,
        "net_kg": round(net, 1),
        "net_t": round(net / 1000.0, 3),
        "n_lines": len(mats),
        "expect": {
            "containers_by_weight_min": max(1, int(math.ceil(net / 26000.0))),
            "net_t_approx": target_t,
        },
        "materials": mats,
    }
    (d / "materials.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "materials"
        cols = [
            "id",
            "name",
            "spec",
            "quantity",
            "weight_kg",
            "total_weight_kg",
            "length_mm",
            "width_mm",
            "height_mm",
            "part_no",
            "note",
        ]
        ws.append(cols)
        for m in mats:
            ws.append([m.get(c) for c in cols])
        wb.save(d / "materials.xlsx")
        xlsx = str(d / "materials.xlsx")
    except Exception:
        xlsx = ""
    return {
        "case_id": case_id,
        "story": story,
        "net_kg": payload["net_kg"],
        "net_t": payload["net_t"],
        "n_lines": len(mats),
        "json": str(d / "materials.json"),
        "xlsx": xlsx,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=6, help="生成套数（最多 6 种模板循环）")
    ap.add_argument("--target-t", type=float, default=30.0, help="目标净重吨")
    args = ap.parse_args()

    target_kg = float(args.target_t) * 1000.0
    n = max(1, int(args.variants))
    index: List[Dict[str, Any]] = []

    for i in range(n):
        name, fn = GENERATORS[i % len(GENERATORS)]
        seed = i + 1
        mats, story = fn(target_kg, seed)
        mats = _trim_to_target(mats, target_kg)
        case_id = f"t30_{name}_s{seed}"
        meta = write_case(case_id, mats, story, args.target_t)
        index.append(meta)
        print(
            f"[OK] {case_id}: lines={meta['n_lines']} net={meta['net_t']}t "
            f"({meta['net_kg']}kg) — {story}"
        )

    OUT_IDX.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_t": args.target_t,
        "count": len(index),
        "cases": index,
    }
    (OUT_IDX / "INDEX.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 合并进 sim INDEX 片段
    sim_index_path = OUT_SIM / "INDEX.json"
    try:
        sim = json.loads(sim_index_path.read_text(encoding="utf-8")) if sim_index_path.exists() else {"cases": {}}
        if "cases" not in sim:
            sim["cases"] = {}
        for c in index:
            sim["cases"][c["case_id"]] = {
                "story": c["story"],
                "n_lines": c["n_lines"],
                "net_kg": c["net_kg"],
                "json": f"test/sim_materials/{c['case_id']}/materials.json",
                "xlsx": f"test/sim_materials/{c['case_id']}/materials.xlsx" if c.get("xlsx") else "",
                "expect": {"net_t_approx": args.target_t},
            }
        sim_index_path.write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("warn: merge INDEX", e)

    print(f"\nINDEX → {OUT_IDX / 'INDEX.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
