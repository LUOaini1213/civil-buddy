#!/usr/bin/env python3
"""In-process TestClient: POST /api/table/parse uses real table_mapper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    csv_path = ROOT / "test" / "generic_tables" / "G1_ecommerce_cartons" / "materials.csv"
    assert csv_path.is_file(), csv_path

    with csv_path.open("rb") as f:
        r = client.post(
            "/api/table/parse",
            files={"file": ("materials.csv", f, "text/csv")},
            data={"session_id": "test-tbl", "store_session": "0"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True, body
    mats = body.get("materials") or []
    assert len(mats) >= 3, mats
    # no free-form xyz as primary output
    for m in mats:
        assert "x" not in m or m.get("length_mm") is not None
        assert "xyz" not in m
        assert float(m.get("length_mm") or 0) >= 10 or float(m.get("length_mm") or 0) == 0
    assert "column_map" in body
    # JSON path entry
    r2 = client.post(
        "/api/table/parse/json",
        json={"path": str(csv_path.relative_to(ROOT)).replace("\\", "/")},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True
    assert len(r2.json().get("materials") or []) >= 3

    # mixed units via path
    g15 = ROOT / "test" / "generic_tables" / "G15_mixed_units_stress" / "materials.csv"
    if g15.is_file():
        r3 = client.post(
            "/api/table/parse/json",
            json={"path": str(g15.relative_to(ROOT)).replace("\\", "/")},
        )
        assert r3.status_code == 200
        for m in r3.json().get("materials") or []:
            L = float(m.get("length_mm") or 0)
            if L > 0:
                assert L >= 50, f"expected mm-scale length, got {L}"

    print("ALL_PASS table_api_parse")
    print(json.dumps({"n": len(mats), "sample_id": mats[0].get("id")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
