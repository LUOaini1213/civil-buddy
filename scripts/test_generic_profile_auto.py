#!/usr/bin/env python3
"""表注入材料 → material_parser 自动套 generic_table profile（真实 agent 入口）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.agents.material_parser import agent_material_parser
    from packing_assistant.tools.table_mapper import parse_table_file

    csv_path = ROOT / "test" / "generic_tables" / "G1_ecommerce_cartons" / "materials.csv"
    pr = parse_table_file(csv_path)
    assert pr["ok"] and pr["materials"], pr
    st = {
        "user_input": "通用材料表装柜",
        "materials": pr["materials"],
        "packing_options": {},
        "messages": [],
    }
    out = agent_material_parser(st)
    opts = out.get("packing_options") or {}
    assert opts.get("profile_id") == "generic_table", opts
    assert opts.get("crate_passthrough") is True, opts
    arts = (out.get("agent_meta") or {}).get("artifacts") or {}
    assert arts.get("profile_applied"), arts
    tools = (out.get("agent_meta") or {}).get("tools_used") or []
    assert any("generic_table" in str(t) for t in tools), tools

    # 显式非 balanced 档不可被表 inject 覆盖
    st2 = {
        "user_input": "钢结构表装柜",
        "materials": pr["materials"],
        "packing_options": {
            "profile_id": "steel_structure",
            "structure_calc": True,
            "crate_passthrough": False,
        },
        "messages": [],
    }
    out2 = agent_material_parser(st2)
    opts2 = out2.get("packing_options") or st2["packing_options"]
    # agent may omit packing_options when unchanged — then state profile must hold
    pid2 = (out2.get("packing_options") or {}).get("profile_id") or st2[
        "packing_options"
    ].get("profile_id")
    assert pid2 == "steel_structure", (opts2, out2.get("packing_options"))
    arts2 = (out2.get("agent_meta") or {}).get("artifacts") or {}
    assert not arts2.get("profile_applied"), arts2

    print("ALL_PASS generic_profile_auto")
    print("profile_id=", opts.get("profile_id"), "tools=", tools)
    print("steel_structure preserved=", pid2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
