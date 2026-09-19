#!/usr/bin/env python3
"""Civil Buddy · 土木版 Codex CLI.

  civil                       TUI，在当前文件夹里工作
  civil "任务"                一次性 exec
  civil exec "任务" | -       非交互执行；- 从标准输入读任务
  civil exec --jsonl "任务"   逐行 JSON 事件流（thread.started → turn.started → item.* → turn.completed）
  civil --mode model "任务"   模型驱动：模型自己选岗位、读资料、调工具（默认 steps：规则路由，不调模型）
  civil -C <文件夹> ...       把该文件夹当作业文件夹（同 cd 进去再运行）
  civil init                  在当前文件夹写一份 CIVIL.md（本工程说明，相当于 Codex 的 AGENTS.md）
  civil status                作业文件夹、工程说明、sandbox / approval、模型
  civil app                   打开工作台应用
  civil mcp --pack bid        IDE stdio MCP
  civil serve                 JSON-RPC app-server（土木 harness，不是官方 Codex 二进制）
  civil skills
  civil resume <thread|--last> [任务]
  civil help
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIRM = "我明白，将由持证人员签认"
VERBS = ("tui", "exec", "app", "mcp", "serve", "skills", "resume", "help", "init", "status")


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
    from packing_assistant.runtime.turn import run_turn

    return run_turn(text, session_id=session_id or "civil-cli", skill=skill, confirm=confirm)


def list_skills():
    from packing_assistant.runtime.expert_skills import catalog

    return catalog()


def enter_workspace(folder: str = "") -> Optional[Path]:
    """-C names the job folder; otherwise the nearest CIVIL.md at or above cwd decides."""
    from packing_assistant.runtime.workspace import activate, find_job_root

    if folder:
        job = Path(folder).expanduser()
        if not job.is_dir():
            raise NotADirectoryError(f"-C 指向的不是文件夹：{folder}")
        os.chdir(job)
        return activate(job)
    job = find_job_root()
    return activate(job) if job else None


def display_path(path: str) -> str:
    """Relative to the job folder when the file is inside it, the way Codex prints repo paths."""
    from packing_assistant.runtime.workspace import active

    job = active()
    if job:
        try:
            return str(Path(path).resolve().relative_to(job))
        except (OSError, ValueError):
            pass
    return str(path)


def _file_paths(out: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for item in out.get("files") or out.get("artifacts") or []:
        path = str(item.get("path") or "") if isinstance(item, dict) else str(item)
        if path and path not in paths:
            paths.append(path)
    return paths


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
        how = {"given": "显式", "model": "模型选用"}.get(src, "选用")
        print(f"skill ${eid} · {out.get('expert_name') or eid} · {how}", file=sys.stderr)
    else:
        print("skill （未选用）" if out.get("agent_mode") == "model" else "skill （未选用，路由器）", file=sys.stderr)
    print(
        f"mode {out.get('agent_mode') or 'steps'} · intent {out.get('intent')} · wrote {out.get('wrote')} · "
        f"submit_blocked {out.get('submit_blocked')} · "
        f"sandbox {out.get('sandbox_mode')} · approval {out.get('approval')}",
        file=sys.stderr,
    )
    if out.get("hitl_pending"):
        print(f"approval 高风险写盘须确认句：{CONFIRM}", file=sys.stderr)
    if out.get("thread_id"):
        print(f"thread {out.get('thread_id')}", file=sys.stderr)
    print(out.get("reply") or "")
    for path in _file_paths(out):
        print(f"  + {display_path(path)}", file=sys.stderr)
    return 0 if out.get("ok", True) else 1


def codex_event(event: Any) -> Optional[Dict[str, Any]]:
    """One bus event as one line of the --jsonl stream. run_ended is folded into turn.completed."""
    payload = dict(getattr(event, "payload", None) or {})
    kind = getattr(event, "type", "")
    base = {"run_id": getattr(event, "run_id", ""), "ts": round(float(getattr(event, "ts", 0.0)), 3)}
    if kind == "run_started":
        return {"type": "turn.started", **base, "intent": payload.get("intent"), "skill": payload.get("expert_id") or ""}
    if kind == "tool_call":
        item = {"type": "tool_call", "name": payload.get("name")}
        if payload.get("arguments"):
            item["arguments"] = payload["arguments"]
        return {"type": "item.started", **base, "item": item}
    if kind == "tool_result":
        return {"type": "item.completed", **base, "item": {"type": "tool_call", **payload}}
    if kind == "hitl":
        return {"type": "approval.required", **base, "confirm_sentence": CONFIRM, **payload}
    if kind == "cancelled":
        return {"type": "turn.cancelled", **base, **payload}
    if kind == "plan":
        return {"type": "plan.updated", **base, **payload}
    if kind == "skill_loaded":
        return {"type": "item.completed", **base, "item": {"type": "skill", **payload}}
    if kind == "message":
        return {"type": "item.completed", **base, "item": {"type": "agent_message", **payload}}
    if kind == "guard":
        return {"type": "guard.flagged", **base, **payload}
    return None


def progress_line(event: Any) -> str:
    """One bus event as one short human line (exec prints these to stderr, the TUI inline)."""
    payload = dict(getattr(event, "payload", None) or {})
    kind = getattr(event, "type", "")
    if kind == "plan":
        marks = {"done": "x", "in_progress": ">", "pending": " "}
        return "\n".join(f"  [{marks.get(row.get('status'), ' ')}] {row.get('step')}" for row in payload.get("steps") or [])
    if kind == "skill_loaded":
        return f"  skill ${payload.get('id')} · {payload.get('name')}"
    if kind == "tool_call":
        arguments = payload.get("arguments") or {}
        brief = " ".join(str(value) for value in arguments.values() if isinstance(value, (str, int, float)))[:60]
        return f"  -> {payload.get('name')}" + (f" {brief}" if brief else "")
    if kind == "tool_result" and not payload.get("ok", True):
        return f"  !! {payload.get('name')}: {payload.get('error_code')}"
    if kind == "hitl":
        return f"  approval 高风险写盘须确认句：{CONFIRM}"
    if kind == "guard":
        return "  guard 无出处的数字：" + "、".join(payload.get("untraced") or [])
    return ""


def with_progress(run, write) -> Dict[str, Any]:
    """Run a turn while ``write(line)`` receives each progress line as it happens."""
    from packing_assistant.runtime.bus import get_bus

    def forward(event: Any) -> None:
        line = progress_line(event)
        if line:
            write(line)

    unsubscribe = get_bus().subscribe(forward)
    try:
        return run()
    finally:
        unsubscribe()


def _emit(line: Dict[str, Any]) -> None:
    print(json.dumps(line, ensure_ascii=False, default=str), flush=True)


def run_jsonl(run, *, thread_id: str = "", last_message_file: str = "") -> int:
    """Run one turn while printing every event as a JSON line, as ``codex exec --json`` does."""
    from packing_assistant.runtime.bus import get_bus
    from packing_assistant.runtime.workspace import active

    _emit({"type": "thread.started", "thread_id": thread_id, "job_root": str(active() or "")})

    root: List[str] = []

    def forward(event: Any) -> None:
        line = codex_event(event)
        if not line:
            return
        # 模型驱动的一轮里，run_skill 会在内部再跑一遍确定性流程（它有自己的 run_id）。
        # 对读事件流的人来说那是这一轮里的一步，不是又一轮：不再报 turn.started，其余标 nested。
        if not root:
            root.append(line["run_id"])
        elif line["run_id"] != root[0]:
            if line["type"] == "turn.started":
                return
            line["nested"] = True
        _emit(line)

    unsubscribe = get_bus().subscribe(forward)
    try:
        out = run()
    except Exception as exc:  # noqa: BLE001 - the stream must end with a terminal event
        _emit({"type": "turn.failed", "error": f"{type(exc).__name__}: {exc}"})
        return 1
    finally:
        unsubscribe()
    done = {
        "type": "turn.completed" if out.get("ok", True) else "turn.failed",
        "ok": bool(out.get("ok", True)),
        "thread_id": out.get("thread_id") or thread_id,
        "skill": out.get("skill") or "",
        "agent_mode": out.get("agent_mode") or "",
        "intent": out.get("intent"),
        "wrote": bool(out.get("wrote")),
        "hitl_pending": bool(out.get("hitl_pending")),
        "submit_blocked": True,
        "error_code": out.get("error_code") or "",
        "files": [display_path(p) for p in _file_paths(out)],
        "reply": out.get("reply") or "",
    }
    for key in ("provenance", "plan", "usage", "mode_notice"):
        if out.get(key):
            done[key] = out[key]
    if last_message_file:
        Path(last_message_file).write_text(done["reply"], encoding="utf-8")
    _emit(done)
    return 0 if done["ok"] else 1


def cmd_app(port: Optional[int], *, no_browser: bool = False) -> int:
    from packing_assistant.runtime.launcher import run_workbench

    return run_workbench(port, no_browser=no_browser)


def cmd_mcp(pack: str, expert: str) -> int:
    demo = Path(__file__).resolve().parents[1] / "demo" / "mcp_stdio.py"
    args = [sys.executable, str(demo)]
    if expert:
        args.extend(["--expert", expert])
    elif pack:
        args.extend(["--pack", pack])
    else:
        args.extend(["--pack", "construction"])
    return int(subprocess.call(args))


def cmd_init() -> int:
    from packing_assistant.runtime.project_instructions import init
    from packing_assistant.runtime.workspace import activate

    path, created = init(Path.cwd())
    activate(Path.cwd())
    if created:
        print(f"已写入 {path.name}。填上项目、辖区等你确认过的事实；留空的栏在成稿里保持 UNSPECIFIED。")
    else:
        print(f"{path.name} 已存在，未改动。")
    return 0


def status_text() -> str:
    from packing_assistant.llm import llm_config
    from packing_assistant.runtime.civil_config import load_config
    from packing_assistant.runtime.workspace import describe

    from packing_assistant.runtime.turn import resolve_mode

    cfg, space, llm = load_config(), describe(), llm_config()
    running, why = resolve_mode()
    lines = [
        f"job      {space['job_root'] or '（未进入作业文件夹；civil init 或 civil -C <文件夹>）'}",
        f"state    {space['state_root'] or '仓库 demo/out'}",
        "CIVIL.md " + (", ".join(display_path(p) for p in space["instruction_files"]) or "（无）"),
    ]
    if space["slots"]:
        lines.append("slots    " + " · ".join(f"{k}={v}" for k, v in space["slots"].items()))
    lines += [
        f"sandbox  {cfg.sandbox}",
        f"approval {cfg.approval}",
        f"mode     {cfg.agent_mode}" + (f" → {running}" if running != cfg.agent_mode else "")
        + "  （steps 规则路由不调模型 · model 模型驱动 · auto 有模型就用；--mode / /mode / CIVIL_AGENT_MODE）",
        f"model    {llm['model']} @ {llm['base_url']}" + ("" if llm.get("api_key") else "  （未配置 Key）"),
    ]
    if why:
        lines.append("         " + why)
    return "\n".join(lines)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--cd", "-C", default="", metavar="DIR", help="作业文件夹（默认：当前目录向上最近的 CIVIL.md）")
    p.add_argument("--skill", "-s", default="", help="强制 skill id")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--session", default="")
    p.add_argument("--thread", default="")
    p.add_argument("--last", action="store_true", help="resume：接着最近一个 thread")
    p.add_argument("--bg", action="store_true")
    p.add_argument("--json", action="store_true", help="结束后打印完整结果（一个 JSON）")
    p.add_argument("--jsonl", action="store_true", help="逐行 JSON 事件流")
    p.add_argument("--output-last-message", "-o", default="", metavar="FILE", help="把最终回复另存到文件")
    p.add_argument("--mode", default="", help="steps | model | auto")
    p.add_argument("--sandbox", default="", help="read-only | workspace-write")
    p.add_argument("--approval", default="", help="untrusted | on-request | never")
    p.add_argument("--list-skills", action="store_true")
    p.add_argument("--port", type=int, default=None, help="工作台端口，默认 CIVIL_PORT 或 8765")
    p.add_argument("--no-browser", action="store_true", help="启动工作台后不自动打开浏览器")
    p.add_argument("--pack", default="")
    p.add_argument("--expert", default="")
    p.add_argument("rest", nargs="*", help="任务或 resume 的 thread id")


def _stderr(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def _finish(out: Dict[str, Any], args: argparse.Namespace) -> int:
    if args.output_last_message:
        Path(args.output_last_message).write_text(str(out.get("reply") or ""), encoding="utf-8")
    return _print_out(out, as_json=args.json)


_VALUE_OPTIONS = frozenset({"--cd", "-C", "--skill", "-s", "--session", "--thread", "--output-last-message", "-o",
                            "--sandbox", "--approval", "--port", "--pack", "--expert", "--mode"})


def split_verb(argv: List[str]) -> tuple[str, List[str]]:
    """The verb is the first word that is not an option or an option's value."""
    skip = False
    for index, token in enumerate(argv):
        if skip:
            skip = False
            continue
        if token.startswith("-") and token != "-":
            skip = token in _VALUE_OPTIONS
            continue
        if token in VERBS:
            return token, argv[:index] + argv[index + 1:]
        break
    return "", argv


def main(argv: Optional[List[str]] = None) -> int:
    verb, argv = split_verb(list(sys.argv[1:] if argv is None else argv))
    p = argparse.ArgumentParser(prog="civil", add_help=True)
    _common(p)
    args = p.parse_args(argv)
    if args.sandbox:
        os.environ["CIVIL_SANDBOX"] = args.sandbox
    if args.approval:
        os.environ["CIVIL_APPROVAL"] = args.approval
    if args.mode:
        os.environ["CIVIL_AGENT_MODE"] = args.mode
    try:
        enter_workspace(args.cd)
    except (OSError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

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

        print(__doc__.strip() + "\n\nTUI 内：\n" + HELP)
        return 0
    if verb == "init":
        return cmd_init()
    if verb == "status":
        print(status_text())
        return 0
    if verb == "app":
        return cmd_app(args.port, no_browser=args.no_browser)
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
        from packing_assistant.runtime.threads import list_threads, run_on_thread

        if args.last:
            recent = list_threads()
            if not recent:
                print("还没有 thread 可以接着做。", file=sys.stderr)
                return 2
            tid, task = recent[0].thread_id, " ".join(rest).strip() or "继续"
        elif rest:
            tid, task = rest[0], " ".join(rest[1:]).strip() or "继续"
        else:
            print("civil resume <thread_id> [任务]  或  civil resume --last [任务]", file=sys.stderr)
            return 2
        def resumed() -> Dict[str, Any]:
            return run_on_thread(tid, task, skill=args.skill, confirm=args.confirm)

        if args.jsonl:
            return run_jsonl(resumed, thread_id=tid, last_message_file=args.output_last_message)
        return _finish(resumed() if args.json else with_progress(resumed, _stderr), args)

    text = " ".join(rest).strip()
    if text == "-":
        text = sys.stdin.read().strip()
    if verb == "exec" and not text:
        print("civil exec 需要任务文本（或用 - 从标准输入读）", file=sys.stderr)
        return 2
    if not text and verb in {"", "tui"}:
        from packing_assistant.civil_tui import run_tui

        return run_tui()
    if not text:
        print("需要任务文本，或直接运行 civil 进入 TUI", file=sys.stderr)
        return 2

    def turn() -> Dict[str, Any]:
        return run_task(
            text,
            skill=args.skill,
            confirm=args.confirm,
            session_id=args.session or args.thread or "civil-cli",
            thread_id=args.thread,
            background=args.bg,
        )

    if args.jsonl:
        return run_jsonl(turn, thread_id=args.thread, last_message_file=args.output_last_message)
    return _finish(turn() if args.json else with_progress(turn, _stderr), args)


if __name__ == "__main__":
    raise SystemExit(main())
