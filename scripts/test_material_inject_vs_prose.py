#!/usr/bin/env python3
"""注入完整物料时，用户句里的「1 个柜」不得被当成缺维清单。"""

from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")


def main() -> int:
    from packing_assistant.agents.material_parser import agent_material_parser

    mats = [
        {
            "id": "H1",
            "name": "重件块",
            "quantity": 1,
            "weight_kg": 16000.0,
            "total_weight_kg": 16000.0,
            "length_mm": 2000.0,
            "width_mm": 1500.0,
            "height_mm": 1200.0,
        }
    ]
    st = {
        "user_input": "超重只准 1 个 40HQ",
        "materials": deepcopy(mats),
        "packing_options": {},
    }
    out = agent_material_parser(st)
    inc = bool(out.get("materials_incomplete"))
    n = len(out.get("materials") or [])
    print(f"incomplete={inc} n={n} source={(out.get('agent_meta') or {}).get('artifacts')}")
    if inc:
        print("FAIL: prose '1 个' marked complete inject as missing dims")
        print("errors", out.get("errors"))
        return 1
    if n != 1:
        print("FAIL: expected 1 material, got", n)
        return 1
    print("PASS inject wins over prose 1 个柜")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
