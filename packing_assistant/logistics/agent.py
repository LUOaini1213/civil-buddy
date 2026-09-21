"""Restricted logistics tools: user's explicit corrections become reviewable proposals."""
from __future__ import annotations

from copy import deepcopy
import math
import re

from packing_assistant.runtime.cancel import check
from .records import digest

NUMERIC = {"package_count", "quantity", "units_per_package", "length_mm", "width_mm", "height_mm", "net_kg", "gross_kg"}
TEXT = {"package_id", "material_id", "name", "spec", "unit", "dimension_scope", "weight_scope"}
ALIASES = {"箱数": "package_count", "包装数": "package_count", "件数": "quantity", "数量": "quantity", "每箱件数": "units_per_package",
           "长": "length_mm", "长度": "length_mm", "宽": "width_mm", "宽度": "width_mm", "高": "height_mm", "高度": "height_mm",
           "净重": "net_kg", "毛重": "gross_kg", "箱号": "package_id", "材料编号": "material_id", "名称": "name", "规格": "spec",
           "单位": "unit", "尺寸口径": "dimension_scope", "重量口径": "weight_scope"}


def propose_changes(document, changes, reason):
    from .ledger import validate_document
    doc = validate_document(document)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ValueError("请记录修订的原话或原因。")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
        raise ValueError("每次须提出 1–100 项修订。")
    rows = {r["id"]: r for r in doc["rows"]}
    seen, normalized = set(), []
    for item in changes:
        check()
        if not isinstance(item, dict) or set(item) != {"row_id", "field", "value"}:
            raise ValueError("修订只能包含 row_id、field、value。")
        ident, field, value = item["row_id"], item["field"], item["value"]
        if not isinstance(ident, str) or ident not in rows or not isinstance(field, str) or field not in NUMERIC | TEXT:
            raise ValueError("只能修改已有台账行的受限字段。")
        if (ident, field) in seen:
            raise ValueError("同一字段不能重复修订。")
        seen.add((ident, field))
        if value != "UNSPECIFIED":
            if field in NUMERIC and (type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1e12):
                raise ValueError("数值须为明确的正有限数，未知请用 UNSPECIFIED。")
            if field in {"package_count", "quantity", "units_per_package"} and (type(value) not in (int, float) or int(value) != value):
                raise ValueError("箱数与件数必须是正整数。")
            if field in TEXT and (not isinstance(value, str) or not value.strip() or len(value) > 500):
                raise ValueError("文本修订须为 1–500 字。")
            if field == "dimension_scope" and value not in {"package", "item"}:
                raise ValueError("尺寸口径仅支持 package / item。")
            if field == "weight_scope" and value not in {"package", "item", "row"}:
                raise ValueError("重量口径仅支持 package / item / row。")
        before = rows[ident].get(field, "UNSPECIFIED")
        if before == value:
            continue
        normalized.append({"row_id": ident, "field": field, "before": before, "after": value})
        rows[ident][field] = value
        evidence = rows[ident].setdefault("evidence", {}).setdefault(field, {"raw": "UNSPECIFIED", "source": {}})
        evidence.setdefault("corrections", []).append({"before": before, "after": value, "reason": reason})
    if not normalized:
        raise ValueError("所填值与台账一致，没有待应用的修订。")
    doc = validate_document(doc)
    return {"schema": "civil.logistics.proposal.v1", "base_digest": digest(document), "source_text": reason,
            "changes": normalized, "document": doc}


def propose_command(document, message):
    if not isinstance(message, str) or not 1 <= len(message) <= 4000:
        raise ValueError("修订指令长度无效。")
    commands = [s.strip() for s in re.split(r"[;；\n]", message) if s.strip()]
    changes = []
    fields = "|".join(sorted([*ALIASES, *NUMERIC, *TEXT], key=len, reverse=True))
    for command in commands:
        match = re.fullmatch(r"(?:把|将)?\s*([A-Za-z][A-Za-z0-9_-]{0,63})\s*(?:的)?\s*(" + fields + r")\s*(?:改为|设为|设置为|=|：|:)\s*(.+?)\s*[。.]?", command)
        if not match:
            raise ValueError("请明确已有行号、字段和新值，例如：把 R00001 毛重改为 120 kg；不会猜测数据。")
        ident, field, raw = match.groups()
        field = ALIASES.get(field, field)
        value = raw.strip()
        if value in {"未知", "未指定", "UNSPECIFIED"}:
            value = "UNSPECIFIED"
        elif field in NUMERIC:
            number = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(mm|cm|m|kg|g|t|毫米|厘米|米|千克|公斤|克|吨|件|箱)?", value, re.I)
            if not number:
                raise ValueError("数字或单位不明确，未提出修订。")
            value, unit = float(number[1]), (number[2] or "").lower()
            if field.endswith("_mm"):
                if unit not in {"", "mm", "cm", "m", "毫米", "厘米", "米"}:
                    raise ValueError("尺寸须使用 mm、cm 或 m。")
                value *= {"cm": 10, "厘米": 10, "m": 1000, "米": 1000}.get(unit, 1)
            elif field.endswith("_kg"):
                if unit not in {"", "kg", "g", "t", "千克", "公斤", "克", "吨"}:
                    raise ValueError("重量须使用 kg、g 或 t。")
                value *= {"g": .001, "克": .001, "t": 1000, "吨": 1000}.get(unit, 1)
            elif unit not in ({"", "箱"} if field == "package_count" else {"", "件"}):
                raise ValueError("包装数使用箱，货物数量和每箱件数使用件；不混用箱与件。")
        elif field in {"dimension_scope", "weight_scope"}:
            value = {"每箱": "package", "包装": "package", "单件": "item", "每件": "item", "整行": "row"}.get(value, value)
        changes.append({"row_id": ident, "field": field, "value": value})
    proposal = propose_changes(document, changes, message)
    proposal["command"] = True
    return proposal


def apply_proposal(document, proposal):
    if not isinstance(proposal, dict) or proposal.get("base_digest") != digest(document):
        raise ValueError("建议属于旧台账，请重新提出。")
    if proposal.get("command"):
        expected = propose_command(document, proposal["source_text"])
    else:
        expected = propose_changes(document, [{"row_id": c["row_id"], "field": c["field"], "value": c["after"]} for c in proposal["changes"]], proposal["source_text"])
    if expected != proposal:
        raise ValueError("建议内容被修改，未应用。")
    check()
    return deepcopy(expected["document"])


def compare_documents(document, other):
    """Only explicit unique material IDs join; no fuzzy name/spec matching."""
    from .ledger import validate_document
    left, right = validate_document(document), validate_document(other)
    def index(doc):
        values, duplicates, unmatched = {}, set(), []
        for row in doc["rows"]:
            key = row.get("material_id", "UNSPECIFIED")
            if key == "UNSPECIFIED":
                unmatched.append(row["id"])
            elif key in values:
                duplicates.add(key)
            else:
                values[key] = row
        return values, duplicates, unmatched
    a, ad, au = index(left)
    b, bd, bu = index(right)
    rows = []
    for key in sorted(set(a) | set(b)):
        x, y = a.get(key), b.get(key)
        if key in ad | bd:
            rows.append({"material_id": key, "status": "ambiguous_duplicate"})
        elif x is None or y is None:
            rows.append({"material_id": key, "status": "only_current" if y is None else "only_comparison"})
        else:
            fields = {f: {"current": x.get(f, "UNSPECIFIED"), "comparison": y.get(f, "UNSPECIFIED")} for f in ("name", "spec", "unit", "quantity", "package_count") if x.get(f) != y.get(f)}
            rows.append({"material_id": key, "current_row": x["id"], "comparison_row": y["id"], "status": "different" if fields else "same", "differences": fields})
    return {"rows": rows, "unmatched_current": au, "unmatched_comparison": bu,
            "note": "仅按明确且唯一的材料编号对照原值；不按名称猜匹配，不推断采购单价。"}


def operation(message, context=None):
    if re.search(r"撤销", message):
        return "logistics_undo"
    if re.search(r"改为|设为|设置为|=", message):
        return "logistics_propose"
    if re.search(r"缺|检查|核对|审计", message):
        return "logistics_audit"
    if re.search(r"汇总|总计|多少", message):
        return "logistics_summarize"
    return "logistics_inspect"


def execute(context, name, args, user_text):
    from .ledger import validate_document, audit_document, summarize, FIELD_LABELS
    if args != {} or name not in {"logistics_inspect", "logistics_audit", "logistics_summarize", "logistics_propose", "logistics_undo"}:
        return {"ok": False, "reply": "物流工具不接受路径、材料数组或模型生成的字段值。"}
    try:
        check()
        doc = validate_document(context["document"])
        if name == "logistics_propose":
            proposal = propose_command(doc, user_text)
            return {"ok": True, "logistics_proposal": proposal, "reply": f"已提出 {len(proposal['changes'])} 项修订建议；台账未修改，请核对原值与新值后确认应用。"}
        if name == "logistics_undo":
            if not re.search(r"撤销", user_text) or not context.get("project", {}).get("can_undo"):
                raise ValueError("当前没有用户明确要求或没有可撤销的历史；未执行撤销。")
            return {"ok": True, "logistics_action": "undo", "reply": "已准备撤销上次台账修改的建议，尚未执行；请在工作台确认。"}
        audit, summary = audit_document(doc), summarize(doc)
        errors = [i for i in audit.get("issues", []) if i.get("severity") == "error"]
        lines = [f"当前台账有 {len(doc['rows'])} 行；检查发现 {len(errors)} 项错误、{len(audit.get('issues', [])) - len(errors)} 项提示。"]
        if name in {"logistics_inspect", "logistics_audit"}:
            lines.extend(f"{i.get('row_id') or '整表'} / {FIELD_LABELS.get(i.get('field'), '检查')}：{i['message'][:300]}" for i in audit.get("issues", [])[:12])
        if name == "logistics_summarize":
            def value(v):
                return "未确定" if v == "UNSPECIFIED" or v is None else f"{v:g}" if type(v) in (int, float) else str(v)
            totals = summary.get("totals", {})
            lines.append(f"包装箱数：{value(totals.get('package_count'))}；净重：{value(totals.get('net_kg'))} kg；毛重：{value(totals.get('gross_kg'))} kg。")
            quantities = summary.get("quantities_by_unit", {})
            lines.append("货物数量按单位分别汇总：" + ("；".join(f"{value(count)} {unit[:100] if unit != 'UNSPECIFIED' else '（单位未明确）'}" for unit, count in list(quantities.items())[:20]) or "未确定") + "。")
            unknown = {f: sum(r.get(f, "UNSPECIFIED") == "UNSPECIFIED" for r in doc["rows"]) for f in NUMERIC | {"dimension_scope", "weight_scope", "unit"}}
            lines.append("待补字段：" + ("；".join(f"{FIELD_LABELS.get(f, f)} {count} 行" for f, count in sorted(unknown.items()) if count) or "本次汇总字段均有明确值") + "。")
        lines.append("本次仅检查台账，没有修改、装箱或导出。")
        selected = doc["rows"][:50]
        selected += [r for r in doc["rows"][50:] if r["id"] in user_text][:10]
        catalog = [{"id": r["id"], "package_id": r["package_id"][:100], "material_id": r["material_id"][:100], "name": r["name"][:100],
                    "known_values": {f: r[f][:100] if isinstance(r[f], str) else r[f] for f in sorted(NUMERIC | {"dimension_scope", "weight_scope", "unit"}) if r[f] != "UNSPECIFIED"},
                    "unknown_fields": [f for f in sorted(NUMERIC | {"dimension_scope", "weight_scope", "unit"}) if r[f] == "UNSPECIFIED"]} for r in selected]
        bounded_audit = {**audit, "issues": [{k: v[:500] if isinstance(v, str) else v for k, v in issue.items()} for issue in audit.get("issues", [])[:50]], "issues_truncated": len(audit.get("issues", [])) > 50}
        bounded_summary = {k: v for k, v in summary.items() if k != "audit"}
        bounded_summary["quantities_by_unit"] = dict(list(summary.get("quantities_by_unit", {}).items())[:50])
        bounded_summary["quantities_truncated"] = len(summary.get("quantities_by_unit", {})) > 50
        check()
        return {"ok": True, "audit": bounded_audit, "summary": bounded_summary, "row_catalog": catalog,
                "row_catalog_truncated": len(doc["rows"]) > len(catalog), "reply": "\n".join(lines)}
    except (ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "reply": str(exc)}


def reply_for(results, context=None):
    if isinstance(results, dict):
        results = [results]
    return "\n\n".join(str(r.get("reply", "")) for r in results if isinstance(r, dict) and r.get("reply")) or "没有工具成功返回结果；台账未修改。"
