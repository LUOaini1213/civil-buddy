"""ToolEngine: register → list → allow → validate → execute → audit.

Chat turns cannot write. Exclusive tools stay on their expert.
Does not re-pack; pack-ship handlers only project solver snapshots.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ERR_OK = "ok"
ERR_DENIED = "permission_denied"
ERR_INVALID = "invalid_args"
ERR_TIMEOUT = "timeout"
ERR_CIRCUIT = "circuit_open"
ERR_UNSPECIFIED = "unspecified"
ERR_MAX_STEPS = "max_steps"

WRITE_TOOLS = frozenset(
    {
        "write_deliverable",
        "spawn_helper",
        "tender.parse",
        "pack-ship__plan",
        "pack-ship__export",
    }
)

_PATH_KEYS = ("path", "write_path", "output_path", "dest", "file")


def _write_path(args: Dict[str, Any]) -> Optional[str]:
    for key in _PATH_KEYS:
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _spawn_cmd(args: Dict[str, Any]) -> tuple[Any, Optional[str]]:
    if "command" in args and args.get("command") is not None:
        return args.get("command"), args.get("kind")
    if "spawn" in args and args.get("spawn") is not None:
        return args.get("spawn"), args.get("kind")
    if "argv" in args and args.get("argv") is not None:
        return args.get("argv"), args.get("kind")
    return None, None


@dataclass
class ToolSpec:
    name: str
    handler: Callable[[Dict[str, Any]], Any]
    schema_keys: tuple[str, ...] = ()
    expert_id: Optional[str] = None
    writes: bool = False
    timeout_s: float = 30.0


@dataclass
class Audit:
    name: str
    error_code: str
    duration_ms: int
    expert_id: str = ""


@dataclass
class ToolEngine:
    tools: Dict[str, ToolSpec] = field(default_factory=dict)
    _fail_streak: Dict[str, int] = field(default_factory=dict)
    circuit_threshold: int = 3
    audit_log: List[Audit] = field(default_factory=list)

    def register(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Any],
        *,
        schema_keys: tuple[str, ...] = (),
        expert_id: Optional[str] = None,
        writes: bool = False,
        timeout_s: float = 30.0,
    ) -> None:
        self.tools[name] = ToolSpec(
            name=name,
            handler=handler,
            schema_keys=schema_keys,
            expert_id=expert_id,
            writes=writes,
            timeout_s=timeout_s,
        )

    def list(self, *, expert_id: Optional[str] = None) -> List[str]:
        names = []
        for spec in self.tools.values():
            if spec.expert_id and expert_id and spec.expert_id != expert_id:
                continue
            names.append(spec.name)
        return names

    def schemas_for(self, expert_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for spec in self.tools.values():
            if spec.expert_id and expert_id and spec.expert_id != expert_id:
                continue
            rows.append(
                {
                    "name": spec.name,
                    "writes": spec.writes,
                    "expert_id": spec.expert_id,
                    "schema_keys": list(spec.schema_keys),
                    "timeout_s": spec.timeout_s,
                }
            )
        return rows

    def allow(
        self,
        name: str,
        *,
        expert_id: str = "",
        intent: str = "run",
        cancelled: bool = False,
    ) -> Optional[str]:
        if cancelled:
            return ERR_DENIED
        spec = self.tools.get(name)
        if spec is None:
            return ERR_INVALID
        if intent == "chat" and spec.writes:
            return ERR_DENIED
        if spec.expert_id and expert_id and spec.expert_id != expert_id:
            return ERR_DENIED
        if self._fail_streak.get(name, 0) >= self.circuit_threshold:
            return ERR_CIRCUIT
        return None

    def execute(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        expert_id: str = "",
        intent: str = "run",
        cancelled: bool = False,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        args = arguments or {}
        denied = self.allow(name, expert_id=expert_id, intent=intent, cancelled=cancelled)
        if denied:
            rec = Audit(name=name, error_code=denied, duration_ms=0, expert_id=expert_id)
            self.audit_log.append(rec)
            return {"ok": False, "error_code": denied, "name": name}
        spec = self.tools[name]
        for key in spec.schema_keys:
            if key not in args:
                rec = Audit(name=name, error_code=ERR_INVALID, duration_ms=0, expert_id=expert_id)
                self.audit_log.append(rec)
                return {"ok": False, "error_code": ERR_INVALID, "name": name, "missing": key}
        from packing_assistant.sandbox import check_write, request_spawn

        sandbox_info: Optional[Dict[str, Any]] = None
        path = _write_path(args)
        if spec.writes and path:
            decision = check_write(path)
            sandbox_info = decision.to_dict()
            if not decision.allowed:
                rec = Audit(name=name, error_code=ERR_DENIED, duration_ms=0, expert_id=expert_id)
                self.audit_log.append(rec)
                return {
                    "ok": False,
                    "error_code": ERR_DENIED,
                    "name": name,
                    "sandbox": sandbox_info,
                    "detail": decision.reason,
                }
        cmd, kind = _spawn_cmd(args)
        if cmd is not None:
            decision = request_spawn(cmd, kind=kind)
            sandbox_info = decision.to_dict()
            if not decision.allowed:
                rec = Audit(name=name, error_code=ERR_DENIED, duration_ms=0, expert_id=expert_id)
                self.audit_log.append(rec)
                return {
                    "ok": False,
                    "error_code": ERR_DENIED,
                    "name": name,
                    "sandbox": sandbox_info,
                    "detail": decision.reason,
                }
        box: Dict[str, Any] = {}

        def _run() -> None:
            try:
                box["data"] = spec.handler(args)
                box["err"] = None
            except Exception as e:  # noqa: BLE001 — surface as timeout/invalid, not invent numbers
                box["err"] = e

        th = threading.Thread(target=_run, daemon=True)
        th.start()
        th.join(spec.timeout_s)
        ms = int((time.perf_counter() - t0) * 1000)
        if th.is_alive():
            self._fail_streak[name] = self._fail_streak.get(name, 0) + 1
            self.audit_log.append(Audit(name=name, error_code=ERR_TIMEOUT, duration_ms=ms, expert_id=expert_id))
            return {"ok": False, "error_code": ERR_TIMEOUT, "name": name, "duration_ms": ms}
        if box.get("err") is not None:
            err = box["err"]
            if isinstance(err, PermissionError):
                self.audit_log.append(Audit(name=name, error_code=ERR_DENIED, duration_ms=ms, expert_id=expert_id))
                denied: Dict[str, Any] = {
                    "ok": False,
                    "error_code": ERR_DENIED,
                    "name": name,
                    "detail": str(err)[:200],
                    "duration_ms": ms,
                }
                if sandbox_info:
                    denied["sandbox"] = sandbox_info
                return denied
            self._fail_streak[name] = self._fail_streak.get(name, 0) + 1
            self.audit_log.append(Audit(name=name, error_code=ERR_INVALID, duration_ms=ms, expert_id=expert_id))
            return {"ok": False, "error_code": ERR_INVALID, "name": name, "detail": str(err)[:200]}
        self._fail_streak[name] = 0
        data = box.get("data")
        self.audit_log.append(Audit(name=name, error_code=ERR_OK, duration_ms=ms, expert_id=expert_id))
        out: Dict[str, Any] = {"ok": True, "error_code": ERR_OK, "name": name, "data": data, "duration_ms": ms}
        if sandbox_info:
            out["sandbox"] = sandbox_info
        if isinstance(data, dict):
            out.update({k: data[k] for k in data if k not in out})
        return out


_ENGINE: Optional[ToolEngine] = None


def _pack_handler(name: str):
    def _h(args: Dict[str, Any]) -> Any:
        from packing_assistant.tools.pack_ship_mcp import call_tool

        return call_tool(name, args)

    return _h


def _write_deliverable(args: Dict[str, Any]) -> Any:
    from packing_assistant.sandbox import guarded_write_text

    path = str(args.get("path") or "")
    text = str(args.get("text") or "")
    target = guarded_write_text(path, text)
    return {"path": str(target), "wrote": True, "n_chars": len(text)}


def _spawn_helper(args: Dict[str, Any]) -> Any:
    from packing_assistant.sandbox import request_spawn

    decision = request_spawn(args.get("command"), kind=args.get("kind"))
    if not decision.allowed:
        raise PermissionError(decision.reason)
    return {
        "allowed": True,
        "reason": decision.reason,
        "spawned": False,
        "note": "sandbox allowlisted; agent does not exec a shell",
    }


def _tender_parse(args: Dict[str, Any]) -> Any:
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    return run_tender_pipeline(
        str(args.get("text") or ""),
        source=str(args.get("source") or "tool-engine"),
        project_name=str(args.get("project_name") or "幕墙项目投标应答（草稿）"),
        p0_confirmed=bool(args.get("p0_confirmed")),
    )


def _tender_review(args: Dict[str, Any]) -> Any:
    from packing_assistant.tools.tender_review import review_draft

    return review_draft(
        draft=str(args.get("draft") or args.get("text") or ""),
        matrix=args.get("matrix") if isinstance(args.get("matrix"), dict) else None,
        packing_summary=args.get("packing_summary")
        if isinstance(args.get("packing_summary"), dict)
        else None,
        tech_outline=args.get("tech_outline") if isinstance(args.get("tech_outline"), dict) else None,
        bidbook_markdown=str(args.get("bidbook_markdown") or ""),
    )


def default_engine() -> ToolEngine:
    eng = ToolEngine()
    eng.register("pack-ship__list", _pack_handler("pack-ship__list"), expert_id="pack-ship", writes=False)
    eng.register("pack-ship__health", _pack_handler("pack-ship__health"), expert_id="pack-ship", writes=False)
    eng.register("pack-ship__plan", _pack_handler("pack-ship__plan"), expert_id="pack-ship", writes=True)
    eng.register("pack-ship__export", _pack_handler("pack-ship__export"), expert_id="pack-ship", writes=True)
    eng.register("tender.parse", _tender_parse, writes=True)
    eng.register("tender.review", _tender_review, writes=False)
    eng.register(
        "write_deliverable",
        _write_deliverable,
        schema_keys=("path",),
        writes=True,
    )
    eng.register("spawn_helper", _spawn_helper, writes=True)
    return eng


def get_engine() -> ToolEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = default_engine()
    return _ENGINE
