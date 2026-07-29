#!/usr/bin/env python3
"""生成随机约 80t（净重）仿真物料，供多柜/多轮测试。

输出:
  test/sim_materials/t80_<variant>/materials.json
  test/sim_materials/t80_<variant>/materials.xlsx
  output/t80_batches/INDEX.json

用法:
  python scripts/gen_80t_materials.py
  python scripts/gen_80t_materials.py --seed 42 --target-t 80
  python scripts/gen_80t_materials.py --variants 4 --seed 7
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_SIM = ROOT / "test" / "sim_materials"
OUT_IDX = ROOT / "output" / "t80_batches"


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
    prefix: str = "T80",
) -> Dict[str, Any]:
    q = max(1, int(qty))
    w = float(unit_kg)
    return {
        "id": f"{prefix}-{i:04d}",
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


def _trim_to_target(
    mats: List[Dict[str, Any]],
    target_kg: float,
    rng: random.Random,
    tol: float = 0.05,
    prefix: str = "T80",
) -> List[Dict[str, Any]]:
    lo, hi = target_kg * (1 - tol), target_kg * (1 + tol)
    out = list(mats)
    while _net(out) > hi and len(out) > 1:
        out.pop(rng.randrange(len(out)))
    i = 0
    while _net(out) < lo and out:
        need = lo - _net(out)
        i += 1
        # 不足时追加明确配重，避免复制后仍偏轻
        uw = min(max(need, 80.0), 900.0)
        out.append(
            {
                "id": f"{prefix}-X{i:04d}",
                "name": f"补重块-{i}",
                "spec": "配重",
                "quantity": 1,
                "weight_kg": round(uw, 3),
                "total_weight_kg": round(uw, 3),
                "length_mm": 900.0,
                "width_mm": 900.0,
                "height_mm": 600.0,
                "part_no": "SIM-T80-PAD",
                "note": "trim pad",
                "category": "重件" if uw >= 200 else "普通件",
            }
        )
        if i > 200:
            break
    # 末行微调：单行调整幅度限制，避免合成 80t 怪兽行
    net = _net(out)
    if out and net > 0 and abs(net - target_kg) / target_kg > 0.02:
        last = out[-1]
        q = max(1, int(last.get("quantity") or 1))
        rest_without = net - float(last.get("total_weight_kg") or 0)
        need_line = target_kg - rest_without
        unit = need_line / q
        base_u = float(last.get("weight_kg") or unit)
        # 最多 ±40% 或 ±200kg
        lo_u = max(10.0, base_u * 0.6)
        hi_u = base_u * 1.4 + 200.0
        unit = max(lo_u, min(hi_u, unit))
        last["weight_kg"] = round(unit, 3)
        last["total_weight_kg"] = round(unit * q, 3)
        # 仍不足则追加小配重块
        j = 0
        while _net(out) < target_kg * 0.97 and j < 40:
            j += 1
            gap = target_kg - _net(out)
            uw = min(max(gap, 30.0), 500.0)
            out.append(
                {
                    "id": f"{prefix}-F{j:04d}",
                    "name": f"微调配重-{j}",
                    "spec": "配重",
                    "quantity": 1,
                    "weight_kg": round(uw, 3),
                    "total_weight_kg": round(uw, 3),
                    "length_mm": 800.0,
                    "width_mm": 800.0,
                    "height_mm": 500.0,
                    "part_no": "SIM-T80-FINE",
                    "note": "trim fill",
                    "category": "重件" if uw >= 200 else "普通件",
                }
            )
    return out


def variant_random_mixed(target_kg: float, rng: random.Random, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """随机混装：钢通/短件/板垛/模块/少量超长，凑到 ~80t。"""
    mats: List[Dict[str, Any]] = []
    idx = 1
    remaining = target_kg

    pools = [
        # (name_prefix, spec, L,W,H ranges, unit_kg range, weight_share)
        ("镀锌钢通", "13—铁件", (900, 1800), (150, 250), (150, 250), (90, 160), 0.28),
        ("短支撑", "13—铁件", (600, 1200), (100, 180), (100, 180), (50, 120), 0.18),
        ("厚板垛", "板材打包", (1500, 2500), (800, 1200), (200, 500), (300, 600), 0.18),
        ("密实模块", "整包模块", (1000, 1400), (900, 1200), (900, 1300), (600, 1100), 0.16),
        ("H型短梁", "H300×150", (2000, 4000), (280, 350), (150, 200), (80, 180), 0.12),
        ("超长杆件", "超长铁件", (5000, 6500), (150, 220), (150, 220), (140, 220), 0.08),
    ]

    for name_p, spec, Lr, Wr, Hr, Wrng, share in pools:
        budget = remaining * share * rng.uniform(0.85, 1.15)
        budget = min(budget, remaining * 0.9)
        used = 0.0
        n_max = 120
        while used < budget and len(mats) < 500 and n_max > 0:
            n_max -= 1
            unit = rng.uniform(*Wrng)
            qty = 1
            if unit < 100 and rng.random() < 0.35:
                qty = rng.randint(2, 6)
                unit = unit / max(qty * 0.5, 1)  # 批量小件
                unit = max(15.0, unit)
            L = rng.uniform(*Lr)
            W = rng.uniform(*Wr)
            H = rng.uniform(*Hr)
            line_w = unit * qty
            if used + line_w > budget * 1.15 and used > budget * 0.5:
                break
            mats.append(
                _row(
                    idx,
                    name=f"{name_p}-{idx}",
                    spec=spec,
                    L=round(L, 1),
                    W=round(W, 1),
                    H=round(H, 1),
                    qty=qty,
                    unit_kg=round(unit, 2),
                    part_no=f"SIM-T80-{name_p[:4]}-{seed}",
                    note=f"sim:t80 random_mixed seed={seed}",
                )
            )
            idx += 1
            used += line_w
        remaining = max(0.0, target_kg - _net(mats))

    # 余量用随机重块填满
    while _net(mats) < target_kg * 0.92 and len(mats) < 600:
        unit = rng.uniform(400, 900)
        mats.append(
            _row(
                idx,
                name=f"配重块-{idx}",
                spec="铸铁/配重",
                L=rng.uniform(800, 1200),
                W=rng.uniform(800, 1100),
                H=rng.uniform(500, 800),
                qty=1,
                unit_kg=unit,
                part_no=f"SIM-T80-BLK-{seed}",
                note=f"sim:t80 random_mixed seed={seed}",
            )
        )
        idx += 1

    mats = _trim_to_target(mats, target_kg, rng, tol=0.03)
    # 重编号
    for i, m in enumerate(mats, 1):
        m["id"] = f"T80-{i:04d}"
    return mats, f"随机混装 ~80t seed={seed}"


def variant_steel_heavy(target_kg: float, rng: random.Random, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """钢通重量主导。"""
    unit = 130.0 + seed % 7 * 5
    n = max(1, int(math.ceil(target_kg / unit)))
    mats = []
    for i in range(n):
        mats.append(
            _row(
                i + 1,
                name=f"镀锌钢通-{i+1}",
                spec="13—铁件",
                L=1000 + (i % 9) * 80,
                W=180 + (i % 4) * 20,
                H=180 + (i % 3) * 20,
                qty=1,
                unit_kg=unit + rng.uniform(-8, 8),
                part_no=f"SIM-T80-STEEL-{seed}",
                note=f"sim:t80 steel_heavy seed={seed}",
            )
        )
    return _trim_to_target(mats, target_kg, rng), f"钢通主导 ~80t seed={seed}"


def variant_modules_plates(target_kg: float, rng: random.Random, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """模块 + 板垛。"""
    mats: List[Dict[str, Any]] = []
    idx = 1
    mod_u = 850.0 + (seed % 5) * 40
    half = target_kg * 0.55
    while _net(mats) < half:
        mats.append(
            _row(
                idx,
                name=f"密实模块-{idx}",
                spec="整包模块",
                L=1200,
                W=1100,
                H=1000 + (idx % 4) * 40,
                qty=1,
                unit_kg=mod_u + rng.uniform(-30, 30),
                part_no=f"SIM-T80-MOD-{seed}",
                note=f"sim:t80 modules_plates seed={seed}",
            )
        )
        idx += 1
    plate_u = 480.0 + seed % 6 * 15
    while _net(mats) < target_kg * 0.95:
        mats.append(
            _row(
                idx,
                name=f"厚板垛-{idx}",
                spec="板材打包",
                L=2000 + (idx % 3) * 100,
                W=1000,
                H=350 + (idx % 5) * 25,
                qty=1,
                unit_kg=plate_u + rng.uniform(-20, 20),
                part_no=f"SIM-T80-PLT-{seed}",
                note=f"sim:t80 modules_plates seed={seed}",
            )
        )
        idx += 1
        if idx > 400:
            break
    return _trim_to_target(mats, target_kg, rng), f"模块+板垛 ~80t seed={seed}"


def variant_long_mix(target_kg: float, rng: random.Random, seed: int) -> Tuple[List[Dict[str, Any]], str]:
    """超长杆 + 短件 + 重块。"""
    mats: List[Dict[str, Any]] = []
    idx = 1
    # 超长约 12–18t
    long_budget = target_kg * 0.18
    while _net(mats) < long_budget and idx < 40:
        mats.append(
            _row(
                idx,
                name=f"超长杆件-{idx}",
                spec="超长铁件",
                L=5800 + (idx % 4) * 150,
                W=160 + (idx % 3) * 20,
                H=160,
                qty=1,
                unit_kg=170 + (seed % 20) + rng.uniform(-10, 10),
                part_no=f"SIM-T80-LONG-{seed}",
                note=f"sim:t80 long_mix seed={seed}",
            )
        )
        idx += 1
    # 短件到 55%
    while _net(mats) < target_kg * 0.55 and idx < 350:
        qty = rng.randint(1, 3)
        unit = rng.uniform(45, 100)
        mats.append(
            _row(
                idx,
                name=f"短支撑-{idx}",
                spec="13—铁件",
                L=rng.uniform(700, 1100),
                W=120,
                H=120,
                qty=qty,
                unit_kg=unit,
                part_no=f"SIM-T80-SH-{seed}",
                note=f"sim:t80 long_mix seed={seed}",
            )
        )
        idx += 1
    # 重块填到目标
    while _net(mats) < target_kg * 0.97 and idx < 450:
        mats.append(
            _row(
                idx,
                name=f"重块-{idx}",
                spec="配重",
                L=900,
                W=900,
                H=650,
                qty=1,
                unit_kg=rng.uniform(450, 750),
                part_no=f"SIM-T80-BLK-{seed}",
                note=f"sim:t80 long_mix seed={seed}",
            )
        )
        idx += 1
    mats = _trim_to_target(mats, target_kg, rng)
    for i, m in enumerate(mats, 1):
        m["id"] = f"T80-{i:04d}"
    return mats, f"超长+短件+重块 ~80t seed={seed}"


GENERATORS = [
    ("random_mixed", variant_random_mixed),
    ("steel_heavy", variant_steel_heavy),
    ("modules_plates", variant_modules_plates),
    ("long_mix", variant_long_mix),
]


def _force_near_target(mats: List[Dict[str, Any]], target_kg: float, prefix: str = "T80") -> List[Dict[str, Any]]:
    """最后一刀：净重拉到 target±1% 内。"""
    out = list(mats)
    j = 0
    while _net(out) < target_kg * 0.99 and j < 50:
        j += 1
        gap = target_kg - _net(out)
        uw = min(max(gap, 20.0), 1200.0)
        out.append(
            {
                "id": f"{prefix}-Z{j:04d}",
                "name": f"目标补重-{j}",
                "spec": "配重",
                "quantity": 1,
                "weight_kg": round(uw, 3),
                "total_weight_kg": round(uw, 3),
                "length_mm": 850.0,
                "width_mm": 850.0,
                "height_mm": 550.0,
                "part_no": "SIM-T80-TARGET",
                "note": "force near target",
                "category": "重件" if uw >= 200 else "普通件",
            }
        )
    while _net(out) > target_kg * 1.01 and len(out) > 1:
        # 优先删补重行
        pad_idx = next(
            (i for i, m in enumerate(out) if "补重" in str(m.get("name") or "") or "配重" in str(m.get("name") or "")),
            len(out) - 1,
        )
        out.pop(pad_idx)
    for i, m in enumerate(out, 1):
        m["id"] = f"{prefix}-{i:04d}"
    return out


def write_case(
    case_id: str,
    mats: List[Dict[str, Any]],
    story: str,
    target_t: float,
    seed: int,
) -> Dict[str, Any]:
    d = OUT_SIM / case_id
    d.mkdir(parents=True, exist_ok=True)
    mats = _force_near_target(mats, float(target_t) * 1000.0)
    net = _net(mats)
    payload = {
        "case_id": case_id,
        "story": story,
        "seed": seed,
        "target_net_t": target_t,
        "net_kg": round(net, 1),
        "net_t": round(net / 1000.0, 3),
        "n_lines": len(mats),
        "expect": {
            "containers_by_weight_min": max(1, int(math.ceil(net / 26000.0))),
            "net_t_approx": target_t,
            "note": "40HQ payload≈28.6t 时约需 3+ 柜（重量界）",
        },
        "materials": mats,
    }
    (d / "materials.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    xlsx = ""
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
            "category",
        ]
        ws.append(cols)
        for m in mats:
            ws.append([m.get(c) for c in cols])
        wb.save(d / "materials.xlsx")
        xlsx = str(d / "materials.xlsx")
    except Exception:
        pass
    return {
        "case_id": case_id,
        "story": story,
        "seed": seed,
        "net_kg": payload["net_kg"],
        "net_t": payload["net_t"],
        "n_lines": len(mats),
        "json": str(d / "materials.json"),
        "xlsx": xlsx,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成随机 ~80t 仿真物料")
    ap.add_argument("--variants", type=int, default=4, help="生成套数（模板循环）")
    ap.add_argument("--target-t", type=float, default=80.0, help="目标净重吨")
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（默认用 UTC 时间秒）",
    )
    ap.add_argument(
        "--only-random",
        action="store_true",
        help="只生成 1 套 random_mixed",
    )
    args = ap.parse_args()

    base_seed = int(args.seed) if args.seed is not None else int(
        datetime.now(timezone.utc).timestamp()
    ) % 1_000_000
    target_kg = float(args.target_t) * 1000.0
    n = 1 if args.only_random else max(1, int(args.variants))
    index: List[Dict[str, Any]] = []

    for i in range(n):
        name, fn = GENERATORS[i % len(GENERATORS)]
        if args.only_random:
            name, fn = GENERATORS[0]
        seed = base_seed + i * 17
        rng = random.Random(seed)
        mats, story = fn(target_kg, rng, seed)
        case_id = f"t80_{name}_s{seed}"
        meta = write_case(case_id, mats, story, args.target_t, seed)
        index.append(meta)
        print(
            f"[OK] {case_id}: lines={meta['n_lines']} net={meta['net_t']}t "
            f"({meta['net_kg']}kg) — {story}"
        )

    OUT_IDX.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_seed": base_seed,
        "target_t": args.target_t,
        "count": len(index),
        "cases": index,
    }
    (OUT_IDX / "INDEX.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 合并进 sim INDEX
    sim_index_path = OUT_SIM / "INDEX.json"
    try:
        sim = (
            json.loads(sim_index_path.read_text(encoding="utf-8"))
            if sim_index_path.exists()
            else {"cases": {}}
        )
        if "cases" not in sim:
            sim["cases"] = {}
        for c in index:
            sim["cases"][c["case_id"]] = {
                "story": c["story"],
                "n_lines": c["n_lines"],
                "net_kg": c["net_kg"],
                "net_t": c["net_t"],
                "seed": c["seed"],
                "json": f"test/sim_materials/{c['case_id']}/materials.json",
                "xlsx": (
                    f"test/sim_materials/{c['case_id']}/materials.xlsx"
                    if c.get("xlsx")
                    else ""
                ),
                "expect": {"net_t_approx": args.target_t},
            }
        sim["t80_latest"] = {
            "base_seed": base_seed,
            "cases": [c["case_id"] for c in index],
            "generated_at": report["generated_at"],
        }
        sim_index_path.write_text(
            json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print("warn: merge INDEX", e)

    print(f"\nINDEX → {OUT_IDX / 'INDEX.json'}")
    print(f"主用例 JSON → {index[0]['json']}" if index else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
