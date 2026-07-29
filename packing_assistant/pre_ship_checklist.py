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
