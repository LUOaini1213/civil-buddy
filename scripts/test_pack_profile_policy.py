#!/usr/bin/env python3
"""Drive shipped pack_profile + booking/loader search policy (no 4-minute pack)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import make_initial_state, public_response
    from packing_assistant.intent_spec import apply_intent_to_state, intent_from_api
    from packing_assistant.pack_profile import (
        apply_pack_profile,
        decide_next_n,
        mid50_driven_extra_n_allowed,
        n_search_candidates,
        repairs_for_worst_mid50,
        resolve_pack_profile,
        wall_clock_budget_s,
    )

    assert resolve_pack_profile(None, {}) == "demo"
    assert resolve_pack_profile("", {}) == "demo"
    demo_opts = apply_pack_profile({})
    assert demo_opts["pack_profile"] == "demo"
    assert demo_opts["lns_worst"] is False
    assert demo_opts["r4_repair"] is False
    assert demo_opts["lateral_repair"] is False
    q_opts = apply_pack_profile({"pack_profile": "quality"})
    assert q_opts["pack_profile"] == "quality"
    assert q_opts["n_search_extra"] >= 2

    st = make_initial_state(user_input="policy dump")
    assert (st.get("packing_options") or {}).get("pack_profile") == "demo"
    assert st.get("pack_profile") == "demo"
    assert st.get("enable_auto_confirm") is False

    spec = intent_from_api(user_input="api no profile")
    st2 = apply_intent_to_state(st, spec)
    assert (st2.get("packing_options") or {}).get("pack_profile") == "demo"

    pub = public_response(st2)
    assert pub.get("pack_profile") == "demo"
    assert pub.get("enable_auto_confirm") is False

    n0 = 3
    demo_ns = n_search_candidates(n0, "demo", n_max=40)
    assert demo_ns == [3, 4], demo_ns
    qual_ns = n_search_candidates(n0, "quality", n_max=40)
    assert 3 in qual_ns and max(qual_ns) > 4, qual_ns
    assert mid50_driven_extra_n_allowed("demo") is False
    assert mid50_driven_extra_n_allowed("quality") is False

    hit = decide_next_n(
        profile="demo",
        n0=n0,
        tried=[],
        last_can_fit=False,
        elapsed_s=wall_clock_budget_s("demo") + 1,
        n_max=40,
        for_mid50=False,
    )
    assert hit["stop"] == "wall_clock" and hit["warn"] is True
    assert hit["next_n"] is None

    first = decide_next_n(
        profile="demo",
        n0=n0,
        tried=[],
        last_can_fit=False,
        elapsed_s=0,
        n_max=40,
    )
    assert first["next_n"] == 3
    second = decide_next_n(
        profile="demo",
        n0=n0,
        tried=[3],
        last_can_fit=False,
        elapsed_s=0,
        n_max=40,
    )
    assert second["next_n"] == 4
    third = decide_next_n(
        profile="demo",
        n0=n0,
        tried=[3, 4],
        last_can_fit=False,
        elapsed_s=0,
        n_max=40,
    )
    assert third["next_n"] is None
    mid_extra = decide_next_n(
        profile="demo",
        n0=n0,
        tried=[3],
        last_can_fit=True,
        elapsed_s=0,
        n_max=40,
        for_mid50=True,
    )
    assert mid_extra["stop"] == "mid50_extra_forbidden"
    assert mid_extra["mid50_extra"] is False

    q_more = decide_next_n(
        profile="quality",
        n0=n0,
        tried=[3, 4],
        last_can_fit=False,
        elapsed_s=0,
        n_max=40,
    )
    assert q_more["next_n"] == 5, q_more

    off = repairs_for_worst_mid50("quality", 0.62)
    assert off == {"lns_worst": False, "r4_repair": False, "lateral_repair": False}
    on = repairs_for_worst_mid50("quality", 0.40)
    assert on == {"lns_worst": True, "r4_repair": True, "lateral_repair": True}
    demo_rep = repairs_for_worst_mid50("demo", 0.10)
    assert all(v is False for v in demo_rep.values())

    from packing_assistant.tools.booking import pack_with_auto_containers

    tiny_boxes = [
        {
            "box_id": f"tb{i}",
            "outer_size_mm": {"length": 800, "width": 600, "height": 500},
            "gross_weight_kg": 40,
            "stackable": True,
        }
        for i in range(4)
    ]
    demo_plan = pack_with_auto_containers(
        tiny_boxes,
        container_type="40HQ",
        n0=1,
        n_max=20,
        packing_options={"pack_profile": "demo"},
    )
    tried_ns = [int(t["n"]) for t in (demo_plan.get("n_tried") or []) if not t.get("merge_back")]
    assert tried_ns, demo_plan.get("n_tried")
    assert max(tried_ns) <= 2, tried_ns
    assert set(tried_ns).issubset({1, 2}), tried_ns

    from packing_assistant.demo_presets import resolve_preset
    from packing_assistant.pack_profile import cog_pipeline_flags

    _pm, _po, _pk = resolve_preset("", user_input="Agent pipeline")
    assert _po is None and _pk == ""
    _bare = apply_pack_profile(_po or {})
    assert _bare["pack_profile"] == "demo"
    assert _bare["lns_worst"] is False and _bare["r4_repair"] is False and _bare["lateral_repair"] is False

    leaked = apply_pack_profile(
        {
            "cog_rebalance": True,
            "r4_repair": True,
            "lns_worst": True,
            "lateral_repair": True,
            "force_cog_repair": True,
        }
    )
    assert leaked["pack_profile"] == "demo"
    assert leaked["r4_repair"] is False
    assert leaked["lns_worst"] is False
    assert leaked["lateral_repair"] is False
    q_hi = cog_pipeline_flags({"pack_profile": "quality", "cog_rebalance": True}, 0.62)
    assert q_hi["force_cog"] is True
    assert q_hi["do_r4"] is False and q_hi["do_lns"] is False and q_hi["do_lat"] is False
    q_lo = cog_pipeline_flags({"pack_profile": "quality", "cog_rebalance": True}, 0.40)
    assert q_lo["do_r4"] is True and q_lo["do_lns"] is True and q_lo["do_lat"] is True

    print("PASS pack_profile policy")
    print("pack_profile=demo")
    print("demo_tried_n=", tried_ns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
