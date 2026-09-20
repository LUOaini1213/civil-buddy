import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.post_drafts.design_basic import build_draft

r = build_draft(
    "architecture",
    "architecture__memo",
    "单体名称：A栋；功能：办公。未提供面积、层数、高度及设计任务书。",
)

assert r
assert "A栋" in r
assert "办公" in r
assert "UNSPECIFIED" in r
assert "可以开工" not in r

print("PASS architecture acceptance")
print("tool = architecture__memo")
print("building =", "A栋" in r)
print("function =", "办公" in r)
print("UNSPECIFIED =", "UNSPECIFIED" in r)
