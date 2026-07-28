#!/usr/bin/env python3
"""
多轮测试：固定测试套件连跑 N 轮，汇总稳定/偶发失败。

  python scripts/run_multi_round_tests.py
  python scripts/run_multi_round_tests.py --rounds 3 --suite quick
  python scripts/run_multi_round_tests.py --rounds 2 --suite full

suite:
  smoke  — 体积门禁 + 评估器 + 详设/待详设
  quick  — smoke + booking_regression + p2_volume_gates
  agent  — smoke + demo_agent_closed_loop
  full   — quick + agent + precommit --quick
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "multi_round_tests"


def _run(cmd: List[str], timeout: int = 300) -> Tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(ROOT),
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
        return int(r.returncode), out[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, str(e)


def suite_commands(suite: str) -> List[Dict[str, Any]]:
    py = sys.executable
    smoke = [
        {
            "id": "volume_gates",
            "cmd": [py, "scripts/check_volume_gates.py"],
            "timeout": 60,
        },
        {
            "id": "evaluator_weights",
            "cmd": [
                py,
                "-c",
                (
                    "from packing_assistant.agents.evaluator import agent_evaluator,_resolve_weights;"
                    "assert _resolve_weights({},'weight')[2]>0.5;"
                    "assert _resolve_weights({},'volume')[0]>0.45;"
                    "st={'container_plan':{'can_fit':True,'unpacked_box_ids':[],"
                    "'booking_volume_utilization':0.18,'outer_space_utilization':0.3,"
                    "'floor_utilization_avg':0.4,'weight_utilization':0.55,"
                    "'containers_used':2,'n0':1,"
                    "'booking':{'n0':1,'binding_constraint':'weight',"
                    "'containers_by_weight':1,'containers_by_volume':1}},"
                    "'boxes':[{'box_id':'B1','structure_conclusion':'通过'}],"
                    "'plan':{'max_containers':10,'n0':1},"
                    "'orchestrator':{'goals':{'targets':{}}},'replan_round':0};"
                    "ev=agent_evaluator(st)['evaluation'];"
                    "assert ev['space_subscore_deprecated'];"
                    "assert ev['metrics_table']['outer_space_utilization']['in_score'] is False;"
                    "print('evaluator_ok',ev['score'],ev['util_weights']['policy'])"
                ),
            ],
            "timeout": 60,
        },
        {
            "id": "structure_design_facts",
            "cmd": [
                py,
                "-c",
                (
                    "from packing_assistant.tools.structure_calc import run_structure_calc;"
                    "from packing_assistant.tools.design_facts import load_design_facts;"
                    "from packing_assistant.tools.section_provider import reload_steel_table;"
                    "reload_steel_table();"
                    "kw=dict(box_type='4米铁架',"
                    "outer_mm={'长':4000,'宽':1150,'高':1200},"
                    "inner_mm={'长':3900,'宽':1050,'高':1100},"
                    "items=[{'外尺寸_mm':{'长':3800,'宽':200,'高':200},'数量':2,'单重_kg':80}],"
                    "tare_kg=180,max_payload_kg=3500,is_steel_frame=True);"
                    "r0=run_structure_calc(**kw,design_facts={});"
                    "assert r0.get('结论')=='待详设', r0.get('结论');"
                    "facts=load_design_facts();"
                    "r1=run_structure_calc(**kw,design_facts=facts);"
                    "assert r1.get('fidelity')=='detailed_design', r1.get('fidelity');"
                    "assert r1.get('结论') in ('通过','需加强','不通过'), r1.get('结论');"
                    "print('structure_ok', r0.get('结论'), r1.get('结论'), r1.get('section_used',{}).get('frame'))"
                ),
            ],
            "timeout": 90,
        },
        {
            "id": "nl_revision_parse",
            "cmd": [
                py,
                "-c",
                (
                    "from packing_assistant.tools.nl_revision import parse_nl_revision;"
                    "p=parse_nl_revision('柜型改成40GP；框架用槽钢16#，底板槽钢14#3根，γ=2.0');"
                    "ops={o['op'] for o in p['ops']};"
                    "assert 'set_container_type' in ops;"
                    "assert 'set_frame_section' in ops;"
                    "assert 'set_bottom_beam' in ops;"
                    "print('nl_ok', sorted(ops))"
                ),
            ],
            "timeout": 30,
        },
    ]
    reg = [
        {
            "id": "booking_regression",
            "cmd": [py, "scripts/test_booking_regression.py"],
            "timeout": 180,
        },
        {
            "id": "p2_volume_gates",
            "cmd": [py, "scripts/test_p2_volume_gates.py"],
            "timeout": 180,
        },
    ]
    agent = [
        {
            "id": "agent_closed_loop",
            "cmd": [py, "scripts/demo_agent_closed_loop.py", "--tiny"],
            "timeout": 180,
        },
    ]
    pre = [
        {
            "id": "precommit_quick",
            "cmd": [py, "scripts/run_precommit_tests.py", "--quick"],
            "timeout": 400,
        },
    ]
    suite = (suite or "quick").lower()
    if suite == "smoke":
        return smoke
    if suite == "agent":
        return smoke + agent
    if suite == "full":
        return smoke + reg + agent + pre
    # quick default
    return smoke + reg


def run_round(round_i: int, tests: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("\n" + "#" * 60)
    print(f"ROUND {round_i}")
    print("#" * 60)
    results = []
    ok_all = True
    t0 = time.time()
    for t in tests:
        tid = t["id"]
        print(f"\n--- [{round_i}] {tid} ---")
        code, out = _run(t["cmd"], timeout=int(t.get("timeout") or 180))
        ok = code == 0
        ok_all = ok_all and ok
        print(f"EXIT {code} {tid}")
        if not ok:
            print(out[-800:])
        results.append(
            {
                "id": tid,
                "ok": ok,
                "exit_code": code,
                "tail": out[-500:] if not ok else (out.strip().splitlines()[-1] if out.strip() else "OK"),
            }
        )
    return {
        "round": round_i,
        "ok": ok_all,
        "duration_s": round(time.time() - t0, 2),
        "tests": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="多轮测试")
    ap.add_argument("--rounds", "-n", type=int, default=3, help="轮数，默认 3")
    ap.add_argument(
        "--suite",
        default="quick",
        choices=["smoke", "quick", "agent", "full"],
        help="测试套件",
    )
    ap.add_argument("--stop-on-fail", action="store_true", help="任一轮失败即停")
    args = ap.parse_args()

    rounds = max(1, int(args.rounds))
    tests = suite_commands(args.suite)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"multi-round suite={args.suite} rounds={rounds} tests={[t['id'] for t in tests]}")

    round_reports: List[Dict[str, Any]] = []
    for i in range(1, rounds + 1):
        rep = run_round(i, tests)
        round_reports.append(rep)
        if args.stop_on_fail and not rep["ok"]:
            print(f"STOP on fail at round {i}")
            break

    # 稳定性汇总
    by_test: Dict[str, List[bool]] = {}
    for r in round_reports:
        for t in r["tests"]:
            by_test.setdefault(t["id"], []).append(bool(t["ok"]))

    stability = {}
    for tid, flags in by_test.items():
        n = len(flags)
        p = sum(1 for x in flags if x)
        stability[tid] = {
            "pass_rounds": p,
            "total_rounds": n,
            "stable_pass": p == n,
            "flaky": 0 < p < n,
            "always_fail": p == 0,
        }

    all_green = all(r["ok"] for r in round_reports)
    summary = {
        "suite": args.suite,
        "rounds_planned": rounds,
        "rounds_run": len(round_reports),
        "all_green": all_green,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stability": stability,
        "rounds": round_reports,
    }

    out_json = OUT_DIR / f"multi_round_{args.suite}_{ts}.json"
    out_latest = OUT_DIR / "latest.json"
    out_md = OUT_DIR / f"multi_round_{args.suite}_{ts}.md"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    out_latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 多轮测试报告 · {args.suite} × {len(round_reports)}",
        "",
        f"- 时间：{summary['generated_at']}",
        f"- 全绿：{'是' if all_green else '否'}",
        "",
        "## 稳定性",
        "",
        "| 测试 | 通过轮 | 稳定 | 偶发 |",
        "|------|--------|------|------|",
    ]
    for tid, s in stability.items():
        lines.append(
            f"| {tid} | {s['pass_rounds']}/{s['total_rounds']} | "
            f"{'Y' if s['stable_pass'] else 'N'} | {'Y' if s['flaky'] else 'N'} |"
        )
    lines.extend(["", "## 各轮", ""])
    for r in round_reports:
        lines.append(f"### Round {r['round']} · {'PASS' if r['ok'] else 'FAIL'} · {r['duration_s']}s")
        for t in r["tests"]:
            mark = "OK" if t["ok"] else "FAIL"
            lines.append(f"- [{mark}] {t['id']} exit={t['exit_code']}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("\n" + "=" * 60)
    print("ALL_GREEN" if all_green else "HAS_FAILURES")
    print("JSON", out_json)
    print("MD  ", out_md)
    print("LATEST", out_latest)
    for tid, s in stability.items():
        flag = "STABLE" if s["stable_pass"] else ("FLAKY" if s["flaky"] else "FAIL")
        print(f"  {flag:6} {tid} {s['pass_rounds']}/{s['total_rounds']}")

    return 0 if all_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
