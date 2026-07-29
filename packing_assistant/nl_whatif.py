"""NL What-if：结合**当前物料画像**生成差异化方案。

不再把「只要铁件/去掉超长」焊死成全局 scenario 名；
而是：解析意图 → 按本票材料分类/尺寸/重量 → 产出选料规则 + packing_options + 柜数。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 物料族（可扩展）
FAMILY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("iron", ("FST", "FHA", "FHU", "铁件", "钢架", "钢通", "铁架", "吊具", "槽钢")),
    ("stainless", ("FSS", "不锈钢")),
    ("aluminum_plate", ("FAC", "铝板", "蜂窝")),
    ("aluminum_profile", ("BAL", "铝型材", "拉弯", "型材")),
    ("glass", ("BGL", "玻璃", "Glass")),
    ("fastener", ("BBF", "紧固", "螺丝", "螺栓", "五金")),
    ("gasket", ("BGK", "胶条", "垫块", "胶皮")),
    ("misc", ("BOM", "瓦楞", "木板", "杂项")),
    ("glass_sealant", ("BSS", "结构胶", "耐候胶")),
]


def _text_of(m: Dict[str, Any]) -> str:
    return " ".join(
        str(m.get(k) or "")
        for k in ("part_no", "name", "spec", "note", "destination", "id")
    )


def classify_material(m: Dict[str, Any]) -> str:
    t = _text_of(m).upper()
    t_raw = _text_of(m)
    for fam, keys in FAMILY_RULES:
        for k in keys:
            if k.upper() in t or k in t_raw:
                return fam
    # 尺寸启发
    try:
        L = float(m.get("length_mm") or m.get("L") or 0)
        H = float(m.get("height_mm") or m.get("H") or 0)
        kg = float(m.get("total_weight_kg") or m.get("weight_kg") or 0)
    except Exception:
        return "unknown"
    if H <= 80 and L >= 800:
        return "aluminum_plate"
    if L >= 4000 and kg < 80:
        return "aluminum_profile"
    if kg >= 200:
        return "iron"
    return "unknown"


def analyze_materials(materials: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
    """本票物料画像：族分布、超长、重量、建议策略。"""
    mats = list(materials or [])
    by_fam: Dict[str, List[Dict[str, Any]]] = {}
    lengths: List[float] = []
    net = 0.0
    long_ge_6: List[str] = []
    long_ge_4: List[str] = []
    crate_like = 0
    thin = 0

    for m in mats:
        fam = classify_material(m)
        by_fam.setdefault(fam, []).append(m)
        try:
            L = float(m.get("length_mm") or m.get("L") or 0)
            H = float(m.get("height_mm") or m.get("H") or 0)
            w = float(m.get("total_weight_kg") or m.get("weight_kg") or 0)
        except Exception:
            L, H, w = 0.0, 0.0, 0.0
        lengths.append(L)
        net += w
        bid = str(m.get("id") or m.get("part_no") or m.get("name") or "?")
        if L >= 6000:
            long_ge_6.append(bid)
        if L >= 4000:
            long_ge_4.append(bid)
        note = str(m.get("note") or "")
        if "crate" in note or "当量" in str(m.get("name") or ""):
            crate_like += 1
        if 0 < H <= 80:
            thin += 1

    n = max(1, len(mats))
    fam_counts = {k: len(v) for k, v in by_fam.items()}
    dominant = max(fam_counts, key=fam_counts.get) if fam_counts else "unknown"
    payload = 28610.0
    n0_weight = max(1, int((net / (payload * 0.92)) + 0.999)) if net > 0 else 1
    max_L = max(lengths) if lengths else 0.0

    # 物料驱动的默认 packing 倾向
    if dominant in ("iron",) or fam_counts.get("iron", 0) >= n * 0.4:
        cargo_mode = "heavy_steel"
    elif dominant in ("aluminum_profile",) or len(long_ge_4) >= n * 0.3:
        cargo_mode = "long_aluminum"
    elif thin >= n * 0.5 or dominant == "aluminum_plate":
        cargo_mode = "thin_plate"
    elif fam_counts.get("fastener", 0) + fam_counts.get("gasket", 0) >= n * 0.5:
        cargo_mode = "small_parts"
    elif crate_like >= n * 0.5:
        cargo_mode = "crate_equiv"
    else:
        cargo_mode = "mixed"

    return {
        "n_lines": len(mats),
        "net_kg": round(net, 1),
        "n0_weight_hint": n0_weight,
        "max_L_mm": max_L,
        "fam_counts": fam_counts,
        "dominant_family": dominant,
        "long_ge_6000": long_ge_6,
        "long_ge_4000_count": len(long_ge_4),
        "crate_like_ratio": round(crate_like / n, 3),
        "thin_ratio": round(thin / n, 3),
        "cargo_mode": cargo_mode,
    }


def _parse_intents(text: str) -> Dict[str, Any]:
    """纯语言意图（与物料无关）。"""
    t = (text or "").strip()
    tl = t.lower()
    intents: Dict[str, Any] = {
        "lock_n": None,
        "plus_n": None,
        "minus_to_n": None,
        "drop_long": False,
        "long_threshold_mm": 6000.0,
        "keep_families": [],  # 只要…
        "drop_families": [],  # 不要…
        "prefer_strict_cog": False,
        "prefer_min_cabin": False,
        "prefer_dense": False,
        "prefer_export": False,
        "site_line": False,
        "factory_line": False,
        "raw": t,
    }

    m = re.search(r"(?:锁|锁定|预算|固定|只要订)\s*(\d+)\s*柜", t)
    if not m:
        m = re.search(r"(?:lock|max)\s*(\d+)\s*(?:cabin|container)?", tl)
    if m:
        intents["lock_n"] = max(1, int(m.group(1)))

    if re.search(r"两柜|两个柜|2\s*柜", t) and intents["lock_n"] is None:
        if re.search(r"锁|预算|工厂|专柜|只要", t):
            intents["lock_n"] = 2
    if re.search(r"一柜|一个柜|1\s*柜|单柜", t) and intents["lock_n"] is None:
        if re.search(r"锁|预算|龙申|刚好|专柜|只要", t):
            intents["lock_n"] = 1

    m2 = re.search(r"(?:少|减少|减)(?:到|至)?\s*(\d+)\s*柜", t)
    if m2 and intents["lock_n"] is None:
        intents["minus_to_n"] = max(1, int(m2.group(1)))
        intents["lock_n"] = intents["minus_to_n"]

    if re.search(r"(?:多|增加|加)\s*(\d+)\s*柜", t) and "锁" not in t:
        m3 = re.search(r"(?:多|增加|加)\s*(\d+)\s*柜", t)
        if m3:
            intents["plus_n"] = int(m3.group(1))

    if re.search(r"去掉超长|排除超长|不要超长|no\s*long|去掉\s*6\s*米", t, re.I):
        intents["drop_long"] = True
        intents["long_threshold_mm"] = 6000.0
    if re.search(r"去掉\s*4\s*米以上|不要\s*4\s*米", t):
        intents["drop_long"] = True
        intents["long_threshold_mm"] = 4000.0

    # 只要某族
    if re.search(r"只要铁|仅铁|只要钢|铁件|iron", t, re.I):
        intents["keep_families"].extend(["iron", "stainless"])
    if re.search(r"只要铝|仅铝|铝板|铝型材", t):
        intents["keep_families"].extend(["aluminum_plate", "aluminum_profile"])
    if re.search(r"只要小料|五金胶条|采购小料", t):
        intents["keep_families"].extend(["fastener", "gasket", "misc"])
    if re.search(r"只要玻璃", t):
        intents["keep_families"].append("glass")

    # 不要某族
    if re.search(r"不要铝|去掉铝|排除铝", t):
        intents["drop_families"].extend(["aluminum_plate", "aluminum_profile"])
    if re.search(r"不要玻璃|去掉玻璃", t):
        intents["drop_families"].append("glass")
    if re.search(r"不要铁|去掉铁", t):
        intents["drop_families"].append("iron")

    if re.search(r"严格|mid50|重心|ctu|中段", t, re.I):
        intents["prefer_strict_cog"] = True
    if re.search(r"最少柜|少柜|压柜", t):
        intents["prefer_min_cabin"] = True
    if re.search(r"密装|直通|当量", t):
        intents["prefer_dense"] = True
    if re.search(r"出运严格|export_strict|严格出运", t, re.I):
        intents["prefer_export"] = True
    if re.search(r"龙申|工地|送工地", t):
        intents["site_line"] = True
    if re.search(r"工厂|送工厂", t):
        intents["factory_line"] = True

    # 去重
    intents["keep_families"] = list(dict.fromkeys(intents["keep_families"]))
    intents["drop_families"] = list(dict.fromkeys(intents["drop_families"]))
    return intents


def select_materials(
    materials: Sequence[Dict[str, Any]],
    intents: Dict[str, Any],
    profile: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """按意图 + 本票画像选料，返回 (选中, 说明)。"""
    notes: List[str] = []
    thr = float(intents.get("long_threshold_mm") or 6000)
    keep = set(intents.get("keep_families") or [])
    drop = set(intents.get("drop_families") or [])
    out: List[Dict[str, Any]] = []
    skipped_long = 0
    skipped_fam = 0

    for m in materials:
        fam = classify_material(m)
        try:
            L = float(m.get("length_mm") or m.get("L") or 0)
        except Exception:
            L = 0.0

        if intents.get("drop_long") and L >= thr:
            skipped_long += 1
            continue
        if drop and fam in drop:
            skipped_fam += 1
            continue
        if keep and fam not in keep:
            # 未知件：若 keep 含 iron 且 kg 大，仍可留
            kg = float(m.get("total_weight_kg") or m.get("weight_kg") or 0)
            if not (fam == "unknown" and "iron" in keep and kg >= 150):
                skipped_fam += 1
                continue
        out.append(dict(m))

    if intents.get("drop_long"):
        if not profile.get("long_ge_6000") and thr >= 6000:
            notes.append(
                f"本票画像 max_L={profile.get('max_L_mm')}mm，"
                f"无≥{thr:.0f}mm 超长件，『去掉超长』对本票无剔除"
            )
        else:
            notes.append(
                f"按本票剔除超长 L≥{thr:.0f}mm：{skipped_long} 行 "
                f"(画像中≥6m共{len(profile.get('long_ge_6000') or [])}件)"
            )
    if keep:
        notes.append(
            f"只保留族 {sorted(keep)}（本票 dominant={profile.get('dominant_family')}），"
            f"命中 {len(out)} 行，剔除 {skipped_fam} 行"
        )
    if drop:
        notes.append(f"排除族 {sorted(drop)}，剔除相关 {skipped_fam} 行")
    if not out and materials:
        notes.append("过滤后为空 → 回退为全量物料，避免空跑")
        out = [dict(m) for m in materials]
    return out, notes


def packing_options_for_cargo(
    profile: Dict[str, Any],
    intents: Dict[str, Any],
    *,
    base_opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """同一句 NL，不同 cargo_mode → 不同 packing_options。"""
    opts = dict(base_opts or {})
    mode = profile.get("cargo_mode") or "mixed"
    opts["single_team_loop"] = True
    opts["multi_start"] = True
    opts["cog_aware"] = True

    if mode == "heavy_steel":
        opts.update(
            {
                "crate_passthrough": True,
                "standard_boxes": False,
                "prefer_stack": True,
                "cog_rebalance": True,
                "lns_worst": True,
                "lateral_repair": True,
                "r4_target_mid50": 0.55,
                "prefer_bottom_weight_kg": 800,
                "scheme_reason": "重钢/铁件为主→当量直通+中段配重+LNS",
            }
        )
    elif mode == "long_aluminum":
        opts.update(
            {
                "dense_mode": True,
                "standard_boxes": False,
                "prefer_stack": False,  # 超长不宜盲目叠
                "cog_rebalance": True,
                "lns_worst": True,
                "lateral_repair": True,
                "clearance_mm": 30,
                "scheme_reason": "超长铝型材为主→密装外廓、少叠高、沿柜长",
            }
        )
    elif mode == "thin_plate":
        opts.update(
            {
                "dense_mode": True,
                "standard_boxes": False,
                "prefer_stack": True,
                "cog_rebalance": True,
                "max_stack_layers": 3,
                "clearance_mm": 20,
                "scheme_reason": "薄板为主→dense 叠层、禁止标准箱撑成 4/6m 架",
            }
        )
    elif mode == "small_parts":
        opts.update(
            {
                "crate_passthrough": True,
                "prefer_stack": True,
                "dense_mode": True,
                "cog_rebalance": True,
                "scheme_reason": "五金/胶条小料→小箱叠高塞缝",
            }
        )
    elif mode == "crate_equiv":
        opts.update(
            {
                "crate_passthrough": True,
                "standard_boxes": False,
                "prefer_stack": True,
                "cog_rebalance": True,
                "lns_worst": True,
                "scheme_reason": "当量箱料→直通禁止二次撑外廓",
            }
        )
    else:
        opts.update(
            {
                "prefer_stack": True,
                "cog_rebalance": True,
                "dense_mode": True,
                "lns_worst": True,
                "lateral_repair": True,
                "scheme_reason": "混装→叠高+密装+CoG 默认",
            }
        )

    # 意图叠加
    if intents.get("prefer_strict_cog") or intents.get("site_line"):
        opts["r4_target_mid50"] = 0.60
        opts["lat_threshold"] = 0.05
        opts["lns_worst"] = True
        opts["lateral_repair"] = True
    if intents.get("prefer_export"):
        opts["export_strict"] = True
        opts["r4_target_mid50"] = max(float(opts.get("r4_target_mid50") or 0.55), 0.60)
    if intents.get("prefer_dense"):
        opts["dense_mode"] = True
    if intents.get("prefer_min_cabin"):
        opts["prefer_stack"] = True
        opts["max_stack_layers"] = max(3, int(opts.get("max_stack_layers") or 3))
    if intents.get("factory_line"):
        opts["dense_mode"] = True
        opts.setdefault("scheme_reason", "")
        opts["scheme_reason"] = (opts.get("scheme_reason") or "") + "|工厂向密装"

    # 锁柜
    lock_n = intents.get("lock_n")
    if lock_n:
        opts["lock_max_containers"] = True
        opts["fixed_container_budget"] = True
        opts["meeting_cap"] = True
        opts["container_budget"] = int(lock_n)
        # 重量是否撑得住
        net = float(profile.get("net_kg") or 0)
        need = profile.get("n0_weight_hint") or 1
        if int(lock_n) < int(need):
            opts["lock_weight_warning"] = (
                f"画像重量柜约{need}，锁定{lock_n}柜可能超重/装不下"
            )

    return opts


def parse_nl_whatif(
    text: str,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    主入口：NL + 可选 materials → 物料相关方案。

    返回:
      intents, material_profile, selected 规则说明,
      scenario(兼容旧字段), max_containers, packing_options, scheme_id, notes
    """
    intents = _parse_intents(text)
    profile = analyze_materials(materials)
    notes: List[str] = []

    notes.append(
        f"物料画像: mode={profile.get('cargo_mode')} dominant={profile.get('dominant_family')} "
        f"行={profile.get('n_lines')} net≈{profile.get('net_kg')}kg "
        f"maxL={profile.get('max_L_mm')} n0重量≈{profile.get('n0_weight_hint')}"
    )

    # 选料（若无 materials，只记意图）
    select_notes: List[str] = []
    if materials:
        _, select_notes = select_materials(materials, intents, profile)
        notes.extend(select_notes)

    opts = packing_options_for_cargo(profile, intents)
    if opts.get("scheme_reason"):
        notes.append(str(opts["scheme_reason"]))
    if opts.get("lock_weight_warning"):
        notes.append("⚠ " + str(opts["lock_weight_warning"]))

    max_c = intents.get("lock_n")
    # 兼容旧 scenario 字段（API/测试）
    if max_c:
        scenario = "lock_containers"
    elif intents.get("keep_families") == ["iron", "stainless"] or (
        intents.get("keep_families") == ["iron"]
    ):
        scenario = "material_family_select"
    elif intents.get("drop_long"):
        scenario = "material_drop_long"
    elif intents.get("prefer_strict_cog"):
        scenario = "strict_mid50"
    elif intents.get("prefer_dense"):
        scenario = "dense_passthrough"
    else:
        scenario = "material_adaptive"

    scheme_id = (
        f"{profile.get('cargo_mode')}"
        f"|lock={max_c or '-'}"
        f"|keep={','.join(intents.get('keep_families') or []) or '-'}"
        f"|drop_long={bool(intents.get('drop_long'))}"
    )

    conf = 0.5
    if materials:
        conf = 0.75
    if max_c or intents.get("keep_families") or intents.get("drop_long"):
        conf = 0.9

    # 兼容 filters 列表（旧 runner）
    filters: List[str] = []
    if intents.get("drop_long"):
        filters.append("no_long")
    if "iron" in (intents.get("keep_families") or []):
        filters.append("keep_iron_family")  # 新语义，不是旧 iron_only 关键字

    return {
        "raw": text,
        "scenario": scenario,
        "scheme_id": scheme_id,
        "max_containers": max_c,
        "filters": filters,
        "profile": (
            "strict_mid50"
            if intents.get("prefer_strict_cog")
            else (
                "export_careful"
                if intents.get("prefer_export")
                else (
                    "min_cabin"
                    if intents.get("prefer_min_cabin")
                    else ""
                )
            )
        ),
        "packing_options": opts,
        "intents": intents,
        "material_profile": profile,
        "selection": {
            "keep_families": intents.get("keep_families"),
            "drop_families": intents.get("drop_families"),
            "drop_long": intents.get("drop_long"),
            "long_threshold_mm": intents.get("long_threshold_mm"),
        },
        "confidence": conf,
        "notes": notes,
    }


def apply_material_selection(
    materials: Sequence[Dict[str, Any]],
    parsed: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """给 whatif runner 调用：按 parse 结果真正筛料。"""
    intents = parsed.get("intents") or _parse_intents(parsed.get("raw") or "")
    profile = parsed.get("material_profile") or analyze_materials(materials)
    return select_materials(materials, intents, profile)
