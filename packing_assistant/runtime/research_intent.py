"""Conservative, deterministic scope binding for supported JPJ question forms.

This is deliberately not general NLU. Unrecognized phrasing asks for a clearer
question. Every model-selected filter must match explicitly recognized wording.
"""
import re

FUEL_ALIASES = {
    "electric": ("electric", "EV", "纯电动", "纯电", "电动车", "电动"),
    "petrol": ("petrol", "gasoline", "汽油"),
    "diesel": ("diesel", "柴油"),
    "greendiesel": ("greendiesel", "green diesel", "绿色柴油"),
    "hybrid_petrol": ("hybrid_petrol", "petrol hybrid", "汽油混合动力", "油电混合"),
    "hybrid_diesel": ("hybrid_diesel", "diesel hybrid", "柴油混合动力"),
    "petrol_ng": ("petrol_ng", "汽油天然气"),
    "other": ("other fuel", "其他燃料"),
}
BRAND_ALIASES = {"BYD": ("比亚迪",), "TESLA": ("特斯拉",), "TOYOTA": ("丰田",)}
ISO_MONTH = r"(?<![0-9])\d{4}-(?:0[1-9]|1[0-2])(?![0-9])"
CN_RANGE = r"(\d{4})年\s*(\d{1,2})月?\s*(?:至|到|[-—~～])\s*(\d{1,2})月"
CN_MONTH = r"(\d{4})年\s*(\d{1,2})月"


def clarify(question):
    return {"ok": False, "executed": False, "error_code": "missing_parameters", "question": question}


def denied(code, reason):
    return {"ok": False, "executed": False, "error_code": code, "reason": reason}


def _recognize(text, vocabulary):
    """Longest non-overlapping literal phrase matches; retain unmatched text."""
    spans, values = [], set()
    for phrase, value in sorted(vocabulary, key=lambda item: len(item[0]), reverse=True):
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9_])"
        # Chinese names may directly adjoin other Chinese words.
        if not phrase.isascii():
            pattern = re.escape(phrase)
        for match in re.finditer(pattern, text, re.I):
            if any(match.start() < end and match.end() > start for start, end in spans):
                continue
            spans.append((match.start(), match.end()))
            values.add(value)
    rest = list(text)
    for start, end in spans:
        rest[start:end] = " " * (end - start)
    return values, "".join(rest)


def _range(prompt):
    iso = re.findall(ISO_MONTH, prompt)
    compact = re.findall(CN_RANGE, prompt)
    explicit_cn = re.findall(CN_MONTH, prompt)
    if compact and not iso and len(compact) == 1:
        year, first, last = compact[0]
        if 1 <= int(first) <= 12 and 1 <= int(last) <= 12:
            return (f"{year}-{int(first):02}", f"{year}-{int(last):02}"), re.sub(CN_RANGE, " ", prompt)
    if iso and not explicit_cn and len(iso) in (1, 2):
        matches = list(re.finditer(ISO_MONTH, prompt))
        if len(matches) == 2 and not re.fullmatch(r"\s*(?:to|至|到|[-—~～])\s*", prompt[matches[0].end():matches[1].start()], re.I):
            return None, prompt
        if len(iso) == 1 and re.search(r"\bfrom\b|\bsince\b|从|自|至|到", prompt, re.I | re.ASCII):
            return None, prompt
        return (iso[0], iso[-1]), re.sub(ISO_MONTH, " ", prompt)
    if explicit_cn and not iso and not compact and len(explicit_cn) in (1, 2):
        matches = list(re.finditer(CN_MONTH, prompt))
        if len(matches) == 2 and not re.fullmatch(r"\s*(?:至|到|[-—~～])\s*", prompt[matches[0].end():matches[1].start()]):
            return None, prompt
        months = [f"{year}-{int(month):02}" for year, month in explicit_cn if 1 <= int(month) <= 12]
        if len(months) == len(explicit_cn):
            return (months[0], months[-1]), re.sub(CN_MONTH, " ", prompt)
    return None, prompt


def validate_model_scope(prompt, name, args, catalog=None):
    if not name.startswith("jpj."):
        return None
    if re.search(r"销量|销售量|\bsales\b|\btiv\b", prompt, re.I | re.ASCII):
        return denied("unsupported_metric", "JPJ 仅提供注册量，无法回答销量或 TIV；请明确改用注册量后查询。")
    if name != "jpj.query":
        return None
    if not isinstance(catalog, dict) or not isinstance(catalog.get("makers"), list) or not isinstance(catalog.get("fuels"), list):
        return clarify("暂时无法核对来源目录，请稍后重试或使用明确参数的确定性工具。")
    months, rest = _range(prompt)
    if months is None or months[0] > months[1]:
        return clarify("请明确开始月份和结束月份，例如 2026-01 至 2026-08；模型不能补充或缩短区间。")
    makers, rest = _recognize(rest, [(maker, maker.upper()) for maker in catalog["makers"] if isinstance(maker, str)] +
        [(alias, maker) for maker, aliases in BRAND_ALIASES.items() if maker in catalog["makers"] for alias in aliases])
    fuels, rest = _recognize(rest, [(alias, fuel) for fuel, aliases in FUEL_ALIASES.items() if fuel in catalog["fuels"] for alias in aliases])
    fuel_dimension = bool(re.search(r"燃料|\bfuels?\b", rest, re.I | re.ASCII))
    ranking = bool(re.search(r"排行|排名|\btop\b|\brank(?:ing)?\b", rest, re.I | re.ASCII))
    brand_grouping = bool(re.search(r"按品牌|分品牌|品牌分组|\bby\s+(?:brand|maker)s?\b", rest, re.I | re.ASCII))
    monthly = bool(re.search(r"逐月|月度|按月|各月|\bmonthly\b", rest, re.I | re.ASCII))
    if brand_grouping and not ranking and len(makers) < 2:
        return clarify("按品牌分组需要明确选择品牌排行，或指定 2 到 8 个品牌作区间总量对比。")
    if makers and (fuels or fuel_dimension):
        return denied("unsupported_dimension", "数据不支持品牌与燃料的交叉查询，不能用边际聚合代替。")
    if len(fuels) > 1 or (makers and ranking) or (len(makers) > 1 and monthly):
        return clarify("此问题超出已支持的查询组合，请明确选择品牌区间总量对比、单品牌月度、燃料月度或品牌排行。")
    limit_match = re.search(r"(?:\btop\s*|前\s*)(\d+)", rest, re.I | re.ASCII)
    limit = int(limit_match.group(1)) if limit_match else None
    if limit_match:
        rest = rest[:limit_match.start()] + " " + rest[limit_match.end():]
    # Closed vocabulary: unknown brands, negation, extra dimensions or qualifiers
    # must not be silently discarded while returning an apparently valid query.
    phrases = ("请查询", "请统计", "告诉我", "给出", "数据来源", "登记次数", "注册数量", "登记数量", "注册量", "登记量",
        "汽车", "车辆", "马来西亚", "是多少", "多少", "数量", "总量", "总计", "来源", "数据", "查询", "统计", "对比", "比较",
        "燃料类型", "燃料", "品牌", "排行", "排名", "逐月", "月度", "按月", "各月", "请", "的", "和", "与", "并", "至", "到", "按")
    for phrase in sorted(phrases, key=len, reverse=True):
        rest = rest.replace(phrase, " ")
    english = "please query show compare and with by between from to registration registrations counts count cars car vehicles vehicle malaysia jpj source sources data give the of in during monthly month total for rank ranking makers maker brands brand fuel fuels types top"
    rest = re.sub(r"\b(?:" + "|".join(english.split()) + r")\b", " ", rest, flags=re.I | re.ASCII)
    if re.sub(r"[\s,，。.?？!！:：;；/\-—~～()（）]", "", rest):
        return clarify("问题包含未识别的品牌、限定或表达。请使用明确月份、目录品牌名称和注册量口径，或改用确定性参数查询。")
    query_id = "fuel_monthly" if fuels or fuel_dimension else "maker_ranking" if ranking else "brand_compare" if len(makers) > 1 else "monthly_registrations"
    expected = {"start_month": months[0], "end_month": months[1]}
    if len(makers) == 1:
        expected["maker"] = next(iter(makers))
    elif len(makers) > 1:
        expected["makers"] = sorted(makers)
    if fuels:
        expected["fuel"] = next(iter(fuels))
    if limit is not None:
        if not ranking:
            return clarify("只有品牌排行支持明确的前 N 名限制。")
        expected["limit"] = limit
    params = args.get("parameters") if isinstance(args, dict) else None
    if not isinstance(params, dict) or args.get("query_id") != query_id:
        return denied("request_scope_mismatch", "模型选择的查询类型与原始问题不一致，已拒绝执行。")
    actual = dict(params)
    if "metric" in actual:
        if actual.pop("metric") != "registrations":
            return denied("unsupported_metric", "仅支持 registrations。")
    if isinstance(actual.get("maker"), str):
        actual["maker"] = actual["maker"].strip().upper()
    if isinstance(actual.get("makers"), list) and all(isinstance(x, str) for x in actual["makers"]):
        actual["makers"] = sorted(x.strip().upper() for x in actual["makers"])
    if isinstance(actual.get("fuel"), str):
        actual["fuel"] = actual["fuel"].strip().lower()
    if actual != expected:
        return denied("request_scope_mismatch", "模型丢弃、增加或改变了原问题的月份、品牌、燃料或排行条件，已拒绝执行。")
    return None
