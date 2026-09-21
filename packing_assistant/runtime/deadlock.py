"""Wait-for graph · multi-agent deadlock detection.

Hold resources, declare wait edges, DFS cycle → fail-fast `deadlock`.
Does not block-sleep. Distinct from:

- `session_busy` — same session re-entry (Scheduler lock)
- `deny_cross` — wrong expert calling an exclusive tool (isolation, not wait)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ERR_DEADLOCK = "deadlock"
ERR_BUSY = "expert_busy"
CODE_DEADLOCK = "deadlock"
CODE_BUSY = "expert_busy"
CODE_ALLOW = "allow"


@dataclass
class DeadlockDecision:
    allow: bool
    code: str
    reason: str
    err: str = "ok"
    cycle: List[str] = field(default_factory=list)
    path: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "allow": self.allow,
            "code": self.code,
            "reason": self.reason,
            "error_code": self.err,
            "cycle": list(self.cycle),
            "path": self.path,
        }
        d.update(self.extra)
        return d


def _allow(who: str, resource: str) -> DeadlockDecision:
    return DeadlockDecision(
        True,
        CODE_ALLOW,
        f"允许：{who} 持有 {resource}。",
        "ok",
        extra={"resource": resource, "run_id": who},
    )


class DeadlockWatch:
    """Process-local wait-for graph. One holder per resource."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._holds: Dict[str, str] = {}  # resource -> run_id
        self._run_holds: Dict[str, Set[str]] = {}  # run_id -> resources
        self._wait: Dict[str, Set[str]] = {}  # waiter -> holders
        self._wait_edge: Dict[Tuple[str, str], str] = {}  # (waiter, holder) -> resource
        self._labels: Dict[str, str] = {}

    def begin(
        self,
        run_id: str,
        *,
        holds: Sequence[str] = (),
        label: str = "",
    ) -> DeadlockDecision:
        """Register a run and acquire exclusive resources. Contended → wait_for."""
        rid = (run_id or "").strip()
        if not rid:
            return DeadlockDecision(
                False,
                CODE_BUSY,
                "拒绝：deadlock.begin 缺少 run_id。",
                ERR_BUSY,
            )
        with self._lock:
            self._labels[rid] = (label or self._labels.get(rid) or rid).strip() or rid
            self._run_holds.setdefault(rid, set())
            taken: List[str] = []
            for res in holds:
                name = (res or "").strip()
                if not name:
                    continue
                owner = self._holds.get(name)
                if owner is None or owner == rid:
                    self._holds[name] = rid
                    self._run_holds[rid].add(name)
                    taken.append(name)
                    continue
                d = self._wait_for_unlocked(rid, name)
                if not d.allow:
                    self._rollback_unlocked(rid, taken)
                    return d
            who = self._lab(rid)
            got = ", ".join(self._run_holds.get(rid) or []) or "（无）"
            return DeadlockDecision(
                True,
                CODE_ALLOW,
                f"允许：{rid}({who}) 持有 {got}。",
                "ok",
                extra={"run_id": rid, "holds": sorted(self._run_holds.get(rid) or [])},
            )

    def wait_for(self, run_id: str, resource: str) -> DeadlockDecision:
        """Need a resource. Free → hold. Held → wait edge, cycle=deadlock else busy. No sleep."""
        rid = (run_id or "").strip()
        res = (resource or "").strip()
        if not rid or not res:
            return DeadlockDecision(
                False,
                CODE_BUSY,
                "拒绝：wait_for 缺少 run_id 或 resource。",
                ERR_BUSY,
            )
        with self._lock:
            return self._wait_for_unlocked(rid, res)

    def end(self, run_id: str) -> None:
        rid = (run_id or "").strip()
        if not rid:
            return
        with self._lock:
            self._drop_unlocked(rid)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            cycle = self._find_cycle_unlocked()
            return {
                "holds": dict(self._holds),
                "wait": {k: sorted(v) for k, v in self._wait.items() if v},
                "labels": dict(self._labels),
                "cycle": list(cycle or []),
            }

    def _lab(self, run_id: str) -> str:
        return self._labels.get(run_id) or run_id

    def _wait_for_unlocked(self, rid: str, res: str) -> DeadlockDecision:
        self._run_holds.setdefault(rid, set())
        owner = self._holds.get(res)
        if owner is None or owner == rid:
            self._holds[res] = rid
            self._run_holds[rid].add(res)
            return _allow(f"{rid}({self._lab(rid)})", res)
        self._wait.setdefault(rid, set()).add(owner)
        self._wait_edge[(rid, owner)] = res
        cycle = self._find_cycle_unlocked()
        if cycle:
            path = self._format_cycle_unlocked(cycle)
            reason = f"死锁：{path}。未阻塞等待，当场失败。"
            return DeadlockDecision(
                False,
                CODE_DEADLOCK,
                reason,
                ERR_DEADLOCK,
                cycle=list(cycle),
                path=path,
                extra={"resource": res, "run_id": rid, "holder": owner},
            )
        who = self._lab(rid)
        other = self._lab(owner)
        kind = "岗" if res.startswith("expert:") else "资源"
        name = res.split(":", 1)[-1] if ":" in res else res
        return DeadlockDecision(
            False,
            CODE_BUSY,
            (
                f"拒绝：{kind} {name} 正被 {owner}({other}) 占用，"
                f"{rid}({who}) 未成环。fail-fast，不阻塞等待。"
            ),
            ERR_BUSY,
            extra={"resource": res, "run_id": rid, "holder": owner},
        )

    def _rollback_unlocked(self, rid: str, taken: Iterable[str]) -> None:
        for res in taken:
            if self._holds.get(res) == rid:
                self._holds.pop(res, None)
            self._run_holds.get(rid, set()).discard(res)
        self._clear_wait_unlocked(rid)
        if not self._run_holds.get(rid) and rid not in self._holds.values():
            self._run_holds.pop(rid, None)
            self._labels.pop(rid, None)

    def _clear_wait_unlocked(self, rid: str) -> None:
        self._wait.pop(rid, None)
        drop = [k for k in self._wait_edge if k[0] == rid]
        for k in drop:
            self._wait_edge.pop(k, None)

    def _drop_unlocked(self, rid: str) -> None:
        for res in list(self._run_holds.get(rid) or ()):
            if self._holds.get(res) == rid:
                self._holds.pop(res, None)
        self._run_holds.pop(rid, None)
        self._clear_wait_unlocked(rid)
        incoming = [k for k in self._wait_edge if k[1] == rid]
        for waiter, holder in incoming:
            self._wait_edge.pop((waiter, holder), None)
            waiting = self._wait.get(waiter)
            if waiting:
                waiting.discard(rid)
                if not waiting:
                    self._wait.pop(waiter, None)
        self._labels.pop(rid, None)

    def _find_cycle_unlocked(self) -> Optional[List[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {}
        parent: Dict[str, str] = {}
        nodes = set(self._wait) | {v for vs in self._wait.values() for v in vs}
        nodes |= set(self._run_holds)

        def dfs(u: str) -> Optional[List[str]]:
            color[u] = GRAY
            for v in sorted(self._wait.get(u) or ()):
                c = color.get(v, WHITE)
                if c == WHITE:
                    parent[v] = u
                    found = dfs(v)
                    if found:
                        return found
                elif c == GRAY:
                    path = [v]
                    x = u
                    while x != v:
                        path.append(x)
                        x = parent.get(x)
                        if x is None:
                            break
                    path.append(v)
                    path.reverse()
                    return path
            color[u] = BLACK
            return None

        for n in sorted(nodes):
            if color.get(n, WHITE) == WHITE:
                found = dfs(n)
                if found:
                    return found
        return None

    def _format_cycle_unlocked(self, cycle: Sequence[str]) -> str:
        if not cycle:
            return ""
        parts: List[str] = []
        for i in range(len(cycle) - 1):
            a, b = cycle[i], cycle[i + 1]
            res = self._wait_edge.get((a, b), "?")
            parts.append(f"{a}({self._lab(a)}) 等 {res}")
        last = cycle[-1]
        parts.append(f"{last}({self._lab(last)})")
        return " → ".join(parts)


def demo_tax_pack_cycle() -> DeadlockDecision:
    """Judge-visible cycle: A holds tax waits pack; B holds pack waits tax."""
    w = DeadlockWatch()
    w.begin("run-A", holds=["expert:finance-tax"], label="finance-tax")
    w.begin("run-B", holds=["expert:pack-ship"], label="pack-ship")
    w.wait_for("run-A", "expert:pack-ship")
    return w.wait_for("run-B", "expert:finance-tax")


_WATCH: Optional[DeadlockWatch] = None
_WATCH_LOCK = threading.Lock()


def get_watch() -> DeadlockWatch:
    global _WATCH
    with _WATCH_LOCK:
        if _WATCH is None:
            _WATCH = DeadlockWatch()
        return _WATCH


def reset_watch() -> DeadlockWatch:
    """Tests only. Drop process-global occupancy."""
    global _WATCH
    with _WATCH_LOCK:
        _WATCH = DeadlockWatch()
        return _WATCH
