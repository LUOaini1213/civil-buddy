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
    # 吨位单位回归：_norm_header 会删掉空白，"Gross Weight (t)" 规范化成
    # "grossweight(t)"；旧代码因为里面含 "weight" 而排除了吨换算，系数落回 1.0，
    # 把吨当成公斤——1000 倍少报，直接污染 N0 按重计算、载重校验与 VGM 草稿。
    from packing_assistant.tools.table_mapper import _infer_weight_scale
    _scale_cases = [
        ("Gross Weight (t)", 1000.0), ("G.W.(T)", 1000.0), ("毛重(吨)", 1000.0),
        ("总重(T)", 1000.0), ("weight_t", 1000.0), ("单重t", 1000.0), ("t", 1000.0),
        ("Net Weight (kg)", 1.0), ("N.W. (kg)", 1.0), ("gross_weight_kg", 1.0),
        ("Weight", 1.0), ("Total", 1.0), ("Tare", 1.0), ("净重 (g)", 0.001),
    ]
    for _h, _want in _scale_cases:
        _got = _infer_weight_scale(_h, [1.35, 2.0, 3.1])
        assert _got == _want, (_h, _got, _want)
    # 端到端：一行 1.35 吨必须落成 1350 kg
    _tonne = rows_to_ir(
        [{"name": "steel bracket", "qty": 2, "length_mm": 1200,
          "width_mm": 400, "height_mm": 300, "Gross Weight (t)": 1.35}],
        headers=["name", "qty", "length_mm", "width_mm", "height_mm", "Gross Weight (t)"],
    )
    assert _tonne, "吨位行被整行丢弃"
    assert abs(_tonne[0]["weight_kg"] - 1350.0) < 1e-6, _tonne[0]

    # 真实出口装箱单表头回归：这一组以前整表解析出 0 行——没有 name 列的模糊
    # 匹配，"Description of Goods" 映射不到，于是每行都在空品名处被丢掉；
    # 合并尺寸列没有拆分器；N.W./G.W. 两个缩写都不认。
    _real = ["S/N", "Description of Goods", "Q'ty",
             "Dimensions (L x W x H) cm", "N.W. (kg)", "G.W. (kg)", "CTN"]
    _m = build_column_map(_real)
    assert _m.get("Description of Goods") == "name", _m
    assert _m.get("Q'ty") == "quantity", _m
    assert _m.get("Dimensions (L x W x H) cm") == "__dims__", _m
    # 装柜看毛重：G.W. 必须赢 N.W.，且与列序无关
    assert _m.get("G.W. (kg)") == "weight_kg", _m
    assert _m.get("N.W. (kg)") != "weight_kg", _m
    _swapped = build_column_map(["Description of Goods", "G.W. (kg)", "N.W. (kg)"])
    assert _swapped.get("G.W. (kg)") == "weight_kg", _swapped
    _swapped2 = build_column_map(["Description of Goods", "N.W. (kg)", "G.W. (kg)"])
    assert _swapped2.get("G.W. (kg)") == "weight_kg", _swapped2

    _ir = rows_to_ir(
        [
            {"S/N": 1, "Description of Goods": "Steel bracket ST-100", "Q'ty": 20,
             "Dimensions (L x W x H) cm": "120 x 40 x 30",
             "N.W. (kg)": 60.0, "G.W. (kg)": 66.5, "CTN": 2},
            {"S/N": 2, "Description of Goods": "Galvanised rail GR-22", "Q'ty": 8,
             "Dimensions (L x W x H) cm": "600*25*25",
             "N.W. (kg)": 210.0, "G.W. (kg)": 228.0, "CTN": 1},
        ],
        headers=_real,
    )
    assert len(_ir) == 2, ("真实表头整表被丢弃", _ir)
    assert abs(_ir[0]["length_mm"] - 1200) < 1e-6, _ir[0]
    assert abs(_ir[0]["width_mm"] - 400) < 1e-6, _ir[0]
    assert abs(_ir[0]["height_mm"] - 300) < 1e-6, _ir[0]
    assert abs(_ir[1]["length_mm"] - 6000) < 1e-6, _ir[1]   # '*' 分隔符
    assert abs(_ir[0]["weight_kg"] - 66.5) < 1e-6, ("毛重未优先", _ir[0])
    assert _ir[0]["meta"]["dims_estimated"] is False, _ir[0]["meta"]

    print("ALL_PASS table_mapper_unit")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
