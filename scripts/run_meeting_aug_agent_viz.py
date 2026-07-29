#!/usr/bin/env python3
"""
会里 8/17 龙申 1 柜 + 8/25 工厂预算 2 柜 → harness 闭环 9 智能体出图。

改进：
  - 走 run_agent_pipeline（内环/出运 replan）
  - packing_options.lock_max_containers：预算柜数不因 replan 加柜
  - 瓦楞板密装（与 run_vmu1_site_only 一致）
  - 工厂第一批叠层架更贴 40HQ 几何

  python scripts/run_meeting_aug_agent_viz.py
  python scripts/run_meeting_aug_agent_viz.py --only 817
  python scripts/run_meeting_aug_agent_viz.py --only 825
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts._est_aug17_25_meeting as meet  # type: ignore
from packing_assistant.harness import run_agent_pipeline

OUT = ROOT / "output" / "meeting_aug_ship" / "agent_viz"


def _por_key(pn: str) -> str:
    return meet.por_key(pn)


def densify_bom0019_rows(mats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    离线 xlsx 仍是旧 2400×1200×500 时，就地改成密装架。
    702 件 → 140/架 ≈ 5 架；W=1100 可双排，H=1100 可叠。
    """
    bom = [m for m in mats if _por_key(str(m.get("part_no") or "")) == "BOM0019"]
    other = [m for m in mats if _por_key(str(m.get("part_no") or "")) != "BOM0019"]
    if not bom:
        return mats
    # 从 note/raw 估件数；否则按旧 80 件/架反推
    raw = 0.0
    for m in bom:
        note = str(m.get("note") or "")
        if "raw_qty=" in note:
            try:
                raw = max(raw, float(note.split("raw_qty=")[1].split(";")[0]))
            except Exception:
                pass
    if raw <= 0:
        raw = len(bom) * 80.0
    per = 140
    n_units = max(1, int(round(raw / per)))
    wt = per * 8.0
    dense: List[Dict[str, Any]] = []
    for i in range(n_units):
        dense.append(
            {
                "id": f"BOM0019-D{i+1:02d}",
                "name": f"瓦楞板架密装×{per}/架 | SLTO-VMU-0001-BOM0019#{i+1}",
                "spec": "28—杂项配件",
                "quantity": 1,
                "weight_kg": wt,
                "total_weight_kg": wt,
                "length_mm": 2200.0,
                "width_mm": 1100.0,
                "height_mm": 1100.0,
                "part_no": "SLTO-VMU-0001-BOM0019",
                "note": f"dense_bom; raw_qty={raw}; crate={i+1}/{n_units}",
                "destination": "工地",
            }
        )
    return other + dense


def build_817_materials(*, full_bom: bool = True) -> List[Dict[str, Any]]:
    """
    满柜推荐：铁 + 吊具 + FSS + 密装 BOM 全量(或上限) + VMU2/3 五金胶条。
    full_bom=True：密装后全部瓦楞进 1 柜试装。
    """
    keys = {
        "FST0023",
        "FST0026",
        "FST0017",
        "FSS0005",
        "BOM0019",
        "BBF0031",
        "BGK0037",
        "BOM0039",
        "BBF0042",
    }
    mats, _ = meet.load_selected(keys)
    mats = densify_bom0019_rows(mats)
    if not full_bom:
        out: List[Dict[str, Any]] = []
        bom_left = 3
        for m in mats:
            k = _por_key(str(m.get("part_no") or ""))
            if k == "BOM0019":
                if bom_left <= 0:
                    continue
                bom_left -= 1
            out.append(m)
        mats = out
    for i, m in enumerate(mats, 1):
        m = dict(m)
        m["id"] = m.get("id") or f"A817-{i:03d}"
        mats[i - 1] = m
    return mats


def load_factory_materials() -> List[Dict[str, Any]]:
    path = ROOT / "output" / "por_vmu_nine" / "materials_por_vmu_real_fac8est.xlsx"
    if not path.exists():
        return []
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h or "").strip() for h in rows[0]]
    mats: List[Dict[str, Any]] = []
    for raw in rows[1:]:
        d = {headers[i]: raw[i] if i < len(raw) else None for i in range(len(headers))}
        L = float(d.get("length_mm") or 0)
        W = float(d.get("width_mm") or 0)
        H = float(d.get("height_mm") or 0)
        if L <= 0 or W <= 0 or H <= 0:
            continue
        mats.append(
            {
                "id": str(d.get("id") or f"F{len(mats)+1:03d}"),
                "name": d.get("name") or d.get("part_no") or "factory",
                "spec": d.get("spec") or "",
                "quantity": int(d.get("quantity") or 1),
                "weight_kg": float(d.get("weight_kg") or 0),
                "total_weight_kg": float(
                    d.get("total_weight_kg") or d.get("weight_kg") or 0
                ),
                "length_mm": L,
                "width_mm": W,
                "height_mm": H,
                "part_no": d.get("part_no"),
                "note": d.get("note"),
                "destination": "工厂",
            }
        )
    wb.close()
    return mats


def _material_to_crates(m: Dict[str, Any], *, max_split: int = 4) -> List[Dict[str, Any]]:
    """单行材料 → 1..N 个 40HQ 友好当量架。"""
    L = float(m["length_mm"])
    W = float(m["width_mm"])
    H = float(m["height_mm"])
    q = max(1, int(m.get("quantity") or 1))
    tw = float(m.get("total_weight_kg") or 0)
    name = str(m.get("name") or "")[:48]
    out: List[Dict[str, Any]] = []
    if H <= 80 and L >= 600:
        stack_h = 1000.0
        per = max(1, int(stack_h // max(H, 3)))
        n_c = min(max(1, math.ceil(q / per)), max_split)
        w_each = tw / n_c if n_c else tw
        for i in range(n_c):
            out.append(
                {
                    "id": f"{m['id']}-R{i+1}",
                    "name": f"叠层架 | {name}#{i+1}",
                    "spec": m.get("spec") or "",
                    "quantity": 1,
                    "weight_kg": round(w_each, 2),
                    "total_weight_kg": round(w_each, 2),
                    "length_mm": min(L + 40, 11800),
                    "width_mm": min(max(W + 40, 900), 1100),
                    "height_mm": stack_h,
                    "part_no": m.get("part_no"),
                    "note": "factory_stack_v3",
                    "destination": "工厂",
                }
            )
    elif L >= 3500:
        out.append(
            {
                "id": m["id"],
                "name": f"长料架 | {name}",
                "spec": m.get("spec") or "",
                "quantity": 1,
                "weight_kg": tw or float(m.get("weight_kg") or 0),
                "total_weight_kg": tw or float(m.get("weight_kg") or 0),
                "length_mm": min(L + 60, 11800),
                "width_mm": min(max(W * 3 if W < 200 else W + 40, 500), 1100),
                "height_mm": min(max(400.0, H * 4 if H < 120 else H + 40), 1200),
                "part_no": m.get("part_no"),
                "note": "factory_long_v3",
                "destination": "工厂",
            }
        )
    else:
        out.append(
            {
                "id": m["id"],
                "name": name,
                "spec": m.get("spec") or "",
                "quantity": 1,
                "weight_kg": tw or float(m.get("weight_kg") or 0),
                "total_weight_kg": tw or float(m.get("weight_kg") or 0),
                "length_mm": min(L, 11800),
                "width_mm": min(max(W, 400), 1100),
                "height_mm": min(max(H, 300), 1200),
                "part_no": m.get("part_no"),
                "destination": "工厂",
            }
        )
    return out


def _crates_can_fit(crates: List[Dict[str, Any]], max_c: int = 2) -> bool:
    from packing_assistant.tools.bin3d import pack_boxes_api

    boxes = []
    for i, m in enumerate(crates, 1):
        L = int(round(float(m["length_mm"])))
        W = int(round(float(m["width_mm"])))
        H = int(round(float(m["height_mm"])))
        boxes.append(
            {
                "box_id": f"PT-{i:03d}",
                "box_type": "当量箱",
                "outer_size_mm": {"length": L, "width": W, "height": H},
                "net_weight_kg": float(m.get("total_weight_kg") or 0),
                "gross_weight_kg": float(m.get("total_weight_kg") or 0) + 40,
                "stackable": H <= 1200 and L < 4000,
                "prefer_bottom": L >= 4000 or float(m.get("total_weight_kg") or 0) >= 800,
                "name": m.get("name"),
            }
        )
    plan = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=max_c,
        packing_options={
            "multi_start": True,
            "prefer_stack": True,
            "cog_rebalance": True,
            "clearance_mm": 25,
        },
    )
    return bool(plan.get("can_fit")) and not plan.get("unpacked_box_ids")


def factory_first_batch_crates(
    mats: List[Dict[str, Any]],
    *,
    max_crates: int = 44,
    target_net_kg: float = 28000.0,
) -> List[Dict[str, Any]]:
    """
    工厂第一批：贪心装箱试装，保证 2×40HQ can_fit，同时尽量抬重量。
    排序：单位外廓重量高的优先（塞满预算柜）。
    """
    # 先全部展开为候选架
    candidates: List[Dict[str, Any]] = []
    for m in mats:
        candidates.extend(_material_to_crates(m, max_split=3))

    def score(c: Dict[str, Any]) -> float:
        L = float(c["length_mm"])
        W = float(c["width_mm"])
        H = float(c["height_mm"])
        vol = max(L * W * H / 1e9, 0.05)
        wt = float(c.get("total_weight_kg") or 0)
        # 偏短 + 偏重优先
        long_pen = 1.0 + max(0.0, (L - 4000) / 4000.0)
        return (wt / vol) / long_pen

    candidates.sort(key=score, reverse=True)

    chosen: List[Dict[str, Any]] = []
    net = 0.0
    for c in candidates:
        if len(chosen) >= max_crates:
            break
        w = float(c.get("total_weight_kg") or 0)
        if net + w > target_net_kg and chosen:
            continue
        trial = chosen + [c]
        # 轻量探测：先按 2 柜；末段再严检
        if len(trial) <= 8 or len(trial) % 3 == 0:
            if not _crates_can_fit(trial, 2):
                continue
        chosen.append(c)
        net += w

    while chosen and not _crates_can_fit(chosen, 2):
        dropped = chosen.pop()
        net -= float(dropped.get("total_weight_kg") or 0)

    # 若 1 柜已装下且还有候选：继续塞到需要 2 柜（贴合「预算 2 柜」会里口径）
    if chosen and _crates_can_fit(chosen, 1):
        for c in candidates:
            if c in chosen or len(chosen) >= max_crates:
                continue
            w = float(c.get("total_weight_kg") or 0)
            if net + w > target_net_kg * 1.15:
                continue
            trial = chosen + [c]
            if _crates_can_fit(trial, 2):
                chosen.append(c)
                net += w
            # 已明显需要 2 柜且重量够则停
            if (
                not _crates_can_fit(chosen, 1)
                and net >= 22000
                and len(chosen) >= 16
            ):
                break

    while chosen and not _crates_can_fit(chosen, 2):
        dropped = chosen.pop()
        net -= float(dropped.get("total_weight_kg") or 0)

    for i, c in enumerate(chosen, 1):
        c["id"] = f"FB-{i:03d}"
    return chosen


def _plan_metrics(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    img = state.get("image_data") or {}
    risk = state.get("risk_report") or {}
    return {
        "materials": len(state.get("materials") or []),
        "boxes": len(state.get("boxes") or []),
        "n0": book.get("n0") or plan.get("n0"),
        "containers_used": plan.get("containers_used"),
        "can_fit": plan.get("can_fit"),
        "unpacked": plan.get("unpacked_box_ids") or [],
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "floor_utilization": plan.get("floor_utilization")
        or plan.get("floor_utilization_avg")
        or plan.get("floor_area_utilization")
        or plan.get("avg_floor_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "risk": risk.get("decision"),
        "risk_level": risk.get("level"),
        "ship_ok": risk.get("ship_ok"),
        "replan_round": state.get("replan_round"),
        "ship_replan_round": state.get("ship_replan_round"),
        "image_data": {
            "side": (img.get("side") or {}).get("path"),
            "side_overview": img.get("side_overview"),
            "side_per_container": img.get("side_per_container"),
        },
    }


def run_closed(
    mats: List[Dict[str, Any]],
    *,
    label: str,
    session_id: str,
    max_containers: int,
    crate_passthrough: bool = True,
) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "multi_start": True,
        "prefer_stack": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "export_strict": False,
        "lock_max_containers": True,
        "fixed_container_budget": True,
        "meeting_cap": True,
        "container_budget": max_containers,
        "max_stack_layers": 3,
        "clearance_mm": 25,
    }
    if crate_passthrough:
        opts.update(
            {
                "crate_passthrough": True,
                "standard_boxes": False,
                "mix_mode": False,
                "dense_mode": True,
            }
        )
    else:
        opts.update(
            {
                "dense_mode": True,
                "standard_boxes": True,
                "mix_mode": True,
                "max_box_net_kg": 800,
            }
        )

    print(f"\n=== {label} · materials={len(mats)} max_c={max_containers} closed-loop ===")
    state = run_agent_pipeline(
        raw_input=f"{label} 40HQ 预算{max_containers}柜 闭环出图",
        materials=mats,
        container_type="40HQ",
        max_containers=max_containers,
        enable_auto_confirm=True,
        packing_options=opts,
        session_id=session_id,
        save_artifacts=True,
        on_event=lambda ev: _print_ev(ev),
    )
    summary = _plan_metrics(state)
    summary["label"] = label
    summary["net_kg"] = round(
        sum(float(m.get("total_weight_kg") or 0) for m in mats), 1
    )
    return {"summary": summary, "state": state}


def _print_ev(ev: Dict[str, Any]) -> None:
    t = ev.get("type")
    if t in ("step", "replan"):
        node = ev.get("node") or ""
        msg = str(ev.get("message") or "")[:120]
        if t == "replan":
            print(f"  [replan] {msg}")
        elif node in (
            "box_scheme",
            "loader",
            "evaluator",
            "risk_compliance",
            "visualizer",
            "finalize",
            "replan_critic",
        ):
            print(f"  [{node}] {msg}")


def collect_images(summary: Dict[str, Any], dest: Path) -> List[str]:
    dest.mkdir(parents=True, exist_ok=True)
    paths: List[str] = []
    img = summary.get("image_data") or {}
    candidates: List[Any] = []
    for k in ("side", "side_overview"):
        if img.get(k):
            candidates.append(img[k])
    for item in img.get("side_per_container") or []:
        if isinstance(item, dict):
            candidates.append(item.get("path"))
        else:
            candidates.append(item)
    seen = set()
    for p in candidates:
        if not p or p in seen:
            continue
        seen.add(p)
        src = Path(str(p))
        if not src.is_absolute():
            src = ROOT / src
        if not src.exists():
            alt = ROOT / "output" / Path(str(p)).name
            if alt.exists():
                src = alt
            else:
                print("  MISS", p)
                continue
        dst = dest / src.name
        shutil.copy2(src, dst)
        paths.append(str(dst.relative_to(ROOT)))
        print("  COPY", dst)
    return paths


def write_readme(reports: List[Dict[str, Any]], images: Dict[str, List[str]]) -> Path:
    lines = [
        "# 会里 3 柜 · Agent 闭环出图（改进版）",
        "",
        "- 流水线：`run_agent_pipeline`（评估内环 + 出运外环 replan）",
        "- **lock_max_containers**：预算 1/2 柜时 replan **不加柜**，改密装/叠高/CoG",
        "- 瓦楞板 **密装** 2200×1100×1100 ×140件/架",
        "",
    ]
    for r in reports:
        s = r["summary"]
        tag = s["label"]
        lines += [
            f"## {tag}",
            "",
            "| 项 | 值 |",
            "|---|---|",
            f"| 净重 | {s.get('net_kg')} kg |",
            f"| 成箱 | {s.get('boxes')} |",
            f"| N0 / 用柜 | {s.get('n0')} / **{s.get('containers_used')}** |",
            f"| can_fit | **{s.get('can_fit')}** |",
            f"| 外廓 / 底 / 重量 | {s.get('outer_space_utilization')} / {s.get('floor_utilization')} / {s.get('weight_utilization')} |",
            f"| 订舱体积率 | {s.get('booking_volume_utilization')} |",
            f"| 风险 | {s.get('risk')} / {s.get('risk_level')} ship_ok={s.get('ship_ok')} |",
            f"| replan 轮 | inner={s.get('replan_round')} ship={s.get('ship_replan_round')} |",
            f"| 未装入 | {len(s.get('unpacked') or [])} |",
            "",
        ]
        for p in images.get(tag) or []:
            name = Path(p).name
            sub = Path(p).parts[-2] if len(Path(p).parts) >= 2 else ""
            lines.append(f"![{name}](./{sub}/{name})")
            lines.append("")
            lines.append(f"`{p}`")
            lines.append("")
    md = OUT / "README.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("817", "825", "all"), default="all")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    reports: List[Dict[str, Any]] = []
    images: Dict[str, List[str]] = {}

    if args.only in ("817", "all"):
        mats = build_817_materials(full_bom=True)
        net = sum(float(m.get("total_weight_kg") or 0) for m in mats)
        bom_n = sum(1 for m in mats if "BOM0019" in str(m.get("part_no") or ""))
        print(f"817 mats={len(mats)} net={net:.0f} bom_frames={bom_n}")
        rep = run_closed(
            mats,
            label="817_龙申_1柜",
            session_id="meeting-817-v2",
            max_containers=1,
            crate_passthrough=True,
        )
        dest = OUT / "817_longshen"
        images[rep["summary"]["label"]] = collect_images(rep["summary"], dest)
        (dest / "summary.json").write_text(
            json.dumps(rep["summary"], ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        reports.append(rep)
        print("SUMMARY817", json.dumps(rep["summary"], ensure_ascii=False, default=str)[:700])

    if args.only in ("825", "all"):
        pool = load_factory_materials()
        crates = factory_first_batch_crates(pool)
        net = sum(float(m.get("total_weight_kg") or 0) for m in crates)
        print(f"825 crates={len(crates)} net={net:.0f} pool={len(pool)}")
        if crates:
            rep = run_closed(
                crates,
                label="825_工厂_2柜",
                session_id="meeting-825-v2",
                max_containers=2,
                crate_passthrough=True,
            )
            dest = OUT / "825_factory"
            images[rep["summary"]["label"]] = collect_images(rep["summary"], dest)
            (dest / "summary.json").write_text(
                json.dumps(rep["summary"], ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            reports.append(rep)
            print(
                "SUMMARY825",
                json.dumps(rep["summary"], ensure_ascii=False, default=str)[:700],
            )

    index = {"runs": [r["summary"] for r in reports], "images": images}
    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    md = write_readme(reports, images)
    print("WROTE", md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
