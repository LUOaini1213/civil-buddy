#!/usr/bin/env python3
"""磁盘新非标夹具 → 真实 inspect_nonstandard 入口回归。

夹具：test/sim_materials/ns_*/materials.json · INDEX: ns_INDEX.json
"""

from __future__ import annotations

import json
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
    inspect_nonstandard,
)

NS_ROOT = ROOT / "test" / "sim_materials"
INDEX = NS_ROOT / "ns_INDEX.json"

# 至少覆盖这些 case（磁盘路径必须存在）
REQUIRED = (
    "ns_overlength_rail",
    "ns_heavy_cast",
    "ns_thin_sheet_stack",
    "ns_missing_dims_mix",
    "ns_factory_crate_path",
    "ns_fragile_process",
    "ns_over_container_width",
    "ns_mixed_industry_bundle",
)


def _load_case(case_id: str) -> list:
    p = NS_ROOT / case_id / "materials.json"
    assert p.is_file(), f"missing fixture {p}"
    data = json.loads(p.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    assert mats, case_id
    return mats


def _all_tags(report: dict) -> set:
    tags = set()
    for m in report.get("materials") or []:
        for t in m.get("tags") or []:
            tags.add(t)
    for t in ((report.get("dashboard") or {}).get("by_tag") or {}):
        tags.add(t)
    return tags


def main() -> int:
    assert INDEX.is_file(), INDEX
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    case_ids = [c["id"] for c in (idx.get("cases") or [])]
    assert len(case_ids) >= 2, case_ids

    for cid in REQUIRED:
        assert cid in case_ids, f"{cid} not in ns_INDEX"
        mats = _load_case(cid)
        r = inspect_nonstandard(materials=mats, case_id=cid, container_type="40HQ")
        overall = r.get("overall")
        tags = _all_tags(r)
        print(f"CASE {cid}: overall={overall} tags={sorted(tags)}")

        if cid == "ns_overlength_rail":
            assert overall in ("WARN", "FAIL", "NEED_DESIGN"), overall
            assert TAG_GEO in tags, tags
        elif cid == "ns_heavy_cast":
            assert TAG_LOAD in tags, tags
        elif cid == "ns_thin_sheet_stack":
            assert TAG_SHAPE in tags or any(
                "thin_plate" in (m.get("flags") or []) for m in r.get("materials") or []
            ), tags
        elif cid == "ns_missing_dims_mix":
            assert overall == "FAIL", overall
            assert TAG_DATA_GAP in tags, tags
        elif cid == "ns_factory_crate_path":
            assert TAG_PACK in tags, tags
        elif cid == "ns_fragile_process":
            assert TAG_PROCESS in tags, tags
        elif cid == "ns_over_container_width":
            assert overall == "FAIL", overall
            assert TAG_GEO in tags, tags
            assert (r.get("ship_gate") or {}).get("blocks_auto_ship") is True
        elif cid == "ns_mixed_industry_bundle":
            # multi-tag mix
            assert overall in ("WARN", "FAIL", "NEED_DESIGN"), overall
            assert len(tags) >= 2, tags

    print("ALL_PASS nonstandard_new_fixtures")
    print(f"n_cases={len(REQUIRED)} index={len(case_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
