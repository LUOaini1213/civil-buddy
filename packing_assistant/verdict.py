"""出运裁决摘要：前端大红条 + API 字段，不必打开 PDF 才看见问题。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _as_cog(plan: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    cog = plan.get("cog") if isinstance(plan.get("cog"), dict) else None
    if cog and (
        cog.get("mass_in_mid50_ratio") is not None
        or cog.get("balance") is not None
        or cog.get("primary")
    ):
        if cog.get("primary") and cog.get("mass_in_mid50_ratio") is None:
            return dict(cog.get("primary") or {})
        return dict(cog)
    bundle = plan.get("cog_bundle") or state.get("cog_bundle") or {}
    if isinstance(bundle, dict):
        w = bundle.get("worst") or bundle.get("primary")
        if isinstance(w, dict):
            return dict(w)
    rr = (state.get("risk_report") or {}).get("cog")
    if isinstance(rr, dict):
        return dict(rr)
    return {}


def build_verdict(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    汇总 can_fit / ship_ok / risk / CoG mid50 为一眼裁决。

    level:
      - ok: 可讨论出运
      - warn: 可装但有合规/重心软问题
      - block: 不可当正式出运（几何失败 / CoG block / risk REJECT / ship_ok=False）
    """
    plan = state.get("container_plan") or {}
    risk = state.get("risk_report") or {}
    evaluation = state.get("evaluation") or {}
    cog = _as_cog(plan, state)

    can_fit = plan.get("can_fit")
    ship_ok = state.get("ship_ok")
    if ship_ok is None and state.get("goal_status"):
        ship_ok = (state.get("goal_status") or {}).get("ship_ok")

    risk_dec = str(risk.get("decision") or evaluation.get("decision") or "").upper()
    risk_level = str(risk.get("level") or "")
    balance = str(cog.get("balance") or "")
    mid50 = cog.get("mass_in_mid50_ratio")
    if mid50 is None:
        mid50 = plan.get("worst_mid50")
    try:
        mid50_f = float(mid50) if mid50 is not None else None
    except (TypeError, ValueError):
        mid50_f = None

    lat = cog.get("lateral_eccentricity")
    long_pos = cog.get("longitudinal_position")
    height_r = cog.get("height_ratio")

    issues: List[str] = []
    actions: List[str] = []
    level = "ok"

    def raise_to(lv: str) -> None:
        nonlocal level
        order = {"ok": 0, "warn": 1, "block": 2}
        if order.get(lv, 0) > order.get(level, 0):
            level = lv

    if can_fit is False:
        issues.append("几何装不下（can_fit=False）")
        actions.append("增加柜数 / 拆箱 / 调合箱后重跑 Team B")
        raise_to("block")

    if balance == "block" or (mid50_f is not None and mid50_f < 0.40):
        mtxt = f"{mid50_f:.0%}" if mid50_f is not None else "—"
        issues.append(f"重心阻断 CoG={balance or 'block'}，中段50%质量 {mtxt}（宜≥60%，<40% 硬阻断）")
        actions.append("打开「总览」重心区：重货移中段 / 再跑拼柜（已启用 cog_rebalance）")
        raise_to("block")
    elif balance in ("warn", "warn_high") or (
        mid50_f is not None and mid50_f < 0.60
    ):
        mtxt = f"{mid50_f:.0%}" if mid50_f is not None else "—"
        issues.append(f"重心预警 mid50={mtxt}（CTU 60/50 宜≥60%），balance={balance or 'warn'}")
        actions.append("建议中段配重或 replan，正式出运前复核")
        raise_to("warn")

    if risk_dec in ("REJECT", "FAIL", "BLOCK"):
        reason = risk.get("reject_reason") or risk.get("explanation") or risk_dec
        issues.append(f"风险合规 {risk_dec}：{str(reason)[:160]}")
        for a in list(risk.get("suggested_actions") or [])[:3]:
            actions.append(str(a))
        raise_to("block")
    elif risk_dec in ("WARN", "WARNING") or risk_level in ("medium", "high", "warn"):
        if risk_dec and risk_dec not in ("PASS", "OK", ""):
            issues.append(f"风险 {risk_dec}（level={risk_level or '—'}）")
            raise_to("warn")

    if ship_ok is False:
        if not any("不可出运" in x or "ship_ok" in x for x in issues):
            issues.append("裁决：不可出运（ship_ok=False）")
        actions.append("整改阻断项后再 finalize / 导出 PDF")
        raise_to("block")

    # 软项：空隙等
    lq = plan.get("layout_quality") or risk.get("layout_quality") or {}
    gap = lq.get("max_horizontal_gap_mm")
    try:
        if gap is not None and float(gap) > 400:
            issues.append(f"水平空隙偏大 max_gap={float(gap):.0f}mm")
            raise_to("warn")
    except (TypeError, ValueError):
        pass

    if not issues:
        if ship_ok is True or (can_fit is True and risk_dec in ("", "PASS", "OK", "WARN")):
            summary = "可讨论出运：几何可装，重心/风险未见硬阻断（正式前仍需 VGM 与人工复核）"
        elif can_fit is None and not plan:
            summary = "尚未拼柜：请先生成方案并确认进入 Team B"
            level = "warn"
        else:
            summary = "结果已生成，请核对总览指标"
    else:
        summary = "；".join(issues)

    if level == "block":
        title = "⛔ 不可出运 / 硬阻断"
    elif level == "warn":
        title = "⚠️ 可装但有预警"
    else:
        title = "✅ 方案可用（建议人工复核）"

    # 一行短讯给 status 栏
    headline_parts = []
    if can_fit is not None:
        headline_parts.append(f"can_fit={'是' if can_fit else '否'}")
    if ship_ok is not None:
        headline_parts.append(f"ship_ok={'是' if ship_ok else '否'}")
    if mid50_f is not None:
        headline_parts.append(f"mid50={mid50_f:.0%}")
    if balance:
        headline_parts.append(f"CoG={balance}")
    if risk_dec:
        headline_parts.append(f"risk={risk_dec}")
    headline = " · ".join(headline_parts) if headline_parts else summary[:80]

    return {
        "level": level,
        "ok": level == "ok",
        "title": title,
        "summary": summary,
        "headline": headline,
        "issues": issues,
        "actions": actions[:6],
        "ship_ok": ship_ok,
        "can_fit": can_fit,
        "risk_decision": risk_dec or None,
        "risk_level": risk_level or None,
        "cog_balance": balance or None,
        "worst_mid50": round(mid50_f, 4) if mid50_f is not None else None,
        "lateral_eccentricity": lat,
        "longitudinal_position": long_pos,
        "height_ratio": height_r,
        "show_banner": bool(plan or risk or state.get("phase") in ("done", "need_revision", "await_user_confirm")),
    }


def attach_verdict(state: Dict[str, Any]) -> Dict[str, Any]:
    """写入 state['verdict']，返回 verdict。"""
    v = build_verdict(state)
    state["verdict"] = v
    return v
