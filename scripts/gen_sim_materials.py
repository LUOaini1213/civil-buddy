#!/usr/bin/env python3
"""
一键生成仿真材料（假设材料，用于回归/演示，不依赖 A: 真实 Excel）。

输出：
  test/sim_materials/<case_id>/materials.json
  test/sim_materials/<case_id>/materials.xlsx
  test/sim_materials/INDEX.json
  test/sim_materials/README.md

用法：
  python scripts/gen_sim_materials.py
  python scripts/gen_sim_materials.py --run-booking   # 生成后跑订柜自检
  python scripts/gen_sim_materials.py --case weight_bound_32t
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "test" / "sim_materials"

COLS = [
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


def _row(
    i: int,
    *,
    name: str,
    spec: str,
    L: float,
    W: float,
    H: float,
    qty: int = 1,
    weight_kg: float = 0.0,
    part_no: str = "SIM",
    note: str = "",
) -> Dict[str, Any]:
    q = max(int(qty), 1)
    w = float(weight_kg)
    return {
        "id": f"SIM-{i:04d}",
        "name": name,
        "spec": spec,
        "quantity": q,
        "weight_kg": round(w, 3),
        "total_weight_kg": round(w * q, 3),
        "length_mm": float(L),
        "width_mm": float(W),
        "height_mm": float(H),
        "part_no": part_no,
        "note": note or "sim_synthetic",
    }


# ── 场景生成器 ─────────────────────────────────────────────

def case_weight_bound_32t() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """~32t 小截面铁通 → 期望重量柜≈2，体积柜≤2。"""
    mats = []
    for i in range(230):
        mats.append(
            _row(
                i + 1,
                name=f"镀锌钢通-{i+1}",
                spec="13—铁件",
                L=1400,
                W=250,
                H=250,
                weight_kg=140,
                part_no="SIM-STEEL-W",
                note="sim:weight_bound ~32t",
            )
        )
    meta = {
        "expect": {
            "containers_by_weight": 2,
            "containers_needed_max": 2,
            "binding_in": ["weight", "both"],
        },
        "story": "重量主导，体积不应抬高柜数",
    }
    return mats, meta


def case_volume_bound_light() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """轻泡大板 → 体积柜 ≥ 重量柜。"""
    mats = []
    for i in range(40):
        mats.append(
            _row(
                i + 1,
                name=f"轻泡板-{i+1}",
                spec="28—杂项配件",
                L=2000,
                W=1200,
                H=800,
                weight_kg=15,
                part_no="SIM-LIGHT-V",
                note="sim:volume_bound light foam",
            )
        )
    meta = {
        "expect": {
            "containers_by_weight": 1,
            "containers_needed_min": 1,
            "binding_in": ["volume", "both", "weight"],
        },
        "story": "轻泡货，体积可能主导",
    }
    return mats, meta


def case_small_one_container() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """小票 → N0=1。"""
    mats = []
    for i in range(8):
        mats.append(
            _row(
                i + 1,
                name=f"短支撑-{i+1}",
                spec="13—铁件",
                L=1200,
                W=100,
                H=100,
                weight_kg=25,
                qty=2,
                part_no="SIM-SMALL",
                note="sim:small shipment",
            )
        )
    meta = {
        "expect": {"containers_needed_max": 1},
        "story": "小票一柜可订",
    }
    return mats, meta


def case_long_frames() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """超长件 4–6m，测选柜与摆位输入。"""
    mats = []
    for i in range(15):
        L = 4200 if i % 3 else 5800
        mats.append(
            _row(
                i + 1,
                name=f"超长钢通-{i+1}",
                spec="13—铁件",
                L=L,
                W=120,
                H=120,
                weight_kg=55 if L < 5000 else 80,
                qty=2,
                part_no="SIM-LONG",
                note="sim:long pieces 4-6m",
            )
        )
    meta = {
        "expect": {"containers_needed_min": 1, "max_length_mm_min": 4000},
        "story": "超长件，柜型应倾向 40 尺",
    }
    return mats, meta


def case_overweight_risk() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """总重接近/超过 2 柜载荷，测重量柜≥2。"""
    mats = []
    for i in range(4):
        mats.append(
            _row(
                i + 1,
                name=f"重件块-{i+1}",
                spec="13—铁件",
                L=2000,
                W=1500,
                H=1200,
                weight_kg=16000,
                part_no="SIM-HEAVY",
                note="sim:overweight stress",
            )
        )
    meta = {
        "expect": {"containers_by_weight_min": 3},  # 64t / 28.6 ≈ 3
        "story": "重货应力，重量柜应≥3",
    }
    return mats, meta


def case_near_payload() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """总重约 27t，期望重量柜=1。"""
    mats = []
    for i in range(27):
        mats.append(
            _row(
                i + 1,
                name=f"中重件-{i+1}",
                spec="13—铁件",
                L=1800,
                W=200,
                H=200,
                weight_kg=1000,
                part_no="SIM-NEAR-PL",
                note="sim:near single payload",
            )
        )
    meta = {
        # estimate_containers 对材料毛重约 ×1.12，27t 净重 → 毛重>28.61t → 重量柜 2
        "expect": {"containers_by_weight": 2, "containers_needed_max": 2},
        "story": "接近单柜载荷（含箱皮后可能 2 柜）",
    }
    return mats, meta


def case_mixed_realistic() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """长短+五金混装，贴近幕墙杂货。"""
    mats: List[Dict[str, Any]] = []
    n = 0
    for i in range(10):
        n += 1
        mats.append(
            _row(
                n,
                name=f"长通-{i+1}",
                spec="13—铁件",
                L=4000,
                W=150,
                H=150,
                weight_kg=60,
                qty=3,
                part_no="SIM-MIX-L",
            )
        )
    for i in range(20):
        n += 1
        mats.append(
            _row(
                n,
                name=f"短件-{i+1}",
                spec="13—铁件",
                L=800,
                W=100,
                H=100,
                weight_kg=12,
                qty=5,
                part_no="SIM-MIX-S",
            )
        )
    for i in range(5):
        n += 1
        mats.append(
            _row(
                n,
                name=f"五金箱当量-{i+1}",
                spec="23—紧固件/螺丝",
                L=600,
                W=400,
                H=350,
                weight_kg=40,
                part_no="SIM-MIX-HW",
                note="sim:hardware carton equiv",
            )
        )
    meta = {
        "expect": {"containers_needed_min": 1, "containers_needed_max": 3},
        "story": "混装真实感小票",
    }
    return mats, meta


def case_hollow_crate_lines() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    模拟「已是当量架」的材料行：大外廓尺寸 + 说明 crate_equiv。
    用于 crate_passthrough / 有效体积路径（件体积仍按 LWH，注意：estimate 用件 AABB）。
    更适合作为「当量箱」测时转 boxes；这里仍给 materials 形状。
    """
    mats = []
    for i in range(20):
        mats.append(
            _row(
                i + 1,
                name=f"1.1米铁件架×80件/架#{i+1}",
                spec="13—铁件",
                L=1100,
                W=1100,
                H=1750,
                weight_kg=1280,
                part_no="SIM-HOLLOW-CRATE",
                note="sim:crate_equiv_est dims=crate_equiv_est crate=1/20",
            )
        )
    meta = {
        "expect": {
            # 20×1280≈25.6t 净重，×1.12 毛重 → 重量柜 2
            "containers_by_weight": 2,
            "containers_needed_max": 2,
        },
        "story": "当量 1.1m 架行；配合 crate_passthrough 做 Agent 测",
        "packing_options_hint": {"crate_passthrough": True},
    }
    return mats, meta


def case_glass_category() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """玻璃货种膨胀更大。"""
    mats = []
    for i in range(12):
        mats.append(
            _row(
                i + 1,
                name=f"中空玻璃-{i+1}",
                spec="24—Glass 玻璃",
                L=1600,
                W=1200,
                H=40,
                weight_kg=48,
                qty=2,
                part_no="SIM-GLASS",
                note="sim:glass category pack_factor",
            )
        )
    meta = {
        "expect": {"containers_needed_max": 2},
        "story": "玻璃货种，pack_factor 应高于钢",
    }
    return mats, meta


def case_tiny() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    mats = [
        _row(
            1,
            name="样品螺栓包",
            spec="23—紧固件/螺丝",
            L=100,
            W=50,
            H=50,
            weight_kg=0.5,
            qty=20,
            part_no="SIM-TINY",
            note="sim:tiny",
        )
    ]
    meta = {
        "expect": {"containers_needed_max": 1},
        "story": "极小票，证明未写死 2 柜",
    }
    return mats, meta


GENERATORS: Dict[str, Callable[[], Tuple[List[Dict[str, Any]], Dict[str, Any]]]] = {
    "weight_bound_32t": case_weight_bound_32t,
    "volume_bound_light": case_volume_bound_light,
    "small_one_container": case_small_one_container,
    "long_frames": case_long_frames,
    "overweight_risk": case_overweight_risk,
    "near_payload": case_near_payload,
    "mixed_realistic": case_mixed_realistic,
    "hollow_crate_lines": case_hollow_crate_lines,
    "glass_category": case_glass_category,
    "tiny": case_tiny,
}


def write_excel(path: Path, mats: List[Dict[str, Any]]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "materials"
    ws.append(COLS)
    for m in mats:
        ws.append([m.get(c) for c in COLS])
    wb.save(path)


def run_booking_check(mats: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.tools.volume_estimate import estimate_containers

    r = estimate_containers(materials=mats, container_type="40HQ", fill_ratio=0.82)
    exp = meta.get("expect") or {}
    ok = True
    fails: List[str] = []

    def chk(key: str, pred: bool, msg: str) -> None:
        nonlocal ok
        if key in exp and not pred:
            ok = False
            fails.append(msg)

    if "containers_by_weight" in exp:
        chk(
            "containers_by_weight",
            r["containers_by_weight"] == exp["containers_by_weight"],
            f"wt {r['containers_by_weight']} != {exp['containers_by_weight']}",
        )
    if "containers_by_weight_min" in exp:
        chk(
            "containers_by_weight_min",
            r["containers_by_weight"] >= exp["containers_by_weight_min"],
            f"wt {r['containers_by_weight']} < {exp['containers_by_weight_min']}",
        )
    if "containers_needed_max" in exp:
        chk(
            "containers_needed_max",
            r["containers_needed"] <= exp["containers_needed_max"],
            f"N {r['containers_needed']} > {exp['containers_needed_max']}",
        )
    if "containers_needed_min" in exp:
        chk(
            "containers_needed_min",
            r["containers_needed"] >= exp["containers_needed_min"],
            f"N {r['containers_needed']} < {exp['containers_needed_min']}",
        )
    if "binding_in" in exp:
        chk(
            "binding_in",
            r["binding_constraint"] in exp["binding_in"],
            f"bind {r['binding_constraint']} not in {exp['binding_in']}",
        )
    if "max_length_mm_min" in exp:
        mx = max(float(m["length_mm"]) for m in mats)
        chk(
            "max_length_mm_min",
            mx >= exp["max_length_mm_min"],
            f"maxL {mx} < {exp['max_length_mm_min']}",
        )

    return {
        "ok": ok,
        "fails": fails,
        "containers_by_weight": r["containers_by_weight"],
        "containers_by_volume": r["containers_by_volume"],
        "containers_needed": r["containers_needed"],
        "binding_constraint": r["binding_constraint"],
        "gross_kg": r["gross_kg"],
        "volume_m3": r["volume_m3"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成仿真材料用例")
    ap.add_argument("--case", action="append", help="只生成指定 case_id，可多次")
    ap.add_argument("--run-booking", action="store_true", help="生成后订柜自检")
    ap.add_argument("--out", type=str, default="", help="输出目录，默认 test/sim_materials")
    args = ap.parse_args()

    out_root = Path(args.out) if args.out else OUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)

    case_ids = args.case or list(GENERATORS.keys())
    index: Dict[str, Any] = {
        "description": "仿真材料（假设数据），用于回归/演示，非真实项目提料",
        "units": {"length": "mm", "weight": "kg"},
        "cases": {},
    }

    all_ok = True
    for cid in case_ids:
        if cid not in GENERATORS:
            print("UNKNOWN case", cid)
            all_ok = False
            continue
        mats, meta = GENERATORS[cid]()
        d = out_root / cid
        d.mkdir(parents=True, exist_ok=True)
        jp = d / "materials.json"
        xp = d / "materials.xlsx"
        jp.write_text(
            json.dumps(
                {
                    "case_id": cid,
                    "story": meta.get("story"),
                    "expect": meta.get("expect"),
                    "packing_options_hint": meta.get("packing_options_hint"),
                    "materials": mats,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        write_excel(xp, mats)

        entry: Dict[str, Any] = {
            "story": meta.get("story"),
            "n_lines": len(mats),
            "net_kg": round(sum(float(m["total_weight_kg"]) for m in mats), 1),
            "json": str(jp.relative_to(ROOT)).replace("\\", "/"),
            "xlsx": str(xp.relative_to(ROOT)).replace("\\", "/"),
            "expect": meta.get("expect"),
            "packing_options_hint": meta.get("packing_options_hint"),
        }
        if args.run_booking:
            chk = run_booking_check(mats, meta)
            entry["booking_check"] = chk
            status = "OK" if chk["ok"] else "FAIL"
            if not chk["ok"]:
                all_ok = False
            print(
                f"[{status}] {cid}: N={chk['containers_needed']} "
                f"wt={chk['containers_by_weight']} vol={chk['containers_by_volume']} "
                f"bind={chk['binding_constraint']} net≈{entry['net_kg']}kg"
                + (f" fails={chk['fails']}" if chk["fails"] else "")
            )
        else:
            print(f"[GEN] {cid}: lines={len(mats)} net≈{entry['net_kg']}kg → {d}")

        index["cases"][cid] = entry

    (out_root / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = f"""# 仿真材料 test/sim_materials

**假设/合成数据**，用于算法与 Agent 回归，**不是**真实工地提料。

## 生成

```bash
python scripts/gen_sim_materials.py
python scripts/gen_sim_materials.py --run-booking
python scripts/gen_sim_materials.py --case weight_bound_32t --case tiny
```

## 用例一览

| case_id | 说明 |
|---------|------|
"""
    for cid, e in index["cases"].items():
        readme += f"| `{cid}` | {e.get('story')}（{e.get('n_lines')} 行，~{e.get('net_kg')} kg） |\n"

    readme += """
## 怎么用

```python
import json
from pathlib import Path
from packing_assistant.tools.volume_estimate import estimate_containers

data = json.loads(Path("test/sim_materials/weight_bound_32t/materials.json").read_text(encoding="utf-8"))
r = estimate_containers(materials=data["materials"], container_type="40HQ")
print(r["containers_needed"], r["binding_constraint"])
```

```bash
# 注入 Agent 演示
python scripts/demo_nine_agents_trace.py   # 自带 demo 材料
# 或自己写脚本 materials=json.load(...)["materials"]
```

## 与真实案例

| 类型 | 路径 |
|------|------|
| 仿真 | `test/sim_materials/` |
| 真实工地 | `scripts/demo_vmu1_site.py` |
| 真实已发 | `scripts/run_vmu1_shipped_fst0003.py` |
"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")
    print("WROTE", out_root / "INDEX.json")
    print("WROTE", out_root / "README.md")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
