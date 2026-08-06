#!/usr/bin/env python3
"""均匀重货 mid50 回归：真实 run_agent_pipeline + materials_high_util_uniform。

要求：can_fit 时 mid50 ≥ 0.60（CTU 硬舒适下限）；≥0.70 仅打印 COMFORT 不强制。
对照：默认 high_util（中段偏重）亦打印实测。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")


def _mid(plan) -> float:
    mid = plan.get("worst_mid50")
    if mid is not None:
        return float(mid)
    cog = plan.get("cog") or {}
    if isinstance(cog, dict):
        if cog.get("mass_in_mid50_ratio") is not None:
            return float(cog["mass_in_mid50_ratio"])
        for k in ("worst", "primary"):
            sub = cog.get(k) or {}
            if isinstance(sub, dict) and sub.get("mass_in_mid50_ratio") is not None:
                return float(sub["mass_in_mid50_ratio"])
    return 0.0


def main() -> int:
    from packing_assistant.demo_presets import (
        materials_high_util,
        materials_high_util_uniform,
        packing_options_high_util,
    )
    from packing_assistant.harness import run_agent_pipeline

    fails = []
    opts = packing_options_high_util()

    st_u = run_agent_pipeline(
        "uniform mid50 probe",
        materials=materials_high_util_uniform(),
        packing_options=opts,
        enable_auto_confirm=True,
        session_id="mid50-uniform",
        save_artifacts=False,
    )
    plan_u = st_u.get("container_plan") or {}
    mid_u = _mid(plan_u)
    print(
        f"uniform: mid50={mid_u:.4f} can_fit={plan_u.get('can_fit')} "
        f"ship_ok={st_u.get('ship_ok')} used={plan_u.get('containers_used')}"
    )
    if plan_u.get("can_fit") is not True:
        fails.append("uniform can_fit!=True")
    if mid_u + 1e-9 < 0.60:
        fails.append(f"uniform mid50 {mid_u} < 0.60 CTU")
    if mid_u + 1e-9 >= 0.70:
        print("COMFORT uniform mid50>=0.70")
    else:
        print(f"NOTE uniform mid50={mid_u:.4f} below 0.70 comfort (honest)")

    st_h = run_agent_pipeline(
        "biased high_util mid50 probe",
        materials=materials_high_util(),
        packing_options=opts,
        enable_auto_confirm=True,
        session_id="mid50-biased",
        save_artifacts=False,
    )
    plan_h = st_h.get("container_plan") or {}
    mid_h = _mid(plan_h)
    print(
        f"biased: mid50={mid_h:.4f} can_fit={plan_h.get('can_fit')} "
        f"used={plan_h.get('containers_used')}"
    )
    if plan_h.get("can_fit") is True and mid_h + 1e-9 < 0.60:
        fails.append(f"biased mid50 {mid_h} < 0.60")

    if fails:
        print("FAIL mid50_uniform", fails)
        return 1
    print("ALL_PASS mid50_uniform")
    print(f"uniform_mid50={mid_u:.4f} biased_mid50={mid_h:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
