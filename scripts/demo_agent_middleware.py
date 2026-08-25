#!/usr/bin/env python3
"""3-minute live script (locked): order → unauthorized → recover → cost fuse."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _box(title: str) -> None:
    print()
    print("=" * 58)
    print(title)
    print("=" * 58)


def main() -> int:
    from packing_assistant.runtime.middleware import live_script

    script = live_script()
    _box("Civil Buddy · 策略引擎 + 失败恢复")
    print("两层 Runtime 中间件（不是五个平庸包装）")
    print("  1. 策略引擎  谁 / 哪个工具 / 花多少 / 能否碰生产数据")
    print("  2. 失败恢复  超时重试 → 降级 UNSPECIFIED → 审计链")
    print("剧本：正常下单 → 越权被拒 → 工具挂掉自动恢复 → 成本超限熔断")

    for i, beat in enumerate(script["beats"], 1):
        print()
        print(f"[{i}/4] {beat['title']}   {beat.get('policy')}")
        print(f"  原因  {beat.get('reason')}")
        if beat["id"] == "order":
            print(
                f"  结果  wrote={beat.get('wrote')}  GST 9%={beat.get('gst9')}  "
                f"files={beat.get('files')}  run={beat.get('run_id')}"
            )
        elif beat["id"] == "unauthorized":
            print(f"  弹窗  {beat.get('reason')}")
            print(f"  密钥  {beat.get('secret_reason')}  文件未落地")
        elif beat["id"] == "recover":
            print(f"  动作  {beat.get('action')}  审计 {beat.get('audit')}")
            print(f"  结果  can_fit={beat.get('can_fit')}  不编柜数")
        elif beat["id"] == "fuse":
            print(f"  代码  {beat.get('error_code')}  已执行={beat.get('executed')}")
    print()
    print("submit_blocked=true  secret_leak=false  禁止：可以投标 / 可以开工")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
