"""The system-level sandbox: tool work runs in a worker process that the kernel confines.

packing_assistant/sandbox.py is a policy the code asks before it writes. It holds as long as
every write goes through it. This is the other kind: the turn's tool work — parsing the user's
spreadsheets and documents, running the packing engine, writing deliverables — happens in a
separate process that has confined *itself* before touching anything, so a parser bug, a
malicious workbook or a missed code path still cannot write outside the job's state folder,
start another program or (on Linux) open a network connection. Same split as Codex: the model
conversation stays in the host, which needs the network; what the model asks for runs confined.

    Linux      Landlock + seccomp                     write ✓  spawn ✓  network ✓   (_linux.py)
    Windows    Low integrity level + job object       write ✓  spawn ✓  network ✗   (_windows.py)
    macOS      not implemented — Seatbelt is the obvious backend and nobody here could run it

`sandbox_backend` (civil.toml) / `CIVIL_SANDBOX_BACKEND` / `civil --sandbox-backend`:
    app    the policy layer only (the default)
    os     kernel confinement, or the turn is refused
    auto   kernel confinement when this machine offers it and a job folder is active, else app — and says which
A job folder is required: its `.civil-buddy/out` is the one place the worker may write.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKENDS = ("app", "os", "auto")
_REPO = Path(__file__).resolve().parents[3]
CALL_TIMEOUT_S = 600.0


def probe() -> Dict[str, Any]:
    """What the kernel on this machine can enforce, without starting anything."""
    if sys.platform.startswith("linux"):
        from packing_assistant.runtime.os_sandbox import _linux

        return _linux.probe()
    if sys.platform == "win32":
        from packing_assistant.runtime.os_sandbox import _windows

        return _windows.probe()
    return {"backend": "none", "available": False, "enforces": {"write": False, "spawn": False, "network": False},
            "reason": f"{sys.platform} 还没有系统级后端（macOS 应接 Seatbelt，尚未实现与验证）"}


def resolve_backend(requested: str = "") -> Tuple[str, str]:
    """("os" | "app", why) — `why` is empty when the answer is exactly what was asked for."""
    from packing_assistant.runtime.civil_config import load_config
    from packing_assistant.runtime.workspace import active

    asked = (requested or load_config().sandbox_backend or "app").strip().lower()
    if asked not in BACKENDS or asked == "app":
        return "app", ""
    found = probe()
    problem = ("" if found["available"] and found["enforces"]["write"] else found.get("reason") or "本机内核无法限制写入")
    if not problem and active() is None:
        problem = "系统级沙箱需要作业文件夹（civil init 或 civil -C <文件夹>）：那里的 .civil-buddy/out 是唯一可写处"
    if not problem:
        return "os", ""
    if asked == "os":
        raise PermissionError("sandbox_backend=os，但无法启用系统级沙箱：" + problem)
    return "app", "系统级沙箱未启用（" + problem + "）；本轮只有应用层策略。"


def write_roots(job_root: Path) -> List[Path]:
    state = Path(job_root) / ".civil-buddy" / "out"
    return [state, state / ".tmp"]


def prepare(job_root: Path) -> List[Path]:
    """Parent side, before the worker starts: the write roots exist and (Windows) carry the Low label."""
    roots = write_roots(job_root)
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        from packing_assistant.runtime.os_sandbox._windows import label_low

        label_low(str(roots[0]))        # inheritable: covers .tmp and everything created later
    return roots


class WorkerError(RuntimeError):
    pass


class WorkerCancelled(WorkerError):
    """The host cancelled a confined operation; this must never trigger fallback."""


class Worker:
    """One confined worker for one turn. ``call`` sends a request and returns its result; bus events
    the worker emits are re-emitted on this process's bus as they arrive."""

    def __init__(self, job_root: Path, *, network: bool = False, spawn: bool = False, timeout: float = CALL_TIMEOUT_S,
                 cancel_event: Any = None):
        self.job_root, self.timeout = Path(job_root).resolve(), timeout
        self.policy = {"job_root": str(self.job_root), "network": network, "spawn": spawn, "real_temp": tempfile.gettempdir()}
        self.process: Optional[subprocess.Popen] = None
        self.confined: Dict[str, Any] = {}
        self._calls = 0
        self._stderr = None
        self.cancel_event = cancel_event

    def __enter__(self) -> "Worker":
        self._check_cancelled(self.cancel_event)
        roots = prepare(self.job_root)
        self.policy["write_roots"] = [str(root) for root in roots]
        temp = str(roots[1])
        env = {**os.environ, "CIVIL_OS_SANDBOX_POLICY": json.dumps(self.policy, ensure_ascii=False), "PYTHONIOENCODING": "utf-8",
               "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "TMP": temp, "TEMP": temp, "TMPDIR": temp, "MPLCONFIGDIR": temp,
               "PYTHONPATH": os.pathsep.join(filter(None, [str(_REPO), os.environ.get("PYTHONPATH", "")]))}
        self._stderr = open(roots[1] / "worker.stderr.log", "w", encoding="utf-8", errors="replace")
        self.process = subprocess.Popen([sys.executable, "-m", "packing_assistant.runtime.os_sandbox.worker"], cwd=str(self.job_root),
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
                                        text=True, encoding="utf-8", errors="replace", bufsize=1)
        try:
            first = self._read(timeout=60.0, cancel_event=self.cancel_event)
        except WorkerCancelled:
            self.close()
            raise
        if first.get("type") != "confined":
            self.close()
            raise WorkerError("沙箱工作进程没有进入受限状态：" + str(first.get("error") or first)[:300])
        self.confined = first
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def close(self) -> None:
        process, self.process = self.process, None
        if process is not None:
            try:
                if process.stdin:
                    process.stdin.close()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
            finally:
                for stream in (process.stdout, self._stderr):
                    try:
                        if stream:
                            stream.close()
                    except OSError:
                        pass

    def _check_cancelled(self, cancel_event: Any = None) -> None:
        if cancel_event is None or not cancel_event.is_set():
            return
        # Do not just abandon the waiter: a live child could still publish files.
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass  # Child finished between poll and terminate.
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        raise WorkerCancelled("本轮已取消；沙箱工作进程已停止。")

    def _read(self, timeout: float, cancel_event: Any = None) -> Dict[str, Any]:
        """One JSON line from the worker, or a fatal record if it dies or stays silent."""
        assert self.process is not None and self.process.stdout is not None
        box: Dict[str, Any] = {}

        def read() -> None:
            box["line"] = self.process.stdout.readline() if self.process and self.process.stdout else ""

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout
        while reader.is_alive():
            self._check_cancelled(cancel_event)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            reader.join(min(0.05, remaining))
        self._check_cancelled(cancel_event)
        if reader.is_alive():
            self.process.kill()
            return {"type": "fatal", "error": f"工作进程 {int(timeout)} 秒没有回应，已终止"}
        line = box.get("line") or ""
        if not line:
            return {"type": "fatal", "error": "工作进程已退出：" + self._stderr_tail()}
        try:
            return json.loads(line)
        except ValueError:
            return {"type": "noise", "text": line[:200]}

    def _stderr_tail(self) -> str:
        try:
            self._stderr.flush()
            return Path(self._stderr.name).read_text(encoding="utf-8", errors="replace")[-400:].strip() or "（无输出）"
        except (OSError, AttributeError, ValueError):
            return "（读不到工作进程的错误输出）"

    def call(self, op: str, *, cancel_event: Any = None, **payload: Any) -> Dict[str, Any]:
        from packing_assistant.runtime.bus import get_bus

        if cancel_event is None:
            cancel_event = self.cancel_event
        self._check_cancelled(cancel_event)
        if self.process is None or self.process.stdin is None:
            raise WorkerError("工作进程未启动")
        self._calls += 1
        request = {"id": self._calls, "op": op, "args": payload}
        try:
            self.process.stdin.write(json.dumps(request, ensure_ascii=False, default=str) + "\n")
            self.process.stdin.flush()
        except OSError as exc:
            raise WorkerError("无法写入工作进程：" + self._stderr_tail()) from exc
        while True:
            message = self._read(self.timeout, cancel_event)
            kind = message.get("type")
            if kind == "event":
                event = message.get("event") or {}
                get_bus().emit(str(event.get("run_id") or ""), str(event.get("type") or ""), dict(event.get("payload") or {}))
            elif kind == "result" and message.get("id") == self._calls:
                return message
            elif kind == "fatal":
                self.close()
                raise WorkerError(str(message.get("error")))


def describe() -> Dict[str, Any]:
    """For `civil status`: what was asked for, what will run, and what the kernel holds."""
    from packing_assistant.runtime.civil_config import load_config

    asked = load_config().sandbox_backend
    try:
        running, why = resolve_backend(asked)
    except PermissionError as exc:
        running, why = "refused", str(exc)
    return {"asked": asked, "running": running, "why": why, "kernel": probe()}
