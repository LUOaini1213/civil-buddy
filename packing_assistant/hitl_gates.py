"""HITL 策略门：何时必须人工确认 / 阻断自动放行。"""

from __future__ import annotations

from typing import Any, Dict, List


def evaluate_hitl_gates(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回:
      require_hitl: bool
      can_auto_confirm: bool
      gates: [{code, severity, message, block_auto}]
      recommended_action: confirm|revise|export_review
    """
    plan = state.get("container_plan") or {}
    risk = state.get("risk_report") or {}
    evaluation = state.get("evaluation") or {}
    opts = dict(state.get("packing_options") or {})
    pp = state.get("packing_plan") or {}
    export_strict = bool(opts.get("export_strict") or risk.get("export_strict"))

    gates: List[Dict[str, Any]] = []

    def add(code: str, severity: str, message: str, block_auto: bool = True):
        gates.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "block_auto": block_auto,
            }
        )

    if not plan.get("can_fit"):
        add("NOT_FIT", "high", "未能全部装入，须确认加柜/改箱", True)

    blockers = risk.get("blockers") or []
    if blockers:
        add("RISK_BLOCK", "high", f"合规阻断 {len(blockers)} 项: {blockers[0]}", True)

    if evaluation.get("decision") == "REJECT_STRUCTURE":
        add("STRUCTURE", "high", "成箱结构不通过，须改箱", True)

    cog = (pp.get("cog") if isinstance(pp, dict) else None) or plan.get("cog") or risk.get("cog") or {}
    if isinstance(cog, dict):
        mid50 = cog.get("mass_in_mid50_ratio")
        if mid50 is not None and float(mid50) < 0.60:
            add(
                "COG_MID50",
                "high" if export_strict else "medium",
                f"CTU 60/50 mid50={float(mid50):.0%}",
                block_auto=export_strict,
            )
        bal = cog.get("balance")
        if bal == "block":
            add("COG_BALANCE", "high", "重心 balance=block", True)

    if export_strict:
        add("EXPORT_STRICT", "medium", "出运严模式：必须人工确认后放行", True)

    # 改柜型 / 超 N0
    n0 = plan.get("n0")
    used = plan.get("containers_used")
    try:
        if n0 is not None and used is not None and int(used) > int(n0):
            add(
                "OVER_N0",
                "medium",
                f"用柜 {used} > N0={n0}，建议确认订舱",
                block_auto=True,
            )
    except Exception:
        pass

    # 用户显式要求 HITL
    if opts.get("force_hitl") or state.get("force_hitl"):
        add("FORCE_HITL", "medium", "强制人工闸门", True)

    # 非标检验门禁
    ns = state.get("nonstandard_summary") or state.get("nonstandard_report") or {}
    ns_overall = str(ns.get("overall") or "")
    ship_gate = ns.get("ship_gate") or {}
    if ns_overall == "FAIL":
        add(
            "NONSTANDARD_FAIL",
            "high",
            ship_gate.get("note") or "非标检验 FAIL：缺尺寸/超柜/超货载等",
            block_auto=True,
        )
    elif ns_overall in ("WARN", "NEED_DESIGN"):
        add(
            "NONSTANDARD_REVIEW",
            "medium",
            ship_gate.get("note") or f"非标检验 {ns_overall}：须人工复核",
            block_auto=bool(opts.get("strict_nonstandard_gate")),
        )
    if ship_gate.get("blocks_confirm_to_team_b") or (
        opts.get("strict_nonstandard_gate") and ns_overall == "FAIL"
    ):
        add(
            "NONSTANDARD_STRICT",
            "high",
            "strict_nonstandard_gate：禁止确认进入拼柜直至整改",
            True,
        )

    block_auto = any(g.get("block_auto") for g in gates)
    # demo 自动确认仅在无阻断门时
    auto_ok = (not block_auto) and not export_strict

    if any(g["severity"] == "high" and g["block_auto"] for g in gates):
        rec = "revise"
    elif gates:
        rec = "export_review" if export_strict else "confirm"
    else:
        rec = "confirm"

    return {
        "require_hitl": bool(gates) or export_strict,
        "can_auto_confirm": auto_ok,
        "gates": gates,
        "recommended_action": rec,
        "export_strict": export_strict,
        "summary": "; ".join(g["message"] for g in gates[:5]) or "无强制闸门",
    }


def should_pause_for_hitl(state: Dict[str, Any], *, enable_auto_confirm: bool) -> bool:
    """auto_confirm 模式下是否仍应暂停。"""
    g = evaluate_hitl_gates(state)
    if not enable_auto_confirm:
        return True
    return not g.get("can_auto_confirm", True)
