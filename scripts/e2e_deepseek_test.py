#!/usr/bin/env python3
"""
完整端到端测试：DeepSeek Flash + 团队A/B + 知识库 + 3D装载。

用法（项目根目录）:
  python scripts/e2e_deepseek_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 先加载 .env
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


def _setup_deepseek_env():
    """配置 DeepSeek Flash；优先 deepseek api.txt / .env / 官方 key。"""
    os.environ.setdefault("LLM_MODEL", "deepseek-v4-flash")
    os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")
    os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com")
    os.environ.setdefault("LLM_BASE_URL", "https://api.deepseek.com")

    # 项目内 key 文件（用户指定）
    for name in ("deepseek api.txt", "deepseek_api.txt", "deepseek-api.txt"):
        key_file = ROOT / name
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
            if key.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = key
                os.environ["OPENAI_API_KEY"] = key
                os.environ["LLM_API_KEY"] = key
                return f"file:{name}"

    if os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"):
        key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        os.environ["OPENAI_API_KEY"] = key or ""
        os.environ["DEEPSEEK_API_KEY"] = key or ""
        return "env"

    return "none"


def _ping_llm() -> dict:
    from packing_assistant.llm import chat, llm_config

    cfg = llm_config()
    t0 = time.time()
    text = chat(
        system="你是测试助手，只回复一个词：OK",
        user="ping",
        temperature=0,
        max_tokens=32,
    )
    return {
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "has_key": bool(cfg.get("api_key")),
        "reply": text,
        "ms": int((time.time() - t0) * 1000),
        "ok": bool(text) and not str(text).startswith("[LLM_ERROR]"),
    }


def _try_models(models: list[str]) -> dict:
    """依次尝试模型名，返回第一个成功的 ping 结果。"""
    last = {}
    for m in models:
        os.environ["LLM_MODEL"] = m
        os.environ["DEEPSEEK_MODEL"] = m
        # 清掉可能缓存的客户端：无缓存则直接测
        last = _ping_llm()
        last["tried_model"] = m
        if last.get("ok"):
            return last
    return last


def run_full() -> dict:
    from packing_assistant.harness import (
        apply_user_confirmation,
        public_response,
        run_pipeline,
        run_team_a,
        run_team_b,
    )
    from packing_assistant.knowledge import kb_version
    from packing_assistant.llm import llm_config

    report: dict = {
        "kb_version": kb_version(),
        "llm": llm_config(),
        "steps": [],
    }

    # —— 1) LLM ping ——
    print("=" * 60)
    print("1) LLM ping (DeepSeek Flash)")
    ping = _try_models(
        [
            os.getenv("LLM_MODEL") or "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-chat",
            "deepseek-v3",
            "qwen-flash",
            "qwen2.5-72b-instruct",
        ]
    )
    report["steps"].append({"name": "llm_ping", **ping})
    print(json.dumps(ping, ensure_ascii=False, indent=2))
    if not ping.get("ok"):
        print("WARNING: LLM 不可用，将继续跑规则引擎全流程（无 LLM 增强）")

    # —— 2) 团队A only ——
    print("=" * 60)
    print("2) 团队A（材料解析→结构→装箱→等待确认）")
    sample = (
        "镀锌钢通 H400 4件 85kg 3800x400x200\n"
        "钢梁 H350 6件 55kg 4200x350x175\n"
        "连接板组件 20件 12kg 800x600x400"
    )
    t0 = time.time()
    state_a = run_team_a(sample, session_id="e2e-deepseek")
    report["steps"].append(
        {
            "name": "team_a",
            "ms": int((time.time() - t0) * 1000),
            "phase": state_a.get("phase"),
            "materials": len(state_a.get("materials") or []),
            "boxes": len(state_a.get("boxes") or []),
            "parse_msg": (state_a.get("messages") or [{}])[-1].get("content")
            if state_a.get("messages")
            else "",
            "box_types": [b.get("box_type") for b in (state_a.get("boxes") or [])],
        }
    )
    print(
        f"  phase={state_a.get('phase')} boxes={len(state_a.get('boxes') or [])} "
        f"materials={len(state_a.get('materials') or [])}"
    )

    # —— 3) 用户确认 + 团队B ——
    print("=" * 60)
    print("3) 用户确认 40HQ → 团队B")
    t0 = time.time()
    state_b = apply_user_confirmation(
        state_a, action="confirm", container_type="40HQ", max_containers=1
    )
    state_b = run_team_b(state_b)
    plan = state_b.get("container_plan") or {}
    risk = state_b.get("risk_report") or {}
    report["steps"].append(
        {
            "name": "team_b",
            "ms": int((time.time() - t0) * 1000),
            "phase": state_b.get("phase"),
            "engine": plan.get("engine"),
            "can_fit": plan.get("can_fit"),
            "space": plan.get("space_utilization"),
            "weight": plan.get("weight_utilization"),
            "risk_score": risk.get("compliance_score"),
            "risk_level": risk.get("level"),
            "views": list((state_b.get("views") or {}).keys()),
            "final_preview": (state_b.get("final_response") or "")[:400],
        }
    )
    print(
        f"  phase={state_b.get('phase')} engine={plan.get('engine')} "
        f"can_fit={plan.get('can_fit')} risk={risk.get('level')}/{risk.get('compliance_score')}"
    )
    print("--- final_response preview ---")
    print((state_b.get("final_response") or "")[:800])

    # —— 4) 全流程 auto_confirm ——
    print("=" * 60)
    print("4) run_pipeline auto_confirm（含 LLM 若可用）")
    t0 = time.time()
    full = run_pipeline(
        "演示：REDACTED-PROJECT钢结构件",
        container_type="40HQ",
        enable_auto_confirm=True,
    )
    report["steps"].append(
        {
            "name": "full_auto",
            "ms": int((time.time() - t0) * 1000),
            "phase": full.get("phase"),
            "status": full.get("status"),
            "engine": (full.get("container_plan") or {}).get("engine"),
            "boxes": len(full.get("boxes") or []),
            "trace_nodes": len({t.get("node") for t in (full.get("traces") or [])}),
            "llm_in_final": "LLM:" in (full.get("final_response") or "")
            or "deepseek" in (full.get("final_response") or "").lower(),
        }
    )
    print(
        f"  phase={full.get('phase')} traces={report['steps'][-1]['trace_nodes']} "
        f"engine={report['steps'][-1]['engine']}"
    )

    # —— 5) eval ——
    print("=" * 60)
    print("5) 黄金集 eval")
    from packing_assistant.eval_runner import run_eval

    passed, total, results = run_eval(verbose=True)
    report["steps"].append(
        {
            "name": "eval",
            "passed": passed,
            "total": total,
            "all_ok": passed == total,
            "failed": [r.case_id for r in results if not r.passed],
        }
    )

    # —— 汇总 ——
    report["public"] = public_response(full)
    # 去掉过大字段
    if "public" in report:
        report["public"].pop("display_markdown", None)
        fr = report["public"].get("final_response") or ""
        report["public"]["final_response"] = fr[:600]

    ok = (
        report["steps"][1].get("phase") == "await_user_confirm"
        and report["steps"][2].get("phase") == "done"
        and report["steps"][3].get("phase") == "done"
        and report["steps"][4].get("all_ok")
    )
    report["e2e_ok"] = ok
    report["llm_ok"] = bool(ping.get("ok"))

    out_path = ROOT / "output" / "e2e_deepseek_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("=" * 60)
    print(f"报告: {out_path}")
    print(f"E2E={'PASS' if ok else 'FAIL'}  LLM={'PASS' if ping.get('ok') else 'FAIL/SKIP'}")
    return report


def main() -> int:
    src = _setup_deepseek_env()
    print(f"LLM 配置来源: {src}")
    print(f"LLM_MODEL={os.getenv('LLM_MODEL')}")
    print(f"BASE={os.getenv('OPENAI_BASE_URL') or os.getenv('DEEPSEEK_BASE_URL')}")
    report = run_full()
    # LLM 失败不阻塞 e2e 规则链路；但用户要求 deepseek，尽量标出
    if not report.get("e2e_ok"):
        return 1
    if not report.get("llm_ok"):
        print("注意：规则全流程通过，但 DeepSeek LLM 调用未成功，请检查 API Key / 模型名。")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
