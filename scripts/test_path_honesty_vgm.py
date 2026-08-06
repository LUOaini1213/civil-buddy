#!/usr/bin/env python3
"""path_honesty + vgm_status on public_response (real harness entry)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import public_response, _path_honesty, _vgm_status

    # steps path
    st_steps = {
        "agent_style": "",
        "agent_mode": "steps",
        "team_mode": "big_team_a_b",
        "phase": "done",
        "container_plan": {"containers_used": 1, "n0": 1, "can_fit": True},
        "messages": [],
        "agent_steps": [],
    }
    ph = _path_honesty(st_steps)
    assert ph.get("primary_path") == "steps", ph
    assert ph.get("reference_only") is False, ph
    assert ph.get("booking_authority") == "steps_tools", ph

    # llm policy fallback
    st_fb = {**st_steps, "agent_style": "policy_fallback", "agent_mode": "llm_toolcall"}
    ph2 = _path_honesty(st_fb)
    assert ph2.get("reference_only") is True, ph2
    assert "fallback" in (ph2.get("note") or "").lower() or "policy" in (
        ph2.get("this_run") or ""
    ), ph2
    assert ph2.get("booking_authority") == "steps_tools", ph2

    # vgm not drafted
    vg = _vgm_status({})
    assert vg.get("human_signoff_required") is True, vg
    assert vg.get("auto_submit_forbidden") is True, vg
    assert vg.get("status") == "not_drafted", vg

    # vgm draft present
    vg2 = _vgm_status(
        {
            "vgm_draft": {
                "status": "draft",
                "method": "method2",
                "containers": [{"no": 1}],
                "totals": {"cargo_kg": 1000},
            }
        }
    )
    assert vg2.get("status") == "draft", vg2
    assert vg2.get("n_containers") == 1, vg2
    assert vg2.get("auto_submit_forbidden") is True

    pub = public_response(st_fb)
    assert "path_honesty" in pub, list(pub.keys())[:20]
    assert pub["path_honesty"].get("reference_only") is True
    assert "vgm_status" in pub
    assert pub["vgm_status"].get("human_signoff_required") is True

    # multi_container big-ticket timing tip
    from packing_assistant.harness import _multi_container_summary

    mc = _multi_container_summary(
        {},
        {
            "n0": 10,
            "containers_used": 10,
            "n0_components": {"weight": 8},
            "weight_utilization": 0.5,
        },
    )
    tips = " ".join(mc.get("tips") or [])
    assert "耗时" in tips or "分钟" in tips, tips
    assert mc.get("big_ticket") is True, mc

    print("ALL_PASS path_honesty_vgm")
    print("path_honesty=", pub["path_honesty"].get("this_run"))
    print("vgm=", pub["vgm_status"].get("status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
