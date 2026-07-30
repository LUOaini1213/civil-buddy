"""装载可行性门禁（Tool）：单件/单箱是否超过柜货载。

Agent 在成箱后、3D 前调用；超限时给出拆箱建议，避免 replan 只加柜空转。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

# 常用柜型货载（kg，与 container_select/booking 量级一致）
PAYLOAD_KG = {
    "20GP": 21770.0,
    "40GP": 26680.0,
    "40HQ": 28610.0,
    "45HQ": 27700.0,
}


def payload_for_container(container_type: str = "40HQ") -> float:
    ct = (container_type or "40HQ").upper().strip()
    return float(PAYLOAD_KG.get(ct, PAYLOAD_KG["40HQ"]))


def _box_net_kg(b: Dict[str, Any]) -> float:
    for k in ("net_weight_kg", "net_kg", "gross_weight_kg", "gross_kg", "weight_kg", "total_weight_kg"):
        try:
            v = float(b.get(k) or 0)
            if v > 0:
                return v
        except Exception:
            continue
    return 0.0


def _mat_net_kg(m: Dict[str, Any]) -> float:
    try:
        t = float(m.get("total_weight_kg") or 0)
        if t > 0:
            return t
        q = float(m.get("quantity") or m.get("qty") or 1)
        u = float(m.get("weight_kg") or 0)
        return u * max(q, 1)
    except Exception:
        return 0.0


def check_cargo_feasibility(
    *,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
    margin: float = 0.92,
) -> Dict[str, Any]:
    """
    返回:
      ok: 无单件/单箱超 payload*margin
      payload_kg, safe_cap_kg
      over_payload_boxes / over_payload_materials
      blockers, suggest_split, max_box_net_kg_recommend
      failure_class: ok | over_payload_box | over_payload_material
    """
    payload = payload_for_container(container_type)
    cap = float(payload) * float(margin)
    over_boxes: List[Dict[str, Any]] = []
    over_mats: List[Dict[str, Any]] = []

    for b in boxes or []:
        if not isinstance(b, dict):
            continue
        net = _box_net_kg(b)
        if net > cap + 1e-6:
            over_boxes.append(
                {
                    "id": b.get("box_id") or b.get("id") or "?",
                    "net_kg": round(net, 1),
                    "cap_kg": round(cap, 1),
                }
            )

    for m in materials or []:
        if not isinstance(m, dict):
            continue
        # 单件：若 qty>1，看 unit；若 unit 已超 cap 才算 material 级不可拆
        try:
            q = max(1, int(float(m.get("quantity") or m.get("qty") or 1)))
            unit = float(m.get("weight_kg") or 0)
            total = float(m.get("total_weight_kg") or unit * q)
            if unit <= 0 and q > 0:
                unit = total / q
        except Exception:
            unit, total, q = 0.0, _mat_net_kg(m), 1
        # 行总重超 cap 但可按件拆：不算 indivisible，除非 unit 也超
        if unit > cap + 1e-6:
            over_mats.append(
                {
                    "id": m.get("id") or m.get("part_no") or "?",
                    "unit_kg": round(unit, 1),
                    "total_kg": round(total, 1),
                    "qty": q,
                    "cap_kg": round(cap, 1),
                    "indivisible": True,
                }
            )
        elif total > cap + 1e-6 and q <= 1:
            over_mats.append(
                {
                    "id": m.get("id") or m.get("part_no") or "?",
                    "unit_kg": round(unit or total, 1),
                    "total_kg": round(total, 1),
                    "qty": q,
                    "cap_kg": round(cap, 1),
                    "indivisible": True,
                }
            )

    blockers: List[str] = []
    for o in over_boxes:
        blockers.append(
            f"单箱超货载: {o['id']} net={o['net_kg']}kg > safe={o['cap_kg']}kg"
        )
    for o in over_mats:
        blockers.append(
            f"单件超货载: {o['id']} unit={o['unit_kg']}kg > safe={o['cap_kg']}kg"
        )

    ok = not over_boxes and not over_mats
    # 推荐拆箱净重上限
    rec_cap = min(3200.0, max(500.0, cap * 0.85))
    n_split_hint = 0
    if over_boxes:
        for o in over_boxes:
            n_split_hint += max(2, int(math.ceil(o["net_kg"] / rec_cap)))
    if over_mats:
        for o in over_mats:
            n_split_hint += max(2, int(math.ceil(o["unit_kg"] / rec_cap)))

    failure_class = "ok"
    if over_boxes:
        failure_class = "over_payload_box"
    elif over_mats:
        failure_class = "over_payload_material"

    return {
        "ok": ok,
        "container_type": (container_type or "40HQ").upper(),
        "payload_kg": round(payload, 1),
        "safe_cap_kg": round(cap, 1),
        "margin": margin,
        "over_payload_boxes": over_boxes,
        "over_payload_materials": over_mats,
        "blockers": blockers,
        "suggest_split": not ok,
        "max_box_net_kg_recommend": round(rec_cap, 1),
        "estimated_split_pieces": n_split_hint,
        "failure_class": failure_class,
        "tool": "cargo_feasibility.check",
    }
