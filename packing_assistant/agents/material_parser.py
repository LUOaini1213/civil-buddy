"""Agent1 材料解析智能体。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from packing_assistant.adapters import classify_material, material_internal_to_api
from packing_assistant.state import PackingState


def agent_material_parser(state: PackingState) -> Dict[str, Any]:
    raw = (state.get("user_input") or state.get("raw_input") or "").strip()  # type: ignore[arg-type]
    existing = state.get("materials") or []

    # 调整指令且已有材料：保留
    note = state.get("adjust_note") or ""
    if existing and note and _is_adjust_only(note) and _has_metrics_api(existing):
        summary = _summary(existing)
        perception = _build_perception(existing, summary, source="retain", note=note)
        return {
            "materials": existing,
            "materials_summary": {**summary, "categories": perception.get("categories")},
            "perception": perception,
            "agent_meta": {
                "node": "material_parser",
                "capability": ["感知环境"],
                "tools_used": ["material_parser.retain"],
                "artifacts": {"total_pieces": summary.get("total_pieces")},
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"【感知】保留材料 {len(existing)} 条，应用调整指令。"
                        f" {perception.get('summary_text')}"
                    ),
                }
            ],
        }

    llm_note = ""
    incomplete_dims = False
    # 显式注入的材料：永远优先保留，禁止缺字段时静默换成 demo 票
    if existing and not _looks_like_list(raw):
        mats = _normalize_llm_materials(list(existing))
        if not mats:
            mats = list(existing)
        source = "inject" if _has_metrics_api(mats) else "inject_partial"
        incomplete_dims = _has_incomplete_dims(mats)
    else:
        mats = _rule_parse(raw)
        source = "rule"
        # DeepSeek 等 LLM 增强结构化（仅当像材料清单时）
        if raw and _looks_like_list(raw):
            from packing_assistant.llm import chat_json_array, llm_available

            if llm_available():
                llm_mats = chat_json_array(
                    system=(
                        "你是钢结构装箱材料解析助手。从用户输入提取材料清单，"
                        "只输出 JSON 数组，每项字段："
                        "id,name,spec,length_mm,width_mm,height_mm,weight_kg,quantity,total_weight_kg,category。"
                        "category 只能是：超长件|重件|普通件。"
                        "length_mm>=4000 为超长件；单重>=200 为重件。"
                        "数字无法确定填 0。不要输出其它文字。"
                    ),
                    user=raw,
                )
                if llm_mats:
                    mats = _normalize_llm_materials(llm_mats)
                    source = "llm"
                    llm_note = f" LLM解析{len(mats)}条"
        # 仅「无注入且解析为空」时用 demo；有注入残缺则保留残缺
        if not mats or not _has_metrics_api(mats):
            if existing:
                mats = _normalize_llm_materials(list(existing)) or list(existing)
                source = "inject_partial"
                incomplete_dims = True
            else:
                mats = _demo_materials()
                source = "demo"
        incomplete_dims = incomplete_dims or _has_incomplete_dims(mats)

    # 应用简单「去掉 xxx」
    if note and ("去掉" in note or "删除" in note):
        mats = _filter_remove(mats, note)

    summary = _summary(mats)
    perception = _build_perception(mats, summary, source=source, note=note)
    summary = {**summary, **{k: perception[k] for k in (
        "categories", "filter_rules", "container_assumption", "longest_mm", "heaviest_unit_kg"
    ) if k in perception}}
    tools_used = ["material_parser.rule_parse" if source == "rule" else f"material_parser.{source}"]
    if source == "llm":
        tools_used.append("llm.chat_json_array")
    warn_bits = []
    if incomplete_dims:
        warn_bits.append("缺尺寸(L/W/H=0)不可默成出运")
    if source == "inject_partial":
        warn_bits.append("注入材料字段不完整")
    msg = (
        f"【感知】材料摘要({source}{llm_note})："
        f"{summary.get('total_pieces')} 件 / {summary.get('total_weight_kg')} kg / "
        f"{summary.get('material_line_count')} 行；"
        f"分类 {perception.get('categories')}；"
        f"过滤={perception.get('filter_rules')}；"
        f"柜型假设={perception.get('container_assumption')}；"
        f"最长={perception.get('longest_mm')}mm 最重单件={perception.get('heaviest_unit_kg')}kg"
        f"{('；警告=' + ';'.join(warn_bits)) if warn_bits else ''}"
        f"｜tools={','.join(tools_used)}"
    )
    out: Dict[str, Any] = {
        "materials": mats,
        "materials_summary": summary,
        "perception": perception,
        "phase": "team_a_running",
        "materials_incomplete": bool(incomplete_dims),
        "agent_meta": {
            "node": "material_parser",
            "capability": ["感知环境"],
            "tools_used": tools_used,
            "artifacts": {
                "total_pieces": summary.get("total_pieces"),
                "total_weight_kg": summary.get("total_weight_kg"),
                "source": source,
                "incomplete_dims": bool(incomplete_dims),
            },
        },
        "messages": [{"role": "assistant", "content": msg}],
    }
    if incomplete_dims:
        errs = list(state.get("errors") or [])  # type: ignore[arg-type]
        errs.append("materials_missing_dims: 存在 L/W/H 为 0 的物料，禁止当完整方案出运")
        out["errors"] = errs
        out["warnings"] = list(state.get("warnings") or []) + [  # type: ignore[arg-type]
            "缺尺寸物料：需补尺寸或剔除后再成箱"
        ]
        # 硬信号：不可 ship
        out["ship_ok"] = False
    return out


def _normalize_llm_materials(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(items, 1):
        if not isinstance(m, dict):
            continue
        qty = int(float(m.get("quantity") or m.get("数量") or 1))
        unit = float(m.get("weight_kg") or m.get("单重_kg") or 0)
        total = float(m.get("total_weight_kg") or unit * qty)
        L = float(m.get("length_mm") or (m.get("外尺寸_mm") or {}).get("长") or 0)
        W = float(m.get("width_mm") or (m.get("外尺寸_mm") or {}).get("宽") or 0)
        H = float(m.get("height_mm") or (m.get("外尺寸_mm") or {}).get("高") or 0)
        name = str(m.get("name") or m.get("名称") or f"材料-{i}")
        text_blob = " ".join(
            str(x)
            for x in (name, m.get("spec"), m.get("规格"), m.get("note"), m.get("备注"))
            if x
        )
        cat = str(m.get("category") or classify_material(L, unit, total, height_mm=H, width_mm=W, text=text_blob))
        try:
            from packing_assistant.knowledge import MATERIAL_CATEGORIES

            allowed = set(MATERIAL_CATEGORIES)
        except Exception:
            allowed = {"超长件", "重件", "薄板", "异形件", "精密件", "工厂架", "普通件"}
        if cat not in allowed:
            cat = classify_material(L, unit, total, height_mm=H, width_mm=W, text=text_blob)
        row = {
            "id": str(m.get("id") or f"M{i:03d}"),
            "name": name,
            "spec": str(m.get("spec") or m.get("规格") or name),
            "length_mm": L,
            "width_mm": W,
            "height_mm": H,
            "weight_kg": unit,
            "quantity": max(qty, 1),
            "total_weight_kg": round(total, 3),
            "category": cat,
        }
        # 可选透传字段（非标检验 / HITL）
        for k in (
            "note",
            "备注",
            "dims_source",
            "orientation",
            "lift_points",
            "stackable",
            "fragile",
            "this_side_up",
            "no_stack",
            "envelope_mm",
            "ns_tags",
            "hazard_class",
            "enrich_source",
        ):
            if m.get(k) is not None:
                row[k] = m.get(k)
        out.append(row)
    return out


def _is_adjust_only(text: str) -> bool:
    return any(k in text for k in ("去掉", "删除", "不要", "单独", "合箱", "改"))


def _looks_like_list(text: str) -> bool:
    t = (text or "").strip()
    if t.startswith("["):
        return True
    if re.search(r"\d+\s*(件|个|根|套|kg)", t, re.I):
        return True
    if re.search(r"\d+[x×]\d+", t):
        return True
    return False


def _has_metrics_api(materials: List[Dict[str, Any]]) -> bool:
    for m in materials:
        if float(m.get("weight_kg") or m.get("单重_kg") or 0) > 0:
            return True
        if float(m.get("length_mm") or (m.get("外尺寸_mm") or {}).get("长") or 0) > 0:
            return True
    return False


def _has_incomplete_dims(materials: List[Dict[str, Any]]) -> bool:
    """任一行缺有效三维 → 不可当完整装箱输入。"""
    if not materials:
        return False
    for m in materials:
        L = float(m.get("length_mm") or (m.get("外尺寸_mm") or {}).get("长") or 0)
        W = float(m.get("width_mm") or (m.get("外尺寸_mm") or {}).get("宽") or 0)
        H = float(m.get("height_mm") or (m.get("外尺寸_mm") or {}).get("高") or 0)
        if L <= 1e-6 or W <= 1e-6 or H <= 1e-6:
            return True
    return False


def _summary(materials: List[Dict[str, Any]]) -> Dict[str, Any]:
    pieces = 0
    weight = 0.0
    for m in materials:
        q = int(m.get("quantity") or m.get("数量") or 1)
        pieces += q
        weight += float(m.get("total_weight_kg") or m.get("总重_kg") or float(m.get("weight_kg") or 0) * q)
    return {
        "total_pieces": pieces,
        "total_weight_kg": round(weight, 2),
        "material_line_count": len(materials),
    }


def _build_perception(
    materials: List[Dict[str, Any]],
    summary: Dict[str, Any],
    *,
    source: str,
    note: str = "",
) -> Dict[str, Any]:
    """跑前状态摘要：件数、总重、分类、过滤规则、柜型假设。"""
    cats: Dict[str, int] = {}
    longest = 0.0
    heaviest = 0.0
    for m in materials:
        cat = str(m.get("category") or "普通件")
        q = int(m.get("quantity") or m.get("数量") or 1)
        cats[cat] = cats.get(cat, 0) + q
        L = float(m.get("length_mm") or (m.get("外尺寸_mm") or {}).get("长") or 0)
        unit = float(m.get("weight_kg") or m.get("单重_kg") or 0)
        longest = max(longest, L)
        heaviest = max(heaviest, unit)
    filter_rules = [
        "length_mm>=4000 → 超长件",
        "单重>=200kg → 重件",
        "其余 → 普通件",
    ]
    if note and ("去掉" in note or "删除" in note):
        filter_rules.append(f"调整指令过滤: {note[:80]}")
    # 柜型假设：超长倾向 40HQ/45；重货注意 PAYLOAD
    if longest >= 12000:
        ctn_assume = "45HQ 或开顶/框架柜（超长>12m 需复核）"
    elif longest >= 5800 or heaviest >= 200:
        ctn_assume = "40HQ（默认；超长/重件需底层与绑扎）"
    else:
        ctn_assume = "40HQ 或 40GP（主控将按重量/体积再推荐）"
    return {
        "total_pieces": summary.get("total_pieces"),
        "total_weight_kg": summary.get("total_weight_kg"),
        "material_line_count": summary.get("material_line_count"),
        "categories": cats,
        "filter_rules": filter_rules,
        "container_assumption": ctn_assume,
        "longest_mm": round(longest, 1),
        "heaviest_unit_kg": round(heaviest, 2),
        "source": source,
        "summary_text": (
            f"{summary.get('total_pieces')}件 / {summary.get('total_weight_kg')}kg / "
            f"{summary.get('material_line_count')}行 | 分类{cats} | 柜型假设={ctn_assume}"
        ),
    }


def _demo_materials() -> List[Dict[str, Any]]:
    """默认演示：高利用率密实模块（避免「空柜感」）。

    钢件轻量叙事请用 preset=steel_light 或文案含「钢件轻量」。
    """
    try:
        from packing_assistant.demo_presets import materials_high_util

        return materials_high_util()
    except Exception:
        from packing_assistant.adapters import material_internal_to_api

        raw = [
            {
                "名称": "H型钢柱",
                "规格": "H400×200",
                "数量": 4,
                "单重_kg": 85,
                "外尺寸_mm": {"长": 3800, "宽": 400, "高": 200},
            },
            {
                "名称": "钢梁",
                "规格": "H350×175",
                "数量": 6,
                "单重_kg": 55,
                "外尺寸_mm": {"长": 4200, "宽": 350, "高": 175},
            },
        ]
        return [material_internal_to_api(m, i) for i, m in enumerate(raw, 1)]


def _rule_parse(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                out = []
                for i, item in enumerate(data, 1):
                    if "name" in item or "length_mm" in item:
                        item = dict(item)
                        item.setdefault("id", f"M{i:03d}")
                        item.setdefault(
                            "category",
                            classify_material(
                                float(item.get("length_mm") or 0),
                                float(item.get("weight_kg") or 0),
                                float(item.get("total_weight_kg") or 0),
                            ),
                        )
                        out.append(item)
                    else:
                        out.append(material_internal_to_api(item, i))
                return out
        except json.JSONDecodeError:
            pass

    materials: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(
            r"(.+?)\s+(\d+)\s*(?:件|个|根|套)?\s*([\d.]+)?\s*kg?"
            r"(?:\s+([\d.]+)[x×]([\d.]+)[x×]([\d.]+))?",
            line,
            re.I,
        )
        if m:
            name = m.group(1).strip()
            qty = int(m.group(2))
            weight = float(m.group(3) or 0)
            L, W, H = m.group(4), m.group(5), m.group(6)
            total = qty * weight
            materials.append(
                {
                    "id": f"M{len(materials)+1:03d}",
                    "name": name,
                    "spec": name,
                    "length_mm": float(L or 0),
                    "width_mm": float(W or 0),
                    "height_mm": float(H or 0),
                    "weight_kg": weight,
                    "quantity": qty,
                    "total_weight_kg": total,
                    "category": classify_material(float(L or 0), weight, total),
                }
            )
        else:
            materials.append(
                {
                    "id": f"M{len(materials)+1:03d}",
                    "name": line,
                    "spec": line,
                    "length_mm": 0,
                    "width_mm": 0,
                    "height_mm": 0,
                    "weight_kg": 0,
                    "quantity": 1,
                    "total_weight_kg": 0,
                    "category": "普通件",
                }
            )
    return materials


def _filter_remove(materials: List[Dict[str, Any]], note: str) -> List[Dict[str, Any]]:
    m = re.search(r"(?:去掉|删除)\s*([^\s,，。；;]+)", note)
    if not m:
        return materials
    key = m.group(1)
    filtered = [
        x
        for x in materials
        if key not in str(x.get("name", ""))
        and key not in str(x.get("id", ""))
        and key not in str(x.get("spec", ""))
    ]
    return filtered if filtered else materials
