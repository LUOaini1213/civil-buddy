#!/usr/bin/env python3
"""Audit VMU1 site remaining vs leader 2-cabinet claim."""
from __future__ import annotations

from pathlib import Path
import openpyxl

VMU = Path(r"A:\JOB\REDACTED-JOB\Project\6. Quality QAQC\6.06 POR\VMU")
SHIPPED = Path(r"A:\JOB\REDACTED-JOB\Project\6. Quality QAQC\6.06 POR\已发货")


def dump(path: Path, max_rows: int = 80) -> None:
    print("=" * 70)
    print("FILE", path.name, "exists", path.exists())
    if not path.exists():
        return
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h or "").strip() for h in rows[0]]
    print("headers:", headers)
    print("nrows:", len(rows) - 1)
    for r in rows[1 : max_rows + 1]:
        d = {headers[i]: r[i] if i < len(r) else None for i in range(len(headers))}
        batch = str(d.get("施工批次") or d.get("施工 批次") or "")
        desc = str(d.get("项目描述") or d.get("項目描述") or "")
        por = str(d.get("訂貨單/加工圖號") or d.get("訂貨單 / 加工圖號") or d.get("POR No.") or "")
        if "0001" not in batch and "REDACTED-CODE" not in desc.upper() and "VMU-0001" not in por.upper():
            # still print if only one sheet site file
            if "送工地" not in path.name and "状态" not in path.name:
                continue
        arr = d.get("已到货数量")
        pend = d.get("未到货数量")
        # try more cols
        total = d.get("总数") or d.get("数量")
        cntr = d.get("货柜号") or d.get("柜号")
        note = d.get("生产情况备注") or d.get("备注")
        dest = d.get("收货  目的地") or d.get("目的地")
        pack = d.get("实际装柜日期") or d.get("订柜时间(VMU批次最晚订柜日)")
        print(
            f"por={por} | arr={arr} pend={pend} total={total} dest={dest} "
            f"cntr={cntr} pack={pack} note={str(note)[:40] if note else ''}"
        )
        print(f"  group={d.get('物料组描述')} desc={desc[:90]}")
    wb.close()


def main() -> None:
    for name in [
        "Material_Summary_VMU送工地.xlsx",
        "Material_Summary_VMU送工地_订柜日更新副本.xlsx",
        "Material_Summary_VMU送工地_校准副本.xlsx",
        "Material_Summary_VMU状态表.xlsx",
        "Material_Summary_VMU减一月.xlsx",
    ]:
        dump(VMU / name)

    print("=" * 70)
    print("SHIPPED hits for site PORs:")
    keys = [
        "REDACTED-REF",
        "FAC0011",
        "FST0022",
        "FSS0005",
        "BBF0007",
        "BBF0022",
        "BOM0019",
        "BGK0015",
        "FST0017",
        "BOM0016",
    ]
    if SHIPPED.exists():
        for p in SHIPPED.rglob("*"):
            n = p.name.upper()
            for k in keys:
                if k in n:
                    print(" ", k, p.name[:100])


if __name__ == "__main__":
    main()
