"""Fold packing-list pieces into named factory racks, then pack racks.

Factory tickets title a sheet 「1.1米铁架1号 / 2米铁架1号」: all lines on
that list go into that rack *type*, split only by rack payload — not one
AABB per steel tube.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_TITLE_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"1\s*\.?\s*1\s*米\s*(铁架|框)"), "1.1米铁架"),
    (re.compile(r"2\s*米\s*(铁架|框)"), "2米铁架"),
    (re.compile(r"4\s*米\s*(铁架|框)"), "4米铁架"),
    (re.compile(r"6\s*米\s*(铁架|框)"), "6米铁架"),
)


def detect_rack_type(text: str) -> Optional[str]:
    blob = str(text or "")
    for pat, name in _TITLE_PATTERNS:
        if pat.search(blob):
            return name
    return None


def _piece_weight(m: Dict[str, Any]) -> float:
    q = max(int(m.get("quantity") or m.get("qty") or 1), 1)
    total = float(m.get("total_weight_kg") or 0)
    if total > 0:
        return total
    unit = float(m.get("weight_kg") or 0)
    return unit * q


def _complete_lwh(m: Dict[str, Any]) -> bool:
    return (
        float(m.get("length_mm") or 0) > 0
        and float(m.get("width_mm") or 0) > 0
        and float(m.get("height_mm") or 0) > 0
    )


def _rack_spec(rack_type: str) -> Dict[str, Any]:
    from packing_assistant.knowledge import get_box_spec

    spec = get_box_spec(rack_type) or {}
    outer = spec.get("outer_mm") or spec.get("外尺寸_mm") or {}
    if not outer and spec.get("length"):
        outer = {
            "length": spec.get("length"),
            "width": spec.get("width"),
            "height": spec.get("height"),
        }
    L = float(outer.get("length") or outer.get("长") or 1100)
    W = float(outer.get("width") or outer.get("宽") or 1100)
    H = float(outer.get("height") or outer.get("高") or 1500)
    payload = float(spec.get("max_payload_kg") or spec.get("最大载荷_kg") or 1200)
    tare = float(spec.get("tare_kg") or spec.get("自重_kg") or 90)
    key = str(spec.get("_key") or rack_type)
    return {
        "key": key,
        "label": rack_type,
        "L": L,
        "W": W,
        "H": H,
        "payload_kg": payload,
        "tare_kg": tare,
        "outer_m3": round(L * W * H / 1e9, 4),
    }


def _seal_rack(
    pieces: List[Dict[str, Any]],
    spec: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    net = round(sum(_piece_weight(p) for p in pieces), 3)
    ids = [str(p.get("id") or "") for p in pieces if p.get("id")]
    content_m3 = 0.0
    for p in pieces:
        q = max(int(p.get("quantity") or 1), 1)
        content_m3 += (
            float(p.get("length_mm") or 0)
            * float(p.get("width_mm") or 0)
            * float(p.get("height_mm") or 0)
            * q
            / 1e9
        )
    fill = min(content_m3 / spec["outer_m3"], 1.5) if spec["outer_m3"] else 0.0
    return {
        "box_id": f"RACK-{spec['label']}-{index:02d}",
        "box_type": spec["label"],
        "base_box_type": spec["key"],
        "outer_size_mm": {
            "length": spec["L"],
            "width": spec["W"],
            "height": spec["H"],
        },
        "outer_m3": spec["outer_m3"],
        "content_m3": round(content_m3, 4),
        "crate_fill_ratio": round(fill, 4),
        "net_weight_kg": net,
        "gross_weight_kg": round(net + spec["tare_kg"], 3),
        "tare_kg": spec["tare_kg"],
        "stackable": True,
        "no_tip": True,
        "prefer_bottom": net >= 2000 or spec["L"] >= 4000,
        "content_ids": ids,
        "content_lines": len(pieces),
        "packing_list_rack": True,
    }


def fold_group_into_racks(
    materials: Sequence[Dict[str, Any]],
    rack_type: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split one titled packing-list group into payload-sized racks."""
    spec = _rack_spec(rack_type)
    complete = [m for m in materials if _complete_lwh(m)]
    skipped = [m for m in materials if not _complete_lwh(m)]
    # Heavier first → fewer leftover-slack racks (closer to payload lower bound).
    complete = sorted(complete, key=_piece_weight, reverse=True)
    bins: List[List[Dict[str, Any]]] = []
    bin_w: List[float] = []
    for m in complete:
        w = _piece_weight(m)
        placed = False
        for i, rw in enumerate(bin_w):
            if rw + w <= spec["payload_kg"] + 1e-6:
                bins[i].append(m)
                bin_w[i] += w
                placed = True
                break
        if not placed:
            bins.append([m])
            bin_w.append(w)
    racks = [_seal_rack(pieces, spec, i + 1) for i, pieces in enumerate(bins)]
    return racks, skipped


def groups_from_options(
    materials: Sequence[Dict[str, Any]],
    packing_options: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Build (rack_type, materials) from options or per-row stamps."""
    opts = dict(packing_options or {})
    declared = opts.get("packing_list_racks") or opts.get("rack_groups") or []
    by_id = {str(m.get("id") or ""): m for m in materials}
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    used: set[str] = set()
    if declared:
        for g in declared:
            if not isinstance(g, dict):
                continue
            rtype = detect_rack_type(str(g.get("rack_type") or g.get("title") or "")) or str(
                g.get("rack_type") or ""
            )
            ids = [str(x) for x in (g.get("material_ids") or [])]
            chunk = [by_id[i] for i in ids if i in by_id]
            if not rtype:
                rtype = detect_rack_type(" ".join(str(m.get("name") or "") for m in chunk)) or ""
            if chunk and rtype:
                groups.append((rtype, chunk))
                used.update(str(m.get("id") or "") for m in chunk)
    leftover: List[Dict[str, Any]] = []
    stamped: Dict[str, List[Dict[str, Any]]] = {}
    for m in materials:
        mid = str(m.get("id") or "")
        if mid in used:
            continue
        stamp = (
            m.get("packing_list_rack")
            or (m.get("meta") or {}).get("packing_list_rack")
            or detect_rack_type(str(m.get("packing_list_title") or ""))
        )
        if stamp:
            key = detect_rack_type(str(stamp)) or str(stamp)
            stamped.setdefault(key, []).append(m)
        else:
            leftover.append(m)
    for rtype, chunk in stamped.items():
        groups.append((rtype, chunk))
    if leftover and not groups:
        return []
    if leftover and groups:
        # unstamped remainder stays out of fold (caller may passthrough)
        groups.append(("", leftover))
    return groups


def fold_packing_list_racks(
    materials: Sequence[Dict[str, Any]],
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    groups = groups_from_options(materials, packing_options)
    if not groups:
        return {"ok": False, "boxes": [], "reason": "no_packing_list_rack_groups"}
    boxes: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    notes: List[str] = []
    for rtype, chunk in groups:
        if not rtype:
            notes.append(f"ungrouped leftover lines={len(chunk)} (not folded)")
            continue
        racks, skip = fold_group_into_racks(chunk, rtype)
        boxes.extend(racks)
        skipped.extend(skip)
        notes.append(
            f"{rtype}: {len(chunk)} lines → {len(racks)} racks "
            f"(dropped_incomplete={len(skip)})"
        )
    return {
        "ok": bool(boxes),
        "boxes": boxes,
        "skipped_incomplete": skipped,
        "notes": notes,
        "mode": "packing_list_racks",
    }
