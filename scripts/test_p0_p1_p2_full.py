#!/usr/bin/env python3
"""P0+P1+P2 全链路验收。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.nl_whatif import parse_nl_whatif
    from packing_assistant.score_plan import compare_plans, score_plan
    from packing_assistant.export_pack import export_shipment_xlsx
    from packing_assistant.eval_harness import run_eval_suite
    from packing_assistant.harness import run_agent_pipeline
    from packing_assistant.whatif import run_whatif
    from packing_assistant.business_presets import list_business_presets
    from packing_assistant.pre_ship_checklist import build_pre_ship_checklist
    from packing_assistant.p2_stubs import (
        build_evidence_pack,
        draft_vgm_submit,
        estimate_freight_stub,
        tip_slide_score,
    )
    from packing_assistant.packing_profiles import apply_profile

    # P0-1 NL：必须带物料才出差异化方案（详见 test_nl_material_scheme.py）
    steel = [
        {
            "id": "S1",
            "name": "铁件架",
            "part_no": "FST0001",
            "spec": "13—铁件",
            "total_weight_kg": 900,
            "length_mm": 2000,
            "width_mm": 1100,
            "height_mm": 1100,
            "quantity": 1,
            "weight_kg": 900,
        }
    ]
    p = parse_nl_whatif("锁 2 柜，去掉超长", materials=steel)
    assert p.get("max_containers") == 2
    assert p.get("material_profile", {}).get("cargo_mode")
    p2 = parse_nl_whatif("只要铁件", materials=steel)
    assert "iron" in str(p2.get("selection") or p2.get("intents") or p2)
    print("PASS NL whatif material-aware", p.get("scheme_id"), p2.get("scheme_id"))

    # P0-2 score
    a = {"can_fit": True, "ship_ok": True, "worst_mid50": 0.7, "cog": {"lateral_eccentricity": 0.02}, "containers_used": 2, "n0": 2, "weight_utilization": 0.6}
    b = {"can_fit": True, "ship_ok": True, "worst_mid50": 0.5, "cog": {"lateral_eccentricity": 0.1}, "containers_used": 3, "n0": 2, "weight_utilization": 0.4}
    cmp = compare_plans(b, a)
    assert cmp["after_is_better"] is True
    print("PASS score_plan", cmp["label"], cmp["delta"])

    # P0-4 eval harness
    ev = run_eval_suite(out_path=ROOT / "output" / "eval_harness_last.json")
    assert ev["ok"], ev
    print("PASS eval harness", ev["passed"], "/", ev["n"])

    # pipeline + export + whatif nl
    mats = []
    for i in range(8):
        mats.append(
            {
                "id": f"M{i}",
                "name": f"架{i}",
                "part_no": f"FST{i:04d}",
                "quantity": 1,
                "weight_kg": 700,
                "total_weight_kg": 700,
                "length_mm": 2000,
                "width_mm": 1100,
                "height_mm": 1100,
                "note": "crate_equiv_est",
            }
        )
    st = run_agent_pipeline(
        "full accept",
        materials=mats,
        enable_auto_confirm=True,
        session_id="full-p0p1p2",
        packing_options=apply_profile(
            {"crate_passthrough": True, "multi_start": True, "cog_aware": True},
            "balanced",
        ),
    )
    assert st.get("team_mode") == "single_closed_loop"
    meta = export_shipment_xlsx(st, output_dir=ROOT / "output" / "exports")
    assert Path(meta["xlsx_path"]).exists()
    print("PASS export xlsx", meta["xlsx_path"])

    w = run_whatif(
        st,
        nl_query="锁 1 柜",
        session_id="full-p0p1p2",
    )
    assert w.get("ok")
    assert w.get("score_compare") is not None
    print("PASS whatif nl+score", w.get("winner_label"), w.get("nl_parsed"))

    # P1
    assert len(list_business_presets()) >= 2
    cl = build_pre_ship_checklist(st, checked={"vgm_signed": True})
    assert "vgm_signed" in [i["id"] for i in cl["items"]]
    print("PASS checklist + business presets")

    # P2 stubs
    plan = st.get("container_plan") or {}
    tip = tip_slide_score(plan, st.get("boxes"))
    assert "risk_score" in tip
    vgm = draft_vgm_submit(st, dry_run=True)
    assert vgm.get("dry_run") is True
    evp = build_evidence_pack(st, output_dir=ROOT / "output" / "evidence")
    assert Path(evp["path"]).exists()
    fr = estimate_freight_stub(plan)
    assert fr.get("total") is not None
    print("PASS P2 stubs", tip.get("level"), fr.get("total"))

    print("ALL PASS P0+P1+P2 full")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
