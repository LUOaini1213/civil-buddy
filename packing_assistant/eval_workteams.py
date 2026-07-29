"""Workteams 影子评测：同一 case 跑 steps vs llm_toolcall，并汇总路由/选工具 KPI。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from packing_assistant.eval_harness import EvalCase, case_tiny, case_20t
from packing_assistant.workteam_kpi import (
    aggregate_kpi_rows,
    compare_kpis,
    compute_kpis,
)


def _run_one(
    case: EvalCase,
    *,
    agent_mode: str,
    session_prefix: str,
) -> Dict[str, Any]:
    from packing_assistant.harness import run_agent_pipeline

    t0 = time.time()
    st = run_agent_pipeline(
        f"workteam-shadow:{case.id}:{agent_mode}",
        materials=case.materials,
        container_type="40HQ",
        max_containers=case.max_containers,
        enable_auto_confirm=True,
        session_id=f"{session_prefix}-{case.id}-{agent_mode}",
        save_artifacts=False,
        packing_options=case.packing_options,
        agent_mode=agent_mode,
        max_llm_rounds=12,
    )
    ms = int((time.time() - t0) * 1000)
    kpi = compute_kpis(st)
    plan = st.get("container_plan") or {}
    return {
        "agent_mode": agent_mode,
        "ms": ms,
        "kpi": kpi,
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "ship_ok": st.get("ship_ok"),
        "agent_style": st.get("agent_style"),
        "team_mode": st.get("team_mode"),
        "n_steps": len(st.get("agent_steps") or []),
        "errors": list(st.get("errors") or [])[:5],
    }


def shadow_one_case(
    case: EvalCase,
    *,
    session_prefix: str = "wt-shadow",
) -> Dict[str, Any]:
    """单 case 影子：steps + llm_toolcall。"""
    steps_run = _run_one(case, agent_mode="steps", session_prefix=session_prefix)
    llm_run = _run_one(case, agent_mode="llm_toolcall", session_prefix=session_prefix)
    cmp_ = compare_kpis(steps_run["kpi"], llm_run["kpi"])
    return {
        "id": case.id,
        "steps": {
            "ms": steps_run["ms"],
            "can_fit": steps_run["can_fit"],
            "containers_used": steps_run["containers_used"],
            "ship_ok": steps_run["ship_ok"],
            "agent_style": steps_run["agent_style"],
            "n_steps": steps_run["n_steps"],
            "errors": steps_run["errors"],
        },
        "llm": {
            "ms": llm_run["ms"],
            "can_fit": llm_run["can_fit"],
            "containers_used": llm_run["containers_used"],
            "ship_ok": llm_run["ship_ok"],
            "agent_style": llm_run["agent_style"],
            "n_steps": llm_run["n_steps"],
            "errors": llm_run["errors"],
        },
        "steps_kpi": steps_run["kpi"],
        "llm_kpi": llm_run["kpi"],
        "compare": cmp_,
        "pass_agree": bool(cmp_.get("agree_core")),
    }


DEFAULT_SHADOW_SUITE = [case_tiny, case_20t]


def run_workteam_shadow_eval(
    cases: Optional[List[Callable[[], EvalCase]]] = None,
    *,
    out_path: Optional[Path] = None,
    session_prefix: str = "wt-shadow",
) -> Dict[str, Any]:
    """
    跑影子套件。

    汇总:
      agree_core_rate (can_fit + 柜数近似一致)
      coverage / illegal tools KPI
    """
    suite = cases or DEFAULT_SHADOW_SUITE
    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for factory in suite:
        case = factory() if callable(factory) else factory
        row = shadow_one_case(case, session_prefix=session_prefix)
        rows.append(row)
        tag = "PASS" if row.get("pass_agree") else "DIFF"
        print(
            tag,
            case.id,
            "steps_fit=",
            row["steps"]["can_fit"],
            "llm_fit=",
            row["llm"]["can_fit"],
            "used",
            row["steps"]["containers_used"],
            "vs",
            row["llm"]["containers_used"],
            "style",
            row["llm"].get("agent_style"),
        )

    agg = aggregate_kpi_rows(rows)
    # 路由 KPI 汇总
    route_events = 0
    replan_sum = 0
    for r in rows:
        for side in ("steps_kpi", "llm_kpi"):
            k = r.get(side) or {}
            route_events += int(k.get("n_route_events") or 0)
            replan_sum += int(k.get("replan_round") or 0) + int(
                k.get("ship_replan_round") or 0
            )

    report = {
        "ok": bool(agg.get("pass_agree_core")) and bool(agg.get("pass_illegal_zero")),
        "ms": int((time.time() - t0) * 1000),
        "aggregate": {
            **agg,
            "route_events_total": route_events,
            "replan_rounds_sum": replan_sum,
            "avg_replan_proxy": round(replan_sum / max(1, len(rows) * 2), 3),
        },
        "cases": rows,
        "kpi_targets": {
            "agree_core_rate": ">=0.90",
            "illegal_tool_calls": "==0",
            "avg_replan_proxy": "跟踪（软）",
        },
        "notes": [
            "llm_toolcall 无 DEEPSEEK_API_KEY 时为 policy_fallback，仍应与 steps 核心一致",
            "agree_core = can_fit 一致 且 柜数差≤1",
        ],
    }
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        report["out_path"] = str(out_path)
    return report
