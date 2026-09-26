"""Write the SYNTHETIC façade panel lists (materials sheet, the format of test/benchmarks/excel).

24 unitised curtain-wall panels, 4200 x 1500 x 250 mm, 450 kg each, east elevation L5-L8.
facade_panels_rev_b.xlsx is the same list at a later revision, for the tender <-> packing link demo:
level L9 added (6 more panels) and the L8 panels re-weighed at 520 kg each (a thicker glass make-up).
The panels, marks and notes are invented for software testing; they are no contractor's data.
Run: python examples/facade-demo/make_panels.py [NAME ...]   (default: every list)
"""
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
HEAD = ["id", "name", "quantity", "weight_kg", "total_weight_kg", "length_mm", "width_mm", "height_mm", "note"]
FLOORS = ("L5", "L6", "L7", "L8")
PER_FLOOR, KG, DIMS = 6, 450, (4200, 1500, 250)
EN = ("Unitised curtain wall panel UCW-E1 east {floor} (SYNTHETIC)",
      "glass, fragile, transport upright on A-frame, do not stack, do not tip")
# name -> (label, note, floors, kg per panel by floor)
LISTS = {
    "facade_panels": (*EN, FLOORS, {}),
    "facade_panels_zh": ("单元式幕墙板块 UCW-E1 东立面{floor}（合成示例）", "玻璃 易碎 禁翻 直立运输 禁叠", FLOORS, {}),
    "facade_panels_rev_b": (EN[0].replace("(SYNTHETIC)", "rev B (SYNTHETIC)"), EN[1], (*FLOORS, "L9"), {"L8": 520}),
}
ABOUT = (
    "SYNTHETIC packing list for software testing and the Civil Buddy façade demo.",
    "Not a real shipment and not any contractor's data: panels, marks, weights and notes are invented.",
    "The packing engine reads the 'materials' sheet only. See examples/facade-demo/README.md.",
)


def main(names=None) -> None:
    for name, (label, note, floors, kg) in LISTS.items():
        if names and name not in names:
            continue
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "materials"
        ws.append(HEAD)
        total = 0
        for i, floor in enumerate(floors, 1):
            each = kg.get(floor, KG)
            total += PER_FLOOR * each
            ws.append([f"P{i:02d}", label.format(floor=floor), PER_FLOOR, each, PER_FLOOR * each, *DIMS, note])
        about = wb.create_sheet("README")
        for line in ABOUT:
            about.append([line])
        wb.properties.title = "SYNTHETIC façade panel list"
        wb.properties.subject = ABOUT[1]
        wb.save(HERE / f"{name}.xlsx")
        print("wrote", f"{name}.xlsx", "pieces", PER_FLOOR * len(floors), "kg", total)


if __name__ == "__main__":
    main(sys.argv[1:])
