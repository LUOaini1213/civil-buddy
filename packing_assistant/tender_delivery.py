"""主线 C：投标应答 + 交付链路（T parse → 矩阵 → A/B 装柜证据）。

不改坏现有 run_big_team 装柜主路径；本模块是产品入口。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def facade_sample_materials() -> List[Dict[str, Any]]:
    """幕墙交付样例料（UI 无上传时的默认交付证据）。"""
    mats = [
        {
            "name": f"1.1m 铁架 #{i}",
            "length_mm": 1100,
            "width_mm": 1100,
            "height_mm": 1750,
            "weight_kg": 400,
            "quantity": 1,
            "total_weight_kg": 400,
        }
        for i in range(4)
    ]
    mats.append(
        {
            "name": "中空玻璃 易碎",
            "note": "禁翻 向上",
            "length_mm": 1800,
            "width_mm": 1000,
            "height_mm": 40,
            "weight_kg": 60,
            "quantity": 2,
            "total_weight_kg": 120,
        }
    )
    return mats


def extract_mid50(pack_state: Optional[dict], plan: Optional[dict] = None) -> Optional[float]:
    """mid50 在 run_big_team 状态中的真实位置（非 top-level cog_bundle）。"""
    st = pack_state or {}
    pl = plan if isinstance(plan, dict) else (st.get("container_plan") or {})
    candidates: List[Any] = []
    cog = st.get("cog")
    if isinstance(cog, dict):
        prim = cog.get("primary")
        if isinstance(prim, dict):
            candidates.append(prim.get("mass_in_mid50_ratio"))
        candidates.append(cog.get("mass_in_mid50_ratio"))
        candidates.append(cog.get("worst_mid50"))
    if isinstance(pl, dict):
        pc = pl.get("cog")
        if isinstance(pc, dict):
            candidates.append(pc.get("mass_in_mid50_ratio"))
        pcb = pl.get("cog_bundle")
        if isinstance(pcb, dict):
            pp = pcb.get("primary") or pcb.get("worst") or {}
            if isinstance(pp, dict):
                candidates.append(pp.get("mass_in_mid50_ratio"))
            candidates.append(pcb.get("worst_mid50"))
    cb = st.get("cog_bundle")
    if isinstance(cb, dict):
        pp = cb.get("primary") or {}
        if isinstance(pp, dict):
            candidates.append(pp.get("mass_in_mid50_ratio"))
        candidates.append(cb.get("worst_mid50"))
    for c in candidates:
        if c is None:
            continue
        try:
            return float(c)
        except (TypeError, ValueError):
            continue
    return None


def packing_summary_from_state(pack_state: Optional[dict], *, container_type: str = "40HQ") -> Dict[str, Any]:
    """把 big_team 状态收成响应矩阵可用的 packing_summary。"""
    st = pack_state or {}
    plan = st.get("container_plan") or {}
    mid50 = extract_mid50(st, plan)
    return {
        "can_fit": plan.get("can_fit"),
        "containers_used": plan.get("containers_used"),
        "n0": plan.get("n0") or st.get("n0"),
        "ship_ok": st.get("ship_ok"),
        "mid50": mid50,
        "phase": st.get("phase"),
        "container_type": plan.get("container_type") or container_type,
    }


def run_tender_delivery_pipeline(
    text: str,
    *,
    run_delivery: bool = True,
    materials: Optional[List[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
    max_containers: int = 2,
    user_input: str = "投标交付：按招标运输包装要求装柜",
    session_id: str = "tender-delivery",
    project_name: str = "幕墙项目投标应答（草稿）",
    enable_auto_confirm: bool = True,
    save_artifacts: bool = False,
    p0_confirmed: bool = False,
) -> Dict[str, Any]:
    """主线 C 端到端：招标文本 →（可选 A/B 装柜）→ 响应矩阵 + 应答导出包。"""
    from packing_assistant.tools.tender_parse import run_tender_pipeline

    packing_summary = None
    pack_state = None
    if run_delivery:
        from packing_assistant.teams.big_team import run_big_team

        mats = materials if isinstance(materials, list) and materials else facade_sample_materials()
        pack_state = run_big_team(
            raw_input=str(user_input or "投标交付：按招标运输包装要求装柜"),
            materials=mats,
            container_type=str(container_type or "40HQ"),
            max_containers=int(max_containers or 2),
            enable_auto_confirm=enable_auto_confirm,
            session_id=str(session_id or "tender-delivery"),
            save_artifacts=save_artifacts,
        )
        packing_summary = packing_summary_from_state(
            pack_state, container_type=str(container_type or "40HQ")
        )

    out = run_tender_pipeline(
        text,
        packing_summary=packing_summary,
        source="tender-delivery",
        project_name=project_name,
        p0_confirmed=p0_confirmed,
    )
    return {
        "ok": bool(out.get("ok")),
        "product": "tender_delivery",
        "product_mainline": "C_tender_delivery",
        "packing_summary": packing_summary,
        "readiness_score": ((out.get("matrix") or {}).get("summary") or {}).get("readiness_score"),
        "n_open_actions": len(out.get("open_actions") or []),
        **out,
    }
