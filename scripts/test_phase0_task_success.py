#!/usr/bin/env python3
"""Drive phase0_benchmark._score_task_success with synthetic states."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main() -> int:
    from packing_assistant.phase0_benchmark import Phase0Case, _score_task_success
    case = Phase0Case(id="ut", tags=["short"], materials=[], expect={"can_fit": True})
    # can_fit true + ship_ok + mid50
    st = {
        "container_plan": {"can_fit": True, "containers_used": 1, "ship_ok": True},
        "ship_ok": True,
        "cog_bundle": {"primary": {"mass_in_mid50_ratio": 0.67}},
        "errors": [],
    }
    s = _score_task_success(st, case)
    assert s >= 0.94, s
    st2 = {
        "container_plan": {"can_fit": True, "containers_used": 1},
        "errors": [],
    }
    s2 = _score_task_success(st2, case)
    assert 0.89 <= s2 <= 0.91, s2
    st3 = {
        "container_plan": {"can_fit": False, "containers_used": 0},
        "errors": [],
    }
    s3 = _score_task_success(st3, case)
    assert s3 <= 0.3, s3  # expect can_fit True but got False
    print("PASS phase0 task_success scoring", s, s2, s3)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
