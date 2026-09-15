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