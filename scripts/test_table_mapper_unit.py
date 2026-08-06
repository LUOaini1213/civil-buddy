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
    # noise / zero rows skipped (G8 + synthetic)
    g8 = base / "G8_noise_rows" / "materials.csv"
    if g8.exists():
        pr = parse_table_file(g8)
        assert pr["ok"]
        names = [m.get("name") for m in pr["materials"]]
        assert all(not str(n).startswith("#") for n in names), names
        assert not any("无效空行" in str(n) for n in names), names
        assert not any("注释" in str(n) for n in names), names
        # only real cargo rows
        assert pr["stats"]["n_rows"] == 3, (pr["stats"], names)
    noisy = rows_to_ir(
        [
            {"name": "# comment", "quantity": 1, "length_mm": 100, "width_mm": 100, "height_mm": 100, "weight_kg": 1},
            {"name": "ok", "quantity": 1, "length_mm": 500, "width_mm": 400, "height_mm": 300, "weight_kg": 2},
            {"name": "zero", "quantity": 0, "length_mm": 0, "width_mm": 0, "height_mm": 0, "weight_kg": 0},
        ],
        headers=["name", "quantity", "length_mm", "width_mm", "height_mm", "weight_kg"],
    )
    assert len(noisy) == 1 and noisy[0]["name"] == "ok", noisy
    # 真货名含 header/表头/跳过 不得被噪声规则误杀
    keep = rows_to_ir(
        [
            {"name": "header rail", "quantity": 1, "length_mm": 1200, "width_mm": 80, "height_mm": 40, "weight_kg": 5},
            {"name": "表头零件A", "quantity": 2, "length_mm": 300, "width_mm": 200, "height_mm": 100, "weight_kg": 1.5},
            {"name": "跳过梁-备用", "quantity": 1, "length_mm": 4000, "width_mm": 200, "height_mm": 200, "weight_kg": 80},
            {"name": "这是注释行", "quantity": 1, "length_mm": 100, "width_mm": 100, "height_mm": 100, "weight_kg": 1},
        ],
        headers=["name", "quantity", "length_mm", "width_mm", "height_mm", "weight_kg"],
    )
    keep_names = [m["name"] for m in keep]
    assert "header rail" in keep_names, keep_names
    assert "表头零件A" in keep_names, keep_names
    assert "跳过梁-备用" in keep_names, keep_names
    assert "这是注释行" not in keep_names, keep_names
    print("ALL_PASS table_mapper_unit")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
