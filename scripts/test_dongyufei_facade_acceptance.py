import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.post_drafts.design_basic import build_draft

r = build_draft(
    "facade",
    "facade__brief",
    "幕墙编号：F01；未提供设计风压、层高、分格及计算书。",
)

assert r
assert "F01" in r
assert "UNSPECIFIED" in r
assert "可以开工" not in r

print("PASS facade acceptance")
print("tool = facade__brief")
print("facade =", "F01" in r)
print("UNSPECIFIED =", "UNSPECIFIED" in r)
