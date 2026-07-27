#!/usr/bin/env python3
"""
Material_Summary 送工地：分别估 VMU1/2/3/4 订柜 N0 + 3D（booking 路径）。
可选 --agents：对某一批用 9 智能体跑通（材料注入→结构→成箱→确认→规划→装载…）。

用法:
  python scripts/run_vmu_all_site_pack.py
  python scripts/run_vmu_all_site_pack.py --agents VMU1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 复用 site-only 成箱逻辑
import scripts.run_vmu1_site_only as site  # type: ignore

OUT = ROOT / "output" / "vmu_all_site"
VMU_TAGS = ("VMU1", "VMU2", "VMU3", "VMU4")


def batch_tag(row: Dict[str, Any]) -> str:
    text = (
        site._s(row.get("施工批次"))
        + " "
        + site._s(row.get("项目描述"))
        + " "
        + site._s(row.get("訂貨單/加工圖號"))
    ).upper()
    # POR 号最可靠：REDACTED-CODE-VMU-0001-...
    for i, tag in enumerate(VMU_TAGS, 1):
        if f"VMU-000{i}" in text or f"VMU000{i}" in text.replace("-", ""):
            return tag
    if "REDACTED-CODE" in text or "VMU-01" in text:
        return "VMU1"
    if "VMU02" in text:
        return "VMU2"
    if "VMU03" in text:
        return "VMU3"
    if "VMU04" in text:
        return "VMU4"
    return "OTHER"


def to_materials_for_tag(
    rows: List[Dict[str, Any]], tag: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """过滤指定 VMU 批次后走与 site-only 相同的当量成箱。"""
    # 临时劫持 is_vmu1
    orig = site.is_vmu1

    def _match(row: Dict[str, Any]) -> bool:
        return batch_tag(row) == tag

    site.is_vmu1 = _match  # type: ignore
    try:
        mats, skipped = site.to_materials(rows)
    finally:
        site.is_vmu1 = orig  # type: ignore
    return mats, skipped


def pack_one(tag: str, mats: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not mats:
        return {
            "tag": tag,
            "empty": True,
            "materials_lines": 0,
            "net_kg": 0,
            "booking": {},
            "snapshot": {},
        }
    best, ms, n0 = site.run_pack(mats, "40HQ")
    net = sum(float(m.get("total_weight_kg") or 0) for m in mats)
    return {
        "tag": tag,
        "empty": False,
        "materials_lines": len(mats),
        "qty_units": sum(int(m.get("quantity") or 1) for m in mats),
        "net_kg": round(net, 1),
        "by_group": dict(Counter(m.get("spec") for m in mats)),
        "by_por": dict(Counter(m.get("part_no") for m in mats)),
        "ms": ms,
        "booking": (best or {}).get("booking") or {},
        "snapshot": (best or {}).get("snapshot") or {},
        "n0": n0,
        "pack_path": "booking+bin3d (site.run_pack)",
        "used_agents": False,
    }


def run_nine_agents(mats: List[Dict[str, Any]], tag: str) -> Dict[str, Any]:
    """9 智能体：材料注入 → … → finalize（auto confirm，自主定柜）。"""
    from packing_assistant.harness import apply_user_confirmation, make_initial_state
    from packing_assistant.agents import (
        agent_box_scheme,
        agent_evaluator,
        agent_finalize,
        agent_loader,
        agent_material_parser,
        agent_orchestrator,
        agent_planner,
        agent_present_team_a,
        agent_risk_compliance,
        agent_structure,
        agent_visualizer,
    )

    # 控制规模：最多 80 行材料（当量箱）以免过久
    mats_use = mats[:80]
    state = make_initial_state(
        user_input=f"{tag} 送工地剩余 9智能体 自主定柜 标准箱混装",
        materials=mats_use,
        container_type="40HQ",
        enable_auto_confirm=True,
        max_containers=0,
        session_id=f"vmu-site-nine-{tag.lower()}",
    )
    state["packing_options"] = {
        "standard_boxes": True,
        "mix_mode": True,
        "max_box_net_kg": 2000,
    }
    agents = [
        ("orchestrator", agent_orchestrator),
        ("material_parser", agent_material_parser),
        ("structure", agent_structure),
        ("box_scheme", agent_box_scheme),
        ("present_team_a", agent_present_team_a),
        ("planner", agent_planner),
        ("loader", agent_loader),
        ("evaluator", agent_evaluator),
        ("risk_compliance", agent_risk_compliance),
        ("visualizer", agent_visualizer),
        ("finalize", agent_finalize),
    ]
    steps = []
    t0 = time.time()
    for name, fn in agents:
        upd = fn(state) or {}
        for k, v in upd.items():
            if k in ("messages", "traces", "errors", "validation_warnings") and isinstance(
                v, list
            ):
                state[k] = list(state.get(k) or []) + v
            else:
                state[k] = v
        if name == "present_team_a":
            state = apply_user_confirmation(
                state, action="confirm", container_type="40HQ", max_containers=0
            )
        last = ""
        for m in reversed(state.get("messages") or []):
            if m.get("content"):
                last = str(m["content"])
                break
        steps.append({"agent": name, "message": last[:300]})
        print(f"  [{name}] {last[:100]}")

    plan = state.get("container_plan") or {}
    booking = state.get("booking") or plan.get("booking") or {}
    return {
        "tag": tag,
        "used_agents": True,
        "agents": [a[0] for a in agents],
        "materials_fed": len(mats_use),
        "materials_total": len(mats),
        "boxes": len(state.get("boxes") or []),
        "n0": booking.get("n0") or plan.get("n0"),
        "containers_used": plan.get("containers_used"),
        "can_fit": plan.get("can_fit"),
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "evaluation": (state.get("evaluation") or {}).get("score"),
        "risk_decision": (state.get("risk_report") or {}).get("decision"),
        "ms": int((time.time() - t0) * 1000),
        "steps": steps,
        "final_preview": (state.get("final_response") or "")[:500],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--agents",
        default="",
        help="对指定批次跑 9 智能体，如 VMU1；空=只跑 booking",
    )
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if not site.SITE_XLSX.exists():
        print("MISSING", site.SITE_XLSX)
        return 1

    rows = site.load_site_rows(site.SITE_XLSX)
    print(f"loaded rows={len(rows)} from {site.SITE_XLSX.name}")

    report: Dict[str, Any] = {
        "source": str(site.SITE_XLSX),
        "batches": {},
        "note": "订柜 N0=booking；3D=outer can_fit；agents 仅在 --agents 时启用",
    }
    summary_rows = []

    for tag in VMU_TAGS:
        mats, skipped = to_materials_for_tag(rows, tag)
        print(f"\n=== {tag} materials={len(mats)} skipped={len(skipped)} ===")
        rec = pack_one(tag, mats)
        report["batches"][tag] = rec
        book = rec.get("booking") or {}
        snap = rec.get("snapshot") or {}
        summary_rows.append(
            {
                "tag": tag,
                "lines": rec.get("materials_lines"),
                "net_kg": rec.get("net_kg"),
                "n0": book.get("n0") or rec.get("n0"),
                "n_wt": book.get("containers_by_weight"),
                "n_vol": book.get("containers_by_volume"),
                "bind": book.get("binding_constraint"),
                "used_3d": snap.get("containers_used"),
                "can_fit": snap.get("can_fit"),
                "book_u": snap.get("booking_volume_util"),
                "outer_u": snap.get("space"),
                "weight_u": snap.get("weight"),
                "agents": False,
            }
        )
        print(
            f"  N0={book.get('n0')} wt={book.get('containers_by_weight')} "
            f"vol={book.get('containers_by_volume')} bind={book.get('binding_constraint')} "
            f"3D_used={snap.get('containers_used')} can_fit={snap.get('can_fit')}"
        )

    agent_tag = (args.agents or "").strip().upper()
    if agent_tag in VMU_TAGS:
        mats, _ = to_materials_for_tag(rows, agent_tag)
        print(f"\n=== 9-AGENTS on {agent_tag} (up to 80 lines) ===")
        try:
            nine = run_nine_agents(mats, agent_tag)
            report["nine_agents"] = nine
            summary_rows.append(
                {
                    "tag": f"{agent_tag}+9agents",
                    "lines": nine.get("materials_fed"),
                    "net_kg": "-",
                    "n0": nine.get("n0"),
                    "n_wt": "-",
                    "n_vol": "-",
                    "bind": "-",
                    "used_3d": nine.get("containers_used"),
                    "can_fit": nine.get("can_fit"),
                    "book_u": nine.get("booking_volume_utilization"),
                    "outer_u": nine.get("outer_space_utilization"),
                    "weight_u": nine.get("weight_utilization"),
                    "agents": True,
                }
            )
            outj = OUT / f"agent_sequence_9_{agent_tag.lower()}.json"
            outj.write_text(json.dumps(nine, ensure_ascii=False, indent=2), encoding="utf-8")
            print("WROTE", outj)
        except Exception as e:
            report["nine_agents_error"] = str(e)
            print("9-agents FAILED", e)

    out_all = OUT / "vmu_all_site_pack.json"
    out_all.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nWROTE", out_all)

    # markdown 对照表
    md = [
        "# VMU 送工地装柜对照（自主定柜）",
        "",
        f"数据源：`{site.SITE_XLSX.name}`",
        "",
        "## 是否用了 Agent？",
        "",
        "| 路径 | 是否 9 智能体 | 说明 |",
        "|------|:------------:|------|",
        "| `run_vmu_all_site_pack` / `run_vmu1_site_only` | 否 | 当量成箱 + **booking 订柜** + bin3d |",
        "| `--agents VMUx` | **是** | 主控→材料→结构→装箱→确认→规划→装载→评估→风险→出图→finalize |",
        "| `run_nine_por_vmu_real`（历史） | 是 | POR/VMU1 提料尺寸+FAC 估算 |",
        "",
        "## 各批次订柜结果（booking 路径）",
        "",
        "| 批次 | 当量箱行 | 净重kg | 订柜N0 | 重量柜 | 体积柜 | 绑定 | 3D用柜 | can_fit | 订柜有效体积率 | 外廓摆柜率 | 重量率 |",
        "|------|--------:|-------:|------:|------:|------:|------|-------:|--------:|---------------:|----------:|-------:|",
    ]
    for r in summary_rows:
        if r.get("agents"):
            continue
        md.append(
            f"| {r['tag']} | {r['lines']} | {r['net_kg']} | **{r['n0']}** | {r['n_wt']} | {r['n_vol']} | "
            f"{r['bind']} | {r['used_3d']} | {r['can_fit']} | {r['book_u']} | {r['outer_u']} | {r['weight_u']} |"
        )
    if any(r.get("agents") for r in summary_rows):
        md.extend(["", "## 9 智能体结果", ""])
        for r in summary_rows:
            if not r.get("agents"):
                continue
            md.append(
                f"- **{r['tag']}**: N0={r['n0']} 3D用柜={r['used_3d']} can_fit={r['can_fit']} "
                f"book_u={r['book_u']} outer_u={r['outer_u']} weight_u={r['weight_u']}"
            )
    md.extend(
        [
            "",
            "## 口径",
            "",
            "- **订柜 N0**：给领导订舱（重量 + pack_effective）",
            "- **3D 用柜**：当量外廓 can_fit 上界",
            "- 禁止写死 2 柜；各批次由算法自主决定",
            "",
            f"产物：`{out_all}`",
        ]
    )
    mdp = OUT / "VMU_送工地_各批次对照.md"
    mdp.write_text("\n".join(md), encoding="utf-8")
    print("WROTE", mdp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
