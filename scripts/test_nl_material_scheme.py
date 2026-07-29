#!/usr/bin/env python3
"""NL What-if 必须按物料画像出不同方案。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def mats_steel_short():
    return [
        {
            "id": f"S{i}",
            "name": f"铁件架{i}",
            "part_no": f"FST{i:04d}",
            "spec": "13—铁件",
            "quantity": 1,
            "weight_kg": 800,
            "total_weight_kg": 800,
            "length_mm": 2000,
            "width_mm": 1100,
            "height_mm": 1100,
            "note": "crate_equiv_est",
        }
        for i in range(6)
    ]


def mats_long_aluminum():
    return [
        {
            "id": f"A{i}",
            "name": f"铝型材{i}",
            "part_no": f"BAL{i:04d}",
            "spec": "22—铝材",
            "quantity": 1,
            "weight_kg": 40,
            "total_weight_kg": 40,
            "length_mm": 6500 if i < 4 else 4200,
            "width_mm": 80,
            "height_mm": 60,
            "note": "profile",
        }
        for i in range(10)
    ] + [
        {
            "id": "FAC1",
            "name": "3mm铝板",
            "part_no": "FAC0008",
            "spec": "11—铝板",
            "quantity": 50,
            "weight_kg": 15,
            "total_weight_kg": 750,
            "length_mm": 2200,
            "width_mm": 1200,
            "height_mm": 3,
            "note": "sheet",
        }
    ]


def main() -> int:
    from packing_assistant.nl_whatif import (
        analyze_materials,
        apply_material_selection,
        parse_nl_whatif,
    )

    steel = mats_steel_short()
    alum = mats_long_aluminum()

    ps = analyze_materials(steel)
    pa = analyze_materials(alum)
    assert ps["cargo_mode"] == "heavy_steel", ps
    assert pa["cargo_mode"] in ("long_aluminum", "thin_plate", "mixed"), pa
    print("PASS profiles", ps["cargo_mode"], "vs", pa["cargo_mode"])

    # 同一句「锁 2 柜」→ 不同 packing_options.scheme_reason / 策略
    r_steel = parse_nl_whatif("锁 2 柜", materials=steel)
    r_alum = parse_nl_whatif("锁 2 柜", materials=alum)
    assert r_steel["max_containers"] == 2 and r_alum["max_containers"] == 2
    os_ = r_steel["packing_options"]
    oa = r_alum["packing_options"]
    # 钢：直通；铝长料：dense 且 prefer_stack 倾向不同
    assert os_.get("crate_passthrough") is True or os_.get("scheme_reason", "").find("铁") >= 0
    assert oa.get("dense_mode") is True or "铝" in str(oa.get("scheme_reason") or "")
    assert r_steel["scheme_id"] != r_alum["scheme_id"]
    print("PASS lock2 different schemes", r_steel["scheme_id"], "|", r_alum["scheme_id"])
    print("  steel reason:", os_.get("scheme_reason"))
    print("  alum reason:", oa.get("scheme_reason"))

    # 「去掉超长」：短铁几乎不删；长铝会删
    d_steel = parse_nl_whatif("去掉超长", materials=steel)
    d_alum = parse_nl_whatif("去掉超长", materials=alum)
    sel_s, ns = apply_material_selection(steel, d_steel)
    sel_a, na = apply_material_selection(alum, d_alum)
    assert len(sel_s) == len(steel), (len(sel_s), ns)  # 无 6m 铁
    assert len(sel_a) < len(alum), (len(sel_a), len(alum), na)
    print("PASS drop_long material-aware", len(sel_s), "steel kept;", len(sel_a), "/", len(alum), "alum")

    # 「只要铁件」：铁票全留；铝票几乎空→回退或极少
    i_steel = parse_nl_whatif("只要铁件", materials=steel)
    i_alum = parse_nl_whatif("只要铁件", materials=alum)
    ks, _ = apply_material_selection(steel, i_steel)
    ka, notes_a = apply_material_selection(alum, i_alum)
    assert len(ks) == len(steel)
    # 铝料 keep iron → 过滤后可能回退全量（有 note）或 0 后回退
    assert any("族" in n or "回退" in n or "铁" in n for n in (i_alum.get("notes") or []) + notes_a)
    print("PASS iron-only material-aware", len(ks), "steel;", len(ka), "alum after", notes_a[:2])

    # 复合：锁 2 柜 + 去掉超长 在铝票上
    both = parse_nl_whatif("锁 2 柜，去掉超长", materials=alum)
    assert both["max_containers"] == 2
    sel_b, nb = apply_material_selection(alum, both)
    assert len(sel_b) < len(alum)
    assert both["packing_options"].get("lock_max_containers") is True
    print("PASS composite lock2+no_long on alum", len(sel_b), both["scheme_id"])

    print("ALL PASS nl material scheme")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
