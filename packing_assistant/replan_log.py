"""replan 归因日志：写入 run 目录，便于统计 Top 失败原因。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def append_replan_event(
    state: Dict[str, Any],
    *,
    ring: str,
    proposal: Dict[str, Any],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """追加一条 replan 事件到 state['replan_log'] 并尝试落盘。"""
    rid = run_id or state.get("run_id") or state.get("session_id") or "run"
    ev = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ring": ring,  # inner | ship
        "route": proposal.get("route"),
        "reasons": list(proposal.get("reasons") or []),
        "replan_round": state.get("replan_round"),
        "ship_replan_round": state.get("ship_replan_round"),
        "team_loop_round": state.get("team_loop_round"),
        "delta_keys": list((proposal.get("packing_options_delta") or {}).keys()),
        "stop": bool(proposal.get("stop")),
    }
    log: List[Dict[str, Any]] = list(state.get("replan_log") or [])
    log.append(ev)
    state["replan_log"] = log

    try:
        root = Path("output") / "runs" / str(rid)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "replan_log.json"
        path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        paths = dict(state.get("artifact_paths") or {})
        paths["replan_log"] = str(path)
        state["artifact_paths"] = paths
    except Exception:
        pass
    return ev


def summarize_replan_log(log: List[Dict[str, Any]]) -> Dict[str, Any]:
    from collections import Counter

    reasons: Counter = Counter()
    routes: Counter = Counter()
    for e in log:
        routes[str(e.get("route") or "?")] += 1
        for r in e.get("reasons") or []:
            # 截断做统计键
            reasons[str(r)[:80]] += 1
    return {
        "n_events": len(log),
        "routes": dict(routes),
        "top_reasons": reasons.most_common(10),
    }
