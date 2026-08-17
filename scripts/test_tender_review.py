#!/usr/bin/env python3
"""Drive shipped 成稿后再审 (禁语 + 缺项). Does not fill 业绩 or mutate can_fit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.tools.tender_review import review_draft

    draft = "技术标目录草稿。本方案可以开工，完成后可交差。未附业绩。"
    matrix = {
        "rows": [
            {
                "req_id": "qual",
                "title": "类似幕墙业绩",
                "status": "gap",
                "exact_text": "须具备类似幕墙业绩",
                "owner": "commercial",
            },
            {
                "req_id": "pack",
                "title": "包装",
                "status": "covered",
                "exact_text": "铁架防护",
            },
        ]
    }
    packing = {"can_fit": False, "mid50": 0.4}
    out = review_draft(draft=draft, matrix=matrix, packing_summary=packing)
    assert out["schema"] == "tender.review.v1"
    assert "可以开工" in out["forbidden_hits"]
    assert "可交差" in out["forbidden_hits"]
    assert out["gaps"] and any(g.get("req_id") == "qual" for g in out["gaps"])
    assert out["can_fit"] is False
    assert out["mutated_can_fit"] is False
    assert packing["can_fit"] is False
    assert out["achievements_filled"] == []
    assert out["业绩"] == []
    blob = json.dumps(out, ensure_ascii=False)
    assert "中标业绩" not in blob
    assert "已完成类似项目" not in blob

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    r = client.post(
        "/api/tender/review",
        json={"draft": draft, "matrix": matrix, "packing_summary": packing},
    )
    assert r.status_code == 200, r.text
    jr = r.json()
    assert "可以开工" in jr.get("forbidden_hits", [])
    assert jr.get("can_fit") is False
    assert jr.get("业绩") == []
    print("PASS tender_review", f"hits={jr.get('forbidden_hits')} gaps={jr.get('n_gaps')} can_fit={jr.get('can_fit')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
