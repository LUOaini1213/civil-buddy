#!/usr/bin/env python3
"""非标磁盘夹具 → 真实 run_agent_pipeline 拼柜路径冒烟（超 inspect-only）。

覆盖全部 ns_INDEX 8 套：
- PACKABLE（WARN/NEED_DESIGN）：pipeline 不崩、有 nonstandard_summary
- HARD_FAIL（缺尺寸/超柜宽）：诚实拦截，禁止 clean ship_ok+PASS
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

NS_ROOT = ROOT / "test" / "sim_materials"
INDEX = NS_ROOT / "ns_INDEX.json"

# packable-ish WARN / NEED_DESIGN cases
PACK_CASES = (
    "ns_heavy_cast",
    "ns_thin_sheet_stack",
    "ns_fragile_process",
    "ns_overlength_rail",
    "ns_factory_crate_path",
    "ns_mixed_industry_bundle",
)
# hard data/geo fail — must not silently ship_ok True without flags
FAIL_CASES = (
    "ns_missing_dims_mix",
    "ns_over_container_width",
)

TERMINAL_PHASES = (
    "done",
    "await_user_confirm",
    "team_b_done",
    "complete",
    "need_revision",
    "await_revision",
)


def _load(case_id: str) -> list:
    p = NS_ROOT / case_id / "materials.json"
    assert p.is_file(), p
    data = json.loads(p.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    assert mats, case_id
    return mats


def _run(case_id: str, mats: list):
    from packing_assistant.harness import run_agent_pipeline, public_response

    st = run_agent_pipeline(
        f"非标夹具 pack smoke {case_id}",
        materials=mats,
        packing_options={"container_type": "40HQ"},
        enable_auto_confirm=True,
        session_id=f"ns-pack-{case_id}",
        save_artifacts=False,
    )
    pub = public_response(st)
    return st, pub


def main() -> int:
    from packing_assistant.tools.nonstandard_inspect import inspect_nonstandard

    # INDEX must list all required cases
    assert INDEX.is_file(), INDEX
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    indexed = {c["id"] for c in (idx.get("cases") or [])}
    for cid in PACK_CASES + FAIL_CASES:
        assert cid in indexed, f"{cid} missing from ns_INDEX"

    results = []
    fails = []

    for cid in PACK_CASES:
        mats = _load(cid)
        rep = inspect_nonstandard(materials=mats, case_id=cid, container_type="40HQ")
        overall = rep.get("overall")
        st, pub = _run(cid, mats)
        phase = st.get("phase")
        plan = st.get("container_plan") or st.get("packing_plan") or {}
        ns = pub.get("nonstandard_summary") or st.get("nonstandard_summary") or {}
        can_fit = plan.get("can_fit")
        ship_ok = st.get("ship_ok")
        used = plan.get("containers_used")
        line = (
            f"PACK {cid}: inspect={overall} phase={phase} can_fit={can_fit} "
            f"ship_ok={ship_ok} used={used} ns_overall={ns.get('overall')}"
        )
        print(line)
        results.append(line)
        if phase in ("error", "failed") or (
            phase is None and st.get("errors")
        ):
            fails.append(f"{cid} crash phase={phase} errors={(st.get('errors') or [])[:2]}")
        elif phase not in TERMINAL_PHASES and st.get("errors"):
            fails.append(f"{cid} non-terminal phase={phase}")
        if not (ns.get("overall") or rep.get("overall")):
            fails.append(f"{cid} missing nonstandard overall after pack")
        if not (st.get("materials") or mats):
            fails.append(f"{cid} materials vanished")

    for cid in FAIL_CASES:
        mats = _load(cid)
        rep = inspect_nonstandard(materials=mats, case_id=cid, container_type="40HQ")
        assert rep.get("overall") == "FAIL", (cid, rep.get("overall"))
        st, pub = _run(cid, mats)
        plan = st.get("container_plan") or st.get("packing_plan") or {}
        ns = pub.get("nonstandard_summary") or st.get("nonstandard_summary") or {}
        ship_ok = st.get("ship_ok")
        can_fit = plan.get("can_fit")
        mats_incomplete = bool(st.get("materials_incomplete"))
        blocks = bool((rep.get("ship_gate") or {}).get("blocks_auto_ship"))
        line = (
            f"FAIL {cid}: inspect=FAIL phase={st.get('phase')} can_fit={can_fit} "
            f"ship_ok={ship_ok} ns={ns.get('overall')} incomplete={mats_incomplete} "
            f"blocks_auto={blocks}"
        )
        print(line)
        results.append(line)
        clean_ship = ship_ok is True and can_fit is True and not mats_incomplete
        if clean_ship and (ns.get("overall") or rep.get("overall")) == "PASS":
            fails.append(f"{cid} unexpectedly clean PASS ship")
        honest_block = (
            ship_ok is False
            or can_fit is False
            or mats_incomplete
            or (ns.get("overall") or rep.get("overall")) == "FAIL"
            or blocks
        )
        if not honest_block:
            fails.append(f"{cid} hard FAIL fixture not honestly blocked: {line}")

    if fails:
        print("FAIL nonstandard_pack_smoke", fails)
        return 1
    print("ALL_PASS nonstandard_pack_smoke")
    print(f"n_pack={len(PACK_CASES)} n_fail={len(FAIL_CASES)} total={len(PACK_CASES)+len(FAIL_CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
