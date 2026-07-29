"""黄金评测 harness：合成 tiny/20t 等，不依赖 t80 大文件。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class EvalCase:
    id: str
    materials: List[Dict[str, Any]]
    packing_options: Dict[str, Any]
    max_containers: int = 0
    asserts: Dict[str, Any] = field(default_factory=dict)


def _mat(
    i: str,
    *,
    L: float,
    W: float,
    H: float,
    kg: float,
    name: str = "",
    part: str = "",
    note: str = "crate_equiv_est",
) -> Dict[str, Any]:
    return {
        "id": i,
        "name": name or i,
        "part_no": part or i,
        "quantity": 1,
        "weight_kg": kg,
        "total_weight_kg": kg,
        "length_mm": L,
        "width_mm": W,
        "height_mm": H,
        "note": note,
        "spec": "sim",
    }


def case_tiny() -> EvalCase:
    mats = [
        _mat("T1", L=2000, W=1100, H=1100, kg=800, name="铁架1", part="FST-T1"),
        _mat("T2", L=1500, W=1000, H=800, kg=400, name="铁架2", part="FST-T2"),
        _mat("T3", L=800, W=600, H=500, kg=80, name="五金", part="BBF-T3", note="crate="),
    ]
    return EvalCase(
        id="tiny",
        materials=mats,
        packing_options={
            "crate_passthrough": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
        max_containers=2,
        asserts={
            "can_fit": True,
            "min_mid50": 0.40,
            "max_lat": 0.15,
            "ship_ok": True,
            "max_containers_used": 2,
        },
    )


def case_20t() -> EvalCase:
    mats = []
    for i in range(12):
        mats.append(
            _mat(
                f"H{i}",
                L=2000,
                W=1100,
                H=1100,
                kg=900 + i * 30,
                name=f"重架{i}",
                part=f"FST{i:04d}",
            )
        )
    for i in range(20):
        mats.append(
            _mat(
                f"L{i}",
                L=1000,
                W=800,
                H=600,
                kg=120,
                name=f"轻箱{i}",
                part="BBF0020",
                note="crate=",
            )
        )
    # ~12*1t + 2.4t ≈ 14–18t range; pad to ~20t
    mats.append(
        _mat("PAD", L=1200, W=1000, H=800, kg=2500, name="配重", part="PAD")
    )
    return EvalCase(
        id="synth_20t",
        materials=mats,
        packing_options={
            "crate_passthrough": True,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "lns_worst": True,
            "lateral_repair": True,
            "r4_target_mid50": 0.55,
            "lat_threshold": 0.08,
        },
        max_containers=4,
        asserts={
            "can_fit": True,
            "min_mid50": 0.50,
            "max_lat": 0.10,
            "ship_ok": True,
            "max_containers_used": 4,
        },
    )


def case_lock_2c() -> EvalCase:
    c = case_20t()
    c.id = "lock_2c"
    c.packing_options = {
        **c.packing_options,
        "lock_max_containers": True,
        "meeting_cap": True,
        "container_budget": 2,
    }
    c.max_containers = 2
    c.asserts = {
        "can_fit": True,  # may fail if 20t needs more — soft: max used <=2 if can_fit
        "max_containers_used": 2,
        "min_mid50": 0.40,
        "max_lat": 0.15,
    }
    return c


DEFAULT_SUITE = [case_tiny, case_20t]


def _check(assert_spec: Dict[str, Any], plan: Dict[str, Any], ship_ok: Any) -> List[str]:
    fails = []
    if "can_fit" in assert_spec and bool(plan.get("can_fit")) != bool(assert_spec["can_fit"]):
        # lock case: allow can_fit false if over packed — only fail if required true
        if assert_spec["can_fit"] is True and not plan.get("can_fit"):
            fails.append(f"can_fit want True got {plan.get('can_fit')}")
    mid = float(plan.get("worst_mid50") or 0)
    if "min_mid50" in assert_spec and plan.get("can_fit") and mid + 1e-9 < float(assert_spec["min_mid50"]):
        fails.append(f"mid50 {mid} < {assert_spec['min_mid50']}")
    lat = float((plan.get("cog") or {}).get("lateral_eccentricity") or 0)
    if "max_lat" in assert_spec and plan.get("can_fit") and lat > float(assert_spec["max_lat"]) + 1e-9:
        fails.append(f"lat {lat} > {assert_spec['max_lat']}")
    if assert_spec.get("ship_ok") is True and plan.get("can_fit") and not ship_ok:
        fails.append("ship_ok False")
    used = int(plan.get("containers_used") or 0)
    if "max_containers_used" in assert_spec and used > int(assert_spec["max_containers_used"]):
        fails.append(f"used {used} > max {assert_spec['max_containers_used']}")
    return fails


def run_eval_suite(
    cases: Optional[List[Callable[[], EvalCase]]] = None,
    *,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    suite = cases or DEFAULT_SUITE
    results = []
    t0 = time.time()
    for factory in suite:
        case = factory() if callable(factory) else factory
        t1 = time.time()
        st = run_agent_pipeline(
            f"eval:{case.id}",
            materials=case.materials,
            container_type="40HQ",
            max_containers=case.max_containers,
            enable_auto_confirm=True,
            session_id=f"eval-{case.id}",
            save_artifacts=False,
            packing_options=case.packing_options,
        )
        plan = st.get("container_plan") or {}
        ship = st.get("ship_ok")
        fails = _check(case.asserts, plan, ship)
        row = {
            "id": case.id,
            "pass": len(fails) == 0,
            "fails": fails,
            "ms": int((time.time() - t1) * 1000),
            "can_fit": plan.get("can_fit"),
            "used": plan.get("containers_used"),
            "mid50": plan.get("worst_mid50"),
            "ship_ok": ship,
            "team_mode": st.get("team_mode"),
        }
        results.append(row)
        print(
            ("PASS" if row["pass"] else "FAIL"),
            case.id,
            row,
        )

    summary = {
        "n": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": sum(1 for r in results if not r["pass"]),
        "ms": int((time.time() - t0) * 1000),
        "results": results,
        "ok": all(r["pass"] for r in results),
    }
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
