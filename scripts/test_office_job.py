#!/usr/bin/env python3
"""Job-root Office interchange: tables → xlsx; never D:\\layout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.office_job import (
        export_md_to_xlsx,
        is_forbidden_layout,
        job_root,
        tables_from_md,
    )

    assert is_forbidden_layout(Path(r"D:\layout"))
    assert is_forbidden_layout(Path(r"D:\layout\foo"))
    assert not is_forbidden_layout(Path(r"C:\Users\LW\civil-buddy"))

    os.environ["CIVIL_JOB_ROOT"] = r"D:\layout"
    assert not is_forbidden_layout(job_root())
    assert str(job_root()).replace("\\", "/").lower().endswith(".civil-buddy/out")

    job = ROOT / "output" / "office-job-test"
    job.mkdir(parents=True, exist_ok=True)
    os.environ["CIVIL_JOB_ROOT"] = str(job)
    os.environ["CIVIL_SANDBOX_ROOTS"] = str(job)
    assert job_root().resolve() == job.resolve()

    md = (
        "# 核算\n\n## 6 报销勾选\n\n"
        "| 检查项 | 本稿 |\n| --- | --- |\n| 发票查验 | 待核 |\n| 审批链 | 待核 |\n\n"
        "## 8 对账缺口\n\n"
        "| 台账 | 本稿 |\n| --- | --- |\n| 物资收发存 | 缺口待列 |\n"
    )
    sheets = tables_from_md(md)
    assert len(sheets) == 2, sheets
    assert sheets[0][0] == "6 报销勾选"
    assert sheets[0][1][0] == ["检查项", "本稿"]
    assert ["发票查验", "待核"] in sheets[0][1]

    src = job / "finance-book__check.md"
    src.write_text(md, encoding="utf-8")
    paths = export_md_to_xlsx(src)
    assert paths, paths
    xlsx = [p for p in paths if p.suffix == ".xlsx"]
    assert xlsx
    import openpyxl

    wb = openpyxl.load_workbook(xlsx[0])
    assert "6 报销勾选" in wb.sheetnames
    assert wb["6 报销勾选"]["A2"].value == "发票查验"
    assert wb["6 报销勾选"]["B2"].value == "待核"
    print("PASS office_job")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
