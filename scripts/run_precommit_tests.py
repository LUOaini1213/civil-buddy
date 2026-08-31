#!/usr/bin/env python3
"""
提交前必跑（比赛第 1 周起）：
  1) test_booking_regression.py
  2) test_p2_volume_gates.py
  3) test_stack_parity.py（三栈 parity：understand.py==agent.rs、SKILL.md 镜像、66 岗名册）
  4) run_vmu1_site_only.py（主案例可复现）
  5) eval_post_scorecard.py（R5 每岗记分卡：quick 2 岗 / 全量 5 岗）

可选：
  --quick   只跑 1+2，不跑工地 Excel
  --more    加跑 test_more_examples.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, timeout: int = 600, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, script] + (extra or [])
    label = script + (" " + " ".join(extra) if extra else "")
    print("\n" + "=" * 60)
    print("RUN", label)
    print("=" * 60)
    r = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout)
    print("EXIT", r.returncode, label)
    return int(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过工地 Excel 重跑")
    ap.add_argument("--more", action="store_true", help="额外更多例子")
    args = ap.parse_args()

    codes = []
    # UX R12 门禁：零外链红线（内网断网可用）+ JS/CSS 语法体检（无 node 时 JS 段 SKIP，CI 必跑）
    codes.append(run("scripts/test_no_external_urls.py", 60))
    codes.append(run("scripts/test_js_syntax.py", 120))
    # UX R14 门禁：符号纪律（浏览器资产 0 装饰符号，规则见 spec 附录 L）
    codes.append(run("scripts/test_ux_no_emoji.py", 60))
    codes.append(run("scripts/test_booking_regression.py", 180))
    codes.append(run("scripts/test_p2_volume_gates.py", 180))
    codes.append(run("scripts/test_stack_parity.py", 120))
    codes.append(run("scripts/test_nonstandard_tools.py", 60))
    codes.append(run("scripts/test_cog_shift_mid_ok.py", 60))
    codes.append(run("scripts/test_phase0_task_success.py", 60))
    codes.append(run("scripts/test_facade_sme_mini.py", 180))
    codes.append(run("scripts/test_hollow_volume_n0.py", 60))
    # D-R3：RAG 三栈对拍（金句 48 条 parity/recall + P50<50ms + 写钩子 + rag.rs 硬编码 grep 门禁）
    codes.append(run("scripts/test_rag_parity.py", 600))
    # R5 每岗记分卡试点：quick 预算只跑 2 岗，全量 5 岗（G1 意图/G2 KB/G3 交付物/G4 诚实度）
    codes.append(run("scripts/eval_post_scorecard.py", 300, extra=["--all-pilots"] + (["--quick"] if args.quick else [])))
    if args.more:
        codes.append(run("scripts/test_more_examples.py", 300))
    if not args.quick:
        # 无工地 Excel 时脚本 exit 0 + SKIP；有数据时仍完整回归
        codes.append(run("scripts/run_vmu1_site_only.py", 600))

    failed = [c for c in codes if c != 0]
    print("\n" + "=" * 60)
    if failed:
        print("PRECOMMIT FAIL", codes)
        return 1
    print("PRECOMMIT ALL GREEN")
    print(
        "  booking_regression + p2_gates + stack_parity + post_scorecard"
        + (" + more" if args.more else "")
        + (" + vmu1_site(or SKIP)" if not args.quick else " (--quick no vmu)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
