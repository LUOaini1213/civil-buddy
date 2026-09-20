#!/usr/bin/env python3
"""Representative tender review case. Runs under pytest and directly."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools.tender_review import review_draft  # noqa: E402


def test_representative_tender_review_case():
    """Representative tender acceptance case."""

    draft = """
    本项目施工方案已编制完成。
    本方案已具备报审条件。
    """

    matrix = {
        "rows": [
            {
                "req_id": "REQ-001",
                "title": "施工组织方案",
                "status": "covered",
                "exact_text": "提交完整施工组织方案",
                "owner": "技术负责人",
            },
            {
                "req_id": "REQ-002",
                "title": "安全措施",
                "status": "missing",
                "exact_text": "提交专项安全措施",
                "owner": "安全负责人",
            },
            {
                "req_id": "REQ-003",
                "title": "项目业绩证明",
                "status": "pending",
                "exact_text": "提供类似项目业绩证明",
                "owner": "商务负责人",
            },
        ]
    }

    packing_summary = {"can_fit": False, "utilization": "UNSPECIFIED"}
    before = copy.deepcopy(packing_summary)

    result = review_draft(
        draft=draft,
        matrix=matrix,
        packing_summary=packing_summary,
    )

    # Forbidden language must be detected.
    assert "已具备报审条件" in result["forbidden_hits"]
    assert result["n_forbidden"] == 1

    # Missing and pending requirements must be reported.
    assert result["n_gaps"] == 2

    gap_ids = {row["req_id"] for row in result["gaps"]}
    assert gap_ids == {"REQ-002", "REQ-003"}

    # The packing result is passed through as given — a failed fit stays failed — and the caller's object is not touched.
    # (`mutated_can_fit` and `achievements_filled` are constants in review_draft, so asserting them proves nothing.)
    assert result["can_fit"] is False
    assert packing_summary == before

    # The system must never invent project achievements: once the caller's own words and the (empty) 业绩 field
    # are taken out of the result, the word does not occur anywhere else.
    blob = json.dumps(result, ensure_ascii=False)
    for given in ("提供类似项目业绩证明", "项目业绩证明", '"业绩"'):
        blob = blob.replace(given, "")
    assert "业绩" not in blob
    assert result["业绩"] == []


if __name__ == "__main__":
    test_representative_tender_review_case()
    print("PASS tender_review_acceptance")
