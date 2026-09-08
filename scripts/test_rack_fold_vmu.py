#!/usr/bin/env python3
"""VMU packing-list fold: 1.1m + 2m racks, N0 weight should match factory 2 cabinets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.booking import compute_booking
    from packing_assistant.tools.rack_fold import (
        detect_rack_type,
        fold_packing_list_racks,
    )
    from scripts.run_real_ticket_demo import _load_xlsx_autohdr

    assert detect_rack_type("1.1米铁架1号 4-8P") == "1.1米铁架"
    assert detect_rack_type("2米铁架1号 远东") == "2米铁架"

    xlsx = ROOT / "data/samples/vmu-fst-iron-sample.xlsx"
    m1 = _load_xlsx_autohdr(xlsx, "7-20装货单1柜")
    m2 = _load_xlsx_autohdr(xlsx, "7-20装货单2柜")
    assert m1.get("detected_rack_type") == "1.1米铁架", m1.get("detected_rack_type")
    assert m2.get("detected_rack_type") == "2米铁架", m2.get("detected_rack_type")

    mats = list(m1.get("materials") or []) + list(m2.get("materials") or [])
    racks = [
        {
            "rack_type": m1["detected_rack_type"],
            "material_ids": [str(m.get("id")) for m in (m1.get("materials") or [])],
        },
        {
            "rack_type": m2["detected_rack_type"],
            "material_ids": [str(m.get("id")) for m in (m2.get("materials") or [])],
        },
    ]
    folded = fold_packing_list_racks(mats, {"packing_list_racks": racks})
    assert folded.get("ok"), folded
    boxes = folded["boxes"]
    types = {}
    for b in boxes:
        types[b["box_type"]] = types.get(b["box_type"], 0) + 1
    print("racks", len(boxes), types)
    assert types.get("1.1米铁架", 0) >= 1
    assert types.get("2米铁架", 0) >= 1
    # payload split: ~19.8t / 1.2t ≈ 17, ~12.7t / 2.5t ≈ 6
    assert 12 <= types["1.1米铁架"] <= 36, types
    assert 4 <= types["2米铁架"] <= 14, types

    book = compute_booking(boxes=boxes, container_type="40HQ")
    comps = book.get("n0_components") or {}
    print("N0", book.get("n0"), "comps", comps, book.get("n0_note"))
    assert int(comps.get("weight") or 0) == 2, comps
    # After fold, geometry must not explode to 228-piece slot count
    assert int(comps.get("geom_slot") or 0) < 20, comps
    print("PASS rack fold VMU factory 2-cabinet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
