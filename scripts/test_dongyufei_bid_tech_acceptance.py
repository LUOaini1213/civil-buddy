#!/usr/bin/env python3
"""Representative acceptance case for the bid-tech expert."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.runtime import tender_workflow as workflow
from packing_assistant.runtime.civil_config import CivilConfig


TENDER = (
    "★投标人须提供营业执照复印件。\n"
    "技术方案评分20分，须编制施工专项方案。\n"
    "工期60日历天。"
)

RESPONSE = (
    "已附营业执照复印件。\n"
    "施工专项方案资料待补。\n"
    "供应商自述工期999日历天。"
)


def main() -> int:
    sources = [
        {
            "source_id": "tender-1",
            "title": "招标资料",
            "text": TENDER,
            "start": 100,
            "role": "tender",
        },
        {
            "source_id": "response-1",
            "title": "投标响应",
            "text": RESPONSE,
            "start": 300,
            "role": "response",
        },
    ]

    with tempfile.TemporaryDirectory(
        dir=ROOT / "output",
        prefix="dongyufei-bid-tech-",
    ) as tmp:
        with patch(
            "packing_assistant.runtime.civil_config.load_config",
            return_value=CivilConfig(),
        ):
            result = workflow.run_tender_workflow(
                TENDER,
                session_id="dongyufei-bid-tech",
                output_root=Path(tmp),
                sources=sources,
                confirmed=False,
            )

        assert result["ok"], result

        tech = next(
            child for child in result["children"]
            if child["skill"] == "bid-tech"
        )

        # 1. bid-tech worker must complete.
        assert tech["status"] == "done"

        # 2. Scoring/special requirements must retain tender evidence.
        assert tech["evidence"]
        assert any(
            "技术方案评分20分" in item.get("quote", "")
            for item in tech["evidence"]
        )

        # 3. Tender evidence must come from tender source, not response.
        assert all(
            item.get("source_id") == "tender-1"
            for item in tech["evidence"]
        )

        # 4. Supplier's 999-day response must not enter bid-tech evidence.
        assert all(
            "999" not in item.get("quote", "")
            for item in tech["evidence"]
        )

        # 5. Original tender duration remains 60 days.
        handoff = json.loads(
            (Path(result["directory"]) / "handoff.json")
            .read_text(encoding="utf-8")
        )
        assert handoff["handoff"]["duration_days"] == 60

        # 6. Generated bid-tech files must exist.
        assert any(f["name"] == "bid-tech.md" for f in tech["files"])
        assert any(f["name"] == "bid-tech.docx" for f in tech["files"])
        for item in tech["files"]:
            assert Path(item["path"]).is_file()

        # 7. Workflow never authorizes bid submission.
        assert result["submit_blocked"] is True

        print("PASS bid-tech acceptance")
        print("status =", tech["status"])
        print("evidence_count =", len(tech["evidence"]))
        print("duration_days =", handoff["handoff"]["duration_days"])
        print("submit_blocked =", result["submit_blocked"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
