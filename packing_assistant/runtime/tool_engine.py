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
        "tender.parse",
        "pack-ship__plan",
        "pack-ship__export",
    }
)


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
            self._fail_streak[name] = self._fail_streak.get(name, 0) + 1
            self.audit_log.append(Audit(name=name, error_code=ERR_INVALID, duration_ms=ms, expert_id=expert_id))
            return {"ok": False, "error_code": ERR_INVALID, "name": name, "detail": str(box["err"])[:200]}
        self._fail_streak[name] = 0
        data = box.get("data")
        self.audit_log.append(Audit(name=name, error_code=ERR_OK, duration_ms=ms, expert_id=expert_id))
        out: Dict[str, Any] = {"ok": True, "error_code": ERR_OK, "name": name, "data": data, "duration_ms": ms}
        if isinstance(data, dict):
            out.update({k: data[k] for k in data if k not in out})
        return out


_ENGINE: Optional[ToolEngine] = None


def _pack_handler(name: str):
    def _h(args: Dict[str, Any]) -> Any:
        from packing_assistant.tools.pack_ship_mcp import call_tool

        return call_tool(name, args)

    return _h


def default_engine() -> ToolEngine:
    eng = ToolEngine()
    eng.register("pack-ship__list", _pack_handler("pack-ship__list"), expert_id="pack-ship", writes=False)
    eng.register("pack-ship__health", _pack_handler("pack-ship__health"), expert_id="pack-ship", writes=False)
    eng.register("pack-ship__plan", _pack_handler("pack-ship__plan"), expert_id="pack-ship", writes=True)
    eng.register("pack-ship__export", _pack_handler("pack-ship__export"), expert_id="pack-ship", writes=True)
    eng.register(
        "tender.parse",
        lambda args: __import__(
            "packing_assistant.tools.tender_parse", fromlist=["run_tender_pipeline"]
        ).run_tender_pipeline(str(args.get("text") or ""), source="tool-engine"),
        writes=True,
    )
    return eng


def get_engine() -> ToolEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = default_engine()
    return _ENGINE
