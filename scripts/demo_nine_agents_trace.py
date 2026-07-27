#!/usr/bin/env python3
"""
证明「Agent 在干活」：逐步跑 9 智能体，打印每个节点输出摘要。

与 demo_vmu1_site（纯 booking 脚本）对照用。

  python scripts/demo_nine_agents_trace.py
  python scripts/demo_nine_agents_trace.py --via-api   # 需 uvicorn :8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def demo_materials() -> List[Dict[str, Any]]:
    """小票材料：足够看出成箱→N0→3D→风险。"""
    return [
        {
            "id": "M1",
            "name": "镀锌钢通",
            "spec": "13—铁件",
            "quantity": 12,
            "weight_kg": 45,
            "total_weight_kg": 540,
            "length_mm": 4200,
            "width_mm": 120,
            "height_mm": 120,
        },
        {
            "id": "M2",
            "name": "短支撑",
            "spec": "13—铁件",
            "quantity": 20,
            "weight_kg": 12,
            "total_weight_kg": 240,
            "length_mm": 1500,
            "width_mm": 100,
            "height_mm": 100,
        },
        {
            "id": "M3",
            "name": "五金",
            "spec": "23—紧固件/螺丝",
            "quantity": 200,
            "weight_kg": 0.05,
            "total_weight_kg": 10,
            "length_mm": 50,
            "width_mm": 30,
            "height_mm": 20,
        },
    ]


def run_local_trace() -> Dict[str, Any]:
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

    agents = [
        ("1 主控", "orchestrator", agent_orchestrator),
        ("2 材料", "material_parser", agent_material_parser),
        ("3 结构", "structure", agent_structure),
        ("4 装箱", "box_scheme", agent_box_scheme),
        ("闸门", "present_team_a", agent_present_team_a),
        ("5 规划", "planner", agent_planner),
        ("6 装载", "loader", agent_loader),
        ("7 评估", "evaluator", agent_evaluator),
        ("8 风险", "risk_compliance", agent_risk_compliance),
        ("9 出图", "visualizer", agent_visualizer),
        ("收口", "finalize", agent_finalize),
    ]

    state = make_initial_state(
        user_input="Agent trace 演示：标准箱混装，自主定柜",
        materials=demo_materials(),
        container_type="40HQ",
        enable_auto_confirm=True,
        max_containers=0,
        session_id="agent-trace-demo",
    )
    state["packing_options"] = {
        "standard_boxes": True,
        "mix_mode": True,
        "max_box_net_kg": 2000,
    }

    steps = []
    print("=" * 64)
    print(" 9 智能体逐步输出（本地 harness，非 booking 捷径）")
    print("=" * 64)

    for title, node, fn in agents:
        upd = fn(state) or {}
        for k, v in upd.items():
            if k in ("messages", "traces", "errors", "validation_warnings") and isinstance(
                v, list
            ):
                state[k] = list(state.get(k) or []) + v
            else:
                state[k] = v

        if node == "present_team_a":
            state = apply_user_confirmation(
                state, action="confirm", container_type="40HQ", max_containers=0
            )

        last = ""
        for m in reversed(state.get("messages") or []):
            if m.get("content"):
                last = str(m["content"])
                break

        # 每步关键状态
        extra = ""
        if node == "box_scheme":
            extra = f" | boxes={len(state.get('boxes') or [])}"
        if node == "planner":
            book = (state.get("plan") or {}).get("booking") or state.get("booking") or {}
            extra = f" | N0={book.get('n0')} bind={book.get('binding_constraint')}"
        if node == "loader":
            p = state.get("container_plan") or {}
            extra = (
                f" | used={p.get('containers_used')} can_fit={p.get('can_fit')} "
                f"book_u={p.get('booking_volume_utilization')} outer_u={p.get('outer_space_utilization') or p.get('space_utilization')}"
            )
        if node == "risk_compliance":
            rr = state.get("risk_report") or {}
            extra = f" | decision={rr.get('decision')} level={rr.get('level')}"

        print(f"\n### {title} [{node}]{extra}")
        print((last or "(no message)")[:280])
        steps.append({"title": title, "node": node, "message": last[:500], "extra": extra})

    plan = state.get("container_plan") or {}
    book = state.get("booking") or plan.get("booking") or {}
    summary = {
        "path": "9-agents",
        "boxes": len(state.get("boxes") or []),
        "n0": book.get("n0") or plan.get("n0"),
        "containers_used": plan.get("containers_used"),
        "can_fit": plan.get("can_fit"),
        "booking_volume_utilization": plan.get("booking_volume_utilization"),
        "outer_space_utilization": plan.get("outer_space_utilization")
        or plan.get("space_utilization"),
        "weight_utilization": plan.get("weight_utilization"),
        "risk": (state.get("risk_report") or {}).get("decision"),
        "phase": state.get("phase"),
    }
    print("\n" + "=" * 64)
    print(" SUMMARY", json.dumps(summary, ensure_ascii=False))
    print("=" * 64)
    print(
        "\n说明：N0/can_fit 仍由 tools(booking/bin3d) 计算；"
        "Agent 负责分工、闸门、结构、风险裁决与过程可解释。"
    )
    out = ROOT / "output" / "agent_trace_demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"summary": summary, "steps": steps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("WROTE", out)
    return {"summary": summary, "steps": steps}


def run_via_api() -> Dict[str, Any]:
    import urllib.request

    base = "http://127.0.0.1:8000"
    # team-a
    body = json.dumps(
        {
            "session_id": "api-trace",
            "user_input": "API Agent 演示",
            "materials": demo_materials(),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        base + "/api/team-a",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        a = json.loads(resp.read().decode("utf-8"))
    print("API team-a phase=", a.get("phase"), "boxes=", len(a.get("boxes") or []))

    body2 = json.dumps(
        {
            "session_id": "api-trace",
            "action": "confirm",
            "container_type": "40HQ",
            "max_containers": 0,
        }
    ).encode("utf-8")
    req2 = urllib.request.Request(
        base + "/api/confirm",
        data=body2,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req2, timeout=180) as resp:
        b = json.loads(resp.read().decode("utf-8"))
    print(
        "API confirm phase=",
        b.get("phase"),
        "can_fit=",
        (b.get("container_plan") or {}).get("can_fit"),
        "used=",
        (b.get("container_plan") or {}).get("containers_used"),
    )
    return {"team_a": a, "team_b": b}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--via-api", action="store_true", help="走 gateway HTTP（需先起服务）")
    args = ap.parse_args()
    if args.via_api:
        try:
            run_via_api()
        except Exception as e:
            print("API 失败（是否已 uvicorn gateway.app:app --port 8000？）:", e)
            print("回退本地 trace…")
            run_local_trace()
            return 1
        return 0
    run_local_trace()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
