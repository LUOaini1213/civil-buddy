"""方案评分卡：统一比较 baseline vs what-if，标「更优」。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def score_plan(snap: Dict[str, Any]) -> Dict[str, Any]:
    """
    snap: whatif.snapshot_for_diff 形态或 container_plan 摘要。
    分数 0–100，越高越好（合规优先）。
    """
    can = 1.0 if snap.get("can_fit") else 0.0
    ship = snap.get("ship_ok")
    if ship is None:
        ship = (snap.get("risk") or {}).get("ship_ok")
    ship_f = 1.0 if ship else 0.0

    mid = snap.get("worst_mid50")
    if mid is None:
        mid = (snap.get("cog") or {}).get("mass_in_mid50_ratio")
    mid = float(mid or 0)

    lat = (snap.get("cog") or {}).get("lateral_eccentricity")
    lat = float(lat if lat is not None else 0.2)

    used = snap.get("containers_used")
    n0 = snap.get("n0")
    try:
        used_f = float(used) if used is not None else 9.0
        n0_f = float(n0) if n0 is not None else used_f
    except Exception:
        used_f, n0_f = 9.0, 9.0

    wt = snap.get("weight_utilization")
    if wt is None:
        wt = (snap.get("metrics") or {}).get("weight_utilization")
    wt = float(wt or 0)

    # 合规主分
    mid_s = min(1.0, mid / 0.60) * 30.0  # mid50 达 60% 拿满分 30
    lat_s = max(0.0, 1.0 - lat / 0.15) * 15.0  # lat 越小越好
    fit_s = can * 25.0
    ship_s = ship_f * 15.0
    # 少柜：在 can_fit 前提下 used 接近 n0 更好
    cabin_s = 0.0
    if can:
        if used_f <= n0_f + 0.1:
            cabin_s = 10.0
        elif used_f <= n0_f + 1.1:
            cabin_s = 6.0
        else:
            cabin_s = max(0.0, 10.0 - (used_f - n0_f) * 2.0)
    util_s = min(1.0, wt / 0.70) * 5.0

    total = fit_s + ship_s + mid_s + lat_s + cabin_s + util_s
    return {
        "score": round(total, 2),
        "parts": {
            "can_fit": round(fit_s, 2),
            "ship_ok": round(ship_s, 2),
            "mid50": round(mid_s, 2),
            "lat": round(lat_s, 2),
            "cabin": round(cabin_s, 2),
            "weight_util": round(util_s, 2),
        },
        "inputs": {
            "can_fit": bool(can),
            "ship_ok": bool(ship),
            "worst_mid50": mid,
            "lat": lat,
            "containers_used": used,
            "n0": n0,
            "weight_utilization": wt,
        },
    }


def compare_plans(
    before: Dict[str, Any], after: Dict[str, Any]
) -> Dict[str, Any]:
    sb = score_plan(before)
    sa = score_plan(after)
    delta = round(sa["score"] - sb["score"], 2)
    winner = "after" if delta > 0.5 else ("before" if delta < -0.5 else "tie")
    better = winner == "after"
    return {
        "before_score": sb,
        "after_score": sa,
        "delta": delta,
        "winner": winner,
        "after_is_better": better,
        "label": (
            "更优 ✓"
            if better
            else ("持平" if winner == "tie" else "未优于基线")
        ),
        "narrative": (
            f"评分 {sb['score']} → {sa['score']}（Δ{delta:+}）· {('更优' if better else winner)}"
        ),
    }
