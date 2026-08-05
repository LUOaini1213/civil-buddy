"""装前检查表：HITL 勾选工件（可选强制后才终态 ship_ok）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


DEFAULT_ITEMS = [
    {"id": "vgm_signed", "label": "VGM 已由托运人签署/确认", "required": True},
    {"id": "lashing_done", "label": "绑扎/气囊/木方已按工单落实", "required": True},
    {"id": "pad_beam", "label": "重件垫梁/集中载荷已处理", "required": False},
    {"id": "photo_door", "label": "柜门端/中段照片已归档", "required": False},
    {"id": "por_checked", "label": "POR 装柜单与实物一致", "required": True},
    {"id": "seal_ready", "label": "铅封/封志准备就绪", "required": False},
]


def build_pre_ship_checklist(
    state: Optional[Dict[str, Any]] = None,
    *,
    checked: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    checked = checked or {}
    items = []
    for it in DEFAULT_ITEMS:
        cid = it["id"]
        items.append(
            {
                **it,
                "checked": bool(checked.get(cid, False)),
            }
        )
    # 合并非标检验必填项
    st = state or {}
    ns = st.get("nonstandard_summary") or st.get("nonstandard_report") or {}
    ns_items = (ns.get("checklist") or {}).get("items") or []
    overall = ns.get("overall") or ""
    if ns_items or overall in ("WARN", "NEED_DESIGN", "FAIL"):
        for it in ns_items:
            cid = str(it.get("id") or "")
            if not cid:
                continue
            if any(x.get("id") == cid for x in items):
                continue
            items.append(
                {
                    "id": cid,
                    "label": it.get("label") or cid,
                    "required": bool(it.get("required")),
                    "checked": bool(checked.get(cid, False)),
                    "source": "nonstandard",
                    "auto_hint": it.get("auto_hint"),
                }
            )
    missing = [
        i["id"]
        for i in items
        if i.get("required") and not i.get("checked")
    ]
    complete = len(missing) == 0
    force = bool((state or {}).get("packing_options", {}).get("require_pre_ship_checklist"))
    return {
        "schema": "pre_ship.checklist.v1",
        "items": items,
        "missing_required": missing,
        "complete": complete,
        "require_for_final_ship_ok": force,
        "blocks_final_ship_ok": force and not complete,
        "nonstandard_overall": overall or None,
        "summary": (
            "装前检查已齐套" if complete else f"缺必填项: {', '.join(missing)}"
        ),
    }


def apply_checklist_to_ship_ok(
    ship_ok: bool, checklist: Dict[str, Any]
) -> bool:
    if checklist.get("blocks_final_ship_ok"):
        return False
    return bool(ship_ok)


def missing_ns_required(
    state: Optional[Dict[str, Any]] = None,
    *,
    checked: Optional[Dict[str, bool]] = None,
) -> List[str]:
    """返回未勾选的非标必填项 id（仅 source=nonstandard 或 id 以 ns_ 开头）。"""
    cl = build_pre_ship_checklist(state, checked=checked or {})
    miss = []
    for it in cl.get("items") or []:
        if not it.get("required") or it.get("checked"):
            continue
        cid = str(it.get("id") or "")
        if it.get("source") == "nonstandard" or cid.startswith("ns_"):
            miss.append(cid)
    return miss


def evaluate_ns_checklist_gate(
    state: Optional[Dict[str, Any]] = None,
    *,
    checked: Optional[Dict[str, bool]] = None,
    enforce: bool = False,
) -> Dict[str, Any]:
    """是否因非标勾选拦截 confirm。"""
    st = state or {}
    opts = dict(st.get("packing_options") or {})
    ns = st.get("nonstandard_summary") or st.get("nonstandard_report") or {}
    overall = str(ns.get("overall") or "")
    must = bool(
        enforce
        or opts.get("require_ns_checklist")
        or opts.get("require_pre_ship_checklist")
    )
    # 无非标关注时不拦
    if overall in ("", "PASS", "INFO") and not opts.get("require_pre_ship_checklist"):
        return {
            "enforce": must,
            "blocks": False,
            "missing": [],
            "overall": overall or None,
            "note": "无非标必填门禁",
        }
    missing = missing_ns_required(st, checked=checked) if must else []
    return {
        "enforce": must,
        "blocks": bool(must and missing),
        "missing": missing,
        "overall": overall or None,
        "note": (
            f"非标预检未齐: {', '.join(missing)}"
            if missing
            else "非标预检已齐套或未强制"
        ),
    }
