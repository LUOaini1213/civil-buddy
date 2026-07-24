#!/usr/bin/env python3
"""
用其它合成/示例用例验证：标准箱库外廓 + 跨长度档混装。

用法:
  python scripts/test_standard_mix_examples.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.adapters import boxes_to_api
from packing_assistant.tools.bin3d import pack_boxes_api
from packing_assistant.tools.packing import run_packing


def _case_mixed_realistic() -> List[Dict[str, Any]]:
    """贴近REDACTED-CLIENT：长短混 + 小件（与 build_steel_test_set.syn_mixed_realistic 一致）。"""

    def M(name, q, w, L, W, H, note=""):
        return {
            "名称": name,
            "数量": q,
            "单重_kg": w,
            "总重_kg": round(w * q, 2),
            "外尺寸_mm": {"长": L, "宽": W, "高": H},
            "备注": note,
            "规格": f"{L}x{W}x{H}",
        }

    return [
        M("镀锌钢通", 60, 45, 2500, 250, 250, "中长"),
        M("镀锌钢通长件", 20, 85, 4200, 250, 250, "4米级"),
        M("幕墙支撑", 15, 70, 3800, 300, 200, "支撑"),
        M("铁垫片", 500, 0.2, 150, 100, 10, "小件"),
        M("短支撑", 40, 18, 800, 150, 150, "短件"),
    ]


def _case_short_frames() -> List[Dict[str, Any]]:
    def M(name, q, w, L, W, H):
        return {
            "名称": name,
            "数量": q,
            "单重_kg": w,
            "总重_kg": round(w * q, 2),
            "外尺寸_mm": {"长": L, "宽": W, "高": H},
            "备注": "短件",
        }

    return [
        M("镀锌短钢通", 40, 25, 900, 120, 120),
        M("连接板", 80, 8, 400, 300, 20),
        M("角码", 120, 2.5, 200, 150, 80),
        M("镀锌圆通短料", 30, 12, 1100, 80, 80),
    ]


def _case_long_6m() -> List[Dict[str, Any]]:
    def M(name, q, w, L, W, H):
        return {
            "名称": name,
            "数量": q,
            "单重_kg": w,
            "总重_kg": round(w * q, 2),
            "外尺寸_mm": {"长": L, "宽": W, "高": H},
            "备注": "超长",
        }

    return [
        M("热镀锌空心铁通6m", 24, 48, 5800, 200, 200),
        M("幕墙支撑钢构件6m", 12, 95, 6000, 250, 180),
        M("长杆件", 8, 60, 5500, 150, 150),
    ]


def _case_web_small_cartons() -> List[Dict[str, Any]]:
    """小纸箱风格（对照利用率，非钢结构）。"""
    mats = []
    for i in range(12):
        mats.append(
            {
                "名称": f"纸箱{i+1}",
                "数量": 4,
                "单重_kg": 12,
                "总重_kg": 48,
                "外尺寸_mm": {"长": 600, "宽": 400, "高": 350},
                "备注": "小件",
            }
        )
    return mats


def run_one(name: str, mats: List[Dict[str, Any]], **opts) -> Dict[str, Any]:
    r = run_packing(
        mats,
        container_type="40HQ",
        max_box_net_kg=float(opts.get("max_box_net_kg", 1500)),
        standard_boxes=bool(opts.get("standard_boxes", True)),
        mix_mode=bool(opts.get("mix_mode", True)),
        dense_mode=bool(opts.get("dense_mode", False)),
    )
    boxes = r["箱子列表"]
    s = r["结构汇总"]
    api = boxes_to_api(boxes)
    plan = pack_boxes_api(api, container_type="40HQ", max_containers=20)
    # 是否标准外廓：与库对比
    from packing_assistant.tools.packing import STANDARD_BOX_TYPES

    std_hits = 0
    for b in boxes:
        base = b.get("base_box_type") or ""
        o = b.get("外尺寸_mm") or {}
        if base in STANDARD_BOX_TYPES:
            so = STANDARD_BOX_TYPES[base]["外尺寸_mm"]
            if (
                abs(float(o.get("宽") or 0) - float(so["宽"])) < 1
                and abs(float(o.get("高") or 0) - float(so["高"])) < 1
                and (
                    abs(float(o.get("长") or 0) - float(so["长"])) < 1
                    or b.get("customized_outer")
                )
            ):
                std_hits += 1
    # 混装箱：内容含多种名称
    mixed_boxes = 0
    for b in boxes:
        names = {c.get("名称") for c in (b.get("装载内容") or [])}
        if len(names) >= 2:
            mixed_boxes += 1

    out = {
        "case": name,
        "opts": {
            "standard_boxes": opts.get("standard_boxes", True),
            "mix_mode": opts.get("mix_mode", True),
            "dense_mode": opts.get("dense_mode", False),
        },
        "boxes": len(boxes),
        "struct_fail": s.get("不通过", 0),
        "struct_pass": s.get("通过", 0),
        "packing_mode": s.get("packing_mode"),
        "outer_m3": s.get("boxes_outer_volume_m3"),
        "cargo_m3": s.get("cargo_item_volume_m3"),
        "crate_fill": s.get("avg_crate_fill"),
        "type_counts": s.get("standard_box_type_counts"),
        "standard_outer_hits": std_hits,
        "mixed_content_boxes": mixed_boxes,
        "bins": f"{s.get('bins_before_merge')}->{s.get('bins_after_merge')}",
        "containers": plan.get("containers_used"),
        "can_fit": plan.get("can_fit"),
        "space": plan.get("space_utilization"),
        "floor": plan.get("floor_utilization_avg"),
        "weight": plan.get("weight_utilization"),
        "sample_outers": [
            {
                "type": b.get("箱型"),
                "base": b.get("base_box_type"),
                "LWH": b.get("外尺寸_mm"),
                "std": b.get("standard_outer"),
                "concl": b.get("结构结论"),
                "items": [c.get("名称") for c in (b.get("装载内容") or [])[:4]],
            }
            for b in boxes[:4]
        ],
        "ok": bool(
            s.get("不通过", 0) == 0
            and plan.get("can_fit")
            and (not opts.get("standard_boxes", True) or std_hits >= max(1, len(boxes) // 2))
        ),
    }
    return out


def main() -> int:
    cases = [
        ("syn_mixed_realistic", _case_mixed_realistic(), {"max_box_net_kg": 1500}),
        ("syn_short_frames", _case_short_frames(), {"max_box_net_kg": 1200}),
        ("syn_long_6m", _case_long_6m(), {"max_box_net_kg": 800}),
        ("web_small_cartons", _case_web_small_cartons(), {"max_box_net_kg": 2000}),
    ]
    modes = [
        {"standard_boxes": True, "mix_mode": True, "dense_mode": False, "label": "std+mix"},
        {"standard_boxes": True, "mix_mode": False, "dense_mode": False, "label": "std-only"},
        {"standard_boxes": False, "mix_mode": False, "dense_mode": False, "label": "modular"},
    ]

    results = []
    print("=" * 72)
    print("标准箱库外廓 + 跨长度档混装 · 其它例子测试")
    print("=" * 72)
    for cname, mats, base_opts in cases:
        print(f"\n### {cname}  materials={len(mats)}")
        for mode in modes:
            opts = {**base_opts, **mode}
            r = run_one(cname, mats, **opts)
            results.append(r)
            flag = "OK" if r["ok"] else "FAIL"
            print(
                f"  [{flag}] {mode['label']:10s} boxes={r['boxes']:2d} "
                f"fail={r['struct_fail']} cont={r['containers']} "
                f"space={r['space']} fill={r['crate_fill']} "
                f"mixed_boxes={r['mixed_content_boxes']} "
                f"types={r['type_counts']}"
            )
            if not r["ok"]:
                print(f"       sample={r['sample_outers'][:2]}")

    out_dir = ROOT / "output" / "standard_mix_tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {path}")

    # 关键：std+mix 用例应全部结构通过且 can_fit
    critical = [r for r in results if r["opts"].get("standard_boxes") and r["opts"].get("mix_mode")]
    bad = [r for r in critical if not r["ok"]]
    if bad:
        print(f"CRITICAL FAIL: {len(bad)}/{len(critical)}")
        for b in bad:
            print(" ", b["case"], b.get("struct_fail"), b.get("can_fit"), b.get("sample_outers"))
        return 1
    print(f"ALL CRITICAL OK: {len(critical)} cases (standard+mix)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
