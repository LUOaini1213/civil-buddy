"""Tax drafting inputs only: no embedded rates, legal determinations or network."""
from __future__ import annotations

import html
import re

from packing_assistant.jurisdiction import infer_jurisdiction

UNKNOWN = "UNSPECIFIED"
_FIELDS = {
    "辖区": "zone", "地区": "zone", "主体类型": "entity", "纳税主体": "entity", "主体": "entity",
    "税种": "tax", "申报期间": "period", "申报期": "period", "期间": "period",
    "申报截止日期": "deadline", "申报截止": "deadline", "截止日期": "deadline", "申报节点": "deadline",
    "用户税率": "rate", "税率": "rate", "用户税额": "amount", "税额": "amount",
    "资料来源": "source", "依据来源": "source", "来源文件": "source", "来源": "source",
    "资料日期": "source_date", "核验日期": "source_date", "责任人": "owner",
    "税号": "tax_id", "项目名称": "project", "企业名称": "project",
}
_KEY = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(k) for k in sorted(_FIELDS, key=len, reverse=True)) + r")\s*[:：=]\s*")
_RATE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?\s*[%％](?!\d)")
_GST_RATE = re.compile(r"\bGST\s*(?:税率|rate)?\s*[:：=]?\s*(\d+(?:\.\d+)?\s*[%％])", re.I)


def _cell(value: str) -> str:
    return html.escape(value.replace("\r", " ").replace("\n", "；"), quote=False).replace("|", "&#124;")


def _split_table(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [html.unescape(cell.strip()) for cell in value.split("|")]


def _records(text: str) -> tuple[str, list[dict[str, str]]]:
    """Keep explicit table rows and repeated tax records separate."""
    lines = text.splitlines()
    header = None
    table_rows = []
    before_table = []
    for line in lines:
        if "|" not in line:
            if header is None:
                before_table.append(line)
            continue
        cells = _split_table(line)
        mapped = [_FIELDS.get(cell) for cell in cells]
        if sum(key is not None for key in mapped) >= 2:
            header = mapped
            continue
        if header is None or all(re.fullmatch(r":?-{2,}:?", cell or "---") for cell in cells):
            continue
        if len(cells) == len(header):
            table_rows.append({key: value for key, value in zip(header, cells) if key and value})
    if table_rows:
        # A row's region never becomes the default for a sibling row.
        return infer_jurisdiction("\n".join(before_table)), table_rows
    matches = list(_KEY.finditer(text))
    if not matches:
        rates = _GST_RATE.findall(text)
        return infer_jurisdiction(text), [{"tax": "GST", "rate": rates[0]}] if len(rates) == 1 else [{}]
    prefix = text[:matches[0].start()]
    global_zone = infer_jurisdiction(prefix)
    rows, current = [], {}
    for index, match in enumerate(matches):
        key = _FIELDS[match.group(1)]
        value = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        value = re.split(r"[;；\r\n]", value, maxsplit=1)[0].strip(" ,，。")
        if (key in {"tax", "entity"} and key in current) or (key == "zone" and any(k in current for k in ("tax", "period", "rate", "amount"))):
            rows.append(current)
            current = {}
        if value:
            # Conflicting percentages stay visible, but must not silently pick
            # the last rate for a record.
            current[key] = current[key] + "；" + value if key == "rate" and key in current else value
    if current:
        rows.append(current)
    return global_zone, rows or [{}]


def records(text: str, previous: str = "") -> list[dict[str, str]]:
    global_zone, raw = _records(text or "")
    if global_zone == UNKNOWN and previous in {"CN", "SG", "EU", "DUAL"}:
        global_zone = previous
    result = []
    for row in raw:
        zone = infer_jurisdiction(row.get("zone", ""), previous=global_zone)
        # DUAL requires independent region rows; a shared percentage cannot be
        # silently applied to both jurisdictions.
        values = _RATE.findall(row.get("rate", ""))
        rate = values[0] if len(values) == 1 and zone in {"CN", "SG", "EU"} else UNKNOWN
        result.append({**row, "zone": zone, "rate": rate,
                       "rate_input": row.get("rate", UNKNOWN),
                       "source": row.get("source", UNKNOWN),
                       "review": "用户提供，适用性及现行版本未核验" if rate != UNKNOWN else "待补明确辖区、税种及税率依据"})
    return result


def explain_tax(text: str, previous: str = "") -> str:
    rows = records(text, previous=previous)
    zones = {row["zone"] for row in rows}
    zone = next(iter(zones)) if len(zones) == 1 else "DUAL"
    lines = [f"辖区：{zone}。GST 等税种的适用范围、税率和申报时限须按具体主体及期间核对。"]
    for row in rows:
        if row["rate"] != UNKNOWN:
            lines.append(f"用户提供税率：{row['rate']}（辖区 {row['zone']}；未核验，不认定为现行适用税率）。")
        else:
            lines.append("税率：UNSPECIFIED。请补明确地区、税种、期间及可定位的资料原文；本机历史知识条目不证明当前税率。")
    lines.append("本次未联网核验、未计算税额，也不构成税务意见。")
    return "\n".join(lines)


def draft_tax(text: str, disclaimer: str) -> str:
    rows = records(text)
    zones = {row["zone"] for row in rows}
    zone = next(iter(zones)) if len(zones) == 1 else "DUAL"
    lines = ["# 税务日历/检查表（AI 草稿）", "", disclaimer, "", "submit_blocked=true；仅供内部起草，未经复核不得作为申报依据。", "",
             f"辖区：{zone}。本表只整理用户提供的资料；不是税务意见书，不认定已完成申报。", "",
             "## 1 辖区、主体与申报日历", "",
             "| 辖区 | 主体 | 税种 | 申报期 | 申报节点 | 用户税率（待核） | 用户税额（待核） |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        values = [row.get(key, UNKNOWN) for key in ("zone", "entity", "tax", "period", "deadline", "rate", "amount")]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines += ["", "## 2 依据与资料核对", "",
              "| 辖区 | 税种 | 用户税率原文 | 资料来源 | 资料日期 | 核验状态 | 责任人 |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        values = [row.get(key, UNKNOWN) for key in ("zone", "tax", "rate_input", "source", "source_date", "review", "owner")]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines += ["", "## 3 发票与申报准备", "",
              "| 核对项 | 用户资料 | 待办 |", "| --- | --- | --- |",
              "| 主体与税号 | " + _cell("；".join(row.get("tax_id", UNKNOWN) for row in rows)) + " | 核对主体、辖区与申报期间 |",
              "| 业务与发票 | UNSPECIFIED | 待附业务、合同及发票资料 |",
              "| 申报与付款状态 | UNSPECIFIED | 待提供申报回执或付款记录 |", "",
              "## 4 缺项与复核", "",
              "- [A001] 缺失的主体、税种、期间、税率或节点依据逐项待填；没有来源不推算申报时限或税额。",
              "- 明确 SG / CN / EU 的记录分别核对；DUAL 不能共用未经确认的税率。",
              "- 用户提供的税率和资料仅作为待核输入。未联网核验，不从历史 KB 或模型记忆补充现行税率。",
              "- 未计算税额，未代办申报。复核人、签认日期：________。", ""]
    return "\n".join(lines)
