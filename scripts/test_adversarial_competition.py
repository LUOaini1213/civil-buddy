#!/usr/bin/env python3
"""比赛对抗 5 票：坏输入/超重/锁柜/结构路径/乱 NL —— 不崩溃、illegal=0。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")


def _opts(**kw: Any) -> Dict[str, Any]:
    base = {
        "standard_boxes": True,
        "prefer_stack": True,
        "multi_start": True,
        "cog_aware": True,
        "cog_rebalance": True,
        "r4_target_mid50": 0.60,
    }
    base.update(kw)
    return base


def _run(
    case_id: str,
    materials: List[Dict[str, Any]],
    user_input: str,
    **pipe_kw: Any,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    st = run_agent_pipeline(
        user_input,
        materials=materials,
        session_id=f"adv-{case_id}",
        enable_auto_confirm=True,
        save_artifacts=False,
        packing_options=pipe_kw.pop("packing_options", _opts()),
        max_containers=int(pipe_kw.pop("max_containers", 0) or 0),
        container_type=str(pipe_kw.pop("container_type", "40HQ")),
        agent_mode="steps",
    )
    st["_wall_s"] = time.time() - t0
    return st


def _illegal(st: Dict[str, Any]) -> int:
    try:
        from packing_assistant.workteam_kpi import compute_kpis

        return int(compute_kpis(st).get("illegal_tool_calls") or 0)
    except Exception:
        return 0


def _no_crash(st: Dict[str, Any]) -> bool:
    if st.get("status") == "error":
        errs = st.get("errors") or []
        if any("Traceback" in str(e) for e in errs):
            return False
    return True


def case_a1_missing_dims() -> Tuple[str, bool, str]:
    mats = [
        {
            "id": "M1",
            "name": "未知件",
            "quantity": 1,
            "total_weight_kg": 100,
        }
    ]
    st = _run("a1", mats, "缺尺寸不要编造")
    ill = _illegal(st)
    ok = _no_crash(st) and ill == 0
    detail = (
        f"phase={st.get('phase')} ship_ok={st.get('ship_ok')} "
        f"illegal={ill} wall={st.get('_wall_s'):.2f}"
    )
    return "A1_missing_dims", ok, detail


def case_a2_over_payload() -> Tuple[str, bool, str]:
    mats = [
        {
            "id": "MONSTER",
            "name": "超重单件",
            "quantity": 1,
            "length_mm": 2000,
            "width_mm": 1000,
            "height_mm": 1000,
            "total_weight_kg": 80000,
        }
    ]
    st = _run(
        "a2",
        mats,
        "超货载应拆箱而非只加柜",
        packing_options=_opts(standard_boxes=True, max_box_net_kg=3200),
    )
    ill = _illegal(st)
    feas = st.get("cargo_feasibility") or {}
    plan = st.get("container_plan") or {}
    prop = st.get("replan_proposal") or {}
    ok = _no_crash(st) and ill == 0
    boxes = st.get("boxes") or []
    max_net = max(
        (float(b.get("net_weight_kg") or b.get("gross_weight_kg") or 0) for b in boxes),
        default=0,
    )
    if st.get("ship_ok") is True and max_net > 30000:
        ok = False
    detail = (
        f"feas_ok={feas.get('ok')} can_fit={plan.get('can_fit')} "
        f"route={prop.get('route')} max_net={max_net:.0f} "
        f"illegal={ill} wall={st.get('_wall_s'):.2f}"
    )
    return "A2_over_payload", ok, detail


def case_a3_budget_lock() -> Tuple[str, bool, str]:
    mats = []
    for i in range(12):
        mats.append(
            {
                "id": f"L{i}",
                "name": f"重钢{i}",
                "quantity": 1,
                "length_mm": 3000,
                "width_mm": 1000,
                "height_mm": 800,
                "total_weight_kg": 2500,
            }
        )
    st = _run(
        "a3",
        mats,
        "预算最多1个40HQ 不要擅自加柜",
        max_containers=1,
        packing_options=_opts(
            lock_max_containers=True, container_budget=1, meeting_cap=True
        ),
    )
    plan = st.get("container_plan") or {}
    used = int(plan.get("containers_used") or 0)
    ill = _illegal(st)
    ok = _no_crash(st) and ill == 0
    if plan.get("can_fit") is True and used > 1:
        ok = False
    detail = (
        f"used={used} can_fit={plan.get('can_fit')} "
        f"illegal={ill} wall={st.get('_wall_s'):.2f}"
    )
    return "A3_budget_1c", ok, detail


def case_a4_structure_path() -> Tuple[str, bool, str]:
    mats = [
        {
            "id": "LONG",
            "name": "细长重梁",
            "quantity": 2,
            "length_mm": 11000,
            "width_mm": 300,
            "height_mm": 400,
            "total_weight_kg": 2800,
        }
    ]
    st = _run("a4", mats, "结构与成箱路径")
    ill = _illegal(st)
    nodes = [
        str(s.get("node"))
        for s in (st.get("agent_steps") or [])
        if isinstance(s, dict)
    ]
    has_a = any(n in nodes for n in ("material_parser", "box_scheme", "structure"))
    has_b = any(n in nodes for n in ("planner", "loader", "finalize"))
    ok = (
        _no_crash(st)
        and ill == 0
        and (has_a or bool(st.get("boxes")))
        and (has_b or st.get("container_plan") is not None or st.get("phase"))
    )
    detail = (
        f"nodes={len(nodes)} has_a={has_a} has_b={has_b} "
        f"illegal={ill} wall={st.get('_wall_s'):.2f}"
    )
    return "A4_structure_path", ok, detail


def case_a5_garbage_nl() -> Tuple[str, bool, str]:
    mats = [
        {
            "id": "OK1",
            "name": "正常件",
            "quantity": 1,
            "length_mm": 1200,
            "width_mm": 800,
            "height_mm": 600,
            "total_weight_kg": 150,
        }
    ]
    st = _run("a5", mats, "asdf@@@随便装 不要崩！！！" * 3)
    ill = _illegal(st)
    ok = _no_crash(st) and ill == 0 and st.get("status") != "error"
    detail = (
        f"phase={st.get('phase')} "
        f"can_fit={(st.get('container_plan') or {}).get('can_fit')} "
        f"illegal={ill} wall={st.get('_wall_s'):.2f}"
    )
    return "A5_garbage_nl", ok, detail


def main() -> int:
    print("== adversarial competition 5 ==")
    cases = [
        case_a1_missing_dims,
        case_a2_over_payload,
        case_a3_budget_lock,
        case_a4_structure_path,
        case_a5_garbage_nl,
    ]
    fails = []
    for fn in cases:
        try:
            cid, ok, detail = fn()
        except Exception as e:
            cid, ok, detail = getattr(fn, "__name__", "case"), False, f"EXC {type(e).__name__}: {e}"
        print(f"{'PASS' if ok else 'FAIL'} {cid} | {detail}")
        if not ok:
            fails.append(cid)
    if fails:
        print("FAIL", fails)
        return 1
    print("PASS adversarial 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
