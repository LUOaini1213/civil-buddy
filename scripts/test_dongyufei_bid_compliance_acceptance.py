#!/usr/bin/env python3
"""Representative acceptance case for the bid-compliance expert."""

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
    "施工方案资料待补。\n"
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

    with tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="dongyufei-bid-compliance-") as tmp:
        with patch(
            "packing_assistant.runtime.civil_config.load_config",
            return_value=CivilConfig(),
        ):
            result = workflow.run_tender_workflow(
                TENDER,
                session_id="dongyufei-bid-compliance",
                output_root=Path(tmp),
                sources=sources,
                confirmed=False,
            )

        assert result["ok"], result

        # Expert acceptance rule 1:
        # Tender workflow must never authorize submission.
        assert result["submit_blocked"] is True

        # Expert acceptance rule 2:
        # Missing / incomplete response evidence must not become verified.
        review = result["review"]
        assert review["response_evidence_supplied"] is True
        assert review["gaps"]
        assert any(not row["verified"] for row in review["response_comparison"])

        # Expert acceptance rule 3:
        # Unresolved items must remain unresolved.
        assert result["quality"]["unresolved"] > 0

        # Expert acceptance rule 4:
        # Supplier's 999-day statement must not overwrite
        # the tender requirement of 60 days.
        handoff = json.loads(
            (Path(result["directory"]) / "handoff.json").read_text(encoding="utf-8")
        )
        assert handoff["handoff"]["duration_days"] == 60

        for evidence in handoff["evidence"]:
            assert "999" not in evidence.get("quote", "")

        # Expert acceptance rule 5:
        # P0 / human-confirmation gate remains present.
        assert handoff["handoff"]["p0_reject_scan"]["human_confirm_required"] is True

        print("PASS bid-compliance acceptance")
        print("submit_blocked =", result["submit_blocked"])
        print("unresolved =", result["quality"]["unresolved"])
        print("duration_days =", handoff["handoff"]["duration_days"])
        print("response_evidence_supplied =", review["response_evidence_supplied"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
