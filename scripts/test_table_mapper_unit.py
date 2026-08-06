#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packing_assistant.tools.table_mapper import build_column_map, rows_to_ir, parse_table_file, normalize_category

def main():
    m = build_column_map(["品名", "数量", "长", "宽", "高", "单重"])
    assert m.get("品名") == "name" and m.get("长") == "length_mm"
    r = rows_to_ir([
        {"item": "p", "qty": 1, "length_cm": 100, "width_cm": 50, "height_cm": 40, "weight": 12}
    ], headers=["item", "qty", "length_cm", "width_cm", "height_cm", "weight"])
    assert abs(r[0]["weight_kg"] - 12) < 1e-6, r[0]
    assert abs(r[0]["length_mm"] - 1000) < 1e-6, r[0]
    assert normalize_category("纸箱") == "carton"
    # core six
    base = ROOT / "test" / "generic_tables"
    for name in ["G1_ecommerce_cartons","G2_pallet_parts","G3_long_pipes","G4_bulk_bags","G5_fragile_glass","G6_messy_headers"]:
        f = base / name / "materials.csv"
        pr = parse_table_file(f)
        assert pr["ok"] and pr["stats"]["n_rows"] >= 1, name
    # semicolon if present
    g10 = base / "G10_semicolon_eu" / "materials.csv"
    if g10.exists():
        pr = parse_table_file(g10)
        assert pr["stats"]["n_rows"] >= 2, pr
    print("ALL_PASS table_mapper_unit")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
