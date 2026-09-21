"""The confined worker:  python -m packing_assistant.runtime.os_sandbox.worker

Order matters. It confines itself first, then proves it (tries to write outside its roots and
expects the kernel to refuse), and only then reads requests. If confinement cannot be applied
it says so and exits — it never runs a request unconfined.

Protocol, one JSON object per line.
    out:  {"type": "confined", backend, enforces, selftest}            once, first
          {"type": "event", "event": {...}}                           bus events, as they happen
          {"type": "result", "id": n, "ok": bool, "out": {...}}        one per request
          {"type": "fatal", "error": "..."}                           and exit
    in:   {"id": n, "op": "run_agent" | "model_tool" | "selftest", "args": {...}}
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


_PROTOCOL = sys.stdout      # tools that print() must not corrupt the protocol: main() points sys.stdout at stderr


def _say(message: Dict[str, Any]) -> None:
    _PROTOCOL.write(json.dumps(message, ensure_ascii=False, default=str) + "\n")
    _PROTOCOL.flush()


def _confine(policy: Dict[str, Any]) -> Dict[str, Any]:
    roots, network, spawn = list(policy["write_roots"]), bool(policy.get("network")), bool(policy.get("spawn"))
    if sys.platform.startswith("linux"):
        from packing_assistant.runtime.os_sandbox._linux import confine_self
    elif sys.platform == "win32":
        from packing_assistant.runtime.os_sandbox._windows import confine_self
    else:
        raise OSError(f"{sys.platform} 没有系统级后端")
    report = confine_self(roots, network=network, spawn=spawn)
    if not network and not report["enforces"]["network"]:
        _refuse_inet_sockets()
        report["network_app_layer"] = True
    return report


def _refuse_inet_sockets() -> None:
    """Application layer only (Windows): honest about being a courtesy, not a wall."""
    real = socket.socket

    class GuardedSocket(real):  # type: ignore[misc,valid-type]
        def __init__(self, family: int = socket.AF_INET, *args: Any, **kwargs: Any) -> None:
            if family in (socket.AF_INET, socket.AF_INET6):
                raise PermissionError("network is not available inside the sandbox worker")
            super().__init__(family, *args, **kwargs)

    socket.socket = GuardedSocket  # type: ignore[misc]


def _attempt(action) -> str:
    try:
        action()
        return "allowed"
    except PermissionError:
        return "denied"
    except OSError as exc:       # WinError 1816 (job quota) and EPERM from seccomp both land here
        return "denied" if getattr(exc, "winerror", None) in (5, 1816) or exc.errno in (1, 13) else f"error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


def selftest(policy: Dict[str, Any]) -> Dict[str, str]:
    """Try the things the sandbox is for. Every answer is what the operating system said."""
    job, inside = Path(policy["job_root"]), Path(policy["write_roots"][0])
    probe_name = f".civil-sandbox-probe-{os.getpid()}"

    def write_and_remove(folder: Path) -> None:
        target = folder / probe_name
        target.write_text("x", encoding="utf-8")
        target.unlink()

    return {
        "write_inside_state": _attempt(lambda: write_and_remove(inside)),
        "write_job_folder": _attempt(lambda: write_and_remove(job)),
        "write_home": _attempt(lambda: write_and_remove(Path.home())),
        "write_system_temp": _attempt(lambda: write_and_remove(Path(policy.get("real_temp") or tempfile.gettempdir()))),
        "spawn_process": _attempt(lambda: subprocess.run([sys.executable, "-c", "pass"], check=True, capture_output=True, timeout=30)),
        "inet_socket": _attempt(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()),
    }


def _run_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.runtime.agent_loop import run_agent

    return run_agent(str(args.get("text") or ""), session_id=str(args.get("session_id") or ""),
                     expert_id=str(args.get("expert_id") or ""), p0_confirmed=args.get("p0_confirmed") is True,
                     force_intent=args.get("force_intent") or None)


def _model_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.runtime import model_loop

    name = str(args.get("name") or "")
    if name not in model_loop.CONFINED_TOOLS:
        return {"result": {"ok": False, "error_code": "unknown_tool", "reason": f"{name} 不在沙箱工作进程里执行"}}
    turn = model_loop._Turn(session_id=str(args.get("session_id") or ""), run_id=str(args.get("run_id") or ""),
                            user_text=str(args.get("user_text") or ""), confirmed=args.get("confirmed") is True, approve=None,
                            material=str(args.get("material") or ""), intent=str(args.get("intent") or ""))
    turn.cad_context = args.get("cad_context")
    turn.cad_confirmed = args.get("cad_confirmed") is True
    turn.cad_mutation_done = args.get("cad_mutation_done") is True
    turn.planning_context = args.get("planning_context")
    try:
        result = model_loop._DISPATCH[name](turn, dict(args.get("arguments") or {}))
    except Exception as exc:  # noqa: BLE001 - same contract as the in-process dispatcher
        result = {"ok": False, "error_code": "tool_failed", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {"result": result, "files": turn.files, "skill": turn.skill, "hitl_pending": turn.hitl_pending, "wrote": turn.wrote,
            "cad_context": turn.cad_context, "cad_changed": turn.cad_changed, "cad_mutation_done": turn.cad_mutation_done}


def main() -> int:
    try:
        policy = json.loads(os.environ["CIVIL_OS_SANDBOX_POLICY"])
        sys.stdout = sys.stderr
        report = _confine(policy)
        checks = selftest(policy)
        if checks["write_inside_state"] != "allowed" or checks["write_job_folder"] != "denied" or checks["write_home"] != "denied":
            raise OSError("自检没有通过，拒绝在未受限的状态下工作：" + json.dumps(checks, ensure_ascii=False))
        from packing_assistant.runtime.bus import get_bus
        from packing_assistant.runtime.workspace import activate

        activate(Path(policy["job_root"]))
        get_bus().subscribe(lambda event: _say({"type": "event", "event": event.to_dict()}))
    except Exception as exc:  # noqa: BLE001 - fail closed, and say why
        _say({"type": "fatal", "error": f"{type(exc).__name__}: {exc}"})
        return 3
    _say({"type": "confined", **report, "selftest": checks, "pid": os.getpid()})
    operations = {"run_agent": _run_agent, "model_tool": _model_tool, "selftest": lambda _args: selftest(policy)}
    for line in sys.stdin:
        if not line.strip():
            continue
        request: Dict[str, Any] = {}
        try:
            request = json.loads(line)
            out = operations[request["op"]](dict(request.get("args") or {}))
            _say({"type": "result", "id": request.get("id"), "ok": True, "out": out})
        except Exception as exc:  # noqa: BLE001 - a failed request is a result; the worker keeps serving
            _say({"type": "result", "id": request.get("id"), "ok": False, "out": {"ok": False, "error_code": "worker_failed", "reply": f"{type(exc).__name__}: {str(exc)[:300]}"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
