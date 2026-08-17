#!/usr/bin/env python3
"""Tables + multi-file excerpts → same tender matrix (no bid book)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NOTICE = """一、投标人须具备建筑工程施工资质及类似幕墙业绩。
二、未实质性响应招标文件的作废标处理。
三、交货期：合同签订后 90 个日历天内到港。
"""

SCORE_CSV = """条款,分值
施工组织设计,25 分
项目管理机构,10 分
★深基坑专项方案须编制,不满足即废标
"""


def main() -> int:
    from openpyxl import Workbook

    from packing_assistant.tools.tender_ingest import decode_file, ingest_files
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    csv_got = decode_file("评分.csv", SCORE_CSV.encode("utf-8"))
    assert csv_got["n_tables"] >= 1
    assert "施工组织设计 | 25 分" in csv_got["text"]

    merged = ingest_files(
        [
            {"filename": "须知.txt", "bytes": NOTICE.encode("utf-8")},
            {"filename": "评分.csv", "bytes": SCORE_CSV.encode("utf-8")},
        ]
    )
    assert merged["n_files"] == 2
    assert "文件：须知.txt" in merged["text"]
    assert "文件：评分.csv" in merged["text"]

    pipe = run_tender_pipeline(merged["text"], source="ingest-test", p0_confirmed=False)
    assert pipe["ok"] is True
    assert pipe["submit_blocked"] is True
    rows = (pipe.get("matrix") or {}).get("rows") or []
    assert rows, pipe
    for r in rows:
        assert r.get("exact_text"), r
    blob = " ".join(str(r.get("exact_text")) for r in rows)
    assert "90" in blob or "日历天" in blob
    assert "25 分" in blob or "施工组织设计" in blob
    assert (pipe.get("handoff") or {}).get("duration_days") == 90

    wb = Workbook()
    ws = wb.active
    ws.append(["条款", "要求"])
    ws.append(["采用海运整柜 40HQ", "包装须铁架防护"])
    buf = io.BytesIO()
    wb.save(buf)
    xls = decode_file("运输.xlsx", buf.getvalue())
    assert "40HQ" in xls["text"]
    assert "铁架" in xls["text"]

    from fastapi.testclient import TestClient

    from gateway.app import app

    client = TestClient(app)
    multi = client.post(
        "/api/tender/parse/files",
        files=[
            ("files", ("须知.txt", NOTICE.encode("utf-8"), "text/plain")),
            ("files", ("评分.csv", SCORE_CSV.encode("utf-8"), "text/csv")),
        ],
    )
    assert multi.status_code == 200, multi.text
    jm = multi.json()
    assert jm.get("submit_blocked") is True
    assert jm.get("ingested_text")
    mrows = (jm.get("matrix") or {}).get("rows") or []
    assert mrows and all(r.get("exact_text") for r in mrows)
    assert (jm.get("handoff") or {}).get("schema") == "tender.handoff.v1"

    still_pdf = client.post(
        "/api/tender/parse/file",
        files={"file": ("scan.pdf", b"%PDF-fake", "application/pdf")},
    )
    assert still_pdf.status_code == 400

    sections = client.post(
        "/api/tender/parse",
        json={
            "sections": [
                {"name": "须知.txt", "text": NOTICE},
                {"name": "评分.csv", "text": "施工组织设计 | 25 分"},
            ]
        },
    )
    assert sections.status_code == 200, sections.text
    assert sections.json().get("submit_blocked") is True
    assert all(
        r.get("exact_text")
        for r in ((sections.json().get("matrix") or {}).get("rows") or [])
    )

    print("PASS tender_ingest", f"rows={len(mrows)} files={merged['n_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
