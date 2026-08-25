"""Failure recovery · timeout / tool error / stuck: retry, degrade, audit.

Never invent xyz / can_fit / mid50. Degrade to the literal UNSPECIFIED.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from packing_assistant.runtime.tool_engine import ERR_INVALID, ERR_TIMEOUT

UNSPEC = "UNSPECIFIED"
RETRYABLE = {ERR_TIMEOUT, ERR_INVALID}


def _audit_append(trail: List[Dict[str, Any]], **row: Any) -> None:
    row.setdefault("ts", time.time())
    trail.append(row)


def degrade_payload(name: str, last: Dict[str, Any]) -> Dict[str, Any]:
    """Safe fallback. Packing numbers stay UNSPECIFIED."""
    reason = (
        f"下游失败 {last.get('error_code') or 'error'}，"
        f"工具 {name} 降级，不编柜数/xyz。"
    )
    data = {
        "utilization": UNSPEC,
        "can_fit": UNSPEC,
        "mid50": UNSPEC,
        "系固待办": UNSPEC,
        "degraded": True,
        "from_tool": name,
    }
    return {
        "ok": True,
        "error_code": "ok",
        "name": name,
        "degraded": True,
        "reason": reason,
        "data": data,
        "utilization": UNSPEC,
        "can_fit": UNSPEC,
        "mid50": UNSPEC,
        "detail": reason,
    }


def execute_with_recovery(
    execute: Callable[..., Dict[str, Any]],
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    retries: int = 1,
    expert_id: str = "",
    intent: str = "run",
) -> Dict[str, Any]:
    """Retry retryable failures, then degrade. Audit every hop."""
    trail: List[Dict[str, Any]] = []
    last: Dict[str, Any] = {}
    args = arguments or {}
    for attempt in range(retries + 1):
        last = execute(name, args, expert_id=expert_id, intent=intent) or {}
        _audit_append(
            trail,
            action="call" if attempt == 0 else "retry",
            attempt=attempt,
            tool=name,
            ok=bool(last.get("ok")),
            error_code=last.get("error_code") or "",
            reason=last.get("reason") or last.get("detail") or "",
        )
        if last.get("ok"):
            last["recovery"] = {
                "action": "ok" if attempt == 0 else "retry_ok",
                "attempts": attempt + 1,
                "audit": trail,
            }
            return last
        code = str(last.get("error_code") or "")
        if code not in RETRYABLE:
            break
    degraded = degrade_payload(name, last)
    _audit_append(
        trail,
        action="degrade",
        attempt=len(trail),
        tool=name,
        ok=True,
        error_code="degraded",
        reason=degraded.get("reason") or "",
    )
    degraded["recovery"] = {
        "action": "degrade",
        "attempts": len([x for x in trail if x.get("action") in {"call", "retry"}]),
        "switched_to": "UNSPECIFIED-fallback",
        "audit": trail,
    }
    return degraded


def flaky_timeout_handler(fail_first: int = 1, sleep_s: float = 2.0):
    """Demo tool: first N calls hang past timeout, then succeed."""
    state = {"n": 0}

    def _h(_args: Dict[str, Any]) -> Any:
        state["n"] += 1
        if state["n"] <= fail_first:
            time.sleep(max(0.05, sleep_s))
        return {"ok": True, "attempt": state["n"], "can_fit": UNSPEC}

    _h.state = state  # type: ignore[attr-defined]
    return _h
