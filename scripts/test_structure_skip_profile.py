#!/usr/bin/env python3
"""Shipped structure-skip predicate + Team A HITL for generic vs steel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


FURNITURE = [
    {
        "id": "sofa1",
        "name": "sofa",
        "length_mm": 1800,
        "width_mm": 800,
        "height_mm": 750,
        "qty": 2,
        "total_weight_kg": 40,
    },
    {
        "id": "tbl1",
        "name": "table",
        "length_mm": 1200,
        "width_mm": 600,
        "height_mm": 750,
        "qty": 1,
        "total_weight_kg": 18,
    },
]

STEEL = [
    {
        "id": "s1",
        "part_no": "FST-001",
        "name": "钢梁",
        "category": "钢结构",
        "length_mm": 6000,
        "width_mm": 200,
        "height_mm": 200,
        "qty": 4,
        "total_weight_kg": 800,
    }
]

MISSING = [
    {
        "id": "m1",
        "name": "unknown crate",
        "length_mm": 0,
        "width_mm": 0,
        "height_mm": 0,
        "qty": 1,
        "total_weight_kg": 10,
    }
]

NS = [
    {
        "id": "ns1",
        "name": "jig",
        "category": "非标夹具",
        "length_mm": 900,
        "width_mm": 400,
        "height_mm": 300,
        "qty": 1,
        "total_weight_kg": 25,
        "nonstandard": True,
    }
]


def main() -> int:
    from packing_assistant.agents.structure_agent import agent_structure
    from packing_assistant.harness import make_initial_state, run_team_a
    from packing_assistant.pack_profile import apply_pack_profile, should_skip_structure

    gen_opts = apply_pack_profile({"profile_id": "generic_table", "crate_passthrough": True})
    skip, reason = should_skip_structure(
        materials=FURNITURE, boxes=[], packing_options=gen_opts
    )
    assert skip and reason, (skip, reason)

    boxes = [
        {
            "box_id": "b1",
            "outer_size_mm": {"length": 1000, "width": 800, "height": 600},
        }
    ]
    skip_b, reason_b = should_skip_structure(
        materials=[], boxes=boxes, packing_options=apply_pack_profile({})
    )
    assert skip_b and "boxes" in reason_b, (skip_b, reason_b)

    steel_skip, _ = should_skip_structure(
        materials=STEEL, boxes=[], packing_options=apply_pack_profile({})
    )
    assert steel_skip is False

    miss_skip, _ = should_skip_structure(
        materials=MISSING, boxes=[], packing_options=apply_pack_profile({})
    )
    assert miss_skip is False

    ns_skip, _ = should_skip_structure(
        materials=NS, boxes=[], packing_options=apply_pack_profile({})
    )
    assert ns_skip is False

    st_gen = make_initial_state(user_input="furniture table", materials=FURNITURE)
    st_gen["packing_options"] = gen_opts
    out_gen = agent_structure(st_gen)
    assert out_gen.get("structure_skipped") is True
    assert out_gen.get("structure_skip_reason")

    st_steel = make_initial_state(user_input="VMU steel", materials=STEEL)
    out_steel = agent_structure(st_steel)
    assert not out_steel.get("structure_skipped")
    assert (out_steel.get("structure_constraints") or out_steel.get("structure_notes"))

    a = run_team_a(
        "generic furniture csv",
        materials=FURNITURE,
        session_id="struct-skip-furniture",
        packing_options=gen_opts,
    )
    phase = str(a.get("phase") or "")
    assert "await_user_confirm" in phase or phase in (
        "await_user_confirm",
        "team_a_done",
    ), phase
    ga = a.get("global_advice") or {}
    skipped_ok = (
        a.get("structure_skipped") is True
        or bool(a.get("structure_skip_reason"))
        or ga.get("skipped") is True
        or any("skipped" in str(n).lower() for n in (a.get("structure_notes") or []))
    )
    assert skipped_ok, {
        "structure_skipped": a.get("structure_skipped"),
        "global_advice": ga,
        "notes": a.get("structure_notes"),
    }

    b = run_team_a(
        "VMU steel ticket",
        materials=STEEL,
        session_id="struct-keep-steel",
    )
    assert not b.get("structure_skipped")

    print("PASS structure skip generic; steel/missing/ns keep structure")
    print("structure_skip_reason=", out_gen.get("structure_skip_reason"))
    print("hitl_phase=", phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
