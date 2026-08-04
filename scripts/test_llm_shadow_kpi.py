#!/usr/bin/env python3
"""llm_toolcall 影子 KPI 门禁。

对照 steps vs llm_toolcall：
- illegal_tool_calls == 0
- agree_core（can_fit + 柜数差≤1）
- 工具/阶段覆盖：intent/A/B/finalize 代理
- 无 Key 时 policy_fallback 仍须与 steps 核心一致

输出: output/competition/llm_shadow_kpi.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

OUT = ROOT / "output" / "competition"


def _coverage_ok(kpi: Dict[str, Any]) -> bool:
    """选工具/阶段覆盖：A+B 或关键 tools 出现。"""
    nodes = list(kpi.get("node_sequence") or [])
    tools = list(kpi.get("tool_sequence") or [])
    has_a = any(
        n in nodes for n in ("material_parser", "box_scheme", "structure")
    ) or any("team_a" in str(t) for t in tools)
    has_b = any(
        n in nodes for n in ("planner", "loader", "evaluator", "risk_compliance")
    ) or any("team_b" in str(t) for t in tools)
    has_fin = "finalize" in nodes or any("finalize" in str(t) for t in tools)
    # policy_fallback 可能只走 steps 节点 —— 仍算覆盖
    return (has_a and has_b) or (has_a and has_fin) or (len(nodes) >= 4)


def main() -> int:
    from packing_assistant.eval_harness import case_tiny, case_20t
    from packing_assistant.eval_workteams import run_workteam_shadow_eval

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "llm_shadow_kpi.json"

    report = run_workteam_shadow_eval(
        cases=[case_tiny, case_20t],
        out_path=out_path,
        session_prefix="llm-shadow-kpi",
    )
    agg = report.get("aggregate") or {}
    cases: List[Dict[str, Any]] = list(report.get("cases") or [])

    illegal = int(agg.get("illegal_tool_calls_total") or 0)
    agree = float(agg.get("agree_core_rate") or 0)
    pass_agree = bool(agg.get("pass_agree_core"))
    pass_illegal = bool(agg.get("pass_illegal_zero")) and illegal == 0

    cov_ok = True
    cov_detail = []
    for row in cases:
        for side in ("steps_kpi", "llm_kpi"):
            k = row.get(side) or {}
            ok = _coverage_ok(k)
            cov_detail.append(
                {
                    "id": row.get("id"),
                    "side": side,
                    "coverage_ok": ok,
                    "agent_style": k.get("agent_style") or (row.get(side.replace("_kpi", "")) or {}).get("agent_style"),
                    "illegal": k.get("illegal_tool_calls"),
                    "n_tools": k.get("n_tools"),
                }
            )
            if not ok:
                cov_ok = False

    # 路由 KPI（软，只记录）
    route_events = int(agg.get("route_events_total") or 0)
    replan_proxy = float(agg.get("avg_replan_proxy") or 0)

    # 门禁：核心一致 + 零非法 + 阶段覆盖
    gates = {
        "illegal_zero": pass_illegal,
        "agree_core": pass_agree and agree >= 0.90,
        "stage_coverage": cov_ok,
    }
    ok = all(gates.values())

    payload = {
        "ok": ok,
        "gates": gates,
        "aggregate": {
            "agree_core_rate": agree,
            "illegal_tool_calls_total": illegal,
            "route_events_total": route_events,
            "avg_replan_proxy": replan_proxy,
            "n_cases": len(cases),
            "pass_agree_core": pass_agree,
            "pass_illegal_zero": pass_illegal,
        },
        "coverage": cov_detail,
        "kpi_targets": {
            "agree_core_rate": ">=0.90",
            "illegal_tool_calls": "==0",
            "stage_coverage": "A+B or A+finalize per side",
        },
        "notes": [
            "无 DEEPSEEK_API_KEY 时 llm 为 policy_fallback，仍须 agree_core",
            "本门禁测的是影子一致性与工具边界，非 LLM 路由「聪明度」",
        ],
        "ms": report.get("ms"),
        "out_path": str(out_path),
        "raw_report_ok": report.get("ok"),
    }
    # 合并写入（覆盖 workteams 原始结构 + 门禁）
    out_path.write_text(
        json.dumps({**report, "gate_result": payload}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(
        "LLM_SHADOW_KPI",
        "ok=" + str(ok),
        "agree=" + str(agree),
        "illegal=" + str(illegal),
        "coverage=" + str(cov_ok),
        "gates=" + str(gates),
    )
    for k, v in gates.items():
        print(f"  gate {k}: {'PASS' if v else 'FAIL'}")
    if not ok:
        return 1
    print("PASS llm_toolcall shadow KPI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
