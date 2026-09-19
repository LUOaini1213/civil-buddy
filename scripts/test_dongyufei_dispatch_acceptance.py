import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.expert_turn import _dispatch_daily_md

text = (
    "作业面：A区；"
    "用户事实：钢筋绑扎已完成；"
    "计划：明日进行模板安装；"
    "责任人：王工。"
)

r = _dispatch_daily_md(text)

assert r
assert "钢筋绑扎已完成" in r
assert "明日进行模板安装" in r
assert "# 调度日报草稿（AI）" in r
assert "不是调度令" in r
assert "[A001]" in r
assert "不编产量、工日、台班" in r

print("PASS dispatch acceptance")
print("user_fact =", "钢筋绑扎已完成" in r)
print("plan =", "明日进行模板安装" in r)
print("draft_guard =", "不是调度令" in r)
print("missing_guard =", "[A001]" in r)
print("no_invention =", "不编产量、工日、台班" in r)
