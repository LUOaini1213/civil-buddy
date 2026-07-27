#!/usr/bin/env python3
"""跑一次 9 智能体全链路，容积按箱体外廓实心长方体，输出逐步原文。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 加载 .env / deepseek api，便于风险/汇总可选调用 DeepSeek
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass
for name in ("deepseek api.txt", "deepseek_api.txt"):
    kf = ROOT / name
    if kf.exists():
        try:
            key = kf.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
            if key.startswith("sk-"):
                import os

                os.environ.setdefault("DEEPSEEK_API_KEY", key)
                os.environ.setdefault("OPENAI_API_KEY", key)
                os.environ.setdefault("LLM_API_KEY", key)
                os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com")
                os.environ.setdefault("LLM_MODEL", "deepseek-v4-flash")
        except Exception:
            pass
        break

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


def main() -> int:
    materials = [
        {
            "id": "M001",
            "name": "镀锌钢通",
            "quantity": 20,
            "weight_kg": 45,
            "total_weight_kg": 900,
            "length_mm": 2500,
            "width_mm": 250,
            "height_mm": 250,
        },
        {
            "id": "M002",
            "name": "镀锌钢通长件",
            "quantity": 8,
            "weight_kg": 85,
            "total_weight_kg": 680,
            "length_mm": 4200,
            "width_mm": 250,
            "height_mm": 250,
        },
        {
            "id": "M003",
            "name": "幕墙支撑",
            "quantity": 6,
            "weight_kg": 70,
            "total_weight_kg": 420,
            "length_mm": 3800,
            "width_mm": 300,
            "height_mm": 200,
        },
        {
            "id": "M004",
            "name": "铁垫片",
            "quantity": 200,
            "weight_kg": 0.2,
            "total_weight_kg": 40,
            "length_mm": 150,
            "width_mm": 100,
            "height_mm": 10,
        },
        {
            "id": "M005",
            "name": "短支撑",
            "quantity": 15,
            "weight_kg": 18,
            "total_weight_kg": 270,
            "length_mm": 800,
            "width_mm": 150,
            "height_mm": 150,
        },
    ]

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
        user_input="容积按箱体外廓实心长方体；9步原文；标准箱+混装；自主定柜",
        materials=materials,
        container_type="40HQ",
        enable_auto_confirm=True,
        max_containers=0,  # 0=自主定柜，禁止写死目标柜数
        session_id="nine-solid-vol",
    )
    state["packing_options"] = {
        "standard_boxes": True,
        "mix_mode": True,
        "max_box_net_kg": 1500,
    }

    steps = []
    for num, name, node, fn in agents:
        upd = fn(state) or {}
        for k, v in upd.items():
            if k in ("messages", "traces", "errors", "validation_warnings") and isinstance(
                v, list
            ):
                state[k] = list(state.get(k) or []) + v
            else:
                state[k] = v
        if node == "present_team_a":
            # 确认闸门：强制 40HQ + 自主定柜（不写死柜数）；覆盖 auto_confirm 的 20GP 误选
            state = apply_user_confirmation(
                state, action="confirm", container_type="40HQ", max_containers=0
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
                        "crate_fill_ratio": b.get("crate_fill_ratio"),
                        "content_max_length_mm": b.get("content_max_length_mm"),
                    }
                )
            step["boxes"] = boxes_out
            step["team_a_summary"] = state.get("team_a_summary")
        if node == "present_team_a":
            step["display_markdown"] = state.get("display_markdown")
            step["user_action"] = state.get("user_action")
            step["packing_plan_id"] = state.get("packing_plan_id")
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
            solid = 0.0
            for p in plan.get("layout") or []:
                s = p.get("size") or {}
                solid += (
                    float(s.get("dx") or 0)
                    * float(s.get("dy") or 0)
                    * float(s.get("dz") or 0)
                )
            step["verify_solid_m3"] = round(solid / 1e9, 4)
            cont = 12032 * 2352 * 2698
            step["verify_util"] = round(solid / cont, 4)
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
                    "risks",
                    "blockers",
                    "explanation",
                    "cog",
                )
            }
        if node == "visualizer":
            step["views_keys"] = list((state.get("views") or {}).keys())
            img = state.get("image_data") or {}
            paths = {}
            if isinstance(img, dict):
                for k, v in img.items():
                    if isinstance(v, dict):
                        paths[k] = v.get("path")
                    elif isinstance(v, list):
                        paths[k] = [
                            (x or {}).get("path") if isinstance(x, dict) else x
                            for x in v
                        ]
                    else:
                        paths[k] = v
            step["image_paths"] = paths
        if node == "finalize":
            step["final_response"] = state.get("final_response")
            step["status"] = state.get("status")

        steps.append(step)
        label = f"{num} {name}" if num else name
        print("=" * 72)
        print(f"### {label} [{node}] phase={state.get('phase')}")
        print(last_msg)
        if node == "box_scheme":
            for b in step.get("boxes") or []:
                print(
                    f"  {b['box_id']} {b['box_type']} outer={b['outer_size_mm']} "
                    f"solid={b['solid_volume_m3']}m3 gross={b['gross_kg']} "
                    f"struct={b['structure_conclusion']} special={b['special_attributes']}"
                )
                print(f"    content={b['content']}")
        if node == "loader":
            cp = step["container_plan"]
            print(
                f"  volume_basis={cp.get('volume_basis')} "
                f"cargo={cp.get('cargo_solid_volume_m3')}m3 "
                f"cont={cp.get('container_inner_volume_m3')}m3"
            )
            print(
                f"  util={cp.get('space_utilization')} floor={cp.get('floor_utilization_avg')} "
                f"wt={cp.get('weight_utilization')}"
            )
            print(f"  note={cp.get('metrics_note')}")
            print(f"  verify solid={step.get('verify_solid_m3')}m3 util={step.get('verify_util')}")
            for ly in cp.get("layout") or []:
                print(f"  layout {ly}")
        if node == "evaluator":
            print("  evaluation=", json.dumps(step.get("evaluation"), ensure_ascii=False))
        if node == "risk_compliance":
            print("  risk=", json.dumps(step.get("risk_report"), ensure_ascii=False)[:1200])
        if node == "finalize":
            print("--- FINAL ---")
            print(step.get("final_response"))

    out = ROOT / "output" / "agent_sequence_9_solid.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"steps": steps}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("=" * 72)
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
