import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.post_drafts.admin import build_draft

r = build_draft(
    "admin-office",
    "admin-office__list",
    "会议名称：项目协调会；会议时间：周三上午10点；会议地点：A会议室；参会人员：张三、李四；责任人：王工。",
)

assert r
assert "项目协调会" in r
assert "周三上午10点" in r
assert "A会议室" in r
assert "张三、李四" in r
assert "UNSPECIFIED" in r

# Must not falsely claim that logistical actions were completed/approved.
guard = "本稿不确认场地已预订、车辆已派出、接待已获批"
assert guard in r

print("PASS admin-office acceptance")
print("tool = admin-office__list")
print("meeting =", "项目协调会" in r)
print("venue =", "A会议室" in r)
print("attendees =", "张三、李四" in r)
print("safety_guard =", guard in r)
