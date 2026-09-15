from packing_assistant.tools.tender_review import review_draft


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

    packing_summary = {"can_fit": True}

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

    # Packing result must be preserved.
    assert result["can_fit"] is True
    assert result["mutated_can_fit"] is False

    # The system must never invent project achievements.
    assert result["achievements_filled"] == []
    assert result["业绩"] == []