#!/usr/bin/env python3
"""Every roster id has exactly one 易标/pack-agent plan. No forbidden goals."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.expert_roster import list_experts
    from packing_assistant.post_horizon import (
        FORBIDDEN_GOALS,
        YIBIAO_STEPS,
        build_post_plans,
        coverage_pairs,
        horizon_order,
        render_markdown,
    )

    roster = [e.id for e in list_experts()]
    plans = build_post_plans()
    ids = [p["id"] for p in plans]
    assert ids == roster, (set(roster) - set(ids), set(ids) - set(roster), len(ids))
    assert len(ids) == len(set(ids)) == 66
    pairs = coverage_pairs()
    assert [a for a, _ in pairs] == roster
    assert all(lane.startswith("lane-") for _, lane in pairs)

    bp = next(p for p in plans if p["id"] == "bid-parse")
    assert bp["benchmark"] == "yibiao"
    for s in YIBIAO_STEPS:
        assert s in bp["steps"] and bp["steps"][s], s
    cons = next(p for p in plans if p["id"] == "construction")
    assert all(s in cons["steps"] for s in YIBIAO_STEPS)
    pack = next(p for p in plans if p["id"] == "pack-ship")
    assert pack["benchmark"] == "pack-agent"
    assert "list" in pack["steps"] and "plan" in pack["steps"] and "export" in pack["steps"]
    assert "UNSPECIFIED" in pack["steps"]["can_fit"]
    assert "UNSPECIFIED" in pack["next_knife"] and "xyz" in pack["next_knife"]
    knives = [p["next_knife"] for p in plans]
    assert len(set(knives)) == 66, f"duplicate next_knife {len(set(knives))}"

    blob = render_markdown(plans)
    ho = "\n".join(horizon_order())
    assert ho.strip()
    for bad in FORBIDDEN_GOALS:
        # may appear as 不以…为完成目标
        assert f"{bad}为完成" not in blob.replace(" ", "")
        assert bad not in ho
    doc = ROOT / "docs" / "civil-buddy" / "post-horizon-2026-08-17.md"
    if doc.is_file():
        text = doc.read_text(encoding="utf-8")
        for eid in roster:
            assert f"### {eid}" in text, eid
        assert "长程总序" in text
    print("PASS post_horizon", f"n={len(ids)} lanes={len({l for _, l in pairs})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
