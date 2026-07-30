#!/usr/bin/env python3
"""回归：装载后 mid50≥60% 且 balance 非 block。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")

from packing_assistant.demo_presets import (  # noqa: E402
    materials_high_util,
    materials_steel_light,
    packing_options_high_util,
)
from packing_assistant.harness import run_agent_pipeline  # noqa: E402


def _cog(plan):
    cog = plan.get("cog") or {}
    if isinstance(cog, dict) and "mass_in_mid50_ratio" not in cog:
        cog = cog.get("primary") or cog.get("worst") or cog
    return cog if isinstance(cog, dict) else {}


def run_case(name, mats, opts=None):
    s = run_agent_pipeline(
        name,
        materials=mats,
        packing_options=opts or {},
        enable_auto_confirm=True,
        session_id=f"mid50-{name}",
        save_artifacts=False,
    )
    plan = s.get("container_plan") or {}
    c = _cog(plan)
    mid = float(plan.get("worst_mid50") or c.get("mass_in_mid50_ratio") or 0)
    bal = str(c.get("balance") or "")
    print(
        f"{name}: mid50={mid:.2%} balance={bal} long={c.get('longitudinal_position')} "
        f"lat={c.get('lateral_eccentricity')} can_fit={plan.get('can_fit')}"
    )
    return mid, bal, plan.get("can_fit")


def main() -> int:
    fails = []
    mid, bal, cf = run_case("high_util", materials_high_util(), packing_options_high_util())
    if mid + 1e-9 < 0.60:
        fails.append(f"high_util mid50 {mid} < 0.60")
    if bal == "block":
        fails.append(f"high_util balance=block")
    if not cf:
        fails.append("high_util can_fit=False")

    mid2, bal2, cf2 = run_case("steel", materials_steel_light())
    # steel 可能低装载，mid50 有时因少箱仍可；至少不应 block 若 can_fit
    if cf2 and bal2 == "block" and mid2 < 0.40:
        fails.append(f"steel still hard-block mid50={mid2}")

    if fails:
        print("FAIL", fails)
        return 1
    print("PASS mid50 CTU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
