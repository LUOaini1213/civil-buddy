#!/usr/bin/env python3
"""Civil Buddy · 完整土木版 Codex CLI.

  civil                      TUI
  civil "任务"               一次性 exec
  civil exec "任务"
  civil app                  打开工作台应用
  civil mcp --pack bid       IDE stdio MCP
  civil serve                JSON-RPC app-server（土木 harness，不是官方 Codex 二进制）
  civil skills
  civil resume <thread> 任务
  civil help
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from typing import List, Optional

CONFIRM = "我明白，将由持证人员签认"
VERBS = ("tui", "exec", "app", "mcp", "serve", "skills", "resume", "help")


def run_task(
    text: str,
    *,
    skill: str = "",
    confirm: bool = False,
    session_id: str = "",
    thread_id: str = "",
    background: bool = False,
):
    if thread_id or background:
        from packing_assistant.runtime.threads import new_thread, run_on_thread, spawn

        if background and not thread_id:
            return spawn(text, skill=skill, confirm=confirm, title=text[:40])
        tid = thread_id or new_thread(text[:40], confirm=confirm).thread_id
        return run_on_thread(tid, text, skill=skill, confirm=confirm, background=background)
    from packing_assistant.runtime.agent_loop import run_agent

    return run_agent(
        text,
        session_id=session_id or "civil-cli",
        expert_id=skill,
        p0_confirmed=confirm,
    )


def list_skills():
    from packing_assistant.runtime.expert_skills import catalog

    return catalog()


def _print_out(out: dict, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0 if out.get("ok") else 1
    if out.get("background"):
        print(f"thread {out.get('thread_id')} 后台 {out.get('state')}", file=sys.stderr)
        return 0
    eid = out.get("skill") or out.get("expert_id") or ""
    src = out.get("skill_source") or ""
    if eid:
        how = "显式" if src == "given" else "选用"
        print(f"skill ${eid} · {out.get('expert_name') or eid} · {how}", file=sys.stderr)
    else:
        print("skill （未选用，路由器）", file=sys.stderr)
    print(
        f"intent {out.get('intent')} · wrote {out.get('wrote')} · "
        f"submit_blocked {out.get('submit_blocked')} · "
        f"sandbox {out.get('sandbox_mode')} · approval {out.get('approval')}",
        file=sys.stderr,
    )
    if out.get("hitl_pending"):
        print(f"approval 高风险写盘须确认句：{CONFIRM}", file=sys.stderr)
    if out.get("thread_id"):
        print(f"thread {out.get('thread_id')}", file=sys.stderr)
    print(out.get("reply") or "")
    files = out.get("files") or out.get("artifacts") or []
    if files:
        print("files:", files, file=sys.stderr)
    return 0 if out.get("ok", True) else 1


def cmd_app(port: int) -> int:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    demo = root / "demo"
    use = port or int(os.environ.get("CIVIL_PORT") or "8765")
    env = os.environ.copy()
    env.setdefault("CIVIL_PORT", str(use))
    print(f"Civil Codex app  http://127.0.0.1:{use}", file=sys.stderr)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(use)],
        cwd=str(demo),
        env=env,
    )
    time.sleep(0.8)
    try:
        webbrowser.open(f"http://127.0.0.1:{use}")
    except Exception:
        pass
    try:
        return int(proc.wait())
    except KeyboardInterrupt:
        proc.terminate()
        return 0


def cmd_mcp(pack: str, expert: str) -> int:
    from pathlib import Path

    demo = Path(__file__).resolve().parents[1] / "demo" / "mcp_stdio.py"
    args = [sys.executable, str(demo)]
    if expert:
        args.extend(["--expert", expert])
    elif pack:
        args.extend(["--pack", pack])
    else:
        args.extend(["--pack", "construction"])
    return int(subprocess.call(args))


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--skill", "-s", default="", help="强制 skill id")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--session", default="")
    p.add_argument("--thread", default="")
    p.add_argument("--bg", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--sandbox", default="", help="read-only | workspace-write")
    p.add_argument("--approval", default="", help="untrusted | on-request | never")
    p.add_argument("--list-skills", action="store_true")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--pack", default="")
    p.add_argument("--expert", default="")
    p.add_argument("rest", nargs="*", help="任务或 resume 的 thread id")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = ""
    if argv and argv[0] in VERBS:
        verb = argv[0]
        argv = argv[1:]
    p = argparse.ArgumentParser(prog="civil", add_help=True)
    _common(p)
    args = p.parse_args(argv)
    if args.sandbox:
        os.environ["CIVIL_SANDBOX"] = args.sandbox
    if args.approval:
        os.environ["CIVIL_APPROVAL"] = args.approval

    rest: List[str] = list(args.rest or [])
    if args.list_skills or verb == "skills":
        rows = list_skills()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            from packing_assistant.runtime.expert_skills import format_catalog_listing

            print(format_catalog_listing())
        return 0
    if verb == "help":
        from packing_assistant.civil_tui import HELP

        print(HELP)
        return 0
    if verb == "app":
        return cmd_app(args.port)
    if verb == "mcp":
        return cmd_mcp(args.pack or "construction", args.expert)
    if verb == "serve":
        from packing_assistant.runtime.app_server import serve_stdio

        print("civil-app-server/v1 stdio · 不是 openai/codex", file=sys.stderr)
        return serve_stdio()
    if verb == "tui":
        from packing_assistant.civil_tui import run_tui

        return run_tui()
    if verb == "resume":
        if not rest:
            print("civil resume <thread_id> [任务]", file=sys.stderr)
            return 2
        tid, task = rest[0], " ".join(rest[1:]).strip() or "继续"
        from packing_assistant.runtime.threads import run_on_thread

        out = run_on_thread(tid, task, skill=args.skill, confirm=args.confirm)
        return _print_out(out, as_json=args.json)

    text = " ".join(rest).strip()
    if verb == "exec" and not text:
        print("civil exec 需要任务文本", file=sys.stderr)
        return 2
    if not text and verb in {"", "tui"}:
        from packing_assistant.civil_tui import run_tui

        return run_tui()
    if not text:
        print("需要任务文本，或直接运行 civil 进入 TUI", file=sys.stderr)
        return 2

    out = run_task(
        text,
        skill=args.skill,
        confirm=args.confirm,
        session_id=args.session or args.thread or "civil-cli",
        thread_id=args.thread,
        background=args.bg,
    )
    return _print_out(out, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
