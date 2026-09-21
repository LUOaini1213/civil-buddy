"""Start one local product: Rust host + fixed Python domain service.

The domain process receives no provider keys and exposes no chat runtime.
Use --env-file only for a user-selected configuration; keys are never printed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--state-root", type=Path, default=ROOT / "demo/data/unified")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    binary = args.binary or ROOT / "workbench/target/release" / ("civil-workbench.exe" if os.name == "nt" else "civil-workbench")
    if not binary.is_file():
        parser.error("Rust executable missing; run cargo build --release --manifest-path workbench/Cargo.toml or specify --binary")
    environment = dict(os.environ)
    if args.env_file:
        from dotenv import dotenv_values
        environment.update({k: v for k, v in dotenv_values(args.env_file).items() if v is not None})
    args.state_root = args.state_root.resolve()
    args.state_root.mkdir(parents=True, exist_ok=True)
    # OS lock prevents a second host from recovering a live host's active turns.
    lock = (args.state_root / "host.lock").open("a+b")
    lock.seek(0)
    lock.write(b"0")
    lock.flush()
    lock.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        parser.error("This state directory already has a running product host")
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        domain_port = reserved.getsockname()[1]
    domain_env = {k: v for k, v in os.environ.items() if k.upper() in
                  {"PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "LANG"}}
    domain_env.update(PYTHONUTF8="1", PYTHON_DOTENV_DISABLED="1", CIVIL_OUT_ROOT=str(args.state_root / "domains"),
                      CIVIL_SANDBOX_ROOTS=str(args.state_root / "domains"),
                      CIVIL_DOMAIN_WORKSPACE=str(args.state_root / "domains"),
                      PACKING_OUTPUT_DIR=str(args.state_root / "packing"),
                      PACKING_TRACE_DIR=str(args.state_root / "packing" / "traces"),
                      CB_DB_PATH=str(args.state_root / "packing" / "civilbuddy.db"),
                      PACKING_LG_CHECKPOINT_PATH=str(args.state_root / "packing" / "checkpoints.db"),
                      PACKING_LLM_AGENT="0", PACKING_SKIP_SKJOLBER="1")
    environment.update(CIVIL_PORT=str(args.port), CIVIL_DOMAIN_URL=f"http://127.0.0.1:{domain_port}",
                       CIVIL_STATE_ROOT=str(args.state_root), CIVIL_DEMO_ROOT=str(ROOT / "demo"),
                       CIVIL_PYTHON=str(Path(args.python).resolve()), CIVIL_UNIFIED_HOME="1",
                       PACKING_AGENT_URL=f"http://127.0.0.1:{domain_port}/packing")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes = []
    logs = [(args.state_root / name).open("ab") for name in ("domains.log", "rust.log")]
    try:
        processes.append(subprocess.Popen([args.python, "-m", "uvicorn", "demo.domain_service:app", "--host", "127.0.0.1", "--port", str(domain_port)],
                                          cwd=ROOT, env=domain_env, creationflags=flags, stdout=logs[0], stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen([str(binary.resolve())], cwd=ROOT, env=environment, creationflags=flags, stdout=logs[1], stderr=subprocess.STDOUT))
        for _ in range(100):
            if any(p.poll() is not None for p in processes):
                raise RuntimeError(f"A product process exited during startup; inspect {args.state_root}/domains.log and rust.log")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/agent/capabilities", timeout=1) as response:
                    ready = response.status == 200
                with urllib.request.urlopen(f"http://127.0.0.1:{domain_port}/health", timeout=1) as response:
                    ready = ready and response.status == 200
                if ready:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Product startup timed out")
        print(f"Civil Buddy: http://127.0.0.1:{args.port}/static/agent.html", flush=True)
        print(f"State: {args.state_root}; Ctrl+C stops both processes", flush=True)
        if args.open:
            webbrowser.open(f"http://127.0.0.1:{args.port}/static/agent.html")
        while all(p.poll() is None for p in processes):
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        lock.close()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
