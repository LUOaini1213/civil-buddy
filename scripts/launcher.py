#!/usr/bin/env python3
"""
装箱拼柜 · 统一启动器（菜单）

用法（仓库根目录）:
  python scripts/launcher.py
  或双击 启动.bat

菜单覆盖：网关 / Agent 闭环 / 演示 A·B / 回归 / 打开产物
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
HOST = "127.0.0.1"
PORT = 8000
BASE = f"http://{HOST}:{PORT}"


def _cd() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _banner() -> None:
    print()
    print("=" * 58)
    print("  智能装箱与拼柜 · 启动器")
    print("  感知→规划→工具→行动→目标 | tools 算数")
    print(f"  仓库: {ROOT}")
    print("=" * 58)


def _menu() -> None:
    print(
        """
  [1] 启动网关 + 前端          →  http://127.0.0.1:8000
  [2] 启动网关（后台）并打开浏览器
  [3] Agent 闭环自检（五条能力）  demo_agent_closed_loop
  [4] 演示 A · 数字（VMU1 工地）  demo_vmu1_site
  [5] 演示 B · 9 Agent 轨迹       demo_nine_agents_trace
  [6] 演示 B+ · 当量直通 9 Agent  demo_vmu1_nine_passthrough
  [7] 提交前回归                  run_precommit_tests --quick
  [8] 评委包                      build_judge_package
  [9] 打开 API 文档 / 最新产物
  [0] 退出
"""
    )


def _run(cmd: list[str], *, title: str = "") -> int:
    if title:
        print(f"\n>>> {title}")
    print(f"$ {' '.join(cmd)}\n")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT))
        return int(r.returncode or 0)
    except KeyboardInterrupt:
        print("\n(已中断)")
        return 130
    except FileNotFoundError as e:
        print(f"命令不可用: {e}")
        return 1


def _gateway_cmd() -> list[str]:
    return [
        PY,
        "-m",
        "uvicorn",
        "gateway.app:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
        "--reload",
    ]


def _port_open(port: int = PORT) -> bool:
    import socket

    try:
        with socket.create_connection((HOST, port), timeout=0.4):
            return True
    except OSError:
        return False


def start_gateway_fg() -> int:
    print(f"\n网关前台运行: {BASE}")
    print("  /docs              OpenAPI")
    print("  POST /api/pipeline Agent 闭环入口")
    print("  POST /api/demo     自动确认全流程")
    print("Ctrl+C 停止\n")
    if not shutil.which("python") and not PY:
        print("未找到 Python")
        return 1
    # 确保依赖提示
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        print("正在安装 fastapi / uvicorn …")
        _run([PY, "-m", "pip", "install", "-q", "fastapi", "uvicorn[standard]"])
    env = os.environ.copy()
    if not env.get("SKJOLBER_URL"):
        env["SKJOLBER_URL"] = "http://127.0.0.1:8080"
    try:
        return subprocess.call(_gateway_cmd(), cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print("\n网关已停止")
        return 0


def start_gateway_bg_and_open() -> int:
    if _port_open():
        print(f"端口 {PORT} 已在监听，直接打开浏览器。")
    else:
        try:
            import uvicorn  # noqa: F401
            import fastapi  # noqa: F401
        except ImportError:
            _run([PY, "-m", "pip", "install", "-q", "fastapi", "uvicorn[standard]"])
        env = os.environ.copy()
        if not env.get("SKJOLBER_URL"):
            env["SKJOLBER_URL"] = "http://127.0.0.1:8080"
        log = ROOT / "output" / "gateway_launcher.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        # 无 reload，后台更稳
        cmd = [
            PY,
            "-m",
            "uvicorn",
            "gateway.app:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
        ]
        print(f"后台启动网关 → 日志 {log}")
        # Windows: DETACHED；跨平台用 start_new_session
        kwargs: dict = {
            "cwd": str(ROOT),
            "env": env,
            "stdout": open(log, "a", encoding="utf-8"),
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)
        for i in range(30):
            if _port_open():
                print(f"网关就绪 ({i+1}s)")
                break
            time.sleep(0.5)
        else:
            print("等待超时：请查看日志或改用 [1] 前台启动")
            return 1
    webbrowser.open(f"{BASE}/")
    webbrowser.open(f"{BASE}/docs")
    print(f"已打开: {BASE}/  与  {BASE}/docs")
    return 0


def open_artifacts() -> int:
    paths = [
        ROOT / "output" / "runs",
        ROOT / "output" / "demo_package" / "latest",
        ROOT / "output" / "judge_package" / "latest",
        ROOT / "docs" / "ai-agent-alignment.md",
    ]
    print("\n常用路径:")
    for p in paths:
        mark = "✓" if p.exists() else "·"
        print(f"  [{mark}] {p}")
    # 优先打开 runs / judge
    for p in (
        ROOT / "output" / "judge_package" / "latest" / "INDEX.md",
        ROOT / "output" / "agent_closed_loop_summary.json",
        ROOT / "output" / "runs",
    ):
        if p.exists():
            if p.is_dir():
                if os.name == "nt":
                    os.startfile(str(p))  # type: ignore[attr-defined]
                else:
                    webbrowser.open(p.as_uri())
            else:
                webbrowser.open(p.as_uri())
            print(f"已打开: {p}")
            break
    if _port_open():
        webbrowser.open(f"{BASE}/docs")
    return 0


def main() -> int:
    _cd()
    # 非交互：launcher.py --gateway / --agent / --help
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg in ("--gateway", "-g", "gateway"):
            return start_gateway_fg()
        if arg in ("--gateway-bg", "--bg"):
            return start_gateway_bg_and_open()
        if arg in ("--agent", "-a", "agent"):
            return _run(
                [PY, str(ROOT / "scripts" / "demo_agent_closed_loop.py"), "--tiny"],
                title="Agent 闭环自检",
            )
        if arg in ("--site", "a"):
            return _run(
                [PY, str(ROOT / "scripts" / "demo_vmu1_site.py")],
                title="演示 A · VMU1 工地",
            )
        if arg in ("--help", "-h"):
            print(__doc__)
            print("快捷: --gateway | --gateway-bg | --agent | --site")
            return 0

    while True:
        _banner()
        _menu()
        try:
            choice = input("请选择 [0-9]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0

        if choice in ("0", "q", "quit", "exit"):
            print("再见。")
            return 0
        if choice == "1":
            return start_gateway_fg()  # 前台阻塞，退出后菜单结束
        if choice == "2":
            start_gateway_bg_and_open()
            input("\n按回车返回菜单…")
            continue
        if choice == "3":
            _run(
                [PY, str(ROOT / "scripts" / "demo_agent_closed_loop.py"), "--tiny"],
                title="Agent 闭环自检",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "4":
            _run(
                [PY, str(ROOT / "scripts" / "demo_vmu1_site.py")],
                title="演示 A · 数字",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "5":
            _run(
                [PY, str(ROOT / "scripts" / "demo_nine_agents_trace.py")],
                title="演示 B · 9 Agent 轨迹",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "6":
            _run(
                [PY, str(ROOT / "scripts" / "demo_vmu1_nine_passthrough.py")],
                title="演示 B+ · 当量直通",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "7":
            _run(
                [PY, str(ROOT / "scripts" / "run_precommit_tests.py"), "--quick"],
                title="提交前回归 (quick)",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "8":
            _run(
                [PY, str(ROOT / "scripts" / "build_judge_package.py")],
                title="评委包",
            )
            input("\n按回车返回菜单…")
            continue
        if choice == "9":
            open_artifacts()
            input("\n按回车返回菜单…")
            continue

        print("无效选项，请输入 0–9")
        time.sleep(0.4)


if __name__ == "__main__":
    raise SystemExit(main())
