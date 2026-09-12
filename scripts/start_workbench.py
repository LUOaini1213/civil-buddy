"""Stdlib-only release bootstrap; dependencies are installed only in this pack's venv."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import runpy
import stat
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("fastapi", "uvicorn", "httpx", "dotenv", "langgraph", "langchain_core",
            "langchain_openai", "multipart", "openpyxl", "pypdf")


def missing_dependencies() -> list[str]:
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def local_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_local(root: Path) -> Path:
    target = root / ".venv"
    reparse = target.exists() and getattr(target.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if target.is_symlink() or reparse or target.resolve().parent != root.resolve():
        raise RuntimeError("The package .venv must be a local directory, not a link.")
    interpreter = local_python(root)
    if not interpreter.is_file():
        print("Creating this package's .venv (system Python is unchanged).", flush=True)
        venv.EnvBuilder(with_pip=True).create(target)
    print("Installing workbench dependencies into this package's .venv...", flush=True)
    subprocess.run([str(interpreter), "-m", "pip", "install", "-r", str(root / "requirements.txt")],
                   cwd=root, check=True)
    return interpreter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the Python Civil Buddy workbench.")
    parser.add_argument("--setup", action="store_true", help="create/repair only this package's .venv")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.", file=sys.stderr)
        return 1
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    os.chdir(ROOT)
    os.environ["PYTHONUTF8"] = "1"
    # A release must import its own sources, even when using another venv.
    os.environ.pop("PYTHONPATH", None)
    sys.path.insert(0, str(ROOT))
    forwarded = ["--no-browser"] if args.no_browser else []
    if args.port is not None:
        forwarded += ["--port", str(args.port)]
    missing = missing_dependencies()
    if args.setup or missing:
        if missing and os.getenv("CIVIL_BOOTSTRAPPED") == "1" and not args.setup:
            print("Dependencies are still incomplete after setup: " + ", ".join(missing) +
                  ". Inspect the pip installation output and retry --setup.", file=sys.stderr)
            return 1
        explicit = bool(os.getenv("CIVIL_PYTHON"))
        if explicit and missing and not args.setup:
            print("CIVIL_PYTHON lacks: " + ", ".join(missing) +
                  ". Use --setup to install into this package's .venv, or select a prepared interpreter.",
                  file=sys.stderr)
            return 1
        try:
            interpreter = install_local(ROOT)
            clean_env = os.environ.copy()
            clean_env.pop("CIVIL_PYTHON", None)
            clean_env["CIVIL_BOOTSTRAPPED"] = "1"
            return subprocess.call([str(interpreter), str(Path(__file__).resolve()), *forwarded],
                                   cwd=ROOT, env=clean_env)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Dependency setup failed ({type(exc).__name__}). Check network access and write permissions; "
                  "retry start-workbench.bat --setup. No system packages were changed.", file=sys.stderr)
            return 1
    sys.argv = ["civil", "app", *forwarded]
    try:
        runpy.run_module("packing_assistant.civil", run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    status = main()
    if status == 1 and sys.stdin.isatty() and "--no-browser" not in sys.argv:
        try:
            input("Startup failed. Press Enter to close this window after reading the message above.")
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(status)
