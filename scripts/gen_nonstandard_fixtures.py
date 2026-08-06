#!/usr/bin/env python3
"""生成/刷新非标件仿真夹具（磁盘 JSON）。

  python scripts/gen_nonstandard_fixtures.py
  python scripts/gen_nonstandard_fixtures.py --seed 20260806
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test" / "sim_materials"


def cases_catalog(seed: int = 20260806) -> dict:
    # seed reserved for future random variants; fixed catalog for regression
    _ = seed
    return {
        "ns_overlength_rail": {
            "story": "超长轨道型材 GEO_OVERSIZE",
            "expect_tags": ["GEO_OVERSIZE"],
            "materials": [
                {
                    "id": "R1",
                    "name": "轨道钢轨-6m",
                    "quantity": 4,
                    "length_mm": 6200,
                    "width_mm": 150,
                    "height_mm": 150,
                    "weight_kg": 180,
                    "total_weight_kg": 720,
                    "category": "超长件",
                },
                {
                    "id": "R2",
                    "name": "连接板",
                    "quantity": 20,
                    "length_mm": 400,
                    "width_mm": 300,
                    "height_mm": 20,
                    "weight_kg": 8,
                    "total_weight_kg": 160,
                },
            ],
        },
        "ns_heavy_cast": {
            "story": "重铸件 LOAD_HEAVY",
            "expect_tags": ["LOAD_HEAVY"],
            "materials": [
                {
                    "id": "H1",
                    "name": "铸铁底座",
                    "quantity": 2,
                    "length_mm": 1800,
                    "width_mm": 1200,
                    "height_mm": 600,
                    "weight_kg": 850,
                    "total_weight_kg": 1700,
                    "category": "重件",
                },
                {
                    "id": "H2",
                    "name": "配重块",
                    "quantity": 6,
                    "length_mm": 600,
                    "width_mm": 400,
                    "height_mm": 300,
                    "weight_kg": 220,
                    "total_weight_kg": 1320,
                    "category": "重件",
                },
            ],
        },
        "ns_thin_sheet_stack": {
            "story": "薄板 SHAPE_CUSTOM",
            "expect_tags": ["SHAPE_CUSTOM"],
            "materials": [
                {
                    "id": "T1",
                    "name": "铝板-2.4m",
                    "quantity": 12,
                    "length_mm": 2400,
                    "width_mm": 1200,
                    "height_mm": 40,
                    "weight_kg": 45,
                    "total_weight_kg": 540,
                    "category": "薄板",
                },
                {
                    "id": "T2",
                    "name": "不锈钢片",
                    "quantity": 8,
                    "length_mm": 1800,
                    "width_mm": 900,
                    "height_mm": 25,
                    "weight_kg": 30,
                    "total_weight_kg": 240,
                    "category": "薄板",
                },
            ],
        },
        "ns_missing_dims_mix": {
            "story": "混缺尺寸 DATA_GAP",
            "expect_tags": ["DATA_GAP"],
            "materials": [
                {
                    "id": "D1",
                    "name": "完整箱",
                    "quantity": 3,
                    "length_mm": 1000,
                    "width_mm": 800,
                    "height_mm": 600,
                    "weight_kg": 50,
                    "total_weight_kg": 150,
                },
                {
                    "id": "D2",
                    "name": "缺宽件",
                    "quantity": 2,
                    "length_mm": 1500,
                    "height_mm": 400,
                    "weight_kg": 40,
                    "total_weight_kg": 80,
                },
                {"id": "D3", "name": "缺尺寸未知件", "quantity": 1, "weight_kg": 25},
            ],
        },
        "ns_factory_crate_path": {
            "story": "工厂架 PACK_PATH",
            "expect_tags": ["PACK_PATH"],
            "materials": [
                {
                    "id": "F1",
                    "name": "叠层架-出厂",
                    "quantity": 3,
                    "length_mm": 3000,
                    "width_mm": 1100,
                    "height_mm": 1500,
                    "weight_kg": 450,
                    "total_weight_kg": 1350,
                    "note": "factory_stack crate_equiv",
                    "category": "工厂架",
                },
                {
                    "id": "F2",
                    "name": "铁件架-长料",
                    "quantity": 2,
                    "length_mm": 5800,
                    "width_mm": 1000,
                    "height_mm": 1200,
                    "weight_kg": 600,
                    "total_weight_kg": 1200,
                    "note": "crate=factory_long",
                },
            ],
        },
        "ns_fragile_process": {
            "story": "易碎禁翻 PROCESS_SPECIAL",
            "expect_tags": ["PROCESS_SPECIAL"],
            "materials": [
                {
                    "id": "G1",
                    "name": "玻璃幕墙模块",
                    "quantity": 4,
                    "length_mm": 2200,
                    "width_mm": 1100,
                    "height_mm": 80,
                    "weight_kg": 95,
                    "total_weight_kg": 380,
                    "note": "易碎禁翻",
                    "fragile": True,
                    "this_side_up": True,
                },
                {
                    "id": "G2",
                    "name": "精密仪表箱",
                    "quantity": 6,
                    "length_mm": 600,
                    "width_mm": 500,
                    "height_mm": 400,
                    "weight_kg": 18,
                    "total_weight_kg": 108,
                    "note": "精密",
                    "fragile": True,
                    "stackable": False,
                },
            ],
        },
        "ns_over_container_width": {
            "story": "超柜内宽 GEO FAIL",
            "expect_tags": ["GEO_OVERSIZE"],
            "materials": [
                {
                    "id": "W1",
                    "name": "超宽设备底座",
                    "quantity": 1,
                    "length_mm": 3000,
                    "width_mm": 2800,
                    "height_mm": 900,
                    "weight_kg": 1200,
                    "total_weight_kg": 1200,
                    "category": "重件",
                },
                {
                    "id": "W2",
                    "name": "标准附件箱",
                    "quantity": 4,
                    "length_mm": 800,
                    "width_mm": 600,
                    "height_mm": 500,
                    "weight_kg": 30,
                    "total_weight_kg": 120,
                },
            ],
        },
        "ns_mixed_industry_bundle": {
            "story": "跨行业混合非标",
            "expect_tags": [
                "GEO_OVERSIZE",
                "LOAD_HEAVY",
                "PACK_PATH",
                "PROCESS_SPECIAL",
            ],
            "materials": [
                {
                    "id": "M1",
                    "name": "管线-11m",
                    "quantity": 2,
                    "length_mm": 11000,
                    "width_mm": 300,
                    "height_mm": 300,
                    "weight_kg": 400,
                    "total_weight_kg": 800,
                    "category": "超长件",
                },
                {
                    "id": "M2",
                    "name": "重电机",
                    "quantity": 1,
                    "length_mm": 1400,
                    "width_mm": 1000,
                    "height_mm": 900,
                    "weight_kg": 2100,
                    "total_weight_kg": 2100,
                    "category": "重件",
                },
                {
                    "id": "M3",
                    "name": "工厂叠层架",
                    "quantity": 2,
                    "length_mm": 2500,
                    "width_mm": 1100,
                    "height_mm": 1400,
                    "weight_kg": 380,
                    "total_weight_kg": 760,
                    "note": "factory_stack",
                },
                {
                    "id": "M4",
                    "name": "玻璃仪器柜",
                    "quantity": 3,
                    "length_mm": 700,
                    "width_mm": 500,
                    "height_mm": 1200,
                    "weight_kg": 55,
                    "total_weight_kg": 165,
                    "note": "易碎禁叠",
                    "fragile": True,
                    "no_stack": True,
                },
            ],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260806)
    args = ap.parse_args()
    cat = cases_catalog(args.seed)
    index = {"version": 1, "suite": "nonstandard_new_materials", "seed": args.seed, "cases": []}
    for cid, data in cat.items():
        d = OUT / cid
        d.mkdir(parents=True, exist_ok=True)
        payload = {
            "case_id": cid,
            "story": data["story"],
            "expect_tags": data["expect_tags"],
            "materials": data["materials"],
        }
        (d / "materials.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index["cases"].append(
            {
                "id": cid,
                "path": cid,
                "story": data["story"],
                "expect_tags": data["expect_tags"],
                "n_materials": len(data["materials"]),
            }
        )
        print("wrote", cid)
    (OUT / "ns_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("INDEX", len(index["cases"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
