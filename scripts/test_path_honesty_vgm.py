#!/usr/bin/env python3
"""path_honesty + vgm_status on public_response (real harness entry)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.harness import public_response, _path_honesty, _vgm_status
    from packing_assistant.tools.vgm_draft import (
        draft_vgm_method2,
        record_human_signoff,
        build_vgm_status_public,
        VGM_CHECKLIST_ITEM_ID,
    )
    from packing_assistant.p2_stubs import draft_vgm_submit

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
    assert ph.get("cabin_count_reference_only") is False, ph
    assert ph.get("booking_authority") == "steps_tools", ph

    # llm policy fallback — cabin count reference-only
    st_fb = {
        **st_steps,
        "agent_style": "policy_fallback",
        "agent_mode": "llm_toolcall",
        "container_plan": {"containers_used": 3, "n0": 3, "can_fit": True},
    }
    ph2 = _path_honesty(st_fb)
    assert ph2.get("reference_only") is True, ph2
    assert ph2.get("cabin_count_reference_only") is True, ph2
    assert ph2.get("ui_label"), ph2
    assert "fallback" in (ph2.get("note") or "").lower() or "policy" in (
        ph2.get("this_run") or ""
    ), ph2
    assert ph2.get("booking_authority") == "steps_tools", ph2
    note_cab = ph2.get("booking_containers_note") or ""
    assert "订舱" in note_cab or "终裁" in note_cab or "对照" in note_cab, note_cab

    # vgm not drafted — human_signoff panel visible
    vg = _vgm_status({})
    assert vg.get("human_signoff_required") is True, vg
    assert vg.get("auto_submit_forbidden") is True, vg
    assert vg.get("status") == "not_drafted", vg
    hs = vg.get("human_signoff") or {}
    assert hs.get("ui_visible") is True, hs
    assert hs.get("signed") is False, hs
    assert hs.get("checklist_item_id") == VGM_CHECKLIST_ITEM_ID, hs
    assert hs.get("pending_action"), hs
    assert vg.get("checklist_item_id") == VGM_CHECKLIST_ITEM_ID

    # vgm draft via real draft_vgm_method2 (per_container path)
    draft = draft_vgm_method2(
        {"container_type": "40HQ", "containers_used": 2},
        [{"box_id": "B1", "gross_weight_kg": 500}, {"box_id": "B2", "gross_weight_kg": 500}],
    )
    assert draft.get("status") == "needs_shipper_signature", draft
    assert draft.get("per_container") and draft.get("containers"), draft
    vg2 = _vgm_status({"vgm_draft": draft})
    assert vg2.get("status") == "needs_shipper_signature", vg2
    assert vg2.get("n_containers") == 2, vg2  # must count per_container
    assert vg2.get("auto_submit_forbidden") is True
    assert (vg2.get("human_signoff") or {}).get("signed") is False
    assert (vg2.get("human_signoff") or {}).get("ui_visible") is True
    assert vg2.get("ui_label")

    # unsigned submit blocked
    blocked = draft_vgm_submit({"vgm_draft": draft}, dry_run=True)
    assert blocked.get("status") == "blocked_unsigned", blocked
    assert blocked.get("blocks_until_signed") is True
    assert blocked.get("accepted") is False

    # record human signoff → signed_local + dual checklist write + submit dry_run
    st_signed = record_human_signoff(
        {"vgm_draft": draft}, signer="demo_shipper", acknowledged=True
    )
    assert st_signed.get("vgm_signoff", {}).get("signed") is True
    assert st_signed.get("checklist_checked", {}).get(VGM_CHECKLIST_ITEM_ID) is True
    assert st_signed.get("pre_ship_checked", {}).get(VGM_CHECKLIST_ITEM_ID) is True
    vg3 = build_vgm_status_public(st_signed)
    assert vg3.get("human_signoff", {}).get("signed") is True, vg3
    assert vg3.get("status") == "signed_local", vg3
    assert vg3.get("ui_label") and "签" in vg3["ui_label"]
    ok_sub = draft_vgm_submit(st_signed, dry_run=True)
    assert ok_sub.get("status") == "dry_run", ok_sub
    assert ok_sub.get("signed_local") is True
    assert ok_sub.get("blocks_until_signed") is False

    # pre_ship checklist built with pre_ship_checked must show vgm_signed checked
    from packing_assistant.pre_ship_checklist import build_pre_ship_checklist

    cl = build_pre_ship_checklist(
        st_signed, checked=st_signed.get("pre_ship_checked") or {}
    )
    vgm_item = next(
        (i for i in (cl.get("items") or []) if i.get("id") == VGM_CHECKLIST_ITEM_ID),
        None,
    )
    assert vgm_item is not None, cl
    assert vgm_item.get("checked") is True, vgm_item
    print("pre_ship_vgm_checked=", vgm_item.get("checked"))

    # UI-only path: pre_ship_checked[vgm_signed]=True (no vgm_signoff) unblocks submit
    st_ui_only = {
        "vgm_draft": draft,
        "pre_ship_checked": {VGM_CHECKLIST_ITEM_ID: True},
    }
    vg_ui = build_vgm_status_public(st_ui_only)
    assert vg_ui.get("human_signoff", {}).get("signed") is True, vg_ui
    assert vg_ui.get("status") == "signed_local", vg_ui
    sub_ui = draft_vgm_submit(st_ui_only, dry_run=True)
    assert sub_ui.get("status") == "dry_run", sub_ui
    assert sub_ui.get("blocks_until_signed") is False, sub_ui
    print("pre_ship_only_submit=", sub_ui.get("status"))

    # revoke signoff must clear both checklists and re-block submit
    st_revoked = record_human_signoff(st_signed, signer="", acknowledged=False)
    assert st_revoked.get("vgm_signoff", {}).get("signed") is False
    assert st_revoked.get("checklist_checked", {}).get(VGM_CHECKLIST_ITEM_ID) is False
    assert st_revoked.get("pre_ship_checked", {}).get(VGM_CHECKLIST_ITEM_ID) is False
    vg_rev = build_vgm_status_public(st_revoked)
    assert vg_rev.get("human_signoff", {}).get("signed") is False, vg_rev
    assert vg_rev.get("status") != "signed_local", vg_rev
    sub_rev = draft_vgm_submit(st_revoked, dry_run=True)
    assert sub_rev.get("status") == "blocked_unsigned", sub_rev
    print(
        "revoke_signed=",
        vg_rev.get("human_signoff", {}).get("signed"),
        "revoke_submit=",
        sub_rev.get("status"),
    )

    pub = public_response(st_fb)
    assert "path_honesty" in pub, list(pub.keys())[:20]
    assert pub["path_honesty"].get("reference_only") is True
    assert pub["path_honesty"].get("cabin_count_reference_only") is True
    assert "vgm_status" in pub
    assert pub["vgm_status"].get("human_signoff_required") is True
    assert (pub["vgm_status"].get("human_signoff") or {}).get("ui_visible") is True

    pub2 = public_response({**st_signed, **st_steps})
    assert pub2["vgm_status"]["human_signoff"]["signed"] is True
    assert pub2["vgm_status"]["status"] == "signed_local"

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
    print("cabin_ref_only=", pub["path_honesty"].get("cabin_count_reference_only"))
    print("vgm=", pub2["vgm_status"].get("status"))
    print("vgm_signed=", pub2["vgm_status"]["human_signoff"].get("signed"))
    print("submit_blocked=", blocked.get("status"), "submit_after=", ok_sub.get("status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
