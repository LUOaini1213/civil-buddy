import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.post_drafts.design_basic import build_draft

r = build_draft(
    "structure",
    "structure__calc_outline",
    "项目：测试结构；构件：梁A。未提供荷载表、材料表或结构计算书。",
)

assert r
assert "梁A" in r
assert "UNSPECIFIED" in r
assert "未核验" in r
assert "不能以提纲代替" in r
assert "可以开工" not in r

print("PASS structure acceptance")
print("tool = structure__calc_outline")
print("UNSPECIFIED =", "UNSPECIFIED" in r)
print("unverified =", "未核验" in r)
