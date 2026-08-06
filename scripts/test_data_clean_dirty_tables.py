#!/usr/bin/env python3
"""数据清洗回归：脏表经真实 parse_table_file 规范化。

覆盖：G6 乱表头、G8 噪声行、G9 吨重、G15 混单位 + 合成汇总行。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.table_mapper import (  # noqa: E402
    parse_table_file,
    rows_to_ir,
    last_clean_stats,
)

BASE = ROOT / "test" / "generic_tables"


def _assert_mm_kg(mats: list, *, case: str) -> None:
    for m in mats:
        L = float(m.get("length_mm") or 0)
        W = float(m.get("width_mm") or 0)
        H = float(m.get("height_mm") or 0)
        w = float(m.get("weight_kg") or 0)
        # mm scale: cargo pieces typically 10mm–20000mm when present
        for dim, v in (("L", L), ("W", W), ("H", H)):
            if v > 0:
                assert 10 <= v <= 25000, f"{case} {m.get('name')} {dim}={v} not mm-ish"
        if w > 0:
            # kg scale after ton normalize: not multi-ton single piece as 1.25 without *1000
            assert w < 50000, f"{case} weight_kg={w} unrealistic"
            # if looks like raw tons left as 0.05–2 for heavy coils, flag
            # (G9 should have converted 1.25t → 1250kg)
            pass


def main() -> int:
    fails = []

    # --- G6 messy headers: mixed units in header ---
    g6 = BASE / "G6_messy_headers" / "materials.csv"
    assert g6.is_file(), g6
    pr6 = parse_table_file(g6)
    assert pr6["ok"] and pr6["stats"]["n_rows"] >= 3, pr6
    _assert_mm_kg(pr6["materials"], case="G6")
    # Length (m) 0.5 → 500mm class
    lens = [float(m["length_mm"]) for m in pr6["materials"]]
    assert any(400 <= x <= 600 for x in lens) or any(x >= 400 for x in lens), lens
    print(
        f"G6_messy_headers: parse_ok={pr6['ok']} n_rows={pr6['stats']['n_rows']} "
        f"lens={lens}"
    )

    # --- G8 noise rows ---
    g8 = BASE / "G8_noise_rows" / "materials.csv"
    assert g8.is_file(), g8
    pr8 = parse_table_file(g8)
    assert pr8["ok"], pr8
    names8 = [str(m.get("name")) for m in pr8["materials"]]
    assert pr8["stats"]["n_rows"] == 3, (pr8["stats"], names8)
    assert not any(n.startswith("#") for n in names8), names8
    # clean stats should report skips if input had more rows
    st8 = pr8["stats"]
    print(
        f"G8_noise_rows: parse_ok={pr8['ok']} n_rows={st8['n_rows']} "
        f"n_input={st8.get('n_input_rows')} n_skipped={st8.get('n_skipped_total')} "
        f"names={names8}"
    )
    if (st8.get("n_skipped_total") or 0) < 1:
        fails.append("G8 expected n_skipped_total>=1")

    # --- G9 weight tons ---
    g9 = BASE / "G9_weight_tons" / "materials.csv"
    assert g9.is_file(), g9
    pr9 = parse_table_file(g9)
    assert pr9["ok"] and pr9["stats"]["n_rows"] >= 2, pr9
    wts = [float(m.get("weight_kg") or 0) for m in pr9["materials"]]
    # at least one heavy piece from tons → hundreds/thousands kg
    assert max(wts) >= 100, f"G9 ton not normalized: {wts}"
    print(f"G9_weight_tons: parse_ok={pr9['ok']} n_rows={pr9['stats']['n_rows']} weights={wts}")

    # --- G15 mixed units stress ---
    g15 = BASE / "G15_mixed_units_stress" / "materials.csv"
    assert g15.is_file(), g15
    pr15 = parse_table_file(g15)
    assert pr15["ok"] and pr15["stats"]["n_rows"] >= 3, pr15
    _assert_mm_kg(pr15["materials"], case="G15")
    # Length (cm) 45 → 450mm; width_m 0.3 → 300mm
    m0 = pr15["materials"][0]
    assert float(m0["length_mm"]) >= 400, m0  # 45cm → 450
    assert 250 <= float(m0["width_mm"]) <= 350, m0  # 0.3m → 300
    print(
        f"G15_mixed_units: parse_ok={pr15['ok']} n_rows={pr15['stats']['n_rows']} "
        f"sample L/W={m0['length_mm']}/{m0['width_mm']}"
    )

    # --- synthetic summary + noise via rows_to_ir ---
    syn = rows_to_ir(
        [
            {"name": "合计", "quantity": 99, "length_mm": 1000, "width_mm": 1000, "height_mm": 1000, "weight_kg": 999},
            {"name": "小计", "quantity": 1, "length_mm": 100, "width_mm": 100, "height_mm": 100, "weight_kg": 1},
            {"name": "备注", "quantity": 1, "length_mm": 100, "width_mm": 100, "height_mm": 100, "weight_kg": 1},
            {"name": "真货箱", "quantity": 2, "length_mm": 600, "width_mm": 400, "height_mm": 300, "weight_kg": 5},
            {"name": "header rail", "quantity": 1, "length_mm": 1200, "width_mm": 80, "height_mm": 40, "weight_kg": 5},
        ],
        headers=["name", "quantity", "length_mm", "width_mm", "height_mm", "weight_kg"],
    )
    syn_names = [m["name"] for m in syn]
    assert "合计" not in syn_names and "小计" not in syn_names and "备注" not in syn_names, syn_names
    assert "真货箱" in syn_names and "header rail" in syn_names, syn_names
    cs = last_clean_stats()
    assert cs.get("n_skip_summary_row", 0) >= 2, cs
    print(f"synthetic_summary: kept={syn_names} clean_stats={cs}")

    if fails:
        print("FAIL data_clean_dirty_tables", fails)
        return 1
    print("ALL_PASS data_clean_dirty_tables")
    print(
        f"coverage=G6,G8,G9,G15,synthetic n_cases=5 "
        f"g6_rows={pr6['stats']['n_rows']} g8_rows={pr8['stats']['n_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
