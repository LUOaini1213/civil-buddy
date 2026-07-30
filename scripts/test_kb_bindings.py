#!/usr/bin/env python3
"""Agent 知识窄接绑定回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.kb_bindings import (  # noqa: E402
    get_binding,
    list_agent_ids,
    load_bindings,
    search_for_agent,
)


NINE = [
    "orchestrator",
    "material_parser",
    "structure",
    "box_scheme",
    "planner",
    "loader",
    "evaluator",
    "risk_compliance",
    "visualizer",
]


def main() -> int:
    data = load_bindings()
    agents = data.get("agents") or {}
    assert agents, "bindings empty"
    ids = list_agent_ids()
    print(f"agents in yaml: {len(ids)} → {ids}")

    missing = [a for a in NINE if a not in agents]
    if missing:
        print("FAIL missing nine:", missing)
        return 1

    # loader must not search by default
    loader_res = search_for_agent("loader", "空隙 15cm")
    if not loader_res.get("skipped"):
        print("FAIL loader should skip search:", loader_res)
        return 1
    print("loader skip OK")

    # box_scheme should hit packing / safety
    bs = search_for_agent("box_scheme", "超货载 标准箱", limit=4)
    paths = [h["path"] for h in bs.get("hits") or []]
    print("box_scheme hits:", paths)
    if not paths:
        print("FAIL box_scheme no hits")
        return 1
    if not any("01_rules" in p or "02_tools" in p or "03_trajectories" in p for p in paths):
        print("FAIL unexpected paths", paths)
        return 1

    # risk should hit ctu
    risk = search_for_agent("risk_compliance", "重心 mid50", limit=4)
    rpaths = [h["path"] for h in risk.get("hits") or []]
    print("risk hits:", rpaths)
    if not any("ctu" in p or "safety" in p or "cog" in p for p in rpaths):
        print("FAIL risk paths", rpaths)
        return 1

    # replan_critic evidence
    from packing_assistant.kb_bindings import brief_evidence

    ev = brief_evidence("replan_critic", "over_payload box_scheme", max_snips=3)
    print("replan evidence:", [e.get("path") for e in ev])
    if not ev:
        print("FAIL no replan evidence")
        return 1

    # binding fields
    b = get_binding("planner")
    assert b.get("path_prefixes"), "planner prefixes"
    assert b.get("allow_search") is True

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
