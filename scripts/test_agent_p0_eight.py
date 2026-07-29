#!/usr/bin/env python3
"""8 条 Agent 改进回归：PackingPlan / HITL / replan / skills / 工单 / VGM / diff / 冒烟。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    fails = []

    # 1 skills
    try:
        from packing_assistant.skills_registry import validate_skills, list_skills

        # docs may be stubbed; modules must import
        r = validate_skills(fail_loud=False)
        if r["missing_modules"]:
            fails.append(f"skills modules: {r['missing_modules']}")
        else:
            print("[OK] skills modules", len(list_skills()))
        if r["missing_docs"]:
            print("[WARN] missing skill docs", r["missing_docs"])
    except Exception as e:
        fails.append(f"skills: {e}")

    # 2 packing plan
    try:
        from packing_assistant.packing_plan import build_packing_plan

        st = {
            "run_id": "test-run",
            "container_plan": {
                "can_fit": True,
                "containers_used": 1,
                "container_type": "40HQ",
                "layout": [{"box_id": "A", "container_no": 1, "position": {"x": 0, "y": 0, "z": 0}, "size": {"dx": 1, "dy": 1, "dz": 1}}],
                "stacking": {"stacked_placements": 0},
                "cog": {"mass_in_mid50_ratio": 0.7, "mid50_ok": True, "balance": "ok"},
            },
            "boxes": [{"box_id": "A", "gross_weight_kg": 100}],
            "evaluation": {"score": 80, "decision": "PASS"},
            "risk_report": {"decision": "PASS", "blockers": []},
            "packing_options": {"prefer_stack": True},
        }
        pp = build_packing_plan(st)
        assert pp.get("schema") == "packing.plan.v1"
        assert pp.get("cog", {}).get("mid50_ok") is True
        print("[OK] packing_plan", pp.get("plan_id"))
    except Exception as e:
        fails.append(f"packing_plan: {e}")

    # 3 hitl gates
    try:
        from packing_assistant.hitl_gates import evaluate_hitl_gates

        g = evaluate_hitl_gates(
            {
                "container_plan": {"can_fit": True, "containers_used": 2, "n0": 1},
                "risk_report": {"blockers": []},
                "packing_options": {"export_strict": True},
                "packing_plan": {"cog": {"mass_in_mid50_ratio": 0.5}},
            }
        )
        assert g.get("require_hitl") is True
        print("[OK] hitl_gates", g.get("summary")[:60])
    except Exception as e:
        fails.append(f"hitl: {e}")

    # 4 replan critic + 出运闭环路由
    try:
        from packing_assistant.agents.replan_critic import agent_replan_critic

        out = agent_replan_critic(
            {
                "evaluation": {"need_replan": True, "decision": "REPLAN"},
                "replan_round": 0,
                "ship_replan_round": 0,
                "container_plan": {
                    "can_fit": True,
                    "cog": {"mass_in_mid50_ratio": 0.4},
                    "layout_quality": {"stackable_floor_only": True},
                },
                "packing_options": {},
                "max_containers": 3,
            }
        )
        prop = out.get("replan_proposal") or {}
        assert prop.get("stop") is False
        assert out.get("packing_options")
        print("[OK] replan_critic", prop.get("reasons"))

        # 结构 → box_scheme
        o2 = agent_replan_critic(
            {
                "replan_round": 0,
                "ship_replan_round": 0,
                "evaluation": {"structure_fail_box_ids": ["X"]},
                "risk_report": {
                    "decision": "REJECT",
                    "reject_to": "box_scheme",
                    "blockers": ["X 成箱结构校核不通过"],
                    "auto_replanable": True,
                },
                "container_plan": {"can_fit": False, "containers_used": 5, "n0": 2},
                "packing_options": {},
                "max_containers": 4,
            }
        )
        assert (o2.get("replan_proposal") or {}).get("route") == "box_scheme"
        print("[OK] closed_loop route=box_scheme")
    except Exception as e:
        fails.append(f"replan: {e}")

    # 5 load sequence
    try:
        from packing_assistant.tools.load_sequence import build_load_sequence

        seq = build_load_sequence(
            {
                "layout": [
                    {
                        "box_id": "B1",
                        "container_no": 1,
                        "layer": 1,
                        "position": {"x": 100, "y": 0, "z": 0},
                        "size": {"dx": 1, "dy": 1, "dz": 1},
                    },
                    {
                        "box_id": "B2",
                        "container_no": 1,
                        "layer": 2,
                        "position": {"x": 100, "y": 0, "z": 500},
                        "size": {"dx": 1, "dy": 1, "dz": 1},
                    },
                ]
            },
            [{"box_id": "B1", "box_type": "木箱"}, {"box_id": "B2", "box_type": "木箱"}],
        )
        assert len(seq.get("steps") or []) == 2
        assert seq["steps"][0]["box_id"] == "B1"  # 底层先
        print("[OK] load_sequence", seq.get("message"))
    except Exception as e:
        fails.append(f"load_seq: {e}")

    # 6 vgm
    try:
        from packing_assistant.tools.vgm_draft import draft_vgm_method2

        v = draft_vgm_method2(
            {"container_type": "40HQ", "containers_used": 2},
            [{"box_id": "A", "gross_weight_kg": 1000}, {"box_id": "B", "gross_weight_kg": 2000}],
        )
        assert v.get("auto_submit_forbidden") is True
        assert v.get("status") == "needs_shipper_signature"
        print("[OK] vgm_draft", v.get("totals"))
    except Exception as e:
        fails.append(f"vgm: {e}")

    # 7 plan_diff
    try:
        from packing_assistant.tools.plan_diff import diff_packing_plans

        d = diff_packing_plans(
            {"can_fit": False, "containers_used": 3, "cog": {"mass_in_mid50_ratio": 0.4}},
            {"can_fit": True, "containers_used": 2, "cog": {"mass_in_mid50_ratio": 0.7}},
        )
        assert d.get("improved_fit") is True
        assert d.get("fewer_containers") is True
        print("[OK] plan_diff", d.get("narrative")[:80].replace("\n", " "))
    except Exception as e:
        fails.append(f"diff: {e}")

    # 8 stack + optional t80 presence
    try:
        from scripts.test_stack_prefer import main as stack_main

        rc = stack_main()
        if rc != 0:
            fails.append("stack_prefer FAIL")
        else:
            print("[OK] stack_prefer")
    except Exception as e:
        fails.append(f"stack: {e}")

    t80 = list((ROOT / "test" / "sim_materials").glob("t80_random_mixed_*/materials.json"))
    if t80:
        data = json.loads(t80[0].read_text(encoding="utf-8"))
        print(f"[OK] t80 case {t80[0].parent.name} net={data.get('net_t')}t lines={data.get('n_lines')}")
    else:
        print("[WARN] no t80_random_mixed case on disk")

    if fails:
        print("FAIL", fails)
        return 1
    print("--- PASS 8 agent tracks ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
