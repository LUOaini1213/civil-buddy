"""Fixed engineering operations in a disposable process; never executes model code."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

OPERATIONS = frozenset({"frame", "section", "ifc_check", "ifc_diff", "planning_optimize"})
MAX_INPUT = 32 * 1024 * 1024
MAX_OUTPUT = 12 * 1024 * 1024


def dispatch(kind: str, payload: dict) -> dict:
    if kind == "planning_optimize":
        from .planning_optimize import optimize
        return optimize(payload)
    if kind == "frame":
        from .frame import analyze_frame
        return analyze_frame(payload)
    if kind == "section":
        from .section import analyze_section
        return analyze_section(payload["document"], payload["config"])
    if kind == "ifc_check":
        from .ifc import check_model
        return check_model(payload)
    if kind == "ifc_diff":
        from .ifc import compare_models
        return compare_models(payload)
    raise ValueError("未知工程计算工具。")


def run(kind: str, payload: dict, *, timeout: float = 120) -> dict:
    """Only host-supplied operation names and temporary paths reach subprocess."""
    from packing_assistant.runtime.cancel import check
    if kind not in OPERATIONS:
        raise ValueError("未知工程计算工具。")
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if len(data.encode("utf-8")) > MAX_INPUT:
        raise ValueError("工程计算输入超过 32 MiB，请缩小模型。")
    check()
    with tempfile.TemporaryDirectory(prefix="civil-engineering-") as directory:
        source, target = Path(directory) / "input.json", Path(directory) / "output.json"
        source.write_text(data, encoding="utf-8")
        env = dict(os.environ)
        for key in list(env):
            if key.endswith("API_KEY") or key in {"CIVIL_TOKEN", "LLM_API_KEY"}:
                env.pop(key, None)
        env.update(PYTHON_DOTENV_DISABLED="1", PYTHONUTF8="1", MPLBACKEND="Agg",
                   NUMBA_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        process = subprocess.Popen(
            [sys.executable, "-m", "packing_assistant.engineering.worker", kind, str(source), str(target)],
            cwd=Path(__file__).resolve().parents[2], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        start = time.monotonic()
        try:
            while process.poll() is None:
                check()
                if time.monotonic() - start > timeout:
                    raise TimeoutError("计算超时，已终止本次任务；请减少构件或轮廓。")
                time.sleep(0.05)
            check()
            if not target.is_file() or target.stat().st_size > MAX_OUTPUT:
                raise ValueError("计算进程未返回有效结果，原始输入保持不变。")
            result = json.loads(target.read_text(encoding="utf-8"))
            if not result.get("ok"):
                if result.get("missing_dependency"):
                    raise ImportError(result["error"])
                raise ValueError(result.get("error", "计算失败。"))
            return result["result"]
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def main() -> None:
    kind, source, target = sys.argv[1:]
    try:
        if kind not in OPERATIONS or Path(source).stat().st_size > MAX_INPUT:
            raise ValueError("计算任务无效或过大。")
        result = {"ok": True, "result": dispatch(kind, json.loads(Path(source).read_text(encoding="utf-8")))}
    except ImportError:
        result = {"ok": False, "missing_dependency": True,
                  "error": "工程计算依赖未就绪，请安装 requirements-engineering.txt。"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)[:1500] or type(exc).__name__}
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_OUTPUT:
        encoded = json.dumps({"ok": False, "error": "结果超过上限，请缩小检查范围。"}, ensure_ascii=False)
    Path(target).write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
