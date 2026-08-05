"""非标备注影子增强：LLM/规则从 name/note 抽字段，禁止改尺寸重量。

开关：
  packing_options.ns_llm_enrich=True 或环境 PACKING_NS_LLM=1 → 尝试 LLM
  默认仅规则关键词（policy_fallback）
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional


def _rule_enrich_one(m: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(m)
    blob = " ".join(
        str(x)
        for x in (
            m.get("name"),
            m.get("名称"),
            m.get("spec"),
            m.get("规格"),
            m.get("note"),
            m.get("备注"),
        )
        if x
    )
    low = blob.lower()
    tags: List[str] = list(m.get("ns_tags") or m.get("ns_tags_hint") or [])
    changed = False

    def add_tag(t: str) -> None:
        nonlocal changed
        if t not in tags:
            tags.append(t)
            changed = True

    if any(k in blob for k in ("易碎", "玻璃", "精密", "仪表")) or "fragile" in low:
        out["fragile"] = True
        add_tag("精密件")
        changed = True
    if any(k in blob for k in ("禁翻", "向上", "直立")) or "this side up" in low:
        out["this_side_up"] = True
        out["orientation"] = out.get("orientation") or "this_side_up"
        changed = True
    if any(k in blob for k in ("禁叠", "不可叠", "勿压")):
        out["no_stack"] = True
        out["stackable"] = False
        changed = True
    if any(k in blob for k in ("开顶", "框架柜", "ot柜")):
        out["ot_container_hint"] = True
        add_tag("超长件")
        changed = True
    if any(k in blob for k in ("叠层架", "铁件架", "当量", "factory_stack", "crate")):
        add_tag("工厂架")
        changed = True
    if any(k in blob for k in ("危险品", "锂电池", "电池")):
        out["hazard_class"] = out.get("hazard_class") or "hint"
        add_tag("合规关注")
        changed = True
    if re.search(r"异形|非标", blob):
        add_tag("异形件")
        changed = True

    if tags:
        out["ns_tags"] = tags
        out["ns_tags_hint"] = tags
    if changed:
        out["enrich_source"] = out.get("enrich_source") or "rules"
    return out


def _try_llm_enrich(materials: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """可选 LLM：只返回 tags/flags，失败返回 None。"""
    try:
        from packing_assistant.llm import chat_json  # type: ignore
    except Exception:
        try:
            from packing_assistant import llm as llm_mod

            chat_json = getattr(llm_mod, "chat_json", None) or getattr(llm_mod, "complete_json", None)
            if not chat_json:
                return None
        except Exception:
            return None

    # 截断样本避免爆 token
    sample = []
    for m in materials[:40]:
        sample.append(
            {
                "id": m.get("id"),
                "name": m.get("name") or m.get("名称"),
                "spec": m.get("spec") or m.get("规格"),
                "note": m.get("note") or m.get("备注"),
            }
        )
    prompt = (
        "从物料 name/spec/note 抽取装运属性，只输出 JSON 数组。"
        "每项: {id, fragile?:bool, this_side_up?:bool, no_stack?:bool, "
        "ot_container_hint?:bool, ns_tags?:string[], hazard_class?:string}。"
        "禁止输出或修改尺寸、重量、柜数。无信息则空数组项可省略字段。\n"
        f"materials={sample!r}"
    )
    try:
        data = chat_json(prompt)  # type: ignore
    except Exception:
        return None
    if not isinstance(data, list):
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data = data["items"]
        else:
            return None
    by_id = {str(x.get("id")): x for x in data if isinstance(x, dict) and x.get("id")}
    out = []
    for m in materials:
        row = dict(m)
        patch = by_id.get(str(m.get("id"))) or {}
        for k in ("fragile", "this_side_up", "no_stack", "ot_container_hint", "hazard_class"):
            if patch.get(k) is not None:
                row[k] = patch[k]
        if patch.get("no_stack"):
            row["stackable"] = False
        if patch.get("this_side_up"):
            row["orientation"] = row.get("orientation") or "this_side_up"
        tags = list(row.get("ns_tags") or [])
        for t in patch.get("ns_tags") or []:
            if t not in tags:
                tags.append(t)
        if tags:
            row["ns_tags"] = tags
        if patch:
            row["enrich_source"] = "llm"
        out.append(row)
    return out


def enrich_materials(
    materials: List[Dict[str, Any]],
    *,
    force_llm: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """先规则，再可选 LLM 覆盖/补充字段。"""
    if not materials:
        return []
    use_llm = force_llm
    if use_llm is None:
        use_llm = os.environ.get("PACKING_NS_LLM", "").strip() in ("1", "true", "TRUE", "yes")
    ruled = [_rule_enrich_one(m) for m in materials if isinstance(m, dict)]
    if not use_llm:
        return ruled
    llm_out = _try_llm_enrich(ruled)
    if not llm_out:
        for r in ruled:
            r.setdefault("enrich_source", "rules")
            r["enrich_llm"] = "policy_fallback"
        return ruled
    # merge: llm flags on top of rules
    return llm_out
