"""Launch and supervise the local Python workbench until the user stops it."""

from __future__ import annotations

import importlib.util
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from threading import Thread
from typing import Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from uuid import uuid4
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
LAUNCH_HEADER = "X-Civil-Launch-ID"
STARTUP_TIMEOUT = 30.0


class AppLaunchError(RuntimeError):
    """A startup failure which can be explained directly in the CLI."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_port(port: Optional[int], env: Mapping[str, str]) -> int:
    value = port if port is not None else env.get("CIVIL_PORT") or "8765"
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AppLaunchError("端口必须是 1–65535 的整数；请检查 --port 或 CIVIL_PORT。") from exc
    if isinstance(value, bool) or not 1 <= parsed <= 65535:
        raise AppLaunchError("端口必须在 1–65535 之间；请检查 --port 或 CIVIL_PORT。")
    return parsed


def _check_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        # Windows SO_REUSEADDR can steal an occupied address. Use exclusive
        # ownership there; POSIX reuse permits a normal restart after TIME_WAIT.
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
        except OSError as exc:
            raise AppLaunchError(
                f"无法使用 {HOST}:{port}：端口可能已被占用。请关闭原服务，或用 --port 指定其他端口。"
            ) from exc


def _server_command(port: int, launch_id: str) -> list[str]:
    return [
        sys.executable, "-m", "uvicorn", "app:app", "--host", HOST,
        "--port", str(port), "--no-access-log", "--header", f"{LAUNCH_HEADER}:{launch_id}",
    ]


def _stop_process(process: subprocess.Popen, *, timeout: float = 5.0) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


class WorkbenchServer:
    def __init__(self, process: subprocess.Popen, port: int, launch_id: str) -> None:
        self.process = process
        self.url = f"http://{HOST}:{port}"
        self.launch_id = launch_id
        self._log_stream = sys.stderr
        self._log_thread = Thread(target=self._forward_logs, name="civil-app-logs", daemon=True)
        self._log_thread.start()

    def _forward_logs(self) -> None:
        # Hidden Windows children have no console handles unless streams are
        # explicitly wired. Drain a pipe so startup tracebacks remain visible.
        if self.process.stdout is None:
            return
        with self.process.stdout as stream:
            for line in stream:
                try:
                    self._log_stream.write(line)
                    self._log_stream.flush()
                except (OSError, ValueError):
                    pass

    def close(self) -> None:
        try:
            _stop_process(self.process)
        finally:
            self._log_thread.join(timeout=1)

    def wait(self) -> int:
        code = int(self.process.wait())
        self._log_thread.join(timeout=1)
        return code

    def __enter__(self) -> "WorkbenchServer":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _wait_for_health(server: WorkbenchServer, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    # Health checks always go directly to loopback, including when the user's
    # shell configures an HTTP proxy. Redirects cannot leave this local server.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    last_error = "服务尚未响应"
    while True:
        code = server.process.poll()
        if code is not None:
            raise AppLaunchError(
                f"工作台启动失败（退出码 {code}）。请查看上方服务日志；"
                "缺少依赖时，用当前 Python 执行 python -m pip install -r requirements.txt。"
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AppLaunchError(f"工作台在 {timeout:g} 秒内未就绪：{last_error}。")
        try:
            with opener.open(server.url + "/api/health", timeout=min(1.0, remaining)) as response:
                if response.headers.get(LAUNCH_HEADER) != server.launch_id:
                    raise AppLaunchError("端口上的服务不属于本次启动，已停止本次进程。请换用其他端口。")
                body = json.loads(response.read(65536).decode("utf-8"))
                if (
                    response.status == 200 and isinstance(body, dict)
                    and body.get("ok") is True and body.get("product") == "civil-codex"
                ):
                    if server.process.poll() is None:
                        return
                last_error = "健康检查未通过"
        except HTTPError as exc:
            last_error = f"健康检查返回 HTTP {exc.code}"
            exc.close()
        except (OSError, URLError, ValueError, HTTPException) as exc:
            last_error = f"健康检查未就绪（{type(exc).__name__}）"
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))


def start_workbench(port: Optional[int] = None, *, startup_timeout: float = STARTUP_TIMEOUT) -> WorkbenchServer:
    """Start the fixed product command and return only after its own health check."""
    env = os.environ.copy()
    use = resolve_port(port, env)
    if not math.isfinite(startup_timeout) or startup_timeout <= 0:
        raise AppLaunchError("启动等待时间必须大于 0。")
    if importlib.util.find_spec("uvicorn") is None:
        raise AppLaunchError("当前 Python 缺少 uvicorn。请运行 python -m pip install -r requirements.txt。")
    _check_port_available(use)
    env["CIVIL_PORT"] = str(use)
    env["PYTHONUTF8"] = "1"
    launch_id = uuid4().hex
    print(f"正在启动 Civil Buddy 工作台：http://{HOST}:{use}", file=sys.stderr, flush=True)
    try:
        process = subprocess.Popen(
            _server_command(use, launch_id), cwd=str(ROOT / "demo"), env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except OSError as exc:
        raise AppLaunchError(f"无法启动工作台进程：{exc}") from exc
    server = WorkbenchServer(process, use, launch_id)
    try:
        _wait_for_health(server, timeout=startup_timeout)
    except BaseException:
        server.close()
        raise
    return server


def run_workbench(port: Optional[int] = None, *, no_browser: bool = False) -> int:
    try:
        with start_workbench(port) as server:
            print(f"Civil Buddy 工作台已就绪：{server.url}（按 Ctrl+C 停止）", file=sys.stderr, flush=True)
            if not no_browser:
                try:
                    opened = webbrowser.open(server.url)
                except Exception:
                    opened = False
                if not opened:
                    print(f"浏览器未能自动打开，请手动访问 {server.url}", file=sys.stderr, flush=True)
            code = server.wait()
            if code:
                print(f"工作台服务已退出（退出码 {code}）。请查看上方服务日志。", file=sys.stderr, flush=True)
            return code
    except KeyboardInterrupt:
        print("工作台已停止。", file=sys.stderr, flush=True)
        return 130
    except AppLaunchError as exc:
        print(f"civil app：{exc}", file=sys.stderr, flush=True)
        return 1
