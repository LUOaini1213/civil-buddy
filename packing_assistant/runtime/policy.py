"""Policy engine · who may call which tool, at what cost, on which data.

Reject always carries a judge-visible `reason`. Runtime, not a prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from packing_assistant.runtime.tool_engine import (
    ERR_CIRCUIT,
    ERR_DENIED,
    ERR_INVALID,
    WRITE_TOOLS,
    _spawn_cmd,
    _write_path,
)

CODE_ALLOW = "allow"
CODE_CHAT_WRITE = "deny_chat_write"
CODE_CROSS = "deny_cross_expert"
CODE_SECRET = "deny_secret"
CODE_PRODUCTION = "deny_production"
CODE_SANDBOX = "deny_sandbox"
CODE_UNKNOWN = "deny_unknown"
CODE_BUDGET = "deny_budget"
CODE_CIRCUIT = "circuit_open"
CODE_CANCEL = "deny_cancelled"

ERR_MAP = {
    CODE_ALLOW: "ok",
    CODE_CHAT_WRITE: ERR_DENIED,
    CODE_CROSS: ERR_DENIED,
    CODE_SECRET: ERR_DENIED,
    CODE_PRODUCTION: ERR_DENIED,
    CODE_SANDBOX: ERR_DENIED,
    CODE_UNKNOWN: ERR_INVALID,
    CODE_BUDGET: ERR_CIRCUIT,
    CODE_CIRCUIT: ERR_CIRCUIT,
    CODE_CANCEL: ERR_DENIED,
}


@dataclass
class SessionLedger:
    max_steps: int = 8
    max_tokens: int = 8000
    steps: int = 0
    tokens: int = 0

    def over(self) -> bool:
        return self.steps >= self.max_steps or self.tokens >= self.max_tokens

    def charge(self, *, steps: int = 1, tokens: int = 0) -> None:
        self.steps += max(0, steps)
        self.tokens += max(0, tokens)

    def snapshot(self) -> Dict[str, int]:
        return {
            "steps": self.steps,
            "max_steps": self.max_steps,
            "tokens": self.tokens,
            "max_tokens": self.max_tokens,
        }


@dataclass
class PolicyDecision:
    allow: bool
    code: str
    reason: str
    err: str = "ok"
    token_cost: int = 0
    sandbox: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "allow": self.allow,
            "code": self.code,
            "reason": self.reason,
            "error_code": self.err,
            "token_cost": self.token_cost,
        }
        if self.sandbox:
            d["sandbox"] = self.sandbox
        d.update(self.extra)
        return d


def _tokens(name: str, args: Dict[str, Any]) -> int:
    n = len(name) + len(str(args.get("text") or args.get("path") or ""))
    return max(16, n // 4 + 16)


def _production_path(path: str) -> bool:
    p = (path or "").replace("/", "\\").lower()
    return "d:\\layout" in p or "\\prod\\" in p or p.endswith("\\prod")


def evaluate(
    *,
    tool: str,
    spec: Any = None,
    expert_id: str = "",
    intent: str = "run",
    args: Optional[Dict[str, Any]] = None,
    cancelled: bool = False,
    ledger: Optional[SessionLedger] = None,
    fail_streak: int = 0,
    circuit_threshold: int = 3,
) -> PolicyDecision:
    args = args or {}
    cost = _tokens(tool, args)
    if cancelled:
        return PolicyDecision(False, CODE_CANCEL, "拒绝：run 已取消，工具未执行。", ERR_DENIED, cost)
    if spec is None:
        return PolicyDecision(
            False,
            CODE_UNKNOWN,
            f"拒绝：未知工具 {tool}。",
            ERR_INVALID,
            cost,
        )
    writes = bool(getattr(spec, "writes", False) or tool in WRITE_TOOLS)
    owner = getattr(spec, "expert_id", None) or ""
    if intent == "chat" and writes:
        return PolicyDecision(
            False,
            CODE_CHAT_WRITE,
            f"拒绝：提问回合不能调写盘工具 {tool}。",
            ERR_DENIED,
            cost,
        )
    if owner and expert_id and owner != expert_id:
        return PolicyDecision(
            False,
            CODE_CROSS,
            f"拒绝：岗 {expert_id} 不能调 {tool}（exclusive 属于 {owner}）。",
            ERR_DENIED,
            cost,
            extra={"actor": expert_id, "owner": owner, "tool": tool},
        )
    if fail_streak >= circuit_threshold:
        return PolicyDecision(
            False,
            CODE_CIRCUIT,
            f"熔断：工具 {tool} 连续失败 {fail_streak} 次。",
            ERR_CIRCUIT,
            cost,
        )
    if ledger is not None and ledger.over():
        snap = ledger.snapshot()
        return PolicyDecision(
            False,
            CODE_BUDGET,
            (
                f"熔断：session 成本超限 "
                f"steps {snap['steps']}/{snap['max_steps']} "
                f"tokens {snap['tokens']}/{snap['max_tokens']}。"
            ),
            ERR_CIRCUIT,
            cost,
            extra={"ledger": snap},
        )
    from packing_assistant.sandbox import check_write, request_spawn

    path = _write_path(args)
    if writes and path:
        if _production_path(path):
            return PolicyDecision(
                False,
                CODE_PRODUCTION,
                f"拒绝：目标 {path} 视为生产数据（禁止 D:\\layout / prod）。",
                ERR_DENIED,
                cost,
            )
        decision = check_write(path)
        sand = decision.to_dict()
        if not decision.allowed:
            code = CODE_SECRET if "secret" in (decision.reason or "") else CODE_SANDBOX
            return PolicyDecision(
                False,
                code,
                f"拒绝：{decision.reason}",
                ERR_DENIED,
                cost,
                sandbox=sand,
            )
    cmd, kind = _spawn_cmd(args)
    if cmd is not None:
        decision = request_spawn(cmd, kind=kind)
        sand = decision.to_dict()
        if not decision.allowed:
            return PolicyDecision(
                False,
                CODE_SANDBOX,
                f"拒绝：{decision.reason}",
                ERR_DENIED,
                cost,
                sandbox=sand,
            )
    who = expert_id or owner or "router"
    return PolicyDecision(
        True,
        CODE_ALLOW,
        f"允许：岗 {who} 调 {tool}，intent={intent}，未碰生产数据。",
        "ok",
        cost,
        extra={"actor": who, "tool": tool},
    )
