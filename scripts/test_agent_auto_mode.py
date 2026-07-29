#!/usr/bin/env python3
"""Agent 自动模式改进冒烟：crate 直通 / 薄板 dense / ship_ok / floor 别名。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.agents.box_scheme import (  # noqa: E402
    _crate_passthrough_enabled,
    _should_force_dense_sheets,
    agent_box_scheme,
)
from packing_assistant.agents.risk_compliance import agent_risk_compliance  # noqa: E402
from packing_assistant.agents.replan_critic import agent_replan_critic  # noqa: E402


def test_passthrough_detect() -> None:
    mats = [
        {
            "id": "1",
            "name": "叠层架 | FAC",
            "length_mm": 2200,
            "width_mm": 1100,
            "height_mm": 1000,
            "quantity": 1,
            "total_weight_kg": 400,
            "note": "factory_stack_v3",
        }
        for _ in range(6)
    ]
    assert _crate_passthrough_enabled(mats, {}) is True
    out = agent_box_scheme({"materials": mats, "packing_options": {}, "container_type": "40HQ"})
    assert out["boxes"]
    assert all(b.get("base_box_type") == "crate_passthrough" for b in out["boxes"])
    print("PASS passthrough detect + box_scheme")


def test_dense_sheets() -> None:
    mats = [
        {
            "id": f"S{i}",
            "name": f"3mm铝板 {i}",
            "length_mm": 2000 + i * 10,
            "width_mm": 1000,
            "height_mm": 3,
            "quantity": 20,
            "total_weight_kg": 100,
        }
        for i in range(10)
    ]
    assert _should_force_dense_sheets(mats, {}) is True
    assert _crate_passthrough_enabled(mats, {}) is False  # 薄片非成品箱
    print("PASS dense sheets detect")


def test_ship_ok_and_floor_alias() -> None:
    from packing_assistant.tools.bin3d import pack_boxes_api

    boxes = [
        {
            "box_id": "B1",
            "outer_size_mm": {"length": 4000, "width": 1100, "height": 1100},
            "net_weight_kg": 2000,
            "gross_weight_kg": 2100,
            "structure_conclusion": "通过",
            "stackable": False,
            "prefer_bottom": True,
            "special_attributes": [],
        },
        {
            "box_id": "B2",
            "outer_size_mm": {"length": 3000, "width": 1100, "height": 1100},
            "net_weight_kg": 1800,
            "gross_weight_kg": 1900,
            "structure_conclusion": "通过",
            "stackable": False,
            "prefer_bottom": True,
            "special_attributes": [],
        },
        {
            "box_id": "B3",
            "outer_size_mm": {"length": 2000, "width": 1100, "height": 800},
            "net_weight_kg": 800,
            "gross_weight_kg": 850,
            "structure_conclusion": "通过",
            "stackable": True,
            "special_attributes": [],
        },
    ]
    plan = pack_boxes_api(
        boxes,
        container_type="40HQ",
        max_containers=1,
        packing_options={"multi_start": True, "cog_rebalance": True},
    )
    assert plan.get("can_fit") is True
    upd = agent_risk_compliance(
        {
            "boxes": boxes,
            "container_plan": plan,
            "evaluation": {"score": 80, "decision": "PASS"},
            "packing_options": {},
        }
    )
    rr = upd["risk_report"]
    assert "ship_ok" in rr, rr
    assert upd.get("ship_ok") is True or rr.get("decision") == "WARN"
    # WARN 也可讨论出运 → ship_ok True；PASS 亦然
    if rr.get("decision") in ("PASS", "WARN"):
        assert upd.get("ship_ok") is True
    floor = rr.get("metrics", {}).get("floor_utilization")
    assert floor is not None and floor == plan.get("floor_utilization_avg")
    print("PASS ship_ok + floor metrics", rr["decision"], rr["ship_ok"], "floor", floor)


def test_hollow_replan_triggers() -> None:
    plan = {
        "can_fit": True,
        "containers_used": 1,
        "outer_space_utilization": 0.18,
        "booking_volume_utilization": 0.12,
        "weight_utilization": 0.30,
        "n0": 1,
    }
    upd = agent_replan_critic(
        {
            "evaluation": {"decision": "PASS", "need_replan": False},
            "risk_report": {"decision": "WARN"},
            "container_plan": plan,
            "packing_options": {},
            "max_containers": 1,
            "replan_round": 0,
            "ship_replan_round": 0,
        }
    )
    prop = upd.get("replan_proposal") or {}
    assert prop.get("stop") is False, prop
    assert any("半柜空洞" in r or "densify" in r.lower() or "空洞" in r for r in (prop.get("reasons") or [])), prop
    assert (upd.get("packing_options") or {}).get("_hollow_densify_done") is True
    print("PASS hollow densify replan", prop.get("reasons"))


def main() -> int:
    test_passthrough_detect()
    test_dense_sheets()
    test_ship_ok_and_floor_alias()
    test_hollow_replan_triggers()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
