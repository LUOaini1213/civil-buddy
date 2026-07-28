"""Agent3 装箱方案智能体。"""

from __future__ import annotations

from typing import Any, Dict, List

from packing_assistant.adapters import boxes_to_api, material_api_to_internal
from packing_assistant.state import PackingState
from packing_assistant.tools.packing import run_packing


def _crate_passthrough_enabled(materials: List[Dict[str, Any]], opts: Dict[str, Any]) -> bool:
    """
    工地当量箱直通：材料行本身已是「一箱一当量」，禁止再标准箱库二次放大外廓。
    开启方式：
      - packing_options.crate_passthrough = True
      - 或 materials 多数带 note: dims=crate_equiv_est / crate=
    """
    if opts.get("crate_passthrough") or opts.get("materials_are_crates"):
        return True
    if not materials:
        return False
    hits = 0
    for m in materials:
        note = str(m.get("note") or m.get("备注") or "")
        name = str(m.get("name") or "")
        if "crate_equiv" in note or "crate=" in note or "当量" in name or "铁件架" in name:
            hits += 1
    return hits >= max(1, int(0.5 * len(materials)))


def _fill_hint(m: Dict[str, Any]) -> float:
    name = str(m.get("name") or "")
    spec = str(m.get("spec") or "")
    if "铁件" in name or "铁件" in spec or "米铁" in name:
        return 0.28
    if "铝板" in name or "铝板" in spec:
        return 0.35
    if "瓦楞" in name or "木板" in name:
        return 0.40
    if "五金" in name or "紧固" in spec or "螺丝" in spec:
        return 0.65
    if "胶" in name or "垫" in name:
        return 0.55
    return 0.35


def materials_to_passthrough_boxes(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """一行材料 = 一箱（外廓=材料 LWH），输出 API boxes，含订柜体积字段。"""
    boxes: List[Dict[str, Any]] = []
    for i, m in enumerate(materials, 1):
        L = float(m.get("length_mm") or m.get("L") or 0)
        W = float(m.get("width_mm") or m.get("W") or 0)
        H = float(m.get("height_mm") or m.get("H") or 0)
        if L <= 0 or W <= 0 or H <= 0:
            continue
        outer = L * W * H / 1e9
        fill = _fill_hint(m)
        content = outer * fill
        net = float(m.get("total_weight_kg") or m.get("weight_kg") or 0)
        # 当量路径：材料重已含货；略加箱皮
        gross = net + 40.0
        longish = L >= 4000
        bid = str(m.get("id") or f"CRATE-{i:03d}")
        name = str(m.get("name") or bid)
        # 订柜体积与 volume_estimate 统一（按 fill_outer 选 k）
        try:
            from packing_assistant.tools.volume_estimate import pack_k_for_fill

            k_pt = pack_k_for_fill(fill, k_max=1.60)
        except Exception:
            k_pt = 1.50
        if content <= 1e-12:
            booking_m3 = outer * 0.45
        else:
            booking_m3 = min(outer, content * k_pt)
        boxes.append(
            {
                "box_id": bid if bid.startswith("CRATE") or bid.startswith("S") else f"PT-{i:03d}",
                "box_type": name.split("|")[0].strip()[:40] or "当量箱",
                "base_box_type": "crate_passthrough",
                "outer_size_mm": {
                    "length": round(L, 1),
                    "width": round(W, 1),
                    "height": round(H, 1),
                },
                "outer_m3": round(outer, 6),
                "content_m3": round(content, 6),
                "crate_fill_ratio": round(fill, 4),
                "fill_outer_ratio": round(fill, 4),
                "booking_volume_m3": round(booking_m3, 6),
                "gross_weight_kg": round(gross, 2),
                "net_weight_kg": round(net, 2),
                "stackable": bool(H <= 1200 and not longish),
                "prefer_bottom": bool(longish or "铁" in name or net >= 800),
                "special_attributes": (["超长", "当量直通"] if longish else ["当量直通"]),
                "structure_conclusion": "通过",
                "content": [
                    {
                        "material_id": str(m.get("id") or ""),
                        "name": name,
                        "quantity": 1,
                        "outer_size_mm": {
                            "length": max(1, int(L * 0.9)),
                            "width": max(1, int(W * 0.7)),
                            "height": max(1, int(H * fill / 0.7)) if fill > 0 else max(1, int(H // 3)),
                        },
                    }
                ],
                "part_no": m.get("part_no"),
                "note": m.get("note"),
            }
        )
    # 保证 box_id 唯一
    seen = set()
    for i, b in enumerate(boxes):
        if b["box_id"] in seen:
            b["box_id"] = f"{b['box_id']}-{i}"
        seen.add(b["box_id"])
    return boxes


def agent_box_scheme(state: PackingState) -> Dict[str, Any]:
    materials = state.get("materials") or []
    constraints = state.get("structure_constraints") or []
    rev = state.get("revision") or {}
    packing_opts = state.get("packing_options") or {}

    ctype = (
        state.get("container_type")
        or (state.get("orchestrator") or {}).get("container_type_chosen")
        or "40HQ"
    )
    max_L = max((float(m.get("length_mm") or 0) for m in materials), default=0)
    total_w = sum(float(m.get("total_weight_kg") or 0) for m in materials)
    if str(ctype).upper() == "20GP" and (max_L >= 4000 or total_w >= 8000):
        ctype = "40HQ"

    # —— 当量箱直通：不二次标准箱合箱 ——
    if _crate_passthrough_enabled(materials, packing_opts):
        boxes = materials_to_passthrough_boxes(materials)
        outer_sum = sum(float(b.get("outer_m3") or 0) for b in boxes)
        content_sum = sum(float(b.get("content_m3") or 0) for b in boxes)
        fills = [float(b.get("crate_fill_ratio") or 0) for b in boxes]
        avg_fill = sum(fills) / len(fills) if fills else 0.0
        summary = {
            "pass": len(boxes),
            "reinforce": 0,
            "fail": 0,
            "crate_passthrough": True,
            "standard_boxes": False,
            "mix_mode": False,
            "boxes_outer_volume_m3": round(outer_sum, 4),
            "cargo_item_volume_m3": round(content_sum, 4),
            "avg_crate_fill": round(avg_fill, 4),
            "packing_mode": "crate_passthrough",
        }
        return {
            "boxes": boxes,
            "team_a_summary": {
                **summary,
                "structure_overall": "通过(当量直通)",
                "total_net_weight_kg": round(sum(float(b.get("net_weight_kg") or 0) for b in boxes), 1),
                "total_gross_weight_kg": round(
                    sum(float(b.get("gross_weight_kg") or 0) for b in boxes), 1
                ),
            },
            "structure_notes": [
                "当量箱直通：材料行=箱外廓，未再走标准箱库合箱（避免外廓虚高）"
            ],
            "agent_meta": {
                "node": "box_scheme",
                "capability": ["使用工具", "采取行动"],
                "tools_used": ["box_scheme.materials_to_passthrough_boxes"],
                "artifacts": {"boxes": len(boxes), "mode": "crate_passthrough"},
            },
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"装箱完成：{len(boxes)} 箱 — 当量直通（crate_passthrough）"
                        f" 外廓{outer_sum:.2f}m³/有效内容{content_sum:.2f}m³ 填充均{avg_fill:.0%}"
                        f"｜tools=passthrough（已生成 boxes[]，非口头建议）"
                    ),
                }
            ],
        }

    internal = [material_api_to_internal(m) for m in materials]
    # 把 material id 写入内部便于 content 回填
    for src, dst in zip(materials, internal):
        dst["加工件编号"] = src.get("id") or ""
        dst["id"] = src.get("id") or ""

    max_net = float(
        rev.get("max_box_net_kg")
        or packing_opts.get("max_box_net_kg")
        or 3200.0
    )
    revision_mode = bool(rev.get("active") or packing_opts.get("revision_mode"))
    # 默认：标准箱库外廓 + 跨长度档混装（短件塞进长标准箱）
    # dense_mode 仅在明确关闭 standard 时生效
    standard_boxes = packing_opts.get("standard_boxes")
    if standard_boxes is None:
        standard_boxes = packing_opts.get("standard_outer")
    if standard_boxes is None:
        standard_boxes = True  # 默认标准化
    standard_boxes = bool(standard_boxes)
    mix_mode = packing_opts.get("mix_mode")
    if mix_mode is None:
        mix_mode = True
    mix_mode = bool(mix_mode)
    dense_mode = bool(
        packing_opts.get("dense_mode")
        or packing_opts.get("dense")
        or rev.get("dense_mode")
    )
    if standard_boxes:
        dense_mode = False
    design_facts = state.get("design_facts") or packing_opts.get("design_facts")
    # 自然语言强制箱型写入 defaults
    if packing_opts.get("force_box_type"):
        design_facts = dict(design_facts or {})
        design_facts.setdefault("defaults", {})
        design_facts["defaults"]["force_box_type"] = packing_opts["force_box_type"]
    result = run_packing(
        internal,
        container_type=str(ctype),
        max_box_net_kg=max_net,
        revision_mode=revision_mode,
        dense_mode=dense_mode,
        standard_boxes=standard_boxes,
        mix_mode=mix_mode,
        design_facts=design_facts if isinstance(design_facts, dict) else None,
    )
    boxes_raw = result.get("箱子列表") or []
    boxes = boxes_to_api(boxes_raw)

    # 用约束补充加固文案
    reinforce_types = {
        c.get("recommended_box_type"): c
        for c in constraints
        if c.get("need_reinforcement")
    }
    for b in boxes:
        c = reinforce_types.get(b.get("box_type"))
        if c and c.get("reinforcement_plan"):
            b["reinforcement"] = c["reinforcement_plan"]
            attrs = list(b.get("special_attributes") or [])
            if "需加固" not in attrs:
                attrs.append("需加固")
            b["special_attributes"] = attrs

        # content material_id 回填
        for item in b.get("content") or []:
            if not item.get("material_id"):
                # 按名称匹配
                for m in materials:
                    if m.get("name") == item.get("name"):
                        item["material_id"] = m.get("id") or ""
                        break

    summary = result.get("结构汇总") or {}
    note_parts = []
    if standard_boxes or summary.get("standard_boxes"):
        counts = summary.get("standard_box_type_counts") or {}
        count_s = ",".join(f"{k}×{v}" for k, v in list(counts.items())[:6])
        note_parts.append(
            f"标准箱库{'+混装' if mix_mode else ''} "
            f"外廓{summary.get('boxes_outer_volume_m3', '?')}m³/"
            f"货{summary.get('cargo_item_volume_m3', '?')}m³ "
            f"填充均{float(summary.get('avg_crate_fill') or 0):.0%}"
            + (f" [{count_s}]" if count_s else "")
        )
    elif dense_mode or summary.get("dense_mode"):
        note_parts.append(
            f"密装外廓 dense "
            f"箱外廓{summary.get('boxes_outer_volume_m3', '?')}m³/"
            f"货件{summary.get('cargo_item_volume_m3', '?')}m³ "
            f"箱内填充均{float(summary.get('avg_crate_fill') or 0):.0%}"
        )
    if revision_mode or summary.get("revision_mode"):
        note_parts.append(
            f"改箱 max_net={max_net:.0f}kg 拆分后料行={summary.get('item_chunks_after_split', '?')}"
        )
    note = f"（{'；'.join(note_parts)}）" if note_parts else ""
    return {
        "boxes": boxes,
        "agent_meta": {
            "node": "box_scheme",
            "capability": ["使用工具", "采取行动"],
            "tools_used": ["packing.run_packing"],
            "artifacts": {
                "boxes": len(boxes),
                "mode": summary.get("packing_mode") or "standard",
            },
        },
        "team_a_summary": {
            "box_count": len(boxes),
            "pass": summary.get("通过", 0),
            "reinforce": summary.get("需加强", 0),
            "fail": summary.get("不通过", 0),
            "total_net_weight_kg": summary.get("总净重_kg", 0),
            "total_gross_weight_kg": summary.get("总毛重_kg", 0),
            "structure_overall": summary.get("结论", ""),
            "max_box_net_kg": summary.get("max_box_net_kg", max_net),
            "revision_mode": bool(revision_mode or summary.get("revision_mode")),
            "dense_mode": bool(dense_mode or summary.get("dense_mode")),
            "standard_boxes": bool(standard_boxes or summary.get("standard_boxes")),
            "mix_mode": bool(mix_mode if mix_mode is not None else summary.get("mix_mode")),
            "packing_mode": summary.get("packing_mode") or "",
            "boxes_outer_volume_m3": summary.get("boxes_outer_volume_m3"),
            "cargo_item_volume_m3": summary.get("cargo_item_volume_m3"),
            "avg_crate_fill": summary.get("avg_crate_fill"),
            "standard_box_type_counts": summary.get("standard_box_type_counts"),
        },
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"装箱完成：{len(boxes)} 箱 — {summary.get('结论', '')}{note}"
                    f"｜tools=packing.run_packing（已生成 boxes[]，属行动非建议）"
                ),
            }
        ],
    }
