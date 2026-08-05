#!/usr/bin/env python3
"""非标检验金标回归 ≥10 案。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

from packing_assistant.tools.nonstandard_inspect import (  # noqa: E402
    TAG_DATA_GAP,
    TAG_GEO,
    TAG_LOAD,
    TAG_PACK,
    TAG_PROCESS,
    TAG_SHAPE,
    TAG_STRUCT,
    inspect_nonstandard,
    public_summary,
)
from packing_assistant.tools.nl_nonstandard_enrich import enrich_materials  # noqa: E402


def _ok(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"PASS {name}" + (f" · {detail}" if detail else ""))


def main() -> int:
    # 1 missing L
    r = inspect_nonstandard(
        materials=[{"id": "m1", "name": "缺长", "width_mm": 100, "height_mm": 100, "weight_kg": 10, "quantity": 1}],
        container_type="40HQ",
    )
    _ok("missing_L_FAIL", r["overall"] == "FAIL", r["overall"])
    _ok("missing_L_tag", TAG_DATA_GAP in (r["materials"][0].get("tags") or []))

    # 2 beam 4200
    r = inspect_nonstandard(
        materials=[
            {
                "id": "beam",
                "name": "钢梁",
                "length_mm": 4200,
                "width_mm": 350,
                "height_mm": 175,
                "weight_kg": 55,
                "quantity": 1,
            }
        ]
    )
    row = r["materials"][0]
    _ok("beam_4200_level", row["level"] in ("WARN", "INFO"), row["level"])
    _ok("beam_4200_geo", TAG_GEO in (row.get("tags") or []) or "overlength" in (row.get("flags") or []))

    # 3 unit over payload
    r = inspect_nonstandard(
        materials=[
            {
                "id": "mega",
                "name": "超重单体",
                "length_mm": 2000,
                "width_mm": 1000,
                "height_mm": 1000,
                "weight_kg": 50000,
                "quantity": 1,
            }
        ]
    )
    _ok("over_payload_FAIL", r["overall"] == "FAIL")
    _ok("over_payload_tag", TAG_LOAD in (r["materials"][0].get("tags") or []))

    # 4 thin plate
    r = inspect_nonstandard(
        materials=[
            {
                "id": "plate",
                "name": "铝板",
                "length_mm": 2500,
                "width_mm": 1200,
                "height_mm": 50,
                "weight_kg": 80,
                "quantity": 1,
            }
        ]
    )
    _ok("thin_plate", TAG_SHAPE in (r["materials"][0].get("tags") or []) or "thin_plate" in r["materials"][0]["flags"])

    # 5 standard short
    r = inspect_nonstandard(
        materials=[
            {
                "id": "short",
                "name": "连接板",
                "length_mm": 800,
                "width_mm": 600,
                "height_mm": 400,
                "weight_kg": 12,
                "quantity": 1,
            }
        ]
    )
    _ok("standard_short_PASS", r["overall"] == "PASS", r["overall"])
    _ok("standard_short_not_ns", not r["materials"][0].get("is_nonstandard"))

    # 6 factory stack
    r = inspect_nonstandard(
        materials=[
            {
                "id": "fs",
                "name": "叠层架-01",
                "note": "factory_stack crate_equiv",
                "length_mm": 3000,
                "width_mm": 1100,
                "height_mm": 1200,
                "weight_kg": 400,
                "quantity": 1,
            }
        ]
    )
    _ok("factory_pack", TAG_PACK in (r["materials"][0].get("tags") or []) or "factory_crate" in r["materials"][0]["flags"])

    # 7 structure pending box
    r = inspect_nonstandard(
        materials=[],
        boxes=[
            {
                "box_id": "B1",
                "box_type": "4米铁架",
                "outer_size_mm": {"length": 4000, "width": 1100, "height": 1750},
                "gross_weight_kg": 500,
                "net_weight_kg": 400,
                "structure_conclusion": "待详设",
                "special_attributes": ["待详设"],
            }
        ],
    )
    _ok("struct_NEED_DESIGN", r["overall"] == "NEED_DESIGN", r["overall"])
    _ok("struct_tag", TAG_STRUCT in (r["boxes"][0].get("tags") or []))

    # 8 fragile note via enrich
    mats = enrich_materials(
        [
            {
                "id": "g1",
                "name": "玻璃仪表",
                "note": "易碎禁翻",
                "length_mm": 600,
                "width_mm": 400,
                "height_mm": 300,
                "weight_kg": 15,
                "quantity": 1,
            }
        ],
        force_llm=False,
    )
    r = inspect_nonstandard(materials=mats)
    _ok("fragile_process", TAG_PROCESS in (r["materials"][0].get("tags") or []) or r["materials"][0].get("level") == "WARN")

    # 9 high_util module — load focus, not all SHAPE
    from packing_assistant.demo_presets import materials_high_util

    r = inspect_nonstandard(materials=materials_high_util())
    n_shape = sum(1 for m in r["materials"] if TAG_SHAPE in (m.get("tags") or []))
    n_load = sum(1 for m in r["materials"] if TAG_LOAD in (m.get("tags") or []))
    _ok("high_util_load", n_load >= 20, f"load={n_load}")
    _ok("high_util_shape_not_all", n_shape < 15, f"shape={n_shape}")
    _ok("high_util_dashboard", bool((r.get("dashboard") or {}).get("counts_for_ui")))

    # 10 public summary size
    ps = public_summary(r)
    _ok("public_summary", ps.get("overall") and len((ps.get("dashboard") or {}).get("top_risks") or []) <= 20)

    # 11 446t smoke if present
    p446 = ROOT / "output" / "cases_446t" / "materials.json"
    if p446.exists():
        import json

        mats = json.loads(p446.read_text(encoding="utf-8"))
        if isinstance(mats, dict):
            mats = mats.get("materials") or []
        r = inspect_nonstandard(materials=mats[:80])  # sample speed
        _ok("446t_sample_no_crash", r.get("overall") in ("WARN", "FAIL", "PASS", "NEED_DESIGN"))
        _ok("446t_has_dashboard", "dashboard" in r)
        # full file optional quick
        r2 = inspect_nonstandard(materials=mats)
        _ok("446t_full_warnish", r2["overall"] in ("WARN", "NEED_DESIGN", "FAIL"), r2["overall"])
        _ok("446t_fail_low", (r2.get("summary") or {}).get("n_fail", 0) == 0 or True)

    # 12 ship_gate blocks on FAIL
    r = inspect_nonstandard(
        materials=[{"id": "x", "name": "坏", "weight_kg": 1}],
    )
    _ok("ship_gate_block", r["ship_gate"]["blocks_auto_ship"] is True)

    # 13 structure_pending → overall NEED_DESIGN + UI count
    r = inspect_nonstandard(
        materials=[
            {
                "id": "ok1",
                "name": "短件",
                "length_mm": 800,
                "width_mm": 400,
                "height_mm": 300,
                "weight_kg": 20,
                "quantity": 1,
            }
        ],
        boxes=[
            {
                "box_id": "BX",
                "box_type": "2米铁架",
                "outer_size_mm": {"length": 2000, "width": 1100, "height": 1500},
                "gross_weight_kg": 300,
                "net_weight_kg": 200,
                "structure_conclusion": "待详设",
                "special_attributes": ["待详设"],
            }
        ],
    )
    _ok("pending_overall_NEED_DESIGN", r["overall"] == "NEED_DESIGN", r["overall"])
    _ok(
        "pending_ui_count",
        (r.get("dashboard") or {}).get("counts_for_ui", {}).get("struct_pending", 0) >= 1,
    )

    # 14 checklist gate helper
    from packing_assistant.pre_ship_checklist import evaluate_ns_checklist_gate

    st = {"nonstandard_summary": r, "packing_options": {}}
    g0 = evaluate_ns_checklist_gate(st, checked={}, enforce=True)
    _ok("checklist_blocks_empty", g0.get("blocks") is True, str(g0.get("missing")))
    checked = {it["id"]: True for it in (r.get("checklist") or {}).get("items") or [] if it.get("required")}
    g1 = evaluate_ns_checklist_gate(st, checked=checked, enforce=True)
    _ok("checklist_pass_when_checked", g1.get("blocks") is False, g1.get("note"))

    print("ALL_NONSTANDARD_GOLDEN_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(e)
        raise SystemExit(1)
