"""VGM Method 2 草稿：货重+包装估算+皮重；必须人工签字，禁止自动申报。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# 常见柜型皮重近似 kg（草稿用，出运以箱门铭牌为准）
TARE_KG = {
    "20GP": 2200.0,
    "40GP": 3800.0,
    "40HQ": 3900.0,
    "45HQ": 4800.0,
}


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
        "container_type": ctype,
        "containers_used": n,
        "totals": {
            "cargo_kg": round(cargo, 1),
            "packaging_kg": round(packaging, 1),
            "dunnage_kg": round(dunnage, 1),
            "tare_kg_total": round(tare * n, 1),
            "vgm_sum_kg": round(vgm_per * n, 1),
        },
        "per_container": containers,
        "disclaimer": (
            "SOLAS VGM 草稿仅供内部核对；提交承运人前必须托运人授权签字，"
            "皮重以箱门铭牌为准，包装/垫料系数可配置。"
        ),
        "box_lines_n": len(lines),
    }
