#!/usr/bin/env python3
"""
VMU1 剩余未发 · 仅「送工地」料单 → 估算装箱柜数（标准箱库+混装）。

数据源优先：
  A:\\...\\POR\\VMU\\Material_Summary_VMU送工地.xlsx
排除：已到货=0 且 未到货=0 的空行；可选对照 已发货 目录。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VMU_DIR = Path(r"A:\JOB\2517SLTO\Project\6. Quality QAQC\6.06 POR\VMU")
SHIPPED_DIR = Path(r"A:\JOB\2517SLTO\Project\6. Quality QAQC\6.06 POR\已发货")
SITE_XLSX = VMU_DIR / "Material_Summary_VMU送工地.xlsx"
OUT = ROOT / "output" / "vmu1_site_only"

# 物料组 → (L,W,H mm, unit_kg, label) 实务粗估，非正式提料尺寸
GROUP_PROFILE: Dict[str, Tuple[float, float, float, float, str]] = {
    "11—铝板": (1800, 1200, 40, 18.0, "铝板"),
    "22—铝材": (4500, 80, 60, 9.5, "铝型材"),
    "13—铁件": (2000, 200, 150, 22.0, "铁件"),
    "14—不锈钢": (800, 200, 80, 4.0, "不锈钢件"),
    "19—胶条、垫块、胶皮": (600, 400, 300, 12.0, "胶条箱当量"),
    "23—紧固件/螺丝": (400, 300, 250, 8.0, "五金箱当量"),
    "24—Glass 玻璃": (1600, 1200, 80, 48.0, "玻璃"),
    "25—门窗锁配件": (500, 350, 250, 6.0, "五金箱当量"),
    "28—杂项配件": (1200, 800, 100, 15.0, "杂项"),
    "18—结构胶/耐候胶": (400, 300, 300, 20.0, "胶桶箱"),
    "17—拉爆螺栓，化学螺栓": (400, 300, 250, 10.0, "螺栓箱"),
}

BULK_PER_CARTON: Dict[str, int] = {
    "19—胶条、垫块、胶皮": 50,
    "23—紧固件/螺丝": 200,
    "25—门窗锁配件": 40,
    "17—拉爆螺栓，化学螺栓": 100,
}


def _f(x: Any) -> float:
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _s(x: Any) -> str:
    return str(x or "").strip()


def load_site_rows(path: Path) -> List[Dict[str, Any]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [_s(h) for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if raw is None or all(c is None or str(c).strip() == "" for c in raw):
            continue
        d = {headers[i]: raw[i] if i < len(raw) else None for i in range(len(headers))}
        out.append(d)
    wb.close()
    return out


def remaining_qty(row: Dict[str, Any]) -> float:
    """未发剩余量：优先未到货；否则已到货（在库待发工地）。双零视为无量。"""
    arr = _f(row.get("已到货数量"))
    pend = _f(row.get("未到货数量"))
    if pend > 0:
        return pend
    if arr > 0:
        return arr
    return 0.0


def is_vmu1(row: Dict[str, Any]) -> bool:
    batch = _s(row.get("施工批次")) + " " + _s(row.get("项目描述")) + " " + _s(
        row.get("訂貨單/加工圖號")
    )
    return "VMU-0001" in batch or "VMU01" in batch.upper() or "VMU1" in batch.upper()


def shipped_por_keys() -> set:
    keys = set()
    if not SHIPPED_DIR.exists():
        return keys
    for p in SHIPPED_DIR.rglob("*"):
        name = p.name.upper()
        if "VMU" not in name and "SLTO" not in name:
            continue
        # 提取 POR 号片段 FAC0011 / FST0003 等
        import re

        for m in re.findall(
            r"(FAC|FST|FSS|FHA|FHU|BBF|BGK|BGL|BSS|BOM|BAL|FST)\d{4}",
            name,
            flags=re.I,
        ):
            keys.add(m.upper())
        keys.add(p.stem[:40])
    return keys


def row_looks_shipped(row: Dict[str, Any], shipped: set) -> bool:
    por = _s(row.get("訂貨單/加工圖號")).upper()
    desc = _s(row.get("项目描述")).upper()
    for k in shipped:
        if len(k) >= 6 and (k in por or k in desc):
            return True
    return False


def to_materials(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    将工地剩余量转为「可拼柜材料行」。
    大票铁件/铝板等按「装木箱/铁架当量」折算，避免 1998 件铁件被当成 1998 个大件虚增柜数。
    """
    mats: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    mid = 0

    for d in rows:
        por = _s(d.get("訂貨單/加工圖號"))
        desc = _s(d.get("项目描述"))
        group = _s(d.get("物料组描述"))
        n = remaining_qty(d)
        raw_n = n

        if not is_vmu1(d):
            skipped.append({"por": por, "reason": "非VMU1", "qty": n})
            continue
        if n <= 0:
            skipped.append({"por": por, "reason": "零量(已到=未到=0)", "qty": 0})
            continue
        if "工厂" in desc and "工地" not in desc:
            skipped.append({"por": por, "reason": "描述像送工厂", "qty": n})
            continue

        pu = por.upper()
        # —— 按 POR/物料组：件数 → 标准箱当量 + 当量外廓/单重 ——
        # 目标：与现场「若干件合一铁架/木箱」一致，而不是 1 件 1 箱
        if "BBF" in pu or "紧固件" in group or "螺丝" in group or "螺栓" in group:
            per = 200
            units = max(1, int(round(n / per)))
            L, W, H, wt = 600.0, 400.0, 350.0, 25.0  # 五金木箱当量
            unit, suffix = "五金箱当量", f"×{per}件/箱"
        elif "BGK" in pu or "胶条" in group or "垫块" in group:
            per = 40
            units = max(1, int(round(n / per)))
            L, W, H, wt = 800.0, 600.0, 500.0, 30.0
            unit, suffix = "胶条垫块箱", f"×{per}/箱"
        elif "FAC0011" in pu or ("铝板" in desc and "FAC" in pu):
            # 铝板叠层装箱：约 25 片/铁架
            per = 25
            units = max(1, int(round(n / per)))
            L, W, H, wt = 2200.0, 1200.0, 800.0, 25 * 18.0  # 整箱重
            unit, suffix = "铝板架", f"×{per}片/架"
        elif "FST0022" in pu or "垫片" in desc:
            per = 60
            units = max(1, int(round(n / per)))
            L, W, H, wt = 1200.0, 800.0, 600.0, 60 * 2.5
            unit, suffix = "钢垫片箱", f"×{per}/箱"
        elif "FST0017" in pu or "吊具" in desc:
            units = max(1, int(round(n)))
            L, W, H, wt = 2000.0, 800.0, 600.0, 45.0
            unit, suffix = "吊具", ""
        elif "FST" in pu or "铁件" in group:
            # 结构铁件：约 30 件/4m 铁架（实务合箱，单架净重控制结构可过）
            per = 30
            units = max(1, int(round(n / per)))
            L, W, H, wt = 4000.0, 1100.0, 1200.0, 30 * 15.0  # ~450kg/架
            unit, suffix = "铁件架", f"×{per}件/架 raw={int(n)}"
        elif "FSS" in pu or "不锈钢" in group:
            per = 40
            units = max(1, int(round(n / per))) if n >= 10 else max(1, int(round(n)))
            L, W, H, wt = 1500.0, 800.0, 600.0, max(n, 1) / max(units, 1) * 4.0
            unit, suffix = "不锈钢箱", f"×{per}/箱" if n >= 10 else ""
        elif "BOM0019" in pu or "瓦楞" in desc:
            per = 40
            units = max(1, int(round(n / per)))
            L, W, H, wt = 2400.0, 1200.0, 600.0, 40 * 8.0
            unit, suffix = "瓦楞板架", f"×{per}/架"
        elif "BOM0016" in pu or "木板" in desc:
            per = 20
            units = max(1, int(round(n / per)))
            L, W, H, wt = 2400.0, 1200.0, 400.0, 20 * 18.0
            unit, suffix = "木板架", f"×{per}/架"
        elif "BSS" in pu or "胶" in group:
            units = max(1, int(round(n / 12))) if n > 12 else max(1, int(round(n)))
            L, W, H, wt = 500.0, 400.0, 400.0, 24.0
            unit, suffix = "胶类箱", ""
        else:
            per = BULK_PER_CARTON.get(group, 1)
            if per > 1:
                units = max(1, int(round(n / per)))
                suffix = f"×{per}/箱当量"
            else:
                units = max(1, int(round(n)))
                suffix = ""
            prof = GROUP_PROFILE.get(group)
            if not prof:
                L, W, H, wt, unit = 1200.0, 800.0, 600.0, 20.0, "通用箱当量"
            else:
                L, W, H, wt, unit = prof

        # 每个当量箱单独一行 quantity=1，避免再被合箱算法并成超重/超跨
        unit_wt = float(wt)
        n_units = max(1, int(units))
        for i in range(n_units):
            mid += 1
            mats.append(
                {
                    "id": f"S{mid:03d}",
                    "name": f"{unit}{suffix} | {por or desc[:40]}#{i+1}",
                    "quantity": 1,
                    "weight_kg": round(unit_wt, 2),
                    "total_weight_kg": round(unit_wt, 2),
                    "length_mm": float(L),
                    "width_mm": float(W),
                    "height_mm": float(H),
                    "spec": group or "未分组",
                    "part_no": por,
                    "note": (
                        f"dest=工地; raw_qty={raw_n}; crate={i+1}/{n_units}; "
                        f"arr={_f(d.get('已到货数量'))}; pend={_f(d.get('未到货数量'))}; "
                        f"dims=crate_equiv_est"
                    ),
                    "destination": "工地",
                    "source_sheet": "Material_Summary_VMU送工地",
                    "raw_qty": raw_n,
                }
            )
    return mats, skipped


def run_pack(mats: List[Dict[str, Any]], container: str = "40HQ") -> Dict[str, Any]:
    """
    当量箱已是「成箱尺寸」，直接 3D 装柜估柜数（不再二次合箱/结构校核虚报）。
    """
    from packing_assistant.tools.bin3d import pack_boxes_api

    net = sum(float(m.get("total_weight_kg") or 0) for m in mats)
    vol = sum(
        float(m["length_mm"])
        * float(m["width_mm"])
        * float(m["height_mm"])
        * float(m["quantity"])
        / 1e9
        for m in mats
    )
    guess = min(max(int(vol / 30) + 1, int(net / 22000) + 1, 1), 30)

    # 材料行 → API boxes（1 行 = 1 当量箱）
    boxes = []
    for i, m in enumerate(mats, 1):
        L = int(round(float(m["length_mm"])))
        W = int(round(float(m["width_mm"])))
        H = int(round(float(m["height_mm"])))
        longish = L >= 4000
        boxes.append(
            {
                "box_id": f"CRATE-{i:03d}",
                "box_type": "当量箱",
                "outer_size_mm": {"length": L, "width": W, "height": H},
                "net_weight_kg": float(m.get("weight_kg") or 0),
                "gross_weight_kg": float(m.get("weight_kg") or 0) + 80,
                "stackable": H <= 1300 and not longish,
                "prefer_bottom": longish or float(m.get("weight_kg") or 0) >= 500,
                "special_attributes": ["超长"] if longish else [],
                "content": [
                    {
                        "name": m.get("name"),
                        "quantity": 1,
                        "material_id": m.get("id"),
                    }
                ],
            }
        )

    t0 = time.time()
    best = None
    mc = max(guess, 2)
    for rnd in range(12):
        plan = pack_boxes_api(boxes, container_type=container, max_containers=mc)
        snap = {
            "round": rnd,
            "max_containers": mc,
            "boxes": len(boxes),
            "can_fit": plan.get("can_fit"),
            "containers_used": plan.get("containers_used"),
            "space": plan.get("space_utilization"),
            "floor": plan.get("floor_utilization_avg"),
            "weight": plan.get("weight_utilization"),
            "risk": "N/A_estimate",
            "risk_level": "estimate",
            "ship_ok": bool(plan.get("can_fit")),
            "struct_fail": 0,
            "engine": plan.get("engine"),
        }
        print("SNAPSHOT", json.dumps(snap, ensure_ascii=False))
        best = {
            "snapshot": snap,
            "steps": [
                {
                    "node": "direct_bin3d",
                    "message": (
                        f"当量箱 {len(boxes)} 只直接 3D 装 {container}×≤{mc} "
                        f"can_fit={plan.get('can_fit')} used={plan.get('containers_used')}"
                    ),
                }
            ],
            "final": "",
            "team_a": {"box_count": len(boxes), "note": "crate_equivalent_skip_rebox"},
            "boxes": [
                {
                    "box_id": b["box_id"],
                    "box_type": b["box_type"],
                    "outer": b["outer_size_mm"],
                    "net": b["net_weight_kg"],
                    "gross": b["gross_weight_kg"],
                    "struct": "当量跳过",
                    "content": [c.get("name") for c in b.get("content") or []],
                }
                for b in boxes[:30]
            ],
            "container_plan": {
                k: plan.get(k)
                for k in (
                    "can_fit",
                    "containers_used",
                    "space_utilization",
                    "floor_utilization_avg",
                    "weight_utilization",
                    "engine",
                    "cargo_solid_volume_m3",
                    "container_inner_volume_m3",
                )
            },
        }
        if plan.get("can_fit"):
            break
        mc = min(mc + 2, 40)
        print(f"cannot fit -> max_containers={mc}")

    ms = int((time.time() - t0) * 1000)
    return best or {}, ms, guess


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SITE_XLSX.exists():
        print("MISSING", SITE_XLSX)
        return 1

    rows = load_site_rows(SITE_XLSX)
    print(f"site summary rows: {len(rows)} from {SITE_XLSX.name}")
    mats, skipped = to_materials(rows)
    by_group = Counter(m["spec"] for m in mats)
    by_por = Counter(m["part_no"] for m in mats)
    net = sum(m["total_weight_kg"] for m in mats)
    pcs = sum(m["quantity"] for m in mats)
    print(f"remaining site materials: {len(mats)} lines, qty_units={pcs}, net≈{net:.1f} kg")
    print("by group:", dict(by_group))
    print("by POR:", dict(by_por))
    print(f"skipped: {len(skipped)}")
    for s in skipped[:15]:
        print("  skip", s)

    # save materials
    import openpyxl

    xlsx = OUT / "materials_vmu1_site_remaining.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "materials"
    cols = [
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
        "destination",
    ]
    ws.append(cols)
    for m in mats:
        ws.append([m.get(c) for c in cols])
    wb.save(xlsx)
    print("WROTE", xlsx)

    if not mats:
        print("NO MATERIALS — nothing to pack")
        return 0

    best, ms, guess = run_pack(mats, "40HQ")
    rep = {
        "scope": "VMU1 剩余未发 · 仅送工地",
        "source": str(SITE_XLSX),
        "materials_file": str(xlsx),
        "materials_lines": len(mats),
        "qty_units": pcs,
        "net_kg": net,
        "by_group": dict(by_group),
        "by_por": dict(by_por),
        "skipped": skipped,
        "dims_note": "Material_Summary 无逐件尺寸，按物料组/POR 实务估算，非正式提料尺寸",
        "pack": best,
        "ms": ms,
        "initial_guess_containers": guess,
    }
    outj = OUT / "vmu1_site_only_pack.json"
    outj.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", outj)

    snap = (best or {}).get("snapshot") or {}
    # 双界估算（给领导订柜）
    cargo_m3 = sum(
        float(m["length_mm"])
        * float(m["width_mm"])
        * float(m["height_mm"])
        * float(m["quantity"])
        / 1e9
        for m in mats
    )
    wt_bound = max(1, int((net / 22000.0) + 0.999))  # ceil
    vol_bound_50 = max(1, int((cargo_m3 / (76.4 * 0.50)) + 0.999))
    vol_bound_40 = max(1, int((cargo_m3 / (76.4 * 0.40)) + 0.999))
    prog_c = snap.get("containers_used")
    if snap.get("can_fit") and prog_c:
        recommend = int(prog_c)
    else:
        recommend = max(wt_bound, vol_bound_50, int(prog_c or 0) or vol_bound_40)

    md = [
        "# VMU1 剩余未发 · 仅送工地 · 装箱柜估算",
        "",
        f"- **数据源**：`{SITE_XLSX.name}`（**不是**送工厂汇总）",
        f"- **范围**：施工批次 **SLTO-VMU-0001**，目的地 **工地**，有剩余量（未到货>0 或 已到货在库）",
        f"- **当量箱行**：{len(mats)}（由提料件数折算为可拼铁架/木箱当量）",
        f"- **估算净重**：约 **{net/1000:.1f} t**（{net:.0f} kg）",
        f"- **当量箱外廓体积**：约 **{cargo_m3:.1f} m³**",
        f"- **尺寸说明**：Material_Summary **无逐件尺寸** → 按 POR/物料组 **合箱当量估算**（非正式提料）",
        "",
        "## 结论（给领导订柜）",
        "",
        f"| 项 | 值 |",
        f"|---|---|",
        f"| 建议柜型 | **40HQ** |",
        f"| **建议订柜数** | **约 {recommend} × 40HQ** |",
        f"| 重量下界（净重÷22t） | {wt_bound} 柜 |",
        f"| 体积下界（当量箱÷柜，50%填充） | {vol_bound_50} 柜 |",
        f"| 体积偏紧（40%填充） | {vol_bound_40} 柜 |",
        f"| 程序拼柜结果 | used={prog_c} can_fit={snap.get('can_fit')} 箱数={snap.get('boxes')} |",
        f"| 容积/底面积/重量利用率 | {float(snap.get('space') or 0):.0%} / {float(snap.get('floor') or 0):.0%} / {float(snap.get('weight') or 0):.0%} |",
        f"| 结构不通过箱 | {snap.get('struct_fail', 0)} |",
        f"| 风险 | {snap.get('risk')} / {snap.get('risk_level')} |",
        "",
        f"> **推荐答复领导：VMU1 剩余送工地货，按当前 Material_Summary 未发量粗算约需 **{recommend} 个 40HQ**（重量约需 {wt_bound} 柜，体积当量约 {vol_bound_50}–{vol_bound_40} 柜）。不含送工厂铝板/铝料/玻璃。**",
        "",
        "## 纳入 POR（VMU1·工地·有剩余量）",
        "",
        "| POR | 物料组 | 当量箱数 | 原料件数 |",
        "|---|---|---:|---:|",
    ]
    por_info = defaultdict(lambda: {"group": "", "qty": 0, "raw": 0.0})
    for m in mats:
        por_info[m["part_no"]]["group"] = m["spec"]
        por_info[m["part_no"]]["qty"] += int(m["quantity"])
        por_info[m["part_no"]]["raw"] = max(
            por_info[m["part_no"]]["raw"], float(m.get("raw_qty") or 0)
        )
    for por, info in sorted(por_info.items()):
        md.append(
            f"| {por} | {info['group']} | {info['qty']} | {info['raw']:.0f} |"
        )
    md.extend(
        [
            "",
            "## 未纳入",
            "",
            "- **送工厂**全部（FAC0008/BAL/BGL/FAC0007 等）— 不在本次范围",
            "- **VMU02/03/04** 送工地行（本表有，但领导只问 VMU1）",
            "- 已到=未到=0 的空量行（BBF0006/BOM0013/BSS0010 等）",
            "",
            "## 说明",
            "",
            "1. 件数→当量箱：铁件约 30 件/架、铝板约 25 片/架、紧固件约 200 件/箱等（实务粗算）。",
            "2. 若 **FST0003 / FAC0011** 已部分发运，请用真实剩余件数替换后重跑，柜数会下降。",
            "3. 正式订柜前建议对照提料单尺寸与已发货目录再校一版。",
            "",
            f"产物：`{outj}`  /  `{xlsx}`",
        ]
    )
    mdp = OUT / "VMU1_送工地_剩余装柜估算.md"
    mdp.write_text("\n".join(md), encoding="utf-8")
    print("WROTE", mdp)
    print("FINAL_CONTAINERS", snap.get("containers_used"), "boxes", snap.get("boxes"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
