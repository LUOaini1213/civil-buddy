#!/usr/bin/env python3
"""Representative acceptance case for the bid-parse expert."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.tender_parse import run_tender_pipeline

TENDER = (
    "★投标人须提供营业执照复印件。\n"
    "技术方案评分20分，须编制施工专项方案。\n"
    "工期60日历天。"
)


def main() -> int:
    result = run_tender_pipeline(
        TENDER,
        source="dongyufei-bid-parse-acceptance",
        project_name="Bid Parse Acceptance",
    )

    assert isinstance(result, dict)

    handoff = result.get("handoff")
    assert isinstance(handoff, dict)

    matrix = result.get("matrix")
    assert isinstance(matrix, dict)

    rows = matrix.get("rows") or []
    assert rows

    # Original tender duration must be preserved.
    assert handoff["duration_days"] == 60

    # Requirements must remain traceable to tender text.
    blob = str(rows)
    assert "营业执照" in blob
    assert "技术方案评分20分" in blob
    assert "20" in blob

    # No unsupported value may be invented.
    assert "999" not in blob
    assert "999" not in str(handoff)

    # Matrix rows must preserve the original tender wording.
    row_blob = str(rows)
    assert "工期60日历天" in row_blob
    assert "技术方案评分20分" in row_blob

    # Parsed handoff must preserve the extracted tender facts.
    assert handoff["duration_days"] == 60
    assert handoff.get("scoring_points")

    # Bid parsing must never authorize submission.
    assert result.get("submit_blocked") is True

    print("PASS bid-parse acceptance")
    print("duration_days =", handoff["duration_days"])
    print("matrix_rows =", len(rows))
    print("submit_blocked =", result.get("submit_blocked"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
