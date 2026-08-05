"""非标件检验 v2（Tool）：taxonomy 分型 + 分级门禁 + 仪表盘。

schema: nonstandard.inspect.v2
规则算数；LLM 仅可通过物料字段/ns_tags 预注（见 nl_nonstandard_enrich）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from packing_assistant.tools.cargo_feasibility import payload_for_container

# Taxonomy
TAG_DATA_GAP = "DATA_GAP"
TAG_GEO = "GEO_OVERSIZE"
TAG_LOAD = "LOAD_HEAVY"
TAG_SHAPE = "SHAPE_CUSTOM"
TAG_PACK = "PACK_PATH"
TAG_STRUCT = "STRUCT_PENDING"
TAG_PROCESS = "PROCESS_SPECIAL"
TAG_COMPLIANCE = "COMPLIANCE"

LEVEL_ORDER = {"PASS": 0, "INFO": 1, "WARN": 2, "NEED_DESIGN": 3, "FAIL": 4}

DEFAULTS = {
    "overlength_mm": 4000.0,
    "heavy_unit_kg": 200.0,
    "heavy_total_kg": 1500.0,
    "thin_h_mm": 80.0,
    "heavy_box_kg": 1000.0,
    "critical_box_kg": 2000.0,
    "safe_payload_margin": 0.92,
    "top_n": 20,
    "module_like_max_aspect": 2.5,  # 规整模块降噪
}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _thresholds() -> Dict[str, float]:
    thr = dict(DEFAULTS)
    try:
        from packing_assistant.knowledge import load_kb

        kb = load_kb() or {}
        ns = kb.get("nonstandard_thresholds") or {}
        for k in thr:
            if k in ns and ns[k] is not None:
                thr[k] = float(ns[k])
        cats = ((kb.get("materials") or {}).get("categories") or {})
        if cats.get("超长件", {}).get("length_mm_gte") is not None:
            thr["overlength_mm"] = float(cats["超长件"]["length_mm_gte"])
        if cats.get("重件", {}).get("unit_weight_kg_gte") is not None:
            thr["heavy_unit_kg"] = float(cats["重件"]["unit_weight_kg_gte"])
        if cats.get("重件", {}).get("or_total_weight_kg_gte") is not None:
            thr["heavy_total_kg"] = float(cats["重件"]["or_total_weight_kg_gte"])
        if cats.get("薄板", {}).get("height_mm_lte") is not None:
            thr["thin_h_mm"] = float(cats["薄板"]["height_mm_lte"])
    except Exception:
        pass
    return thr


def _container_inner(container_type: str = "40HQ") -> Tuple[float, float, float]:
    ct = (container_type or "40HQ").upper().strip()
    try:
        from packing_assistant.knowledge import container_inner_mm

        m = container_inner_mm().get(ct) or {}
        L, W, H = _f(m.get("L")), _f(m.get("W")), _f(m.get("H"))
        if L > 0 and W > 0 and H > 0:
            return L, W, H
    except Exception:
        pass
    defaults = {
        "20GP": (5898.0, 2352.0, 2385.0),
        "40GP": (12032.0, 2352.0, 2385.0),
        "40HQ": (12032.0, 2352.0, 2698.0),
        "45HQ": (13556.0, 2352.0, 2698.0),
    }
    return defaults.get(ct, defaults["40HQ"])


def _fits_any_standard_box(L: float, W: float, H: float, unit_kg: float) -> Tuple[bool, Optional[str], bool]:
    """返回 (纯落入, 箱名, 可标准加长落入)。"""
    try:
        from packing_assistant.tools.packing import STANDARD_BOX_TYPES, _BOX_ORDER

        order = list(_BOX_ORDER) or list(STANDARD_BOX_TYPES.keys())
        pure = False
        pure_name = None
        extend_ok = False
        extend_name = None
        max_std_L = 0.0
        for name in order:
            spec = STANDARD_BOX_TYPES.get(name) or {}
            od = spec.get("外尺寸_mm") or {}
            bL, bW, bH = _f(od.get("长")), _f(od.get("宽")), _f(od.get("高"))
            max_load = _f(spec.get("最大载荷_kg"), 2000.0)
            if bL <= 0 or bW <= 0 or bH <= 0:
                continue
            max_std_L = max(max_std_L, bL)
            if unit_kg > max_load + 1e-6:
                continue
            if L <= bL + 1e-6 and W <= bW + 1e-6 and H <= bH + 1e-6:
                pure, pure_name = True, name
                break
            # 标准加长：宽高进箱、长可放长（常见超长型钢）
            if W <= bW + 1e-6 and H <= bH + 1e-6 and L <= max(bL * 1.35, bL + 800):
                extend_ok, extend_name = True, name
        if pure:
            return True, pure_name, False
        if extend_ok:
            return False, extend_name, True
        return False, None, False
    except Exception:
        return True, None, False


def _mat_dims(m: Dict[str, Any]) -> Tuple[float, float, float]:
    env = m.get("envelope_mm") or m.get("envelope") or {}
    if isinstance(env, dict) and any(_f(env.get(k)) > 0 for k in ("L", "length", "长", "W", "width", "宽", "H", "height", "高")):
        return (
            _f(env.get("L") or env.get("length") or env.get("长")),
            _f(env.get("W") or env.get("width") or env.get("宽")),
            _f(env.get("H") or env.get("height") or env.get("高")),
        )
    dims = m.get("outer_size_mm") or m.get("外尺寸_mm") or {}
    if isinstance(dims, dict) and any(dims.get(k) for k in ("长", "length", "L", "宽", "width", "高", "height")):
        return (
            _f(dims.get("长") or dims.get("length") or dims.get("L")),
            _f(dims.get("宽") or dims.get("width") or dims.get("W")),
            _f(dims.get("高") or dims.get("height") or dims.get("H")),
        )
    return (
        _f(m.get("length_mm") or m.get("length") or m.get("L")),
        _f(m.get("width_mm") or m.get("width") or m.get("W")),
        _f(m.get("height_mm") or m.get("height") or m.get("H")),
    )


def _mat_weights(m: Dict[str, Any]) -> Tuple[float, float, int]:
    q = max(1, int(_f(m.get("quantity") or m.get("qty") or 1, 1)))
    unit = _f(m.get("weight_kg") or m.get("单重_kg") or m.get("unit_weight_kg"))
    total = _f(m.get("total_weight_kg") or m.get("总重_kg"))
    if total <= 0 and unit > 0:
        total = unit * q
    if unit <= 0 and total > 0 and q > 0:
        unit = total / q
    return unit, total, q


def _bump(cur: str, new: str) -> str:
    return new if LEVEL_ORDER.get(new, 0) > LEVEL_ORDER.get(cur, 0) else cur


def _is_module_like(L: float, W: float, H: float, thr: Dict[str, float]) -> bool:
    """规整密实模块：有尺寸、三边都 >200、长宽比不过分 → 不因「不落标准箱」刷 SHAPE。"""
    if min(L, W, H) < 200:
        return False
    if max(L, W, H) > 2500:
        return False
    aspect = max(L, W) / max(min(L, W), 1.0)
    return aspect <= float(thr.get("module_like_max_aspect") or 2.5)


def _text_blob(m: Dict[str, Any]) -> str:
    parts = [
        m.get("category"),
        m.get("note"),
        m.get("备注"),
        m.get("spec"),
        m.get("规格"),
        m.get("name"),
        m.get("名称"),
    ]
    ns = m.get("ns_tags") or m.get("ns_tags_hint") or []
    if isinstance(ns, (list, tuple)):
        parts.extend(str(x) for x in ns)
    elif ns:
        parts.append(str(ns))
    for k in ("fragile", "this_side_up", "no_stack", "hazard_class"):
        if m.get(k):
            parts.append(k)
    return " ".join(str(x) for x in parts if x).lower()


def inspect_material_row(
    m: Dict[str, Any],
    *,
    container_type: str = "40HQ",
    thr: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    thr = thr or _thresholds()
    mid = str(m.get("id") or m.get("part_no") or m.get("加工件编号") or m.get("name") or "?")
    name = str(m.get("name") or m.get("名称") or mid)
    cat = str(m.get("category") or m.get("类别") or "")
    L, W, H = _mat_dims(m)
    unit, total, qty = _mat_weights(m)
    cL, cW, cH = _container_inner(container_type)
    payload = payload_for_container(container_type)
    safe_cap = payload * float(thr["safe_payload_margin"])
    overlength_mm = float(thr["overlength_mm"])
    heavy_unit = float(thr["heavy_unit_kg"])
    heavy_total = float(thr["heavy_total_kg"])
    thin_h = float(thr["thin_h_mm"])

    tags: List[str] = []
    flags: List[str] = []
    checks: List[Dict[str, Any]] = []
    level = "PASS"
    path_ns = False  # 路径非标（SHAPE/PACK/GEO 硬）
    load_focus = False  # 仅载荷关注

    def add(check_id: str, ok: bool, lev: str, msg: str, tag: Optional[str] = None, *, path: bool = False, load: bool = False) -> None:
        nonlocal level, path_ns, load_focus
        checks.append({"id": check_id, "ok": ok, "level": lev if not ok else "PASS", "message": msg})
        if not ok:
            level = _bump(level, lev)
            flags.append(check_id)
            if tag and tag not in tags:
                tags.append(tag)
            if path:
                path_ns = True
            if load:
                load_focus = True

    # DATA
    missing = [x for x, v in (("L", L), ("W", W), ("H", H)) if v <= 0]
    if missing:
        add("missing_dims", False, "FAIL", f"缺尺寸: {','.join(missing)}", TAG_DATA_GAP, path=True)
    else:
        add("missing_dims", True, "PASS", "长宽高齐全")
    if unit <= 0 and total <= 0:
        add("missing_weight", False, "FAIL", "缺单重/总重", TAG_DATA_GAP, path=True)
    else:
        add("missing_weight", True, "PASS", f"unit={unit:.1f} total={total:.1f} qty={qty}")

    dims_source = str(m.get("dims_source") or "").lower()
    if dims_source in ("estimate", "est", "估算"):
        add("dims_estimate", False, "WARN", "尺寸来源=估算，装前须实测", TAG_DATA_GAP, path=True)

    # GEO
    if L > 0 and L > cL + 1e-6:
        add("over_container_L", False, "FAIL", f"件长 {L:.0f}>{cL:.0f}mm 超柜内", TAG_GEO, path=True)
    elif L >= overlength_mm:
        add("overlength", False, "WARN", f"超长 L={L:.0f}mm", TAG_GEO, path=True)
    if W > 0 and W > cW + 1e-6:
        add("over_container_W", False, "FAIL", f"件宽 {W:.0f}>{cW:.0f}mm", TAG_GEO, path=True)
    if H > 0 and H > cH + 1e-6:
        add("over_container_H", False, "FAIL", f"件高 {H:.0f}>{cH:.0f}mm", TAG_GEO, path=True)

    # LOAD
    if unit > safe_cap + 1e-6:
        add(
            "over_payload_unit",
            False,
            "FAIL",
            f"单件 {unit:.0f}kg > safe {safe_cap:.0f}kg",
            TAG_LOAD,
            path=True,
            load=True,
        )
    elif unit >= heavy_unit or total >= heavy_total:
        add("heavy", False, "WARN", f"重件 unit={unit:.0f} total={total:.0f}", TAG_LOAD, load=True)

    # SHAPE / PACK — 降噪：规整模块不因标准箱刷屏
    module_like = _is_module_like(L, W, H, thr) if L > 0 and W > 0 and H > 0 else False
    if L > 0 and W > 0 and H > 0:
        fit, box_name, extendable = _fits_any_standard_box(L, W, H, unit if unit > 0 else total)
        if fit:
            add("no_standard_box", True, "PASS", f"标准箱: {box_name}")
        elif extendable and not module_like:
            # 标准加长 → INFO，不算主非标列表路径（除非同时超长）
            add(
                "standard_extend",
                False,
                "INFO",
                f"标准箱加长档: {box_name}",
                TAG_SHAPE if L >= overlength_mm else None,
                path=L >= overlength_mm,
            )
        elif not module_like:
            add(
                "no_standard_box",
                False,
                "WARN",
                "无法落入标准箱库 → 定制外廓/铁架",
                TAG_SHAPE,
                path=True,
            )
        else:
            add("no_standard_box", True, "PASS", "规整模块：载荷路径为主，不刷 SHAPE")

    if 0 < H <= thin_h and L >= 1500:
        add("thin_plate", False, "WARN", f"薄板 H={H:.0f}mm", TAG_SHAPE, path=True)

    blob = _text_blob(m)
    pack_kw = ("crate_equiv", "crate=", "factory_stack", "factory_long", "叠层架", "铁件架", "长料架", "当量", "密装架")
    if any(k in blob for k in pack_kw) or cat in ("工厂架",):
        add("factory_crate", False, "WARN", "工厂架/当量路径", TAG_PACK, path=True)

    if cat in ("异形件", "异形") or "异形" in blob or "非标" in blob:
        if TAG_SHAPE not in tags:
            add("marked_shape", False, "WARN", "标记异形/非标", TAG_SHAPE, path=True)

    # PROCESS
    fragile = bool(m.get("fragile")) or any(k in blob for k in ("易碎", "玻璃", "精密", "仪表", "fragile"))
    this_up = bool(m.get("this_side_up")) or any(k in blob for k in ("禁翻", "向上", "this side up", "this_side_up"))
    no_stack = m.get("stackable") is False or bool(m.get("no_stack")) or "禁叠" in blob or "不可叠" in blob
    orient = str(m.get("orientation") or "").lower()
    if fragile or this_up or no_stack or orient in ("this_side_up", "upright"):
        bits = []
        if fragile:
            bits.append("易碎/精密")
        if this_up or orient in ("this_side_up", "upright"):
            bits.append("禁翻/直立")
        if no_stack:
            bits.append("禁叠")
        add("process_special", False, "WARN", "；".join(bits) or "工艺特殊", TAG_PROCESS, path=True)

    lift = str(m.get("lift_points") or "").lower()
    if lift in ("none", "无", "missing"):
        add("no_lift_points", False, "WARN", "吊点缺失", TAG_PROCESS, path=True)

    # COMPLIANCE 预留
    if m.get("hazard_class") or any(k in blob for k in ("危险品", "电池", "锂电池", "hazard", "dg ")):
        add("compliance_hint", False, "WARN", "合规关注（申报边界，仅提示）", TAG_COMPLIANCE, path=True)

    if cat in ("超长件",) and TAG_GEO not in tags and L >= overlength_mm * 0.95:
        if TAG_GEO not in tags:
            tags.append(TAG_GEO)
    if cat in ("重件",) and TAG_LOAD not in tags:
        tags.append(TAG_LOAD)
        load_focus = True
    if cat in ("薄板",) and TAG_SHAPE not in tags:
        tags.append(TAG_SHAPE)
        path_ns = True
    if cat in ("精密件",) and TAG_PROCESS not in tags:
        tags.append(TAG_PROCESS)
        path_ns = True

    # is_nonstandard: 路径非标 或 FAIL/NEED_DESIGN；纯重件 load_focus 也算非标关注
    is_ns = path_ns or level in ("FAIL", "NEED_DESIGN") or (load_focus and level != "PASS")
    # INFO-only standard_extend without other tags → not main ns list
    if level == "INFO" and not path_ns and not load_focus:
        is_ns = False

    primary = tags[0] if tags else None
    advice: List[str] = []
    try:
        from packing_assistant.knowledge import reinforcement_advice

        advice = reinforcement_advice(L, unit, total)
    except Exception:
        pass

    return {
        "id": mid,
        "name": name,
        "category": cat or None,
        "dims_mm": {"L": round(L, 1), "W": round(W, 1), "H": round(H, 1)},
        "unit_kg": round(unit, 2),
        "total_kg": round(total, 2),
        "qty": qty,
        "tags": tags,
        "primary_tag": primary,
        "is_nonstandard": is_ns,
        "is_path_nonstandard": path_ns,
        "is_load_focus": load_focus,
        "level": level,
        "flags": flags,
        "checks": checks,
        "reinforcement_advice": advice,
        "inspect_actions": _actions_for(flags, level, tags),
        "enrich_source": m.get("enrich_source") or "rules",
    }


def _actions_for(flags: List[str], level: str, tags: List[str]) -> List[str]:
    acts: List[str] = []
    if "missing_dims" in flags or "missing_weight" in flags:
        acts.append("补齐尺寸/重量并回填")
    if any(f.startswith("over_container") for f in flags):
        acts.append("评估开顶/框架柜或拆解，禁止硬塞标柜")
    if "overlength" in flags:
        acts.append("沿柜长 + 多点支撑 + 加强绑扎")
    if "over_payload_unit" in flags:
        acts.append("分票/特种运输，不可只加柜")
    if "heavy" in flags:
        acts.append("重下轻上、垫梁、叉车复核")
    if "no_standard_box" in flags or "thin_plate" in flags:
        acts.append("定制外廓/密装当量，结构半严格")
    if "factory_crate" in flags:
        acts.append("禁止二次标准箱撑大，crate 直通")
    if "process_special" in flags:
        acts.append("独立缓冲/禁翻标识/禁叠")
    if "structure_fail" in flags:
        acts.append("改箱后复检结构")
    if "structure_pending" in flags:
        acts.append("补详设截面后复检")
    if level == "FAIL":
        acts.append("阻断自动出运直至整改")
    elif level in ("WARN", "NEED_DESIGN"):
        acts.append("装前人工复核并勾选预检")
    return acts


def inspect_box_row(b: Dict[str, Any], *, container_type: str = "40HQ", thr: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    from packing_assistant.adapters import box_internal_to_api

    thr = thr or _thresholds()
    api = box_internal_to_api(b) if "外尺寸_mm" in b or "箱号" in b else dict(b)
    bid = str(api.get("box_id") or b.get("箱号") or "?")
    special = list(api.get("special_attributes") or b.get("特殊属性") or [])
    outer = api.get("outer_size_mm") or {}
    L = _f(outer.get("length") or outer.get("长"))
    W = _f(outer.get("width") or outer.get("宽"))
    H = _f(outer.get("height") or outer.get("高"))
    gross = _f(api.get("gross_weight_kg") or b.get("毛重_kg"))
    net = _f(api.get("net_weight_kg") or b.get("净重_kg"))
    struct = str(api.get("structure_conclusion") or b.get("结构结论") or "")
    customized = bool(
        api.get("customized_outer")
        or b.get("定制外廓")
        or "定制" in str(api.get("box_type") or "")
        or "当量直通" in special
    )
    cL, cW, cH = _container_inner(container_type)
    safe_cap = payload_for_container(container_type) * float(thr["safe_payload_margin"])

    tags: List[str] = []
    flags: List[str] = []
    checks: List[Dict[str, Any]] = []
    level = "PASS"
    path_ns = False

    def add(cid: str, ok: bool, lev: str, msg: str, tag: Optional[str] = None, *, path: bool = False) -> None:
        nonlocal level, path_ns
        checks.append({"id": cid, "ok": ok, "level": lev if not ok else "PASS", "message": msg})
        if not ok:
            level = _bump(level, lev)
            flags.append(cid)
            if tag and tag not in tags:
                tags.append(tag)
            if path:
                path_ns = True

    if customized:
        add("customized_outer", False, "WARN", "定制/当量外廓箱", TAG_PACK, path=True)
    if "超长" in special or L >= float(thr["overlength_mm"]):
        add("overlength_box", False, "WARN", f"超长箱 L={L:.0f}", TAG_GEO, path=True)
    if L > cL or W > cW or H > cH:
        add("box_exceeds_container", False, "FAIL", f"外廓超柜 {L:.0f}×{W:.0f}×{H:.0f}", TAG_GEO, path=True)
    if net > safe_cap or gross > safe_cap:
        add("box_over_payload", False, "FAIL", f"箱重超 safe", TAG_LOAD, path=True)
    elif gross >= float(thr["critical_box_kg"]):
        add("heavy_box_critical", False, "WARN", f"毛重 {gross:.0f}kg 全项校核", TAG_LOAD)
    elif gross >= float(thr["heavy_box_kg"]):
        add("heavy_box", False, "WARN", f"毛重 {gross:.0f}kg 优先铁箱", TAG_LOAD)

    if struct == "不通过" or "结构不通过" in special:
        add("structure_fail", False, "FAIL", "结构不通过", TAG_STRUCT, path=True)
    elif struct == "待详设" or "待详设" in special:
        add("structure_pending", False, "NEED_DESIGN", "结构待详设", TAG_STRUCT, path=True)
    elif struct == "需加强" or "结构需加强" in special or "需加固" in special:
        add("structure_reinforce", False, "WARN", "结构需加强", TAG_STRUCT, path=True)

    if api.get("section_too_large") or b.get("section_too_large"):
        add("section_too_large", False, "WARN", "截面过大", TAG_SHAPE, path=True)

    is_ns = path_ns or level in ("FAIL", "NEED_DESIGN", "WARN")
    return {
        "box_id": bid,
        "box_type": api.get("box_type") or b.get("箱型"),
        "outer_mm": {"L": round(L, 1), "W": round(W, 1), "H": round(H, 1)},
        "gross_kg": round(gross, 1),
        "net_kg": round(net, 1),
        "special_attributes": special,
        "structure_conclusion": struct,
        "tags": tags,
        "primary_tag": tags[0] if tags else None,
        "is_nonstandard": is_ns,
        "level": level,
        "flags": flags,
        "checks": checks,
        "inspect_actions": _actions_for(flags, level, tags),
    }


def _build_dashboard(
    mat_rows: List[Dict[str, Any]],
    box_rows: List[Dict[str, Any]],
    *,
    top_n: int,
) -> Dict[str, Any]:
    by_tag: Dict[str, int] = {}
    by_level: Dict[str, int] = {"PASS": 0, "INFO": 0, "WARN": 0, "NEED_DESIGN": 0, "FAIL": 0}
    for r in mat_rows:
        by_level[r.get("level") or "PASS"] = by_level.get(r.get("level") or "PASS", 0) + 1
        for t in r.get("tags") or []:
            by_tag[t] = by_tag.get(t, 0) + 1
    for r in box_rows:
        for t in r.get("tags") or []:
            by_tag[f"box:{t}"] = by_tag.get(f"box:{t}", 0) + 1

    # top risks: non-pass materials first by severity
    ranked = sorted(
        [r for r in mat_rows if r.get("level") not in ("PASS",) or r.get("is_nonstandard")],
        key=lambda x: (-LEVEL_ORDER.get(x.get("level") or "PASS", 0), x.get("id") or ""),
    )
    top = []
    for r in ranked[:top_n]:
        top.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "level": r.get("level"),
                "tags": r.get("tags") or [],
                "primary_tag": r.get("primary_tag"),
                "dims_mm": r.get("dims_mm"),
                "unit_kg": r.get("unit_kg"),
                "flags": r.get("flags") or [],
                "action": "；".join((r.get("inspect_actions") or [])[:2]),
                "lane": "path" if r.get("is_path_nonstandard") else ("load" if r.get("is_load_focus") else "other"),
            }
        )

    n_path = sum(1 for r in mat_rows if r.get("is_path_nonstandard"))
    n_load = sum(1 for r in mat_rows if r.get("is_load_focus"))
    return {
        "n_materials": len(mat_rows),
        "n_boxes": len(box_rows),
        "n_nonstandard_materials": sum(1 for r in mat_rows if r.get("is_nonstandard")),
        "n_path_nonstandard": n_path,
        "n_load_focus": n_load,
        "n_nonstandard_boxes": sum(1 for r in box_rows if r.get("is_nonstandard")),
        "by_tag": by_tag,
        "by_level": by_level,
        "top_risks": top,
        "counts_for_ui": {
            "overlength": by_tag.get(TAG_GEO, 0),
            "heavy": by_tag.get(TAG_LOAD, 0),
            "custom_shape": by_tag.get(TAG_SHAPE, 0) + by_tag.get(TAG_PACK, 0),
            # 仅 structure_pending 旗标，不含「需加强」WARN，避免口播与 overall 不一致
            "struct_pending": sum(
                1
                for r in mat_rows + box_rows
                if "structure_pending" in (r.get("flags") or [])
            ),
            "struct_reinforce": sum(
                1
                for r in mat_rows + box_rows
                if "structure_reinforce" in (r.get("flags") or [])
            ),
            "data_gap": by_tag.get(TAG_DATA_GAP, 0),
            "process": by_tag.get(TAG_PROCESS, 0),
        },
    }


def _build_checklist(mat_rows: List[Dict[str, Any]], box_rows: List[Dict[str, Any]], overall: str) -> Dict[str, Any]:
    all_rows = mat_rows + box_rows
    has = lambda *fs: any(any(f in (r.get("flags") or []) for f in fs) for r in all_rows)
    has_tag = lambda *ts: any(any(t in (r.get("tags") or []) for t in ts) for r in all_rows)
    items = [
        {"id": "ns_dims", "label": "非标件三边尺寸与重量已核实", "required": True, "auto_hint": "缺项" if has("missing_dims", "missing_weight", "dims_estimate") else "OK"},
        {"id": "ns_photo", "label": "非标件实物拍照（铭牌/吊点/支点）已归档", "required": True, "auto_hint": "人工"},
        {"id": "ns_overlength", "label": "超长件装载与支撑方案已确认", "required": has_tag(TAG_GEO) or has("overlength", "overlength_box"), "auto_hint": "适用" if has_tag(TAG_GEO) else "N/A"},
        {"id": "ns_heavy", "label": "重件垫梁/叉车/集中载荷已确认", "required": has_tag(TAG_LOAD) or has("heavy", "heavy_box", "heavy_box_critical"), "auto_hint": "适用" if has_tag(TAG_LOAD) else "N/A"},
        {"id": "ns_custom", "label": "定制箱/铁架图纸与结构校核已确认", "required": has_tag(TAG_SHAPE, TAG_PACK, TAG_STRUCT) or has("customized_outer", "structure_pending"), "auto_hint": "适用" if has_tag(TAG_SHAPE, TAG_PACK, TAG_STRUCT) else "N/A"},
        {"id": "ns_process", "label": "易碎/禁翻/禁叠工艺已落实", "required": has_tag(TAG_PROCESS), "auto_hint": "适用" if has_tag(TAG_PROCESS) else "N/A"},
        {"id": "ns_lashing", "label": "非标绑扎/限位点已标在工单", "required": overall not in ("PASS", "INFO"), "auto_hint": "人工"},
        {"id": "ns_por", "label": "POR/装箱单与非标件号一致", "required": True, "auto_hint": "人工"},
        {"id": "ns_design_ack", "label": "已知悉结构待详设（非正式签章）", "required": overall == "NEED_DESIGN" or has("structure_pending"), "auto_hint": "适用" if overall == "NEED_DESIGN" else "N/A"},
    ]
    return {"schema": "nonstandard.checklist.v2", "items": items, "overall_hint": overall}


def inspect_nonstandard(
    *,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    boxes: Optional[Sequence[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
    case_id: str = "",
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    thr = _thresholds()
    opts = dict(packing_options or {})
    mat_rows = [
        inspect_material_row(dict(m), container_type=container_type, thr=thr)
        for m in (materials or [])
        if isinstance(m, dict)
    ]
    box_rows = [
        inspect_box_row(dict(b), container_type=container_type, thr=thr)
        for b in (boxes or [])
        if isinstance(b, dict)
    ]

    fails = [r for r in mat_rows + box_rows if r.get("level") == "FAIL"]
    need = [r for r in mat_rows + box_rows if r.get("level") == "NEED_DESIGN"]
    warns = [r for r in mat_rows + box_rows if r.get("level") == "WARN"]
    # 任何 structure_pending 旗标 → 至少 NEED_DESIGN（与口播「待详设」一致）
    has_pending = any(
        "structure_pending" in (r.get("flags") or []) for r in mat_rows + box_rows
    )
    if fails:
        overall = "FAIL"
    elif need or has_pending:
        overall = "NEED_DESIGN"
    elif warns or any(r.get("is_nonstandard") for r in mat_rows):
        overall = "WARN"
    else:
        overall = "PASS"

    top_n = int(opts.get("ns_top_n") or thr.get("top_n") or 20)
    dashboard = _build_dashboard(mat_rows, box_rows, top_n=top_n)
    checklist = _build_checklist(mat_rows, box_rows, overall)

    n = max(len(mat_rows), 1)
    ns_ratio = dashboard["n_nonstandard_materials"] / n
    path_ratio = dashboard["n_path_nonstandard"] / n
    strategy_hints: List[str] = []
    if path_ratio >= 0.4 or ns_ratio >= 0.5:
        strategy_hints.append("nonstandard_ratio_high→建议 crate_passthrough / 定制外廓，避免盲目 standard_boxes")
    if dashboard["counts_for_ui"].get("overlength", 0) > 0:
        strategy_hints.append("存在超长：拼柜沿柜长、multi 时注意 mid50")
    if overall == "FAIL":
        strategy_hints.append("存在 FAIL：整改前勿自动出运")

    strict = bool(opts.get("strict_nonstandard_gate"))
    ship_gate = {
        "blocks_auto_ship": overall == "FAIL",
        "blocks_confirm_to_team_b": strict and overall == "FAIL",
        "requires_human_review": overall in ("FAIL", "NEED_DESIGN", "WARN"),
        "strict_nonstandard_gate": strict,
        "note": (
            "存在 FAIL：禁止自动出运"
            if overall == "FAIL"
            else (
                "待详设：可演示，非正式结构签章"
                if overall == "NEED_DESIGN"
                else (
                    "有非标/告警：装前人工复核"
                    if overall == "WARN"
                    else "检验通过（正式出运仍建议预检表）"
                )
            )
        ),
    }

    flag_counts: Dict[str, int] = {}
    for r in mat_rows + box_rows:
        for f in r.get("flags") or []:
            flag_counts[f] = flag_counts.get(f, 0) + 1

    full = {
        "schema": "nonstandard.inspect.v2",
        "tool": "nonstandard_inspect",
        "case_id": case_id or None,
        "container_type": (container_type or "40HQ").upper(),
        "overall": overall,
        "dashboard": dashboard,
        "summary": {
            "n_materials": dashboard["n_materials"],
            "n_boxes": dashboard["n_boxes"],
            "n_nonstandard_materials": dashboard["n_nonstandard_materials"],
            "n_nonstandard_boxes": dashboard["n_nonstandard_boxes"],
            "n_fail": len(fails),
            "n_need_design": len(need),
            "n_warn": len(warns),
            "n_pass_materials": sum(1 for r in mat_rows if r.get("level") == "PASS"),
            "flag_counts": flag_counts,
            "ns_ratio": round(ns_ratio, 3),
            "path_ratio": round(path_ratio, 3),
        },
        "materials": mat_rows,
        "boxes": box_rows,
        "nonstandard_materials": [r for r in mat_rows if r.get("is_nonstandard")],
        "nonstandard_boxes": [r for r in box_rows if r.get("is_nonstandard")],
        "path_nonstandard_materials": [r for r in mat_rows if r.get("is_path_nonstandard")],
        "load_focus_materials": [r for r in mat_rows if r.get("is_load_focus")],
        "checklist": checklist,
        "ship_gate": ship_gate,
        "strategy_hints": strategy_hints,
        "thresholds_used": thr,
    }
    return full


def public_summary(report: Dict[str, Any], *, top_n: int = 20) -> Dict[str, Any]:
    """API/前端轻量摘要，避免 359 行全量。"""
    if not report:
        return {}
    dash = dict(report.get("dashboard") or {})
    top = list(dash.get("top_risks") or [])[:top_n]
    dash["top_risks"] = top
    return {
        "schema": "nonstandard.inspect.v2.summary",
        "overall": report.get("overall"),
        "container_type": report.get("container_type"),
        "case_id": report.get("case_id"),
        "dashboard": dash,
        "summary": report.get("summary"),
        "checklist": report.get("checklist"),
        "ship_gate": report.get("ship_gate"),
        "strategy_hints": report.get("strategy_hints") or [],
        "top_risks": top,
    }


def report_markdown(report: Dict[str, Any]) -> str:
    s = report.get("summary") or {}
    d = report.get("dashboard") or {}
    ui = d.get("counts_for_ui") or {}
    lines = [
        "# 非标件检验报告 v2",
        "",
        f"- **case**: {report.get('case_id') or '-'}",
        f"- **柜型**: {report.get('container_type')}",
        f"- **总判定**: **{report.get('overall')}**",
        f"- 物料 {s.get('n_materials')} · 非标 **{s.get('n_nonstandard_materials')}** "
        f"(路径 {d.get('n_path_nonstandard')} / 载荷 {d.get('n_load_focus')}) · "
        f"FAIL {s.get('n_fail')} · NEED_DESIGN {s.get('n_need_design')} · WARN {s.get('n_warn')}",
        f"- 成箱 {s.get('n_boxes')} · 非标箱 **{s.get('n_nonstandard_boxes')}**",
        "",
        f"**出运门禁**: {(report.get('ship_gate') or {}).get('note')}",
        "",
        "## 仪表盘",
        "",
        f"| 超长 | 重件 | 定制/形状 | 结构 | 数据缺口 | 工艺 |",
        f"|-----:|-----:|----------:|-----:|---------:|-----:|",
        f"| {ui.get('overlength',0)} | {ui.get('heavy',0)} | {ui.get('custom_shape',0)} | "
        f"{ui.get('struct_pending',0)} | {ui.get('data_gap',0)} | {ui.get('process',0)} |",
        "",
        "### by_tag",
        "",
        "| tag | count |",
        "|-----|------:|",
    ]
    for k, v in sorted((d.get("by_tag") or {}).items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} |")
    if not d.get("by_tag"):
        lines.append("| _(无)_ | 0 |")

    hints = report.get("strategy_hints") or []
    if hints:
        lines += ["", "## 策略提示", ""]
        for h in hints:
            lines.append(f"- {h}")

    lines += ["", "## Top 风险", ""]
    top = d.get("top_risks") or report.get("top_risks") or []
    if not top:
        lines.append("_无_")
    else:
        lines += [
            "| id | level | tags | lane | L×W×H | kg | 动作 |",
            "|----|-------|------|------|-------|---:|------|",
        ]
        for r in top:
            dims = r.get("dims_mm") or {}
            ds = f"{dims.get('L',0):.0f}×{dims.get('W',0):.0f}×{dims.get('H',0):.0f}"
            lines.append(
                f"| {r.get('id')} | {r.get('level')} | {','.join(r.get('tags') or [])} | "
                f"{r.get('lane')} | {ds} | {r.get('unit_kg')} | {r.get('action') or ''} |"
            )

    lines += ["", "## 装运检验勾选", ""]
    for it in (report.get("checklist") or {}).get("items") or []:
        req = "必填" if it.get("required") else "可选"
        lines.append(f"- [ ] **{it.get('label')}** （{req} · {it.get('auto_hint')}）")

    lines += [
        "",
        "---",
        "_schema nonstandard.inspect.v2 · `packing_assistant.tools.nonstandard_inspect`_",
    ]
    return "\n".join(lines) + "\n"


def run_and_attach(
    state: Dict[str, Any],
    *,
    enrich: bool = False,
) -> Dict[str, Any]:
    """供 Team A 调用：可选 enrich → inspect → 写 state 字段。"""
    mats = list(state.get("materials") or [])
    if enrich:
        try:
            from packing_assistant.tools.nl_nonstandard_enrich import enrich_materials

            mats = enrich_materials(mats)
            state = {**state, "materials": mats}
        except Exception:
            pass
    ctype = str(state.get("container_type") or "40HQ")
    opts = dict(state.get("packing_options") or {})
    # 高非标时给 box_scheme 的提示写进 opts 建议（不强制改用户选项）
    rep = inspect_nonstandard(
        materials=mats,
        boxes=state.get("boxes") or [],
        container_type=ctype,
        case_id=str(state.get("session_id") or state.get("packing_plan_id") or ""),
        packing_options=opts,
    )
    summary = public_summary(rep)
    out = {
        "nonstandard_report": rep,
        "nonstandard_summary": summary,
    }
    if rep.get("strategy_hints"):
        notes = list(state.get("structure_notes") or [])
        for h in rep["strategy_hints"]:
            if h not in notes:
                notes.append(f"[非标] {h}")
        out["structure_notes"] = notes
    return out
