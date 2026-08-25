"""Interactive Civil Codex TUI: slash commands, $skills, threads, approvals."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

from packing_assistant.runtime.civil_config import CONFIRM, APPROVAL_MODES, SANDBOX_MODES, load_config

HELP = """/help              本页
/status            sandbox · approval · thread · 作业根 · 会话槽
/skills [词]       技能目录（name + description）
/approvals [mode]  untrusted | on-request | never
/sandbox [mode]    read-only | workspace-write
/new [标题]        新 thread（可并行）
/threads           列出 thread
/resume <id>       切到该 thread
/bg <任务>         在新 thread 后台跑
/files             本 thread 交付物
/confirm           本 thread 视同已打确认句
/mcp               IDE/MCP 怎么挂
/quit              退出

任务直接回车。显式 skill： $construction  或  @施工方案
高风险写盘确认句：""" + CONFIRM


def _enable_vt() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def _c(code: str, text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


class TuiState:
    def __init__(self) -> None:
        from packing_assistant.runtime.threads import new_thread

        self.cfg = load_config()
        self.thread = new_thread("主对话")
        self.confirm = self.cfg.auto_confirm()
        self.last_skill = ""
        self.last_skill_source = ""


def _banner(st: TuiState) -> None:
    from packing_assistant.office_job import job_root, job_root_granted
    from packing_assistant.runtime.expert_skills import list_expert_skill_ids

    n = len(list_expert_skill_ids())
    root = str(job_root()) if job_root_granted() else st.cfg.job_root or "（cwd/.civil-buddy/out）"
    print(_c("1", "Civil Buddy · 土木版 Codex"))
    print(
        f"  thread {st.thread.thread_id}  sandbox {st.cfg.sandbox}  "
        f"approval {st.cfg.approval}  skills {n}"
    )
    print(f"  job {root}")
    print(_c("2", "  /help  /skills  /new  /bg  /approvals  /sandbox   空行退出"))
    print()


def _print_out(out: Dict[str, Any]) -> None:
    eid = out.get("skill") or out.get("expert_id") or ""
    src = out.get("skill_source") or ""
    if eid:
        how = "显式" if src == "given" else "选用"
        print(_c("36", f"skill ${eid} · {out.get('expert_name') or eid} · {how}"))
    else:
        print(_c("36", "skill （路由器）"))
    bits = [
        f"intent {out.get('intent')}",
        f"wrote {out.get('wrote')}",
        f"submit_blocked {out.get('submit_blocked')}",
    ]
    if out.get("sandbox_mode"):
        bits.append(f"sandbox {out.get('sandbox_mode')}")
    if out.get("approval"):
        bits.append(f"approval {out.get('approval')}")
    print(_c("2", " · ".join(bits)))
    if out.get("hitl_pending"):
        print(_c("33", f"approval 须确认句：{CONFIRM}"))
    print(out.get("reply") or "")
    files = out.get("artifacts") or out.get("files") or []
    if files:
        print(_c("2", "files: " + ", ".join(str(f) for f in files)))
    print()


def _slash_skills(q: str) -> str:
    from packing_assistant.runtime.expert_skills import format_catalog_listing

    return format_catalog_listing(q, limit=30)


def _slash_mcp() -> str:
    return (
        "IDE 面：Cursor / VS Code / Grok 挂 MCP，不另装专有插件二进制。\n"
        "  python -m packing_assistant.civil mcp --pack construction\n"
        "  配置样例：ide/cursor/mcp.json  ·  ide/vscode/mcp.json  ·  docs/civil-buddy/mcp-host.example.toml\n"
        "不要把 API Key 写进 MCP 配置。"
    )


def handle_slash(line: str, st: TuiState) -> Optional[str]:
    raw = line.strip()
    if not raw.startswith("/"):
        return None
    parts = raw[1:].split(None, 1)
    cmd = (parts[0] or "").lower()
    arg = parts[1] if len(parts) > 1 else ""
    if cmd in {"help", "h", "?"}:
        return HELP
    if cmd == "quit" or cmd == "exit" or cmd == "q":
        raise SystemExit(0)
    if cmd == "status":
        from packing_assistant.runtime.memory import assemble_context, prompt_prefix

        ctx = assemble_context(st.thread.session_id)
        src = st.last_skill_source
        how = "显式" if src == "given" else "规则选用" if src == "matched" else "未点名"
        skill = f"${st.last_skill}" if st.last_skill else "（未点名）"
        return (
            f"thread {st.thread.thread_id}\n"
            f"skill {skill} · {how}\n"
            f"sandbox {st.cfg.sandbox}\n"
            f"approval {st.cfg.approval}\n"
            f"confirm {st.confirm}\n"
            f"{prompt_prefix(ctx) or '会话槽空'}"
        )
    if cmd == "skills":
        return _slash_skills(arg)
    if cmd in {"approvals", "approval"}:
        if arg:
            from packing_assistant.runtime.civil_config import _strip_mode

            st.cfg.approval = _strip_mode(arg, APPROVAL_MODES, st.cfg.approval)
            os.environ["CIVIL_APPROVAL"] = st.cfg.approval
            if st.cfg.auto_confirm():
                st.confirm = True
            return f"approval = {st.cfg.approval}"
        return "approval=" + st.cfg.approval + "  可选 " + " | ".join(APPROVAL_MODES)
    if cmd == "sandbox":
        if arg:
            from packing_assistant.runtime.civil_config import _strip_mode

            st.cfg.sandbox = _strip_mode(arg, SANDBOX_MODES, st.cfg.sandbox)
            os.environ["CIVIL_SANDBOX"] = st.cfg.sandbox
            return f"sandbox = {st.cfg.sandbox}"
        return "sandbox=" + st.cfg.sandbox + "  可选 " + " | ".join(SANDBOX_MODES)
    if cmd == "confirm":
        st.confirm = True
        st.thread.confirm = True
        return "本 thread 已确认：" + CONFIRM
    if cmd == "new":
        from packing_assistant.runtime.threads import new_thread

        st.thread = new_thread(arg or "新对话", confirm=st.confirm)
        return f"thread {st.thread.thread_id} · {st.thread.title}"
    if cmd == "threads":
        from packing_assistant.runtime.threads import list_threads, thread_status

        rows = list_threads()[:20]
        if not rows:
            return "还没有 thread。"
        lines = []
        for th in rows:
            mark = "*" if th.thread_id == st.thread.thread_id else " "
            stt = thread_status(th.thread_id)
            lines.append(f"{mark} {th.thread_id}  {stt.get('state')}  {th.title[:40]}")
        return "\n".join(lines)
    if cmd == "resume":
        from packing_assistant.runtime.threads import load_thread

        th = load_thread(arg.strip())
        if not th:
            return "未知 thread"
        st.thread = th
        st.confirm = th.confirm or st.confirm
        return f"切到 {th.thread_id} · {th.title}"
    if cmd == "files":
        arts = st.thread.artifacts
        if not arts:
            from packing_assistant.runtime.threads import load_thread

            fresh = load_thread(st.thread.thread_id)
            arts = (fresh.artifacts if fresh else []) or []
        return "\n".join(arts) if arts else "本 thread 还没有交付物。"
    if cmd == "mcp":
        return _slash_mcp()
    if cmd == "bg":
        if not arg.strip():
            return "用法：/bg 出一份税务日历"
        from packing_assistant.runtime.threads import spawn

        got = spawn(arg.strip(), confirm=st.confirm, title=arg.strip()[:40])
        return f"后台 thread {got.get('thread_id')}  state={got.get('state')}"
    return f"未知命令 /{cmd}。/help"


def run_tui() -> int:
    from packing_assistant.runtime.threads import run_on_thread

    _enable_vt()
    st = TuiState()
    _banner(st)
    while True:
        try:
            line = input(_c("32", f"{st.thread.thread_id}> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            return 0
        if line.startswith("/"):
            try:
                msg = handle_slash(line, st)
            except SystemExit:
                return 0
            if msg:
                print(msg)
                print()
            continue
        confirm = st.confirm or CONFIRM in line
        out = run_on_thread(
            st.thread.thread_id,
            line,
            confirm=confirm,
        )
        from packing_assistant.runtime.threads import load_thread

        fresh = load_thread(st.thread.thread_id)
        if fresh:
            st.thread = fresh
        st.last_skill = str(out.get("skill") or out.get("expert_id") or "")
        st.last_skill_source = str(out.get("skill_source") or "")
        _print_out(out)
    return 0
