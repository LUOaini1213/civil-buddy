#!/usr/bin/env python3
"""
Material_Summary → 估算材料 → 9 智能体逐步跑通（主控…可视化…finalize）。

用法:
  python scripts/dump_nine_agents_material_summary.py
  python scripts/dump_nine_agents_material_summary.py --xlsx "C:/.../Material_Summary (3).xlsx"
  python scripts/dump_nine_agents_material_summary.py --container 40HQ --max-containers 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
from packing_assistant.harness import apply_user_confirmation, make_initial_state

# 同目录材料转换（Material_Summary → materials[]）
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "run_material_summary_pack", ROOT / "scripts" / "run_material_summary_pack.py"
)
_msp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_msp)
to_materials = _msp.to_materials
save_materials_xlsx = _msp.save_materials_xlsx


def _apply_update(state: dict, upd: dict) -> dict:
    for k, v in (upd or {}).items():
        if k in ("messages", "traces", "errors", "validation_warnings") and isinstance(
            v, list
        ):
            state[k] = list(state.get(k) or []) + v
        else:
            state[k] = v
    return state


def run_nine(
    materials: list,
    *,
    container_type: str = "40HQ",
    max_containers: int = 6,
    user_input: str = "",
    max_box_net_kg: float = 3200.0,
    revision_mode: bool = False,
    revision_round: int = 0,
) -> dict:
    agents = [
        (1, "主控智能体", "orchestrator", agent_orchestrator),
        (2, "材料解析智能体", "material_parser", agent_material_parser),
        (3, "结构计算智能体", "structure", agent_structure),
        (4, "装箱方案智能体", "box_scheme", agent_box_scheme),
        (0, "确认闸门 present_team_a", "present_team_a", agent_present_team_a),
        (5, "规划智能体", "planner", agent_planner),
        (6, "装载执行智能体", "loader", agent_loader),
        (7, "评估优化智能体", "evaluator", agent_evaluator),
        (8, "风险合规智能体", "risk_compliance", agent_risk_compliance),
        (9, "可视化智能体", "visualizer", agent_visualizer),
        (0, "主控汇总 finalize", "finalize", agent_finalize),
    ]

    state = make_initial_state(
        user_input=user_input
        or "Material_Summary 8月业务 9智能体测试；容积=箱体外廓实心长方体",
        materials=materials,
        container_type=container_type,
        enable_auto_confirm=True,
        max_containers=max_containers,
        session_id=f"nine-material-summary-aug-r{revision_round}",
    )
    state["packing_options"] = {
        "max_box_net_kg": max_box_net_kg,
        "revision_mode": revision_mode,
    }
    if revision_mode:
        state["revision"] = {
            "active": True,
            "round": revision_round,
            "max_box_net_kg": max_box_net_kg,
            "reason": "structure_or_compliance_reject",
        }

    steps = []
    for num, name, node, fn in agents:
        upd = fn(state) or {}
        state = _apply_update(state, upd)

        if node == "present_team_a":
            # HITL：本测试强制使用调用方指定柜型（模拟用户确认，不盲从主控误推 20GP）
            state = apply_user_confirmation(
                state,
                action="confirm",
                container_type=container_type,
                max_containers=max_containers,
            )

        last_msg = ""
        for m in reversed(state.get("messages") or []):
            c = str(m.get("content") or "")
            if c:
                last_msg = c
                break

        step: dict = {
            "n": num,
            "name": name,
            "node": node,
            "phase": state.get("phase"),
            "message": last_msg,
        }

        if node == "orchestrator":
            step["orchestrator"] = state.get("orchestrator")
            step["container_type"] = state.get("container_type")
        if node == "material_parser":
            step["materials"] = [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "q": m.get("quantity"),
                    "L": m.get("length_mm"),
                    "W": m.get("width_mm"),
                    "H": m.get("height_mm"),
                    "wt": m.get("weight_kg"),
                    "total": m.get("total_weight_kg"),
                }
                for m in (state.get("materials") or [])
            ]
            step["materials_summary"] = state.get("materials_summary")
        if node == "structure":
            step["structure_notes"] = state.get("structure_notes")
            step["structure_constraints"] = state.get("structure_constraints")
            step["global_advice"] = state.get("global_advice")
        if node == "box_scheme":
            boxes_out = []
            for b in state.get("boxes") or []:
                o = b.get("outer_size_mm") or {}
                solid = (
                    float(o.get("length") or 0)
                    * float(o.get("width") or 0)
                    * float(o.get("height") or 0)
                )
                boxes_out.append(
                    {
                        "box_id": b.get("box_id"),
                        "box_type": b.get("box_type"),
                        "base_box_type": b.get("base_box_type"),
                        "outer_size_mm": o,
                        "solid_volume_m3": round(solid / 1e9, 4),
                        "net_kg": b.get("net_weight_kg"),
                        "gross_kg": b.get("gross_weight_kg"),
                        "structure_conclusion": b.get("structure_conclusion"),
                        "special_attributes": b.get("special_attributes"),
                        "content": b.get("content") or b.get("contents"),
                    }
                )
            step["boxes"] = boxes_out
            step["team_a_summary"] = state.get("team_a_summary")
        if node == "present_team_a":
            step["display_markdown"] = state.get("display_markdown")
            step["user_action"] = state.get("user_action")
            step["packing_plan_id"] = state.get("packing_plan_id")
            step["container_type_confirmed"] = state.get("container_type")
            step["max_containers"] = state.get("max_containers")
        if node == "planner":
            step["plan"] = state.get("plan")
        if node == "loader":
            plan = state.get("container_plan") or {}
            step["container_plan"] = {
                k: plan.get(k)
                for k in (
                    "can_fit",
                    "containers_used",
                    "space_utilization",
                    "space_utilization_best_container",
                    "floor_utilization_avg",
                    "weight_utilization",
                    "engine",
                    "message",
                    "metrics_note",
                    "volume_basis",
                    "cargo_solid_volume_m3",
                    "container_inner_volume_m3",
                    "layout",
                    "unpacked_box_ids",
                    "per_container",
                )
            }
        if node == "evaluator":
            step["evaluation"] = state.get("evaluation")
        if node == "risk_compliance":
            rr = state.get("risk_report") or {}
            step["risk_report"] = {
                k: rr.get(k)
                for k in (
                    "passed",
                    "compliance_score",
                    "level",
                    "decision",
                    "need_revision",
                    "reject_to",
                    "reject_reason",
                    "risks",
                    "blockers",
                    "explanation",
                    "cog",
                )
            }
        if node == "visualizer":
            step["views_keys"] = list((state.get("views") or {}).keys())
            img = state.get("image_data") or {}
            step["image_paths"] = (
                {k: (v or {}).get("path") for k, v in img.items()}
                if isinstance(img, dict)
                else {}
            )
        if node == "finalize":
            step["final_response"] = state.get("final_response")
            step["status"] = state.get("status")
            step["container_type"] = state.get("container_type")

        steps.append(step)
        label = f"{num} {name}" if num else name
        print("=" * 72)
        print(f"### {label} [{node}] phase={state.get('phase')}")
        print(last_msg[:1500] if last_msg else "(no message)")
        if node == "box_scheme":
            for b in step.get("boxes") or []:
                print(
                    f"  {b['box_id']} {b['box_type']} outer={b['outer_size_mm']} "
                    f"solid={b['solid_volume_m3']}m3 gross={b['gross_kg']} "
                    f"struct={b['structure_conclusion']}"
                )
        if node == "loader":
            cp = step.get("container_plan") or {}
            print(
                f"  can_fit={cp.get('can_fit')} used={cp.get('containers_used')} "
                f"space={cp.get('space_utilization')} floor={cp.get('floor_utilization_avg')} "
                f"wt={cp.get('weight_utilization')} engine={cp.get('engine')}"
            )
            for pc in cp.get("per_container") or []:
                print(f"  per_container {pc}")
        if node == "evaluator":
            print("  evaluation=", json.dumps(step.get("evaluation"), ensure_ascii=False)[:800])
        if node == "risk_compliance":
            print("  risk=", json.dumps(step.get("risk_report"), ensure_ascii=False)[:1200])
        if node == "visualizer":
            print("  images=", step.get("image_paths"))
        if node == "finalize":
            print("--- FINAL ---")
            print(step.get("final_response"))

    snap = {
        "packing_plan_id": state.get("packing_plan_id"),
        "container_type": state.get("container_type"),
        "phase": state.get("phase"),
        "status": state.get("status"),
        "ship_ok": state.get("ship_ok"),
        "boxes_n": len(state.get("boxes") or []),
        "struct_fail": sum(
            1
            for b in (state.get("boxes") or [])
            if b.get("structure_conclusion") == "不通过"
        ),
        "can_fit": (state.get("container_plan") or {}).get("can_fit"),
        "containers_used": (state.get("container_plan") or {}).get("containers_used"),
        "risk_decision": (state.get("risk_report") or {}).get("decision"),
        "risk_level": (state.get("risk_report") or {}).get("level"),
        "reject_to": (state.get("risk_report") or {}).get("reject_to"),
        "max_box_net_kg": max_box_net_kg,
        "revision_round": revision_round,
    }
    return {"steps": steps, "state_snapshot": snap, "state": state}


def needs_revision(snap: dict) -> bool:
    if snap.get("risk_decision") == "REJECT" and snap.get("reject_to") == "box_scheme":
        return True
    if snap.get("status") == "rejected" and (snap.get("struct_fail") or 0) > 0:
        return True
    return False


def needs_more_containers(snap: dict) -> bool:
    return (not snap.get("can_fit")) and (snap.get("struct_fail") or 0) == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--xlsx",
        default=r"C:\Users\wenjie.luo\Downloads\Material_Summary (3).xlsx",
    )
    ap.add_argument("--container", default="40HQ")
    ap.add_argument("--max-containers", type=int, default=6)
    ap.add_argument("--max-revision", type=int, default=2, help="结构打回后最多改箱轮数")
    ap.add_argument("--max-box-net-kg", type=float, default=3200.0)
    args = ap.parse_args()

    src = Path(args.xlsx)
    if not src.exists():
        print("文件不存在:", src)
        return 1

    mats, skipped = to_materials(src)
    out_dir = ROOT / "output" / "aug_material_summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_materials_xlsx(mats, out_dir / "materials_estimated.xlsx")

    print(f"源表: {src}")
    print(f"材料行: {len(mats)} | 跳过: {len(skipped)}")
    print(
        f"柜型: {args.container} | max_containers={args.max_containers} | "
        f"max_box_net={args.max_box_net_kg} | max_revision={args.max_revision}"
    )

    all_rounds = []
    cap = float(args.max_box_net_kg)
    mc = int(args.max_containers)
    final_result = None
    rnd = 0
    max_loops = args.max_revision + 6  # 改箱 + 加柜
    while rnd <= max_loops:
        rev_mode = needs_revision(all_rounds[-1]["state_snapshot"]) if all_rounds else False
        # 仅结构打回才收紧净重；装不下则加柜
        if all_rounds:
            prev = all_rounds[-1]["state_snapshot"]
            if needs_revision(prev):
                cap = max(1200.0, min(cap * 0.75, 2500.0 if rnd == 1 else cap * 0.75))
                rev_mode = True
                print("=" * 72)
                print(f"### 改箱重跑 round={rnd} max_box_net_kg={cap:.0f}")
            elif needs_more_containers(prev):
                mc = min(mc + 4, 40)
                rev_mode = False
                print("=" * 72)
                print(f"### 加柜重跑 round={rnd} max_containers={mc}")
            else:
                break
        else:
            print("开始 9 智能体逐步执行…")

        result = run_nine(
            mats,
            container_type=args.container,
            max_containers=mc,
            user_input=(
                f"Material_Summary 9智能体测试 | {src.name} | r{rnd} | "
                f"max_net={cap:.0f} | mc={mc}"
            ),
            max_box_net_kg=cap,
            revision_mode=rev_mode,
            revision_round=rnd,
        )
        slim = {
            "steps": result["steps"],
            "state_snapshot": result["state_snapshot"],
        }
        all_rounds.append(slim)
        final_result = result
        snap = result["state_snapshot"]
        print("ROUND SNAPSHOT", json.dumps(snap, ensure_ascii=False))

        if snap.get("ship_ok") or (
            snap.get("can_fit")
            and snap.get("risk_decision") in ("PASS", "WARN", None)
            and snap.get("status") == "success"
        ):
            print(f"闭环成功：round={rnd}")
            break
        if not needs_revision(snap) and not needs_more_containers(snap):
            print(f"闭环结束：round={rnd}（无改箱/加柜信号）")
            break
        if rnd >= max_loops:
            print(f"已达最大轮次 {max_loops}，停止")
            break
        rnd += 1

    out_payload = {
        "source": str(src),
        "materials_count": len(mats),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "note": (
            "9智能体逐步调用 + 结构/合规 REJECT 时自动降低 max_box_net_kg 改箱重跑；"
            "材料尺寸为估算"
        ),
        "rounds": all_rounds,
        "final_snapshot": (final_result or {}).get("state_snapshot"),
    }
    out = out_dir / "agent_sequence_9_material_summary.json"
    out.write_text(
        json.dumps(out_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("=" * 72)
    print("WROTE", out)
    print("FINAL", json.dumps(out_payload.get("final_snapshot"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
