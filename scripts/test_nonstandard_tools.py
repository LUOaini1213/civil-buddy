#!/usr/bin/env python3
"""Drive shipped nonstandard.inspect / nonstandard.enrich entry points."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tool_registry import TOOL_CATALOG, get_tool
    from packing_assistant.tools.nl_nonstandard_enrich import enrich_materials
    from packing_assistant.tools.nonstandard_inspect import (
        inspect_nonstandard,
        public_summary,
    )

    ids = {t.id for t in TOOL_CATALOG}
    assert "nonstandard.inspect" in ids, "catalog missing nonstandard.inspect"
    assert "nonstandard.enrich" in ids, "catalog missing nonstandard.enrich"
    assert get_tool("nonstandard.inspect") is not None
    assert get_tool("nonstandard.enrich") is not None

    docs = ROOT / "knowledge_base" / "02_tools"
    inspect_md = (docs / "nonstandard_inspect.md").read_text(encoding="utf-8")
    enrich_md = (docs / "nonstandard_enrich.md").read_text(encoding="utf-8")
    assert "nonstandard.inspect" in inspect_md
    assert "nonstandard.enrich" in enrich_md

    mats = [
        {
            "name": "中空玻璃 易碎",
            "note": "禁翻 向上",
            "L": 2000,
            "W": 1000,
            "H": 30,
            "weight_kg": 80,
            "qty": 2,
        },
        {
            "name": "标准角钢",
            "L": 3000,
            "W": 100,
            "H": 100,
            "weight_kg": 50,
            "qty": 4,
        },
    ]
    enriched = enrich_materials(mats)
    assert isinstance(enriched, list) and len(enriched) == 2
    glass = enriched[0]
    assert glass.get("fragile") is True, glass
    assert glass.get("this_side_up") is True or glass.get("orientation"), glass
    # must not mutate dimensions
    assert float(glass["L"]) == 2000 and float(glass["weight_kg"]) == 80

    report = inspect_nonstandard(materials=enriched, container_type="40HQ", case_id="ut-ns")
    assert report.get("schema") == "nonstandard.inspect.v2"
    assert report.get("overall") in ("PASS", "WARN", "NEED_DESIGN", "FAIL")
    assert "summary" in report and "ship_gate" in report

    summary = public_summary(report)
    assert summary.get("schema") == "nonstandard.inspect.v2.summary"
    assert summary.get("overall") == report.get("overall")
    # public path must not require full material dump
    assert "materials" not in summary or summary.get("materials") is None

    print(
        "PASS nonstandard tools",
        f"overall={report.get('overall')}",
        f"ns={report.get('summary', {}).get('n_nonstandard_materials')}",
        f"fragile={glass.get('fragile')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
