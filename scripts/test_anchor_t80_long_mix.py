#!/usr/bin/env python3
"""锚点回归：t80_long_mix_s297883 + 超货载拆箱门禁。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_feasibility_tool() -> None:
    from packing_assistant.tools.cargo_feasibility import check_cargo_feasibility

    bad = check_cargo_feasibility(
        materials=[
            {
                "id": "X1",
                "weight_kg": 80000,
                "total_weight_kg": 80000,
                "quantity": 1,
            }
        ],
        container_type="40HQ",
    )
    assert bad["ok"] is False, bad
    assert bad["failure_class"] in (
        "over_payload_material",
        "over_payload_box",
    ), bad
    ok = check_cargo_feasibility(
        materials=[
            {
                "id": "Y1",
                "weight_kg": 200,
                "total_weight_kg": 200,
                "quantity": 1,
            }
        ],
        container_type="40HQ",
    )
    assert ok["ok"] is True, ok
    print("PASS feasibility tool")


def test_mass_split() -> None:
    from packing_assistant.tools.packing import _explode_items_by_net_cap

    items = [
        {
            "名称": "怪兽件",
            "数量": 1,
            "单重_kg": 80000,
            "总重_kg": 80000,
            "加工件编号": "M1",
            "L": 6000,
            "W": 200,
            "H": 160,
        }
    ]
    out = _explode_items_by_net_cap(items, 2500.0)
    assert len(out) >= 2, out
    assert all(float(x["总重_kg"]) <= 2500 + 1 for x in out), out
    print("PASS mass_split", len(out))


def test_anchor_pipeline() -> None:
    from packing_assistant.harness import run_agent_pipeline
    from packing_assistant.tools.cargo_feasibility import check_cargo_feasibility

    path = ROOT / "test/sim_materials/t80_long_mix_s297883/materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    assert len(mats) >= 50, f"fixture still corrupt n={len(mats)}"
    max_line = max(float(m.get("total_weight_kg") or 0) for m in mats)
    assert max_line < 26000, f"max line {max_line}"

    st = run_agent_pipeline(
        "anchor t80_long_mix_s297883",
        materials=mats,
        container_type="40HQ",
        max_containers=0,
        enable_auto_confirm=True,
        session_id="anchor-t80-297883",
        save_artifacts=False,
        packing_options={
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
        agent_mode="steps",
    )
    plan = st.get("container_plan") or {}
    feas = check_cargo_feasibility(
        boxes=st.get("boxes") or [],
        container_type="40HQ",
    )
    print(
        "RESULT can_fit=",
        plan.get("can_fit"),
        "used=",
        plan.get("containers_used"),
        "n0=",
        plan.get("n0"),
        "boxes=",
        len(st.get("boxes") or []),
        "replan=",
        st.get("replan_round"),
        "feas_ok=",
        feas.get("ok"),
    )
    assert feas.get("ok") is True, feas
    assert plan.get("can_fit") is True, plan
    print("PASS anchor pipeline")


def test_over_payload_monster_fixture() -> None:
    """永久脏料：必须 feasibility 检出 + critic 路由 box_scheme。"""
    from packing_assistant.agents.replan_critic import agent_replan_critic
    from packing_assistant.tools.cargo_feasibility import check_cargo_feasibility
    from packing_assistant.tools.packing import _explode_items_by_net_cap

    path = ROOT / "test/phase0/over_payload_monster.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mats = data["materials"]
    feas = check_cargo_feasibility(materials=mats, container_type="40HQ")
    assert feas["ok"] is False
    # mass split
    items = [
        {
            "名称": mats[0]["name"],
            "数量": 1,
            "单重_kg": 80000,
            "总重_kg": 80000,
            "加工件编号": "M",
        }
    ]
    split = _explode_items_by_net_cap(items, 2500)
    assert len(split) >= 2
    # critic
    st = {
        "container_type": "40HQ",
        "replan_round": 0,
        "ship_replan_round": 0,
        "packing_options": {},
        "materials": mats,
        "boxes": [{"box_id": "PT-1", "net_weight_kg": 80000}],
        "container_plan": {"can_fit": False, "unpacked_box_ids": ["PT-1"], "n0": 3},
        "evaluation": {"need_replan": True, "decision": "REPLAN"},
        "risk_report": {},
    }
    prop = (agent_replan_critic(st).get("replan_proposal") or {})
    assert prop.get("route") == "box_scheme", prop
    print("PASS over_payload_monster fixture")


def test_critic_over_payload_routes_box_scheme() -> None:
    from packing_assistant.agents.replan_critic import agent_replan_critic

    state = {
        "container_type": "40HQ",
        "max_containers": 3,
        "replan_round": 0,
        "ship_replan_round": 0,
        "packing_options": {},
        "boxes": [
            {
                "box_id": "PT-1",
                "net_weight_kg": 80000,
                "gross_weight_kg": 80040,
            }
        ],
        "container_plan": {"can_fit": False, "unpacked_box_ids": ["PT-1"], "n0": 3},
        "evaluation": {"need_replan": True, "decision": "REPLAN"},
        "risk_report": {},
    }
    out = agent_replan_critic(state)
    prop = out.get("replan_proposal") or {}
    assert prop.get("route") == "box_scheme", prop
    assert float((out.get("packing_options") or {}).get("max_box_net_kg") or 99999) < 5000
    print("PASS critic over_payload → box_scheme", prop.get("reasons"))


if __name__ == "__main__":
    import os

    test_feasibility_tool()
    test_mass_split()
    test_over_payload_monster_fixture()
    test_critic_over_payload_routes_box_scheme()
    if os.getenv("ANCHOR_SKIP_PIPELINE") != "1":
        test_anchor_pipeline()
    else:
        print("SKIP anchor pipeline (ANCHOR_SKIP_PIPELINE=1)")
    print("ALL_ANCHOR_PASS")
