"""计划 diff：两版 PackingPlan / container_plan 对比叙事。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def diff_packing_plans(
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    b = before or {}
    a = after or {}

    def _m(p: Dict[str, Any], *keys, default=None):
        cur: Any = p
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
        return cur if cur is not None else default

    changes: List[Dict[str, Any]] = []

    def ch(field: str, bv, av, better: Optional[str] = None):
        if bv == av:
            return
        changes.append(
            {
                "field": field,
                "before": bv,
                "after": av,
                "delta_note": better or "",
            }
        )

    ch("can_fit", b.get("can_fit"), a.get("can_fit"))
    ch("containers_used", b.get("containers_used"), a.get("containers_used"))
    ch("n0", b.get("n0") or _m(b, "metrics", "n0"), a.get("n0") or _m(a, "metrics", "n0"))
    ch(
        "weight_utilization",
        _m(b, "metrics", "weight_utilization", default=b.get("weight_utilization")),
        _m(a, "metrics", "weight_utilization", default=a.get("weight_utilization")),
    )
    ch(
        "booking_volume_utilization",
        _m(b, "metrics", "booking_volume_utilization"),
        _m(a, "metrics", "booking_volume_utilization"),
    )
    ch(
        "outer_space_utilization",
        _m(b, "metrics", "outer_space_utilization", default=b.get("outer_space_utilization")),
        _m(a, "metrics", "outer_space_utilization", default=a.get("outer_space_utilization")),
    )
    ch(
        "stacked_placements",
        _m(b, "stacking", "stacked_placements"),
        _m(a, "stacking", "stacked_placements"),
    )
    ch(
        "mid50",
        _m(b, "cog", "mass_in_mid50_ratio", default=b.get("worst_mid50")),
        _m(a, "cog", "mass_in_mid50_ratio", default=a.get("worst_mid50")),
    )
    ch(
        "worst_mid50",
        b.get("worst_mid50") or _m(b, "metrics", "worst_mid50"),
        a.get("worst_mid50") or _m(a, "metrics", "worst_mid50"),
    )
    ch(
        "lat",
        _m(b, "cog", "lateral_eccentricity"),
        _m(a, "cog", "lateral_eccentricity"),
    )
    ch(
        "ship_ok",
        b.get("ship_ok") if b.get("ship_ok") is not None else _m(b, "risk", "ship_ok"),
        a.get("ship_ok") if a.get("ship_ok") is not None else _m(a, "risk", "ship_ok"),
    )
    ch(
        "eval_score",
        _m(b, "evaluation", "score"),
        _m(a, "evaluation", "score"),
    )

    # 叙事
    lines = []
    if not changes:
        lines.append("两版方案关键指标无变化。")
    else:
        lines.append(f"共 {len(changes)} 项指标变化：")
        for c in changes:
            lines.append(f"- {c['field']}: {c['before']} → {c['after']}")

    return {
        "changes": changes,
        "narrative": "\n".join(lines),
        "improved_fit": bool(a.get("can_fit")) and not bool(b.get("can_fit")),
        "fewer_containers": (
            a.get("containers_used") is not None
            and b.get("containers_used") is not None
            and int(a["containers_used"]) < int(b["containers_used"])
        ),
    }
