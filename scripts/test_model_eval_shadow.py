#!/usr/bin/env python3
"""模型评测回归：workteams 影子（steps vs llm）+ 诚实标签。

- 驱动真实 run_workteam_shadow_eval / public_response / _path_honesty
- 禁止把本地 SCORECARD 当对外总分（仅打印对照）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.eval_harness import case_tiny
    from packing_assistant.eval_workteams import run_workteam_shadow_eval
    from packing_assistant.harness import public_response, _path_honesty

    out = ROOT / "output" / "eval_workteams_model_eval.json"
    report = run_workteam_shadow_eval(cases=[case_tiny], out_path=out)
    agg = report.get("aggregate") or {}
    ok = bool(report.get("ok"))
    agree = float(agg.get("agree_core_rate") or 0)
    illegal = int(agg.get("illegal_tool_calls_total") or 0)
    pass_agree = bool(agg.get("pass_agree_core"))
    pass_illegal = bool(agg.get("pass_illegal_zero"))

    print(
        f"WORKTEAM_SHADOW ok={ok} agree={agree} illegal={illegal} "
        f"pass_agree={pass_agree} pass_illegal={pass_illegal} out={out}"
    )
    assert pass_agree and agree >= 0.99, agg
    assert pass_illegal and illegal == 0, agg

    # Honesty: llm path reference_only
    case = report.get("cases") or report.get("results") or []
    # rebuild path_honesty for llm policy_fallback style
    ph_llm = _path_honesty(
        {
            "agent_style": "policy_fallback",
            "agent_mode": "llm_toolcall",
            "container_plan": {"containers_used": 1, "can_fit": True},
        }
    )
    assert ph_llm.get("reference_only") is True, ph_llm
    assert ph_llm.get("cabin_count_reference_only") is True, ph_llm
    assert ph_llm.get("booking_authority") == "steps_tools", ph_llm
    pub = public_response(
        {
            "agent_style": "policy_fallback",
            "agent_mode": "llm_toolcall",
            "container_plan": {"containers_used": 1, "can_fit": True},
            "phase": "done",
            "messages": [],
            "agent_steps": [],
        }
    )
    assert pub.get("path_honesty", {}).get("reference_only") is True
    print(
        f"honesty reference_only={ph_llm.get('reference_only')} "
        f"booking_authority={ph_llm.get('booking_authority')} "
        f"ui_label={ph_llm.get('ui_label')}"
    )

    # Explicit: local scorecard is NOT external lead
    scorecard = ROOT / "output" / "competition" / "SCORECARD.md"
    local_note = "local_SCORECARD~9.75_not_external_lead"
    if scorecard.is_file():
        text = scorecard.read_text(encoding="utf-8", errors="replace")
        has_975 = "9.75" in text
        print(f"scorecard_present={has_975} note={local_note}")
    else:
        print(f"scorecard_present=False note={local_note}")

    # Persist compact summary next to report
    summary = {
        "ok": True,
        "agree_core_rate": agree,
        "illegal_tool_calls_total": illegal,
        "reference_only": True,
        "booking_authority": "steps_tools",
        "local_scorecard_external_lead": False,
        "external_network_score_note": "use networked calibration (~9.10), not local 9.75",
    }
    sum_path = ROOT / "output" / "eval_workteams_model_eval_summary.json"
    sum_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ALL_PASS model_eval_shadow")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
