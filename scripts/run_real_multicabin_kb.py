#!/usr/bin/env python3
"""Multi-container real ticket + knowledge-base checks.

Factory ground truth: VMU 7-20 装货单1柜 + 2柜 = 2 cabinets.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _complete(m: dict) -> bool:
    return (
        float(m.get("length_mm") or 0) > 0
        and float(m.get("width_mm") or 0) > 0
        and float(m.get("height_mm") or 0) > 0
    )


def main() -> int:
    from packing_assistant.harness import (
        apply_user_confirmation,
        run_team_a,
        run_team_b,
    )
    from packing_assistant.pack_profile import apply_pack_profile
    from packing_assistant.tools.booking import compute_booking
    from packing_assistant.tools.search_knowledge import search_knowledge
    from scripts.run_real_ticket_demo import _load_xlsx_autohdr

    xlsx = ROOT / "data/samples/vmu-fst-iron-sample.xlsx"
    m1 = _load_xlsx_autohdr(xlsx, "7-20装货单1柜")
    m2 = _load_xlsx_autohdr(xlsx, "7-20装货单2柜")
    mats = [m for m in (m1.get("materials") or []) + (m2.get("materials") or []) if _complete(m)]
    wt = sum(float(m.get("total_weight_kg") or 0) for m in mats)
    print("=== factory ticket: 装货单1柜+2柜 ===")
    print(f"lines={len(mats)} weight_kg={wt:.1f} factory_cabinets=2")

    # --- knowledge retrieval grounded in this ticket ---
    queries = [
        "N0 订舱柜数 重量 体积",
        "mid50 重心 红线",
        "铁架 成箱 空心 订舱体积",
        "双口径 订舱体积 outer",
        "40HQ payload 超重",
        "中新走廊 出口装柜",
    ]
    print("\n=== knowledge.search ===")
    for q in queries:
        res = search_knowledge(q, limit=3)
        hits = res.get("hits") or []
        paths = [h.get("path") for h in hits]
        print(f"Q: {q}")
        print(f"   hits={paths}")

    from packing_assistant.tools.rack_fold import detect_rack_type, fold_packing_list_racks

    racks = []
    for sheet, parsed in (("7-20装货单1柜", m1), ("7-20装货单2柜", m2)):
        rtype = parsed.get("detected_rack_type") or detect_rack_type(sheet)
        ids = [str(m.get("id")) for m in (parsed.get("materials") or []) if m.get("id")]
        if rtype and ids:
            racks.append({"rack_type": rtype, "material_ids": ids, "title": sheet})
    folded = fold_packing_list_racks(mats, {"packing_list_racks": racks})
    boxes = list(folded.get("boxes") or [])
    print("fold", folded.get("notes"), "racks", len(boxes))
    book = compute_booking(boxes=boxes, container_type="40HQ")
    print("\n=== N0 after rack fold (compute_booking) ===")
    print(
        "n0=",
        book.get("n0"),
        "n0_note=",
        book.get("n0_note"),
        "binding=",
        book.get("binding_constraint"),
        "comps=",
        book.get("n0_components"),
    )
    print("factory_cabinets=2  vs  N0=", book.get("n0"))

    opts = apply_pack_profile(
        {
            "profile_id": "steel",
            "crate_passthrough": False,
            "packing_list_racks": racks,
        }
    )
    print("rack_groups", [(g["rack_type"], len(g["material_ids"])) for g in racks])
    t0 = time.perf_counter()
    a = run_team_a(
        "VMU 两柜合并 远东新加坡LTA",
        materials=mats,
        session_id="real-multicabin",
        packing_options=opts,
    )
    print(f"\nteam_a {time.perf_counter()-t0:.2f}s phase={a.get('phase')} boxes={len(a.get('boxes') or [])}")
    t1 = time.perf_counter()
    b = run_team_b(apply_user_confirmation(a, action="confirm", container_type="40HQ"))
    plan = b.get("container_plan") or {}
    print(
        f"team_b {time.perf_counter()-t1:.2f}s phase={b.get('phase')} "
        f"n0={plan.get('n0')} used={plan.get('containers_used')} "
        f"can_fit={plan.get('can_fit')} ship_ok={b.get('ship_ok')} "
        f"mid50={plan.get('worst_mid50')} tried={plan.get('n_tried')}"
    )

    # t30 ~30t → knowledge: N_weight=2
    t30 = json.loads(
        (ROOT / "test/sim_materials/t30_steel_tubes_s1/materials.json").read_text(
            encoding="utf-8"
        )
    )
    t30_mats = t30.get("materials") or []
    t30_boxes = [
        {
            "box_id": m.get("id") or f"T{i}",
            "outer_size_mm": {
                "length": m["length_mm"],
                "width": m["width_mm"],
                "height": m["height_mm"],
            },
            "gross_weight_kg": float(m.get("total_weight_kg") or 0),
            "stackable": True,
        }
        for i, m in enumerate(t30_mats, 1)
    ]
    b30 = compute_booking(boxes=t30_boxes, container_type="40HQ")
    print("\n=== t30 steel ~30t (expect N_weight>=2) ===")
    print(
        "lines=",
        len(t30_mats),
        "net_t=",
        t30.get("net_t"),
        "n0=",
        b30.get("n0"),
        "comps=",
        b30.get("n0_components"),
        "expect_wt_min=",
        (t30.get("expect") or {}).get("containers_by_weight_min"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
