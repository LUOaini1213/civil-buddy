#!/usr/bin/env python3
"""可复现随机物料生成（比赛 round20 用）。"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]

FAMILIES = (
    "steel_mix",
    "steel_mix",
    "steel_mix",
    "module_plate",
    "module_plate",
    "long_heavy",
    "long_heavy",
    "light_volume",
    "light_volume",
    "junk_edge",
)


def _row(
    rid: str,
    name: str,
    L: float,
    W: float,
    H: float,
    wt: float,
    qty: int = 1,
    note: str = "",
) -> Dict[str, Any]:
    return {
        "id": rid,
        "name": name,
        "spec": note or name,
        "quantity": int(qty),
        "weight_kg": round(wt / max(qty, 1), 3),
        "total_weight_kg": round(wt, 3),
        "length_mm": float(L),
        "width_mm": float(W),
        "height_mm": float(H),
        "part_no": rid,
        "note": note,
    }


def gen_family(rng: random.Random, family: str, seed: int) -> List[Dict[str, Any]]:
    mats: List[Dict[str, Any]] = []
    if family == "steel_mix":
        n = rng.randint(10, 22)
        for i in range(n):
            kind = rng.choice(["tube", "beam", "plate", "bracket"])
            if kind == "tube":
                L = rng.uniform(1500, 5800)
                W, H = rng.uniform(40, 200), rng.uniform(40, 200)
                wt = rng.uniform(15, 180) * rng.randint(1, 4)
            elif kind == "beam":
                L = rng.uniform(2000, 6000)
                W, H = rng.uniform(100, 350), rng.uniform(150, 400)
                wt = rng.uniform(40, 320)
            elif kind == "plate":
                L = rng.uniform(800, 2500)
                W = rng.uniform(500, 1200)
                H = rng.uniform(8, 40)
                wt = rng.uniform(20, 200)
            else:
                L = rng.uniform(200, 800)
                W, H = rng.uniform(100, 400), rng.uniform(50, 300)
                wt = rng.uniform(5, 60) * rng.randint(1, 6)
            qty = rng.randint(1, 3)
            mats.append(
                _row(
                    f"RND-S{seed}-{i:03d}",
                    f"钢混-{kind}-{i}",
                    L,
                    W,
                    H,
                    wt * qty,
                    qty,
                    f"steel_mix seed={seed}",
                )
            )
    elif family == "module_plate":
        # 控制在 40HQ 可装范围，避免随机票过难导致 cannot_fit 虚高失败
        n = rng.randint(10, 20)
        for i in range(n):
            if rng.random() < 0.55:
                L = rng.uniform(1000, 1400)
                W = rng.uniform(800, 1100)
                H = rng.uniform(800, 1200)
                wt = rng.uniform(300, 900)
                name = f"模块-{i}"
            else:
                L = rng.uniform(1000, 2400)
                W = rng.uniform(500, 1000)
                H = rng.uniform(10, 50)
                wt = rng.uniform(40, 280)
                name = f"板件-{i}"
            mats.append(
                _row(
                    f"RND-M{seed}-{i:03d}",
                    name,
                    L,
                    W,
                    H,
                    wt,
                    1,
                    f"module_plate seed={seed}",
                )
            )
    elif family == "long_heavy":
        n = rng.randint(6, 14)
        for i in range(n):
            if i < 2:
                L = rng.uniform(9000, 11500)
                W, H = rng.uniform(200, 450), rng.uniform(200, 500)
                wt = rng.uniform(800, 2500)
            else:
                L = rng.uniform(2500, 7000)
                W, H = rng.uniform(150, 400), rng.uniform(150, 400)
                wt = rng.uniform(100, 900)
            mats.append(
                _row(
                    f"RND-L{seed}-{i:03d}",
                    f"长重-{i}",
                    L,
                    W,
                    H,
                    wt,
                    1,
                    f"long_heavy seed={seed}",
                )
            )
    elif family == "light_volume":
        n = rng.randint(15, 35)
        for i in range(n):
            L = rng.uniform(600, 2000)
            W = rng.uniform(400, 1100)
            H = rng.uniform(400, 1500)
            # 轻泡：体积大重量小
            vol_m3 = (L * W * H) / 1e9
            wt = max(2.0, vol_m3 * rng.uniform(30, 120))
            qty = rng.randint(1, 4)
            mats.append(
                _row(
                    f"RND-V{seed}-{i:03d}",
                    f"轻泡箱-{i}",
                    L,
                    W,
                    H,
                    wt * qty,
                    qty,
                    f"light_volume seed={seed}",
                )
            )
    else:  # junk_edge
        n = rng.randint(5, 12)
        for i in range(n):
            if i == 0:
                # 缺尺寸
                mats.append(
                    {
                        "id": f"RND-J{seed}-miss",
                        "name": "缺尺寸件",
                        "quantity": 1,
                        "total_weight_kg": 50,
                        "note": f"junk_edge missing_dims seed={seed}",
                    }
                )
            elif i == 1:
                mats.append(
                    _row(
                        f"RND-J{seed}-big",
                        "近极限件",
                        rng.uniform(10000, 11900),
                        rng.uniform(2000, 2300),
                        rng.uniform(2000, 2500),
                        rng.uniform(500, 3000),
                        1,
                        f"junk_edge big seed={seed}",
                    )
                )
            else:
                mats.append(
                    _row(
                        f"RND-J{seed}-{i:03d}",
                        f"边角-{i}",
                        rng.uniform(100, 1500),
                        rng.uniform(50, 800),
                        rng.uniform(50, 800),
                        rng.uniform(1, 200),
                        rng.randint(1, 5),
                        f"junk_edge seed={seed}",
                    )
                )
    return mats


def gen_case(seed: int, family: str | None = None) -> Dict[str, Any]:
    rng = random.Random(int(seed))
    fam = family or FAMILIES[int(seed) % len(FAMILIES)]
    materials = gen_family(rng, fam, int(seed))
    soft = fam == "junk_edge"
    return {
        "case_id": f"rnd_{fam}_s{seed}",
        "family": fam,
        "seed": int(seed),
        "story": f"随机物料 family={fam} seed={seed}",
        "expect": {
            "allow_soft_fail": soft,
            "allow_cannot_fit": soft,
        },
        "materials": materials,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260730)
    ap.add_argument("--family", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    data = gen_case(args.seed, args.family or None)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print("wrote", p, "n=", len(data["materials"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
