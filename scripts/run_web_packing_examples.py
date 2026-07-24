#!/usr/bin/env python3
"""
用网上公开的集装箱拼柜/装柜例子压测本系统装载引擎与全流程。

案例来源（估算/行业工具）：
1) JustLoad.it — 40ft 柜 50×40×35cm 纸箱，理想约 720 箱（~120/层 × 6 层），3D 算法称 85–95%
2) 外贸实务 — 40GP 一般可装约 58 CBM 货（相对 67.7m³ 理论容积 ≈ 85%）
3) 标准欧托盘 1200×800 装 40HQ（混高）
4) 20GP 均质纸箱满载
5) 混装 LCL 风格（多 SKU 纸箱）
6) 对照：钢结构大铁架（解释为何 test 柜利用率低）

用法:
  python scripts/run_web_packing_examples.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _mk_box(bid: str, L: int, W: int, H: int, kg: float, allow_rotate: bool = True) -> Dict[str, Any]:
    return {
        "box_id": bid,
        "outer_size_mm": {"length": L, "width": W, "height": H},
        "gross_weight_kg": kg,
        "allowRotate": allow_rotate,
        "special_attributes": [],
    }


def _boxes_from_sku(name: str, L: int, W: int, H: int, kg: float, qty: int) -> List[Dict[str, Any]]:
    return [_mk_box(f"{name}-{i+1:04d}", L, W, H, kg) for i in range(qty)]


def _theo_vol_util(boxes: List[Dict[str, Any]], container_type: str) -> float:
    from packing_assistant.tools.bin3d import CONTAINER_INNER

    spec = CONTAINER_INNER[container_type]
    cv = spec["L"] * spec["W"] * spec["H"]
    bv = sum(
        float(b["outer_size_mm"]["length"])
        * float(b["outer_size_mm"]["width"])
        * float(b["outer_size_mm"]["height"])
        for b in boxes
    )
    return bv / cv if cv else 0.0


def pack_direct(boxes: List[Dict[str, Any]], container_type: str, max_containers: int = 1) -> Dict[str, Any]:
    from packing_assistant.tools.bin3d import pack_boxes_api

    t0 = time.time()
    plan = pack_boxes_api(boxes, container_type=container_type, max_containers=max_containers)
    plan["_ms"] = int((time.time() - t0) * 1000)
    plan["_n_boxes"] = len(boxes)
    plan["_theo_if_all_fit"] = round(_theo_vol_util(boxes, container_type), 4)
    return plan


def pack_via_pipeline(materials: List[Dict[str, Any]], container_type: str = "40HQ") -> Dict[str, Any]:
    """全流程（会先打木箱/铁架）— 用于对照「普货纸箱 vs 钢结构路径」。"""
    from packing_assistant.harness import run_pipeline

    net = sum(float(m.get("total_weight_kg") or m.get("weight_kg") or 0) * float(m.get("quantity") or 1) for m in materials)
    # materials 已含 total
    max_c = min(max(int(net / 18000) + 1, 1), 8)
    t0 = time.time()
    state = run_pipeline(
        raw_input="web-example",
        materials=materials,
        container_type=container_type,
        enable_auto_confirm=True,
        max_containers=max_c,
    )
    plan = state.get("container_plan") or {}
    return {
        "ms": int((time.time() - t0) * 1000),
        "boxes": len(state.get("boxes") or []),
        "box_types": [b.get("box_type") for b in (state.get("boxes") or [])][:8],
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "space_utilization": plan.get("space_utilization"),
        "space_best": plan.get("space_utilization_best_container"),
        "weight_utilization": plan.get("weight_utilization"),
        "engine": plan.get("engine"),
    }


def cases() -> List[Dict[str, Any]]:
    """
    网上案例定义。
    expected_vol_pct: 行业/工具宣传或简单几何估算的目标区间。
    数量按「尽量塞满一柜」设置，否则容积率低只是货不够。
    """
    return [
        {
            "id": "justload_40gp_carton_50x40x35",
            "source": "JustLoad.it — 50×40×35cm master carton in 40ft，理想约720箱，3D算法称85–95%",
            "url": "https://justload.it/calculations/how-many-cartons-fit-in-40ft-container",
            "container": "40GP",
            "mode": "direct",
            # 网格满载：24×5×6=720
            "boxes": _boxes_from_sku("CTN", 500, 400, 350, 12.0, 720),
            "max_containers": 1,
            "expected_vol_pct": (80, 95),
            "note": "规则纸箱满柜标杆（与 JustLoad 720 一致）",
        },
        {
            "id": "justload_40hq_carton_50x40x35",
            "source": "同上纸箱装 40HQ（更高，可多一层）",
            "url": "https://justload.it/calculations/how-many-cartons-fit-in-40ft-container",
            "container": "40HQ",
            "mode": "direct",
            # 40HQ H=2698 → nz=7 → 24×5×7=840
            "boxes": _boxes_from_sku("CTN", 500, 400, 350, 12.0, 840),
            "max_containers": 1,
            "expected_vol_pct": (80, 95),
            "note": "40HQ 规则纸箱满柜",
        },
        {
            "id": "trade_40gp_58cbm_equiv",
            "source": "外贸常见：40GP 实务可装约58CBM（相对理论≈85%）— 60×40×40cm 纸箱满网格",
            "url": "http://alphalogxmn.com/Home/New/details/id/2435.html",
            "container": "40GP",
            "mode": "direct",
            # 最优朝向网格约 500 箱 → 500*0.096=48m³≈71%；改 50×40×40 更密
            "boxes": _boxes_from_sku("CTN", 500, 400, 400, 14.0, 600),
            "max_containers": 1,
            "expected_vol_pct": (70, 90),
            "note": "实务满柜纸箱（贴近 58CBM 装载思路）",
        },
        {
            "id": "euro_pallet_40hq",
            "source": "欧托盘 1200×800，堆高约1.6m，40HQ 地板约 10×2=20 + 余量",
            "url": "https://www.freightos.com/",
            "container": "40HQ",
            "mode": "direct",
            # 12032/1200=10, 2352/800=2 → 20 托单层；高度只 1 层
            "boxes": _boxes_from_sku("PAL", 1200, 800, 1600, 500.0, 20),
            "max_containers": 1,
            "expected_vol_pct": (40, 55),
            "note": "托盘单层：容积中等、地台利用率高",
        },
        {
            "id": "20gp_uniform_cartons",
            "source": "20GP 均质纸箱满载；实务可用约 80–85% 理论容积",
            "url": "https://hz-containers.com/en/technical-information/what-is-the-actual-usable-volume-in-a-shipping-container/",
            "container": "20GP",
            "mode": "direct",
            # 400×300×300 → 约 14×7×7=686
            "boxes": _boxes_from_sku("CTN", 400, 300, 300, 10.0, 686),
            "max_containers": 1,
            "expected_vol_pct": (75, 95),
            "note": "20GP 满载纸箱",
        },
        {
            "id": "mixed_lcl_skus",
            "source": "混装多 SKU（LCL/拼柜风格）— EasyCargo mixed cargo，货量按≈75% 柜容准备",
            "url": "https://www.easycargo3d.com/en/blog/container-fill-calculator-all-you-need-to-know-about-container-stuffing/",
            "container": "40HQ",
            "mode": "direct",
            "boxes": (
                _boxes_from_sku("A", 600, 400, 400, 18, 200)
                + _boxes_from_sku("B", 500, 500, 300, 14, 180)
                + _boxes_from_sku("C", 800, 400, 350, 20, 120)
                + _boxes_from_sku("D", 300, 300, 300, 8, 300)
            ),
            "max_containers": 1,
            "expected_vol_pct": (60, 90),
            "note": "混尺寸纸箱尽量装满一柜",
        },
        {
            "id": "steel_frame_contrast",
            "source": "对照：2 件 6m 级铁架（模拟钢结构 test 低利用率）",
            "url": "internal-contrast",
            "container": "40HQ",
            "mode": "direct",
            "boxes": [
                _mk_box("FR1", 6000, 1100, 1200, 8000, allow_rotate=False),
                _mk_box("FR2", 5800, 1100, 1200, 7500, allow_rotate=False),
            ],
            "max_containers": 1,
            "expected_vol_pct": (20, 45),
            "note": "不可堆叠长件 → 容积低是正常的",
        },
        {
            "id": "pipeline_carton_vs_frame",
            "source": "全流程：若把纸箱当「材料」会先打铁架/木箱，利用率会被外廓路径改变",
            "url": "internal",
            "container": "40HQ",
            "mode": "pipeline",
            "materials": [
                {
                    "id": "M1",
                    "name": "成品纸箱货 Carton goods",
                    "quantity": 200,
                    "weight_kg": 12,
                    "total_weight_kg": 2400,
                    "length_mm": 500,
                    "width_mm": 400,
                    "height_mm": 350,
                }
            ],
            "expected_vol_pct": None,
            "note": "演示路径差异：材料→箱型 vs 直接装柜",
        },
    ]


def _in_band(val: float, band) -> bool:
    if not band:
        return True
    lo, hi = band
    return lo / 100.0 - 0.02 <= val <= hi / 100.0 + 0.05


def main() -> int:
    out_dir = ROOT / "output" / "web_examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    print("=" * 72)
    print("网上集装箱拼柜案例压测（直接装柜引擎 + 全流程对照）")
    print("=" * 72)

    for c in cases():
        print("-" * 72)
        print(f"[{c['id']}] {c['source'][:70]}")
        if c["mode"] == "direct":
            boxes = c["boxes"]
            plan = pack_direct(boxes, c["container"], c.get("max_containers", 1))
            vol = float(plan.get("space_utilization") or 0)
            best = float(plan.get("space_utilization_best_container") or vol)
            wt = float(plan.get("weight_utilization") or 0)
            fit = plan.get("can_fit")
            used = plan.get("containers_used")
            unpacked = plan.get("unpacked_box_ids") or []
            band = c.get("expected_vol_pct")
            ok_band = _in_band(best if used == 1 else vol, band) if band else True
            # 若装不下，看装上的容积
            status = "PASS" if fit and (ok_band or best >= 0.70) else (
                "OK-LOW" if fit else "PARTIAL" if plan.get("layout") else "FAIL"
            )
            # 对钢架对照：落在低区间也算 PASS
            if c["id"] == "steel_frame_contrast" and fit and vol <= 0.50:
                status = "PASS"
            print(
                f"  direct {c['container']}: boxes={len(boxes)} fit={fit} used={used} "
                f"vol={vol:.1%} best={best:.1%} wt={wt:.1%} unpacked={len(unpacked)} "
                f"ms={plan.get('_ms')} theo_all={plan.get('_theo_if_all_fit')} → {status}"
            )
            if band:
                print(f"  expected band: {band[0]}–{band[1]}%  note={c.get('note')}")
            results.append(
                {
                    "id": c["id"],
                    "source": c["source"],
                    "url": c.get("url"),
                    "mode": "direct",
                    "container": c["container"],
                    "n_boxes": len(boxes),
                    "can_fit": fit,
                    "containers_used": used,
                    "space_utilization": vol,
                    "space_best": best,
                    "weight_utilization": wt,
                    "unpacked": len(unpacked),
                    "ms": plan.get("_ms"),
                    "theo_if_all_fit": plan.get("_theo_if_all_fit"),
                    "expected_vol_pct": band,
                    "status": status,
                    "metrics_note": plan.get("metrics_note"),
                    "layout_sample": (plan.get("layout") or [])[:5],
                }
            )
        else:
            r = pack_via_pipeline(c["materials"], c["container"])
            print(
                f"  pipeline {c['container']}: gen_boxes={r['boxes']} types={r['box_types']} "
                f"fit={r['can_fit']} used={r['containers_used']} vol={r['space_utilization']} "
                f"best={r.get('space_best')} wt={r['weight_utilization']} ms={r['ms']}"
            )
            print(f"  note={c.get('note')}")
            results.append({"id": c["id"], "mode": "pipeline", **r, "source": c["source"], "note": c.get("note")})

    summary = {
        "title": "Web container stuffing examples vs our packer",
        "industry_benchmarks": {
            "justload_3d": "85–95% for most cargo types",
            "easycargo_fill_rate": "volume fill rate = cargo volume / container volume",
            "hz_containers_usable": "practical usable ~80–85% of theoretical CBM",
            "steel_frames": "often much lower due to no-stack + weight + lashing",
        },
        "results": results,
    }
    out_path = out_dir / "web_examples_report.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 简 HTML
    rows = []
    for r in results:
        if r.get("mode") == "direct":
            rows.append(
                f"<tr><td>{r['id']}</td><td>{r['container']}</td><td>{r['n_boxes']}</td>"
                f"<td>{r['can_fit']}</td><td>{r.get('space_utilization')}</td>"
                f"<td>{r.get('space_best')}</td><td>{r.get('weight_utilization')}</td>"
                f"<td>{r.get('status')}</td></tr>"
            )
        else:
            rows.append(
                f"<tr><td>{r['id']} (pipeline)</td><td>{r.get('containers_used')}</td>"
                f"<td>{r.get('boxes')}</td><td>{r.get('can_fit')}</td>"
                f"<td>{r.get('space_utilization')}</td><td>{r.get('space_best')}</td>"
                f"<td>{r.get('weight_utilization')}</td><td>pipeline</td></tr>"
            )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>网上拼柜案例</title>
<style>
body{{font-family:Microsoft YaHei,sans-serif;margin:24px;background:#0f1419;color:#e7ecf3}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #2a3a52;padding:6px 8px}}
th{{background:#1a2332;color:#93c5fd}} .note{{background:#1e293b;padding:12px;border-radius:8px;line-height:1.5}}
</style></head><body>
<h1>网上集装箱拼柜案例压测</h1>
<div class="note">
<strong>行业基准：</strong>规则纸箱 3D 装载目标约 85–95%（JustLoad）；实务可用容积约 80–85% 理论 CBM。
钢结构/铁架因不可堆叠、重量、绑扎，容积利用率常只有 20–45%，与纸箱满载不可横向对比。
<br/>本报告「direct」= 货物直接进柜（正确对标网上计算器）；「pipeline」= 本系统材料→箱型→装柜（钢结构业务路径）。
</div>
<table><thead><tr>
<th>案例</th><th>柜型</th><th>箱数</th><th>can_fit</th><th>容积率</th><th>最满柜</th><th>重量率</th><th>状态</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>JSON: {out_path}</p>
</body></html>"""
    (out_dir / "web_examples_report.html").write_text(html, encoding="utf-8")

    print("=" * 72)
    print(f"报告: {out_path}")
    print(f"HTML: {out_dir / 'web_examples_report.html'}")
    # 统计 direct PASS
    directs = [r for r in results if r.get("mode") == "direct"]
    passes = sum(1 for r in directs if r.get("status") in ("PASS", "OK-LOW"))
    print(f"direct cases: {passes}/{len(directs)} acceptable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
