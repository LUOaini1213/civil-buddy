#!/usr/bin/env python3
"""
最终架构 CLI：团队A → 用户确认 → 团队B

用法:
  python main.py --demo              # 默认 high_util 预设：过合规门，done/WARN 收尾
  python main.py --demo --preset structure_fail   # 负例：演示合规阻断生效（REJECT 为预期）
  python main.py --team-a            # 只跑团队A，打印确认单
  python main.py --interactive       # 交互：先A后确认再B
  python main.py --eval              # 现行评测 = phase0 基线 quick（全过退出码 0）
  python main.py --eval --cases eval/cases.json   # 旧黄金集（deprecated，仅历史回归）
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from packing_assistant.harness import (
    apply_user_confirmation,
    format_trace_report,
    public_response,
    run_pipeline,
    run_team_a,
    run_team_b,
)


def cmd_demo(args) -> int:
    materials = None
    packing_options = None
    user_input = args.input or ""

    if not user_input:
        from packing_assistant.demo_presets import PRESETS

        key = (args.preset or "high_util").strip().lower()
        if key == "structure_fail":
            # 负例路径：默认成箱选项下 BOX-01 结构校核阻断——演示「合规门是活的」。
            # REJECT / need_revision 是这条路径的预期结果，不是缺陷。
            print("== 合规门负例演示：预期 BOX-01 成箱结构校核阻断（REJECT=门生效）==")
            user_input = "演示材料清单"
        else:
            if key not in PRESETS:
                key = "high_util"
            preset = PRESETS[key]
            materials = preset["materials"]()
            packing_options = preset["packing_options"]()
            user_input = preset["user_input"]
            print(f"== 演示预设: {key} · {preset['label']} ==")

    result = run_pipeline(
        user_input,
        materials=materials,
        packing_options=packing_options,
        container_type=args.container,
        enable_auto_confirm=True,
        persist_trace=args.save_trace,
    )
    if args.trace:
        print(format_trace_report(result))
        print()
    if args.json:
        print(json.dumps(public_response(result), ensure_ascii=False, indent=2, default=str))
    else:
        print(result.get("final_response") or "")
        side = ((result.get("image_data") or {}).get("side") or {}).get("path")
        if side:
            print(f"\n侧视图: {side}")
        print(f"\nphase={result.get('phase')} status={result.get('status')}")
    return 0


def cmd_team_a(args) -> int:
    result = run_team_a(args.input or "演示材料清单")
    if args.json:
        print(json.dumps(public_response(result), ensure_ascii=False, indent=2, default=str))
    else:
        print(result.get("display_markdown") or result.get("final_response") or "")
        print(f"\n---\nphase={result.get('phase')} packing_plan_id={result.get('packing_plan_id')}")
        print("请使用 --interactive 确认柜型，或 --demo 自动确认。")
    return 0


def cmd_interactive(args) -> int:
    print("=" * 60)
    print("装箱拼柜 · 最终架构（团队A → 用户确认 → 团队B）")
    print("输入材料清单，回车使用演示数据；quit 退出")
    print("=" * 60)

    while True:
        try:
            user = input("\n材料/指令> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0
        if user.lower() in ("quit", "exit", "q"):
            print("再见。")
            return 0
        if not user:
            user = "演示材料清单"

        state = run_team_a(user)
        print("\n" + (state.get("display_markdown") or state.get("final_response") or ""))
        print("\n--- 用户确认 ---")
        print("柜型默认 40HQ；输入: 40HQ / 40GP / 20GP / 45HQ")
        print("或: revise 去掉 钢梁 | cancel")

        try:
            conf = input("确认> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0

        if not conf or conf.upper() in ("40HQ", "40GP", "20GP", "45HQ"):
            ctype = conf.upper() if conf else "40HQ"
            if ctype not in ("40HQ", "40GP", "20GP", "45HQ"):
                ctype = "40HQ"
            state = apply_user_confirmation(
                state, action="confirm", container_type=ctype, max_containers=1
            )
            state = run_team_b(state)
            print("\n" + (state.get("final_response") or ""))
            side = ((state.get("image_data") or {}).get("side") or {}).get("path")
            if side:
                print(f"\n侧视图: {side}")
        elif conf.lower().startswith("revise") or conf.startswith("调整"):
            note = conf
            if conf.lower().startswith("revise"):
                note = conf[6:].strip() or conf
            state = run_team_a(user, adjust_note=note, materials=state.get("materials"))
            print("\n" + (state.get("display_markdown") or ""))
            print("（已重算团队A，请再次确认柜型；本轮简化为结束，可重新输入材料）")
        elif conf.lower() in ("cancel", "取消"):
            print("已取消。")
        else:
            # 把整句当柜型失败则当 revise
            if conf.upper() in ("40HQ", "40GP", "20GP", "45HQ"):
                state = apply_user_confirmation(state, action="confirm", container_type=conf.upper())
                state = run_team_b(state)
                print("\n" + (state.get("final_response") or ""))
            else:
                print("未识别，请输入柜型或 revise/cancel")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="装箱拼柜最终架构 CLI")
    p.add_argument("--input", "-i", default="", help="材料清单文本")
    p.add_argument("--container", "-c", default="40HQ", help="自动确认时的柜型")
    p.add_argument("--demo", action="store_true", help="自动确认跑完全程（默认 high_util 预设）")
    p.add_argument(
        "--preset",
        default="high_util",
        help=(
            "演示预设：high_util(默认,过合规门) / steel_light / five_containers / "
            "high_util_uniform / structure_fail(负例,演示合规阻断)"
        ),
    )
    p.add_argument("--team-a", action="store_true", help="只跑团队A")
    p.add_argument("--interactive", action="store_true", help="交互确认")
    p.add_argument("--json", action="store_true")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--save-trace", action="store_true")
    p.add_argument("--eval", action="store_true", help="现行评测：phase0 基线 quick")
    p.add_argument(
        "--cases",
        default="",
        help="显式指定旧黄金集 cases 文件（deprecated，仅历史回归）；默认忽略",
    )
    args = p.parse_args(argv)

    if args.eval:
        if args.cases:
            # 旧黄金集口径（boxes 上限等）已过时，仅作历史回归用。
            print(f"[eval] 旧黄金集（deprecated）：{args.cases}")
            from packing_assistant.eval_runner import run_eval

            passed, total, _ = run_eval(args.cases, verbose=True)
            return 0 if passed == total else 1

        # 现行评测（2026-08 起）：phase0 基线 quick，与
        # `python scripts/run_phase0_baseline.py --quick` 同一口径。
        # 旧 eval/cases.json 口径已 deprecated，未删除，可用 --cases 显式回归。
        from packing_assistant.phase0_benchmark import build_phase0_cases, run_baseline

        report = run_baseline(
            build_phase0_cases(include_heavy=False),
            agent_mode="steps",
            quick=True,
        )
        print("-" * 48)
        print(
            "EVAL phase0-quick:",
            "n=",
            report.get("n"),
            "passed=",
            report.get("passed"),
            "pass_rate=",
            report.get("pass_rate"),
            "avg_score=",
            report.get("avg_score"),
        )
        print("report:", (report.get("paths") or {}).get("md"))
        print("-" * 48)
        return 0 if float(report.get("pass_rate") or 0) >= 1.0 else 1

    if args.interactive:
        return cmd_interactive(args)
    if args.team_a:
        return cmd_team_a(args)
    # 默认 demo 全流程
    return cmd_demo(args)


if __name__ == "__main__":
    sys.exit(main())
