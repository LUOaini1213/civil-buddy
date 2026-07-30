#!/usr/bin/env python3
"""search_knowledge 金标 Recall@3 + 叙事守卫。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.search_knowledge import search_knowledge  # noqa: E402
from packing_assistant.tool_registry import get_tool, list_tools  # noqa: E402


def main() -> int:
    golden_path = ROOT / "test" / "kb" / "rag_golden.json"
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    items = data["items"]
    hits_ok = 0
    fail_ids = []
    for it in items:
        res = search_knowledge(it["q"], limit=3)
        paths = [h["path"] for h in res.get("hits") or []]
        expect = it["expect_paths"]
        ok = any(e in paths for e in expect)
        # narrative: no coord keys
        for h in res.get("hits") or []:
            for k in h:
                if k.lower() in ("x", "y", "z", "xyz", "positions", "layout_items"):
                    ok = False
                    fail_ids.append(f"{it['id']}:coord_key:{k}")
        if ok:
            hits_ok += 1
        else:
            fail_ids.append(f"{it['id']}: got={paths} expect_any={expect}")

    n = len(items)
    recall = hits_ok / n if n else 0.0
    # registry
    spec = get_tool("knowledge.search")
    reg_ok = spec is not None and any(t["id"] == "knowledge.search" for t in list_tools())

    print(f"Recall@3: {hits_ok}/{n} = {recall:.3f}")
    print(f"registry knowledge.search: {reg_ok}")
    if fail_ids:
        print("FAIL detail (first 12):")
        for line in fail_ids[:12]:
            print(" ", line)
    if not reg_ok:
        print("FAIL: knowledge.search not in tool_registry")
        return 1
    if recall < 0.90:
        print(f"FAIL: Recall@3 {recall:.3f} < 0.90")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
