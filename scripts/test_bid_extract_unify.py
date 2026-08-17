#!/usr/bin/env python3
"""Same sample through workbench bid-parse extract AND packing tender-handoff."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

SAMPLE = """
Harbourline Facade DEMO
交货期：合同签订后 90 个日历天内到港。
★深基坑专项方案须编制，不满足即废标。
技术标评分：施工组织设计 25 分、项目管理机构 10 分。
包装采用铁架防护。
"""


def _texts(rows: list) -> list[str]:
    return [str(r.get("text") or "").strip() for r in rows]


def main() -> int:
    from packing_assistant.tools.tender_parse import parse_tender_text, workbench_bid_extract

    pack = parse_tender_text(SAMPLE, source="unify-pack")
    ho = pack.get("handoff") or {}
    bench = workbench_bid_extract(SAMPLE, project_name="unify")

    assert bench.get("submit_blocked") is True
    assert bench.get("duration_days") == pack.get("duration_days") == 90
    assert _texts(bench.get("star_items") or []) == _texts(ho.get("star_items") or [])
    assert _texts(bench.get("scoring_points") or []) == _texts(ho.get("scoring_points") or [])
    star_blob = " ".join(_texts(bench.get("star_items") or []))
    score_blob = " ".join(_texts(bench.get("scoring_points") or []))
    assert "深基坑" in star_blob
    assert "25 分" in score_blob or "施工组织设计" in score_blob
    assert bench.get("duration_days") != 180
    assert "CW02" not in str(bench.get("handoff", {}).get("workheads"))

    # workbench CLI entry (what Rust bid-parse__extract calls)
    script = ROOT / "workbench" / "scripts" / "run_tender_extract.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps({"tender_text": SAMPLE, "project_name": "unify"}, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        env={**__import__("os").environ, "PACKING_AGENT_ROOT": str(ROOT)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    cli = json.loads(proc.stdout.strip().splitlines()[-1])
    assert cli.get("duration_days") == 90
    assert _texts(cli.get("star_items") or []) == _texts(ho.get("star_items") or [])
    assert _texts(cli.get("scoring_points") or []) == _texts(ho.get("scoring_points") or [])

    # demo exclusive tool entry
    from agent import execute_tool
    from catalog_seed import EXPERTS

    parse = next(e for e in EXPERTS if e.id == "bid-parse")
    with tempfile.TemporaryDirectory() as td:
        raw = execute_tool(
            "extract_tender",
            {"tender_text": SAMPLE, "project_name": "unify"},
            expert=parse,
            confirm_ok=True,
            out_dir=Path(td),
            citations=[],
            deliverables=[],
        )
    tool = json.loads(raw)
    assert tool.get("submit_blocked") is True
    assert tool.get("duration_days") == 90
    assert _texts(tool.get("star_items") or []) == _texts(ho.get("star_items") or [])
    assert _texts(tool.get("scoring_points") or []) == _texts(ho.get("scoring_points") or [])

    print(
        "PASS bid_extract_unify",
        f"days={bench.get('duration_days')}",
        f"stars={_texts(bench.get('star_items') or [])}",
        f"scores={_texts(bench.get('scoring_points') or [])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
