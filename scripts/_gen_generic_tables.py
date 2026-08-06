#!/usr/bin/env python3
"""Generate test/generic_tables G1-G6 fixtures."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1] / "test" / "generic_tables"


def write_csv(path: Path, headers: list, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_xlsx(path: Path, headers: list, rows: list, sheet: str = "materials") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    wb.save(path)


def exp(path: Path, **kwargs) -> None:
    path.write_text(json.dumps(kwargs, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)

    g1 = ROOT / "G1_ecommerce_cartons"
    h1 = ["品名", "数量", "长", "宽", "高", "单重", "料号", "类别"]
    r1 = [
        {"品名": "蓝牙音箱纸箱", "数量": 40, "长": 320, "宽": 220, "高": 180, "单重": 1.2, "料号": "SKU-A1", "类别": "纸箱"},
        {"品名": "键盘纸箱", "数量": 60, "长": 450, "宽": 180, "高": 60, "单重": 0.9, "料号": "SKU-B2", "类别": "纸箱"},
        {"品名": "显示器缓冲箱", "数量": 20, "长": 700, "宽": 450, "高": 200, "单重": 4.5, "料号": "SKU-C3", "类别": "纸箱"},
        {"品名": "配件小盒", "数量": 100, "长": 150, "宽": 100, "高": 80, "单重": 0.3, "料号": "SKU-D4", "类别": "纸箱"},
    ]
    write_csv(g1 / "materials.csv", h1, r1)
    write_xlsx(g1 / "materials.xlsx", h1, r1)
    exp(g1 / "expected.json", min_rows=4, require_can_fit=True, story="电商纸箱 SKU 表")

    g2 = ROOT / "G2_pallet_parts"
    h2 = ["item", "qty", "length_cm", "width_cm", "height_cm", "weight", "sku", "type"]
    r2 = [
        {"item": "Motor pallet", "qty": 8, "length_cm": 120, "width_cm": 100, "height_cm": 110, "weight": 280, "sku": "PLT-01", "type": "pallet"},
        {"item": "Gearbox crate", "qty": 12, "length_cm": 80, "width_cm": 60, "height_cm": 70, "weight": 95, "sku": "PLT-02", "type": "crate"},
        {"item": "Fastener carton", "qty": 30, "length_cm": 40, "width_cm": 30, "height_cm": 25, "weight": 12, "sku": "PLT-03", "type": "carton"},
    ]
    write_csv(g2 / "materials.csv", h2, r2)
    write_xlsx(g2 / "materials.xlsx", h2, r2)
    exp(g2 / "expected.json", min_rows=3, require_can_fit=True, story="机械零件托盘行")

    g3 = ROOT / "G3_long_pipes"
    h3 = ["名称", "件数", "长度_m", "宽度_mm", "高度_mm", "单重kg", "类别"]
    r3 = [
        {"名称": "镀锌钢管 6m", "件数": 24, "长度_m": 6.0, "宽度_mm": 120, "高度_mm": 120, "单重kg": 45, "类别": "管材"},
        {"名称": "方管 5.8m", "件数": 18, "长度_m": 5.8, "宽度_mm": 100, "高度_mm": 100, "单重kg": 38, "类别": "型材"},
        {"名称": "角钢 4.2m", "件数": 30, "长度_m": 4.2, "宽度_mm": 80, "高度_mm": 80, "单重kg": 22, "类别": "长材"},
    ]
    write_csv(g3 / "materials.csv", h3, r3)
    write_xlsx(g3 / "materials.xlsx", h3, r3)
    exp(g3 / "expected.json", min_rows=3, require_can_fit=True, story="管材长件")

    g4 = ROOT / "G4_bulk_bags"
    h4 = ["product", "count", "L_mm", "W_mm", "H_mm", "gross_kg", "category"]
    r4 = [
        {"product": "树脂吨袋", "count": 10, "L_mm": 1100, "W_mm": 1100, "H_mm": 1400, "gross_kg": 1000, "category": "吨袋"},
        {"product": "填料吨袋", "count": 8, "L_mm": 1050, "W_mm": 1050, "H_mm": 1350, "gross_kg": 950, "category": "集装袋"},
        {"product": "辅料袋", "count": 20, "L_mm": 600, "W_mm": 400, "H_mm": 500, "gross_kg": 25, "category": "bulk_bag"},
    ]
    write_csv(g4 / "materials.csv", h4, r4)
    write_xlsx(g4 / "materials.xlsx", h4, r4)
    exp(g4 / "expected.json", min_rows=3, require_can_fit=True, story="化工吨袋")

    g5 = ROOT / "G5_fragile_glass"
    h5 = ["name", "quantity", "length_mm", "width_mm", "height_mm", "weight_kg", "category", "note"]
    r5 = [
        {"name": "钢化玻璃 A", "quantity": 16, "length_mm": 2000, "width_mm": 1200, "height_mm": 80, "weight_kg": 45, "category": "易碎", "note": "立放"},
        {"name": "夹胶玻璃 B", "quantity": 10, "length_mm": 1800, "width_mm": 1000, "height_mm": 90, "weight_kg": 52, "category": "玻璃", "note": "禁压"},
        {"name": "镜片箱", "quantity": 24, "length_mm": 600, "width_mm": 400, "height_mm": 300, "weight_kg": 8, "category": "fragile", "note": ""},
    ]
    write_csv(g5 / "materials.csv", h5, r5)
    write_xlsx(g5 / "materials.xlsx", h5, r5)
    exp(g5 / "expected.json", min_rows=3, require_can_fit=True, story="玻璃易碎")

    g6 = ROOT / "G6_messy_headers"
    h6 = ["Item Description", "QTY.", "Length (m)", "Width (cm)", "Height(mm)", "Net Weight(kg)", "SKU Code", "备注"]
    r6 = [
        {"Item Description": "Mixed gadget case", "QTY.": 15, "Length (m)": 0.5, "Width (cm)": 40, "Height(mm)": 300, "Net Weight(kg)": 6.5, "SKU Code": "MX-01", "备注": "retail"},
        {"Item Description": "Cable drum", "QTY.": 6, "Length (m)": 1.2, "Width (cm)": 120, "Height(mm)": 1200, "Net Weight(kg)": 180, "SKU Code": "MX-02", "备注": ""},
        {"Item Description": "Toolkit carton", "QTY.": 40, "Length (m)": 0.4, "Width (cm)": 30, "Height(mm)": 250, "Net Weight(kg)": 3.2, "SKU Code": "MX-03", "备注": "纸箱"},
        {"Item Description": "Spare panel", "QTY.": 8, "Length (m)": 2.4, "Width (cm)": 80, "Height(mm)": 50, "Net Weight(kg)": 28, "SKU Code": "MX-04", "备注": "flat"},
    ]
    write_csv(g6 / "materials.csv", h6, r6)
    write_xlsx(g6 / "materials.xlsx", h6, r6)
    exp(g6 / "expected.json", min_rows=4, require_can_fit=True, story="混乱中英表头")

    (ROOT / "INDEX.json").write_text(
        json.dumps(
            {
                "version": 1,
                "cases": [
                    {"id": "G1_ecommerce_cartons", "path": "G1_ecommerce_cartons", "tags": ["carton", "short"]},
                    {"id": "G2_pallet_parts", "path": "G2_pallet_parts", "tags": ["pallet"]},
                    {"id": "G3_long_pipes", "path": "G3_long_pipes", "tags": ["long"]},
                    {"id": "G4_bulk_bags", "path": "G4_bulk_bags", "tags": ["weight"]},
                    {"id": "G5_fragile_glass", "path": "G5_fragile_glass", "tags": ["fragile"]},
                    {"id": "G6_messy_headers", "path": "G6_messy_headers", "tags": ["mapping"]},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (ROOT / "README.md").write_text(
        "# generic_tables — 非建材材料表样例（线 A）\n\n"
        "| ID | 说明 |\n|----|------|\n"
        "| G1 | 电商纸箱中文表头 |\n| G2 | 托盘/零件 英制 cm |\n"
        "| G3 | 长管材 长度用 m |\n| G4 | 吨袋重量主导 |\n"
        "| G5 | 玻璃易碎 |\n| G6 | 混乱中英表头混单位 |\n\n"
        "```bash\npython scripts/run_generic_table_tests.py\n"
        "python scripts/run_generic_table_tests.py --pack\n```\n",
        encoding="utf-8",
    )
    print("OK", ROOT)


if __name__ == "__main__":
    main()
