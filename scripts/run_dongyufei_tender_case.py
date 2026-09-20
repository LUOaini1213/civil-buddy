from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.runtime.tender_workflow import run_tender_workflow

TENDER = """★投标人须提供营业执照复印件。
技术方案评分20分，须编制施工专项方案。
工期60日历天。
"""

RESPONSE = """已附营业执照复印件。
施工方案资料待补。
供应商自述工期999日历天。
"""


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


output_root = Path("output/dongyufei-tender-case")
output_root.mkdir(parents=True, exist_ok=True)

result = run_tender_workflow(
    TENDER,
    session_id="dongyufei-tender-case",
    output_root=output_root,
    sources=sources,
    confirmed=False,
)

print("ok:", result["ok"])
print("run_id:", result["run_id"])
print("submit_blocked:", result["submit_blocked"])
print("directory:", result["directory"])

print("\nGenerated files:")
for item in result["files"]:
    print("-", item["path"])

# The acceptance record (docs/dongyufei_tender_acceptance.md) as assertions, so it cannot go stale quietly.
review = result["review"]
rows = {row["requirement"]: row for row in review["response_comparison"]}
status = {text[:6]: row["status"] for text, row in rows.items()}
assert result["ok"] is True and result["submit_blocked"] is True
# 13 since 2026-09-20: the parse table and the technical outline are tables now, so each comes with a
# workbook as well (tender-extract.xlsx, worker-bid-tech/bid-tech.xlsx) - "正文有表格时可导出 Excel".
assert len(result["files"]) == 13, [Path(f["path"]).name for f in result["files"]]
assert len(rows) == 3, list(rows)                                   # one row per tender line (#32)
assert status["工期60日历"] == "conflict_requires_review", status   # 999 日历天 against 60 日历天 is pointed out, not judged
assert status["技术方案评分"] == "not_matched", status
assert status["★投标人须提"] == "candidate_requires_review", status
assert any("999" in c["note"] and "60" in c["note"] for c in review["conflicts"]), review["conflicts"]
assert "999" not in str(result.get("matrix") or "") and "999" not in TENDER   # the bid's number never becomes the tender's
assert result["quality"]["unresolved"] == 3 and result["quality"]["responses_verified"] == 0, result["quality"]
print("\nPASS tender_case rows=3 conflict=duration unresolved=3")

