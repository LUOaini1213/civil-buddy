#!/usr/bin/env python3
"""Run demo-profile pipeline on real VMU packing lists + a generic furniture table."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_xlsx_autohdr(path: Path, sheet: str) -> Dict[str, Any]:
    import openpyxl

    from packing_assistant.tools.table_mapper import parse_table_rows

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet]
    raw = list(ws.iter_rows(values_only=True))
    wb.close()
    hdr_i = 0
    for i, row in enumerate(raw[:20]):
        blob = " ".join(str(c or "") for c in row)
        if "名称" in blob and ("长" in blob or "长度" in blob):
            hdr_i = i
            break
    headers = [str(c or "").strip() for c in raw[hdr_i]]
    rows: List[Dict[str, Any]] = []
    for row in raw[hdr_i + 1 :]:
        d = {
            headers[j]: (row[j] if j < len(row) else None)
            for j in range(len(headers))
        }
        rows.append(d)
    parsed = parse_table_rows(rows, headers=headers, source=f"xlsx:{sheet}")
    from packing_assistant.tools.rack_fold import detect_rack_type

    title = " ".join(str(c or "") for row in raw[:6] for c in (row or []))
    title = f"{sheet} {title}"
    rtype = detect_rack_type(title)
    if rtype:
        mats = list(parsed.get("materials") or [])
        prefix = f"{sheet}-"
        for i, m in enumerate(mats, 1):
            m["id"] = f"{prefix}{i:03d}"
            m["packing_list_rack"] = rtype
            m["packing_list_title"] = title[:80]
            meta = dict(m.get("meta") or {})
            meta["packing_list_rack"] = rtype
            m["meta"] = meta
        parsed["materials"] = mats
        parsed["detected_rack_type"] = rtype
    return parsed


def _summarize_mats(mats: Sequence[Dict[str, Any]]) -> str:
    n = len(mats)
    wt = sum(float(m.get("total_weight_kg") or 0) for m in mats)
    missing = sum(
        1
        for m in mats
        if not (
            float(m.get("length_mm") or 0) > 0
            and float(m.get("width_mm") or 0) > 0
            and float(m.get("height_mm") or 0) > 0
        )
    )
    return f"n={n} weight_kg={wt:.1f} missing_lwh={missing}"


def _run_ticket(
    label: str,
    mats: List[Dict[str, Any]],
    *,
    packing_options: Optional[Dict[str, Any]] = None,
    do_team_b: bool = False,
) -> Dict[str, Any]:
    from packing_assistant.harness import (
        apply_user_confirmation,
        run_team_a,
        run_team_b,
    )
    from packing_assistant.pack_profile import apply_pack_profile, should_skip_structure

    opts = apply_pack_profile(packing_options or {})
    skip, reason = should_skip_structure(
        materials=mats, boxes=[], packing_options=opts
    )
    print(f"\n===== {label} =====")
    print("materials", _summarize_mats(mats))
    print("pack_profile", opts.get("pack_profile"))
    print("structure_skip_pred", skip, reason)

    t0 = time.perf_counter()
    a = run_team_a(
        label,
        materials=mats,
        session_id=f"real-{label[:24]}",
        packing_options=opts,
    )
    dt_a = time.perf_counter() - t0
    ga = a.get("global_advice") or {}
    print(
        f"team_a {dt_a:.2f}s phase={a.get('phase')} "
        f"boxes={len(a.get('boxes') or [])} "
        f"skipped={a.get('structure_skipped') or ga.get('skipped')} "
        f"skip_reason={a.get('structure_skip_reason') or ga.get('reason')}"
    )
    if not do_team_b:
        return a

    t1 = time.perf_counter()
    confirmed = apply_user_confirmation(a, action="confirm", container_type="40HQ")
    b = run_team_b(confirmed)
    dt_b = time.perf_counter() - t1
    plan = b.get("container_plan") or {}
    print(
        f"team_b {dt_b:.2f}s phase={b.get('phase')} "
        f"n0={plan.get('n0')} used={plan.get('containers_used')} "
        f"can_fit={plan.get('can_fit')} ship_ok={b.get('ship_ok')} "
        f"mid50={plan.get('worst_mid50')} "
        f"profile={plan.get('pack_profile') or (b.get('packing_options') or {}).get('pack_profile')}"
    )
    return b


def main() -> int:
    from packing_assistant.tools.table_mapper import parse_table_file

    furn = parse_table_file(ROOT / "test/generic_tables/G12_furniture/materials.csv")
    print("furniture parse ok=", furn.get("ok"), furn.get("stats"))
    _run_ticket(
        "furniture-G12",
        list(furn.get("materials") or []),
        packing_options={"profile_id": "generic_table", "crate_passthrough": True},
        do_team_b=True,
    )

    xlsx = ROOT / "data/samples/vmu-fst-iron-sample.xlsx"
    for sheet in ("7-20装货单1柜", "7-20装货单2柜"):
        parsed = _load_xlsx_autohdr(xlsx, sheet)
        print(f"\nVMU sheet {sheet} parse ok={parsed.get('ok')} stats={parsed.get('stats')}")
        mats = list(parsed.get("materials") or [])
        if not mats:
            print("SKIP empty parse")
            continue
        _run_ticket(
            f"vmu-{sheet}",
            mats,
            packing_options={"profile_id": "steel", "crate_passthrough": True},
            do_team_b=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
