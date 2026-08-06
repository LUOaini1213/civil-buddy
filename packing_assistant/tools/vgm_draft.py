"""VGM Method 2 草稿：货重+包装估算+皮重；必须人工签字，禁止自动申报。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

# 常见柜型皮重近似 kg（草稿用，出运以箱门铭牌为准）
TARE_KG = {
    "20GP": 2200.0,
    "40GP": 3800.0,
    "40HQ": 3900.0,
    "45HQ": 4800.0,
}

# 装前检查表必填项 id（与 pre_ship_checklist.DEFAULT_ITEMS 对齐）
VGM_CHECKLIST_ITEM_ID = "vgm_signed"
VGM_CHECKLIST_LABEL = "VGM 已由托运人签署/确认"


def draft_vgm_method2(
    plan: Dict[str, Any],
    boxes: Sequence[Dict[str, Any]],
    *,
    packaging_factor: float = 0.02,
    dunnage_kg_per_container: float = 80.0,
) -> Dict[str, Any]:
    """
    Method 2: 逐件货重累加 + 包装/垫料估算 + 集装箱皮重。
    返回 draft，status=needs_shipper_signature。
    """
    ctype = str(plan.get("container_type") or "40HQ")
    tare = float(TARE_KG.get(ctype, 3900.0))
    n = max(1, int(plan.get("containers_used") or 1))

    cargo = 0.0
    lines: List[Dict[str, Any]] = []
    for b in boxes:
        w = float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0)
        cargo += w
        lines.append(
            {
                "box_id": b.get("box_id"),
                "gross_weight_kg": w,
            }
        )

    packaging = cargo * float(packaging_factor)
    dunnage = dunnage_kg_per_container * n
    # 均分到各柜的 VGM（草稿：总货均摊 + 单柜皮重）
    cargo_per = cargo / n
    pack_per = packaging / n
    dunnage_per = dunnage_kg_per_container
    vgm_per = cargo_per + pack_per + dunnage_per + tare

    containers = []
    for i in range(1, n + 1):
        containers.append(
            {
                "container_no": i,
                "container_type": ctype,
                "cargo_kg": round(cargo_per, 1),
                "packaging_kg": round(pack_per, 1),
                "dunnage_kg": round(dunnage_per, 1),
                "tare_kg": tare,
                "vgm_kg": round(vgm_per, 1),
                "note": "均摊草稿，正式须按实装重分柜",
            }
        )

    return {
        "method": 2,
        "status": "needs_shipper_signature",
        "auto_submit_forbidden": True,
        "human_signoff_required": True,
        "container_type": ctype,
        "containers_used": n,
        "totals": {
            "cargo_kg": round(cargo, 1),
            "packaging_kg": round(packaging, 1),
            "dunnage_kg": round(dunnage, 1),
            "tare_kg_total": round(tare * n, 1),
            "vgm_sum_kg": round(vgm_per * n, 1),
        },
        # 双写：历史读 containers；草稿生成写 per_container
        "per_container": containers,
        "containers": containers,
        "disclaimer": (
            "SOLAS VGM 草稿仅供内部核对；提交承运人前必须托运人授权签字，"
            "皮重以箱门铭牌为准，包装/垫料系数可配置。"
        ),
        "box_lines_n": len(lines),
        "signoff": {
            "required": True,
            "signed": False,
            "checklist_item_id": VGM_CHECKLIST_ITEM_ID,
            "label": VGM_CHECKLIST_LABEL,
        },
    }


def _sync_vgm_checklist_flags(st: Dict[str, Any], *, checked: bool) -> None:
    """双写 checklist_checked 与 pre_ship_checked（UI/finalize 用后者）。"""
    for key in ("checklist_checked", "pre_ship_checked"):
        cur = st.get(key)
        d = dict(cur) if isinstance(cur, dict) else {}
        d[VGM_CHECKLIST_ITEM_ID] = bool(checked)
        st[key] = d


def is_vgm_signed(state: Optional[Dict[str, Any]] = None) -> bool:
    """人签是否成立：vgm_signoff 或任一侧装前勾选 vgm_signed。"""
    st = state or {}
    so = st.get("vgm_signoff")
    if not isinstance(so, dict):
        vgm = st.get("vgm_draft") if isinstance(st.get("vgm_draft"), dict) else {}
        so = (vgm or {}).get("signoff") or {}
    if isinstance(so, dict) and so.get("signed"):
        return True
    for key in ("checklist_checked", "pre_ship_checked"):
        c = st.get(key)
        if isinstance(c, dict) and c.get(VGM_CHECKLIST_ITEM_ID):
            return True
    return False


def record_human_signoff(
    state: Dict[str, Any],
    *,
    signer: str,
    acknowledged: bool = True,
    note: str = "",
) -> Dict[str, Any]:
    """
    记录托运人/授权人 VGM 人签（本地状态，不向船司提交）。

    写入 state['vgm_signoff']，并在存在 vgm_draft 时同步 status=signed_local。
    acknowledged=False 则清除签署（回到待签），并清两侧 checklist 勾选。
    """
    st = dict(state or {})
    now = datetime.now(timezone.utc).isoformat()
    if not acknowledged:
        signoff = {
            "signed": False,
            "signer": "",
            "signed_at": None,
            "checklist_item_id": VGM_CHECKLIST_ITEM_ID,
            "label": VGM_CHECKLIST_LABEL,
            "note": note or "已撤销本地人签",
            "auto_submit_forbidden": True,
        }
        st["vgm_signoff"] = signoff
        draft = dict(st.get("vgm_draft") or {})
        if draft:
            draft["status"] = "needs_shipper_signature"
            draft["signoff"] = {**signoff, "required": True}
            st["vgm_draft"] = draft
        # 撤销必须清两侧勾选，否则仍被当作已签
        _sync_vgm_checklist_flags(st, checked=False)
        return st

    who = (signer or "").strip() or "shipper"
    signoff = {
        "signed": True,
        "signer": who,
        "signed_at": now,
        "checklist_item_id": VGM_CHECKLIST_ITEM_ID,
        "label": VGM_CHECKLIST_LABEL,
        "note": note
        or "本地人签已记录；仍禁止自动向船司/码头申报，正式提交须承运人通道。",
        "auto_submit_forbidden": True,
        "carrier_submit": "not_configured",
    }
    st["vgm_signoff"] = signoff
    draft = dict(st.get("vgm_draft") or {})
    if draft:
        draft["status"] = "signed_local"
        draft["signoff"] = {**signoff, "required": True}
        st["vgm_draft"] = draft
    # 同步装前检查两侧（finalize/gateway 读 pre_ship_checked）
    _sync_vgm_checklist_flags(st, checked=True)
    return st


def container_rows(vgm: Dict[str, Any]) -> List[Dict[str, Any]]:
    """兼容 per_container / containers 双键。"""
    if not isinstance(vgm, dict):
        return []
    rows = vgm.get("per_container") or vgm.get("containers") or []
    return list(rows) if isinstance(rows, list) else []


def build_vgm_status_public(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    对外 VGM 状态面：草稿 + 人签可见字段（供 public_response / UI）。

    超越单纯 status 字符串：带 checklist 绑定、pending_action、ui_visible。
    """
    st = state or {}
    vgm = st.get("vgm_draft") or {}
    if not isinstance(vgm, dict):
        vgm = {}
    so = st.get("vgm_signoff") or vgm.get("signoff") or {}
    if not isinstance(so, dict):
        so = {}

    signed = is_vgm_signed(st)
    status = str(vgm.get("status") or "")
    if signed and status in ("", "draft", "needs_shipper_signature"):
        status = "signed_local"
    if not status and not vgm and not signed:
        status = "not_drafted"
    # 撤销后 draft 可能仍残留 signed_local 字符串，以 signed 为准
    if not signed and status == "signed_local":
        status = "needs_shipper_signature" if vgm else "not_drafted"

    rows = container_rows(vgm)
    method = vgm.get("method") or "method2"
    if method == 2:
        method = "method2"

    pending = (
        None
        if signed
        else (
            "勾选装前检查「VGM 已由托运人签署/确认」或调用 record_human_signoff"
            if vgm
            else "先完成拼柜生成 VGM 草稿，再由托运人签署"
        )
    )

    human = {
        "required": True,
        "signed": signed,
        "signer": (so.get("signer") or "") if signed else "",
        "signed_at": so.get("signed_at") if signed else None,
        "checklist_item_id": VGM_CHECKLIST_ITEM_ID,
        "label": VGM_CHECKLIST_LABEL,
        "pending_action": pending,
        "ui_visible": True,
        "blocks_auto_submit": True,
        "carrier_submit": "not_configured",
    }

    note = (
        f"VGM 本地人签完成（{human.get('signer') or 'shipper'}）；仍禁止自动申报。"
        if signed
        else (
            f"VGM 状态={status}；须托运人签署（检查项 {VGM_CHECKLIST_ITEM_ID}），禁止自动申报。"
            if status != "not_drafted"
            else "VGM 尚未生成草稿；出运前须方法2草稿 + 托运人签署（系统禁止自动申报）。"
        )
    )

    return {
        "status": status or "not_drafted",
        "human_signoff_required": True,
        "human_signoff": human,
        "auto_submit_forbidden": True,
        "method": method,
        "totals": vgm.get("totals") or {},
        "n_containers": len(rows) or int(vgm.get("containers_used") or 0) or 0,
        "disclaimer": vgm.get("disclaimer")
        or "VGM 草稿不可自动向船司/码头申报，须人签。",
        "note": note,
        "checklist_item_id": VGM_CHECKLIST_ITEM_ID,
        "ui_label": (
            f"VGM 已签 · {human.get('signer') or 'local'}"
            if signed
            else f"VGM {status or 'not_drafted'} · 须人签"
        ),
    }
