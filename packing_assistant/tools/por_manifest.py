"""POR / part_no 装柜单：按柜汇总料号、箱、重量（钢结构交付物）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence


def build_por_manifest(
    plan: Dict[str, Any],
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    返回:
      by_container: [{container_no, rows:[{part_no, box_id, name, weight_kg}], gross_kg}]
      by_part: [{part_no, containers, total_kg, boxes}]
      rows: 扁平明细
    """
    box_meta: Dict[str, Dict[str, Any]] = {}
    for b in boxes or []:
        bid = str(b.get("box_id") or "")
        if not bid:
            continue
        part = b.get("part_no")
        if not part:
            # content 回溯
            for c in b.get("content") or []:
                if c.get("part_no"):
                    part = c.get("part_no")
                    break
        if not part and materials:
            for m in materials:
                mid = str(m.get("id") or "")
                if mid and mid in bid:
                    part = m.get("part_no") or mid
                    break
        box_meta[bid] = {
            "part_no": str(part or "") or "—",
            "name": str(b.get("box_type") or b.get("name") or bid)[:48],
            "weight_kg": float(b.get("gross_weight_kg") or b.get("net_weight_kg") or 0),
        }

    by_c: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    layout = plan.get("layout") or []
    for it in layout:
        cno = int(it.get("container_no") or 1)
        bid = str(it.get("box_id") or "")
        meta = box_meta.get(bid) or {
            "part_no": "—",
            "name": bid,
            "weight_kg": float(it.get("gross_weight_kg") or 0),
        }
        by_c[cno].append(
            {
                "box_id": bid,
                "part_no": meta["part_no"],
                "name": meta["name"],
                "weight_kg": meta["weight_kg"],
            }
        )

    containers_out: List[Dict[str, Any]] = []
    flat: List[Dict[str, Any]] = []
    part_acc: Dict[str, Dict[str, Any]] = {}

    for cno in sorted(by_c.keys()):
        rows = by_c[cno]
        g = round(sum(r["weight_kg"] for r in rows), 1)
        containers_out.append(
            {
                "container_no": cno,
                "n_boxes": len(rows),
                "gross_kg": g,
                "rows": rows,
            }
        )
        for r in rows:
            flat.append({**r, "container_no": cno})
            pn = r["part_no"]
            acc = part_acc.setdefault(
                pn,
                {"part_no": pn, "total_kg": 0.0, "boxes": [], "containers": set()},
            )
            acc["total_kg"] += r["weight_kg"]
            acc["boxes"].append(r["box_id"])
            acc["containers"].add(cno)

    by_part = []
    for pn, acc in sorted(part_acc.items(), key=lambda x: -x[1]["total_kg"]):
        by_part.append(
            {
                "part_no": pn,
                "total_kg": round(acc["total_kg"], 1),
                "n_boxes": len(acc["boxes"]),
                "containers": sorted(acc["containers"]),
            }
        )

    return {
        "schema": "por.manifest.v1",
        "n_containers": len(containers_out),
        "n_rows": len(flat),
        "by_container": containers_out,
        "by_part": by_part[:200],
        "rows": flat[:500],
        "summary": (
            f"POR装柜单：{len(containers_out)} 柜 / {len(flat)} 箱 / "
            f"{len(by_part)} 料号"
        ),
    }
