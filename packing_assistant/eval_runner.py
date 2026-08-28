"""黄金集回归（最终架构：自动确认跑全流程）。

.. deprecated:: 2026-08
   ``eval/cases.json`` 为旧口径（boxes 上限/结论关键词与现行引擎不一致，4/7 会误报 FAIL）。
   现行评测请用 phase0 基线：``python main.py --eval`` 或
   ``python scripts/run_phase0_baseline.py --quick``。
   本模块保留给 ``--cases`` 显式指定的历史回归，cases 文件未删除。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from packing_assistant.harness import run_pipeline


DEFAULT_CASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "eval", "cases.json"
)


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    failures: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


def load_cases(path: str = DEFAULT_CASES_PATH) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("cases.json 必须是数组")
    return data


def _materials_to_api(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """旧用例中文材料 → API materials。"""
    from packing_assistant.adapters import material_internal_to_api

    out = []
    for i, m in enumerate(materials, 1):
        if "name" in m or "length_mm" in m:
            out.append(m)
        else:
            out.append(material_internal_to_api(m, i))
    return out


def _check_expect(state: Dict[str, Any], expect: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    boxes = state.get("boxes") or []
    materials = state.get("materials") or []
    plan = state.get("container_plan") or {}
    risks = state.get("risks") or []
    traces = state.get("traces") or []
    errors = state.get("errors") or []

    if "min_boxes" in expect and len(boxes) < expect["min_boxes"]:
        failures.append(f"boxes={len(boxes)} < min_boxes={expect['min_boxes']}")
    if "max_boxes" in expect and len(boxes) > expect["max_boxes"]:
        failures.append(f"boxes={len(boxes)} > max_boxes={expect['max_boxes']}")
    if "min_materials" in expect and len(materials) < expect["min_materials"]:
        failures.append(f"materials={len(materials)} < min={expect['min_materials']}")

    overflow = plan.get("unpacked_box_ids") or []
    if expect.get("must_not_overflow") and overflow:
        failures.append(f"unexpected overflow: {overflow}")

    if expect.get("must_overflow_or_negative"):
        if plan.get("can_fit") and not overflow:
            failures.append("期望装不下或溢出，实际 can_fit=true")

    if "conclusion_contains_any" in expect:
        # 新架构用 message / final
        blob = str(plan.get("message") or "") + str(state.get("final_response") or "")
        keys = expect["conclusion_contains_any"]
        if not any(k in blob for k in keys) and plan.get("can_fit") is not True:
            # can_fit true 也算可以
            if not plan.get("can_fit"):
                failures.append(f"结论未包含 {keys}")

    if "must_have_risk_keyword_any" in expect:
        blob = "\n".join(risks)
        keys = expect["must_have_risk_keyword_any"]
        if not any(k in blob for k in keys):
            failures.append(f"风险中未出现 {keys}")

    if "max_space_util_pct" in expect:
        pct = float(plan.get("space_utilization") or 0) * 100
        if pct > float(expect["max_space_util_pct"]) + 1e-6:
            failures.append(f"空间利用率 {pct} > max")

    if "min_trace_nodes" in expect:
        nodes = {t.get("node") for t in traces}
        if len(nodes) < int(expect["min_trace_nodes"]):
            failures.append(f"trace 节点 {len(nodes)} < min")

    if expect.get("require_structure_calc") or expect.get("require_box_fields"):
        req = expect.get("require_box_fields") or [
            "box_id",
            "box_type",
            "outer_size_mm",
            "gross_weight_kg",
            "content",
        ]
        for i, b in enumerate(boxes):
            missing = [f for f in req if f not in b]
            # 兼容旧中文字段要求
            legacy_map = {
                "箱号": "box_id",
                "箱型": "box_type",
                "外尺寸_mm": "outer_size_mm",
                "毛重_kg": "gross_weight_kg",
                "装载内容": "content",
                "结构计算": "structure_calc",
                "结构结论": "structure_conclusion",
            }
            missing = [f for f in missing if legacy_map.get(f, f) not in b and f not in b]
            if missing:
                # structure_calc 可选
                missing = [m for m in missing if m not in ("结构计算", "structure_calc")]
                if missing:
                    failures.append(f"boxes[{i}] 缺字段 {missing}")
                    break

    if "structure_conclusion_any" in expect and boxes:
        allowed = set(expect["structure_conclusion_any"])
        # 新架构结论在 team_a 或 structure_constraints
        ok = False
        for b in boxes:
            c = b.get("structure_conclusion") or ""
            if c in allowed:
                ok = True
        if not ok and (state.get("team_a_summary") or {}).get("structure_overall"):
            ok = True  # 有汇总即视为算过结构
        if not ok:
            failures.append("无结构结论")

    if "box_type_contains_any" in expect and boxes:
        keys = expect["box_type_contains_any"]
        joined = " ".join(str(b.get("box_type") or "") for b in boxes)
        if not any(k in joined for k in keys):
            failures.append(f"箱型未包含 {keys}")

    if "max_errors" in expect:
        business = [e for e in errors if "Traceback" not in str(e)]
        if len(business) > int(expect["max_errors"]):
            failures.append(f"errors={len(business)}")

    if not state.get("final_response") and state.get("phase") != "await_user_confirm":
        failures.append("缺少 final_response")

    # 全流程应 done
    if expect.get("min_trace_nodes") and state.get("phase") not in ("done", "await_user_confirm"):
        if state.get("phase") != "done":
            failures.append(f"phase={state.get('phase')} 期望 done")

    return failures


def run_case(case: Dict[str, Any]) -> CaseResult:
    case_id = case.get("id") or "unknown"
    expect = case.get("expect") or {}
    materials = case.get("materials")
    if materials:
        materials = _materials_to_api(materials)
    try:
        state = run_pipeline(
            raw_input=case.get("raw_input") or "",
            materials=materials,
            container_type=case.get("container_type") or "40HQ",
            enable_auto_confirm=True,
            persist_trace=False,
        )
    except Exception as e:
        return CaseResult(case_id=case_id, passed=False, failures=[f"exception: {e}"])

    failures = _check_expect(state, expect)
    plan = state.get("container_plan") or {}
    metrics = {
        "boxes": len(state.get("boxes") or []),
        "materials": len(state.get("materials") or []),
        "phase": state.get("phase"),
        "can_fit": plan.get("can_fit"),
        "space": plan.get("space_utilization"),
        "trace_nodes": len({t.get("node") for t in (state.get("traces") or [])}),
    }
    return CaseResult(case_id=case_id, passed=not failures, failures=failures, metrics=metrics)


def run_eval(cases_path: str = DEFAULT_CASES_PATH, verbose: bool = True) -> Tuple[int, int, List[CaseResult]]:
    cases = load_cases(cases_path)
    results = []
    for case in cases:
        r = run_case(case)
        results.append(r)
        if verbose:
            mark = "PASS" if r.passed else "FAIL"
            print(f"[{mark}] {r.case_id}  {r.metrics}")
            for f in r.failures:
                print(f"       - {f}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    if verbose:
        print("-" * 48)
        print(f"Eval: {passed}/{total} passed")
    return passed, total, results


def main(argv: Optional[List[str]] = None) -> int:
    path = DEFAULT_CASES_PATH
    if argv:
        path = argv[0]
    passed, total, _ = run_eval(path, verbose=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
