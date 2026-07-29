"""
装箱工具：材料清单 → 木箱/铁箱方案（含结构计算）。

流程：
1. 规范化材料尺寸/重量
2. 按几何与载荷选型（或升级箱型）
3. 尝试合箱（同箱型、载荷与空间允许）
4. 对每箱执行 structure_calc.run_structure_calc
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from packing_assistant.knowledge import clearance_mm, merge_rules, standard_box_types_for_packing
from packing_assistant.tools.structure_calc import (
    orient_dims,
    run_structure_calc,
)

# 标准箱型库 ← knowledge/packing_knowledge_base.json
STANDARD_BOX_TYPES: Dict[str, Dict[str, Any]] = standard_box_types_for_packing()

# 选型优先级：由短到长（标准名）
_BOX_ORDER = [
    "1.1米铁架",
    "1.1米框",
    "铁笼",
    "2米铁架",
    "2米框",
    "3米木箱",
    "4米铁架",
    "4米框",
    "6米铁架",
    "6米框",
]
_BOX_ORDER = [n for n in _BOX_ORDER if n in STANDARD_BOX_TYPES]

CLEARANCE_MM = clearance_mm()


def _inner_dims(spec: Dict[str, Any]) -> Dict[str, float]:
    outer = spec["外尺寸_mm"]
    t = float(spec.get("壁厚_mm") or 40)
    # 底盘较厚：高度方向双倍壁厚近似
    return {
        "长": max(float(outer["长"]) - 2 * t, 0),
        "宽": max(float(outer["宽"]) - 2 * t, 0),
        "高": max(float(outer["高"]) - 2 * t, 0),
    }


def _normalize_material(mat: Dict[str, Any], idx: int) -> Dict[str, Any]:
    dims = mat.get("外尺寸_mm") or {}
    L, W, H = orient_dims(dims.get("长"), dims.get("宽"), dims.get("高"))
    qty = max(int(mat.get("数量") or 1), 1)
    unit = float(mat.get("单重_kg") or 0)
    total = mat.get("总重_kg")
    if total is None:
        total = qty * unit
    else:
        total = float(total)
    return {
        "名称": mat.get("名称") or mat.get("规格") or f"材料-{idx}",
        "规格": mat.get("规格") or "",
        "数量": qty,
        "单重_kg": unit,
        "总重_kg": round(total, 3),
        "外尺寸_mm": {"长": L, "宽": W, "高": H},
        "备注": mat.get("备注") or "",
        "加工件编号": mat.get("加工件编号") or mat.get("编号") or "",
    }


def _item_fits_box(
    item: Dict[str, Any],
    box_name: str,
    *,
    allow_length_extend: bool = False,
) -> bool:
    spec = STANDARD_BOX_TYPES[box_name]
    inner = _inner_dims(spec)
    d = item["外尺寸_mm"]
    need_L = d["长"] + CLEARANCE_MM
    need_a = d["宽"] + CLEARANCE_MM
    need_b = d["高"] + CLEARANCE_MM
    inn_L, inn_W, inn_H = inner["长"], inner["宽"], inner["高"]
    # 标准加长：允许货长略超标准内长（外长会放长，挠度按实际外长算，优于硬跳 6m）
    if need_L > inn_L + 1e-6:
        if not allow_length_extend:
            return False
        # 最多比标准外长多 20% 或 +800mm
        outer_L = float(spec["外尺寸_mm"]["长"])
        max_ext = max(outer_L * 1.2, outer_L + 800.0)
        if need_L + 2 * float(spec.get("壁厚_mm") or 40) > max_ext + 1e-6:
            return False
    # 单件截面两种朝向
    return (need_a <= inn_W and need_b <= inn_H) or (
        need_a <= inn_H and need_b <= inn_W
    )


def _weight_fits(items: List[Dict[str, Any]], box_name: str) -> bool:
    net = sum(float(i.get("总重_kg") or 0) for i in items)
    return net <= float(STANDARD_BOX_TYPES[box_name]["最大载荷_kg"]) + 1e-6


def _standard_tier_candidates(content_long_mm: float) -> List[str]:
    """按货长推荐标准箱档（允许该档加长），从短到长。"""
    L = float(content_long_mm or 0)
    if L <= 1050:
        cands = ["1.1米铁架", "1.1米框", "铁笼", "2米铁架"]
    elif L <= 1950:
        cands = ["2米铁架", "2米框", "铁笼", "3米木箱"]
    elif L <= 2900:
        # 2.5m 级：优先 4m 铁架（高 1750 截面够用）；3m 木箱偏矮易装不下
        cands = ["4米铁架", "4米框", "3米木箱", "2米铁架", "铁笼"]
    elif L <= 4500:
        # 4.2m 货优先 4 米档加长，勿直接跳 6m（跨距过大易挠度不过）
        cands = ["4米铁架", "4米框", "6米铁架", "6米框"]
    else:
        cands = ["6米铁架", "6米框", "4米铁架"]
    return [n for n in cands if n in STANDARD_BOX_TYPES]


def _pick_box_type_for_item(item: Dict[str, Any], *, standard: bool = False) -> str:
    """选能装下单件几何 + 重量的最小箱型；都不行则用最大并交结构计算暴露问题。"""
    rules = merge_rules()
    L = float(item.get("外尺寸_mm", {}).get("长") or 0)
    if standard:
        for name in _standard_tier_candidates(L):
            if _item_fits_box(item, name, allow_length_extend=True) and _weight_fits(
                [item], name
            ):
                return name
        for name in _standard_tier_candidates(L):
            if _item_fits_box(item, name, allow_length_extend=True):
                return name
        return "6米铁架" if "6米铁架" in STANDARD_BOX_TYPES else (
            _BOX_ORDER[-1] if _BOX_ORDER else "6米铁架"
        )
    # 超长优先 6 米框
    if L >= float(rules.get("solo_overlong_mm") or 5000):
        for name in ("6米框", "6米铁架"):
            if name in STANDARD_BOX_TYPES:
                return name
    for name in _BOX_ORDER:
        if name not in STANDARD_BOX_TYPES:
            continue
        if _item_fits_box(item, name) and _weight_fits([item], name):
            return name
    for name in _BOX_ORDER:
        if name in STANDARD_BOX_TYPES and _item_fits_box(item, name):
            return name
    return _BOX_ORDER[-1] if _BOX_ORDER else "6米铁架"


def _pick_box_type_for_items(
    items: List[Dict[str, Any]], *, standard: bool = False
) -> str:
    if not items:
        return "4米铁架"
    longest = max(items, key=lambda x: float(x["外尺寸_mm"]["长"]))
    name = _pick_box_type_for_item(longest, standard=standard)
    # 重量不够则升级
    if not _weight_fits(items, name):
        up = _upgrade_box(name, items)
        if up:
            return up
    return name


def _can_merge(
    existing: List[Dict[str, Any]],
    new_item: Dict[str, Any],
    box_name: str,
    *,
    aggressive: bool = True,
    allow_reinforce: bool = False,
    max_combined_net_kg: Optional[float] = None,
    dense: bool = False,
    standard: bool = False,
    container_type: str = "40HQ",
) -> bool:
    """合箱前做重量 + 结构几何试算；aggressive 时放宽填充率与试算箱外廓。"""
    trial = existing + [new_item]
    net = sum(float(i.get("总重_kg") or 0) for i in trial)
    if max_combined_net_kg is not None and net > float(max_combined_net_kg) + 1e-6:
        return False
    if not _weight_fits(trial, box_name):
        return False
    spec = STANDARD_BOX_TYPES[box_name]
    wall = float(spec.get("壁厚_mm") or 40)
    # standard：按标准库外廓试算；否则允许货包络定制外廓
    outer, inner, _ = _fit_outer_to_cargo(
        dict(spec["外尺寸_mm"]),
        wall,
        trial,
        aggressive=aggressive,
        container_type=container_type,
        dense=dense and not standard,
        standard=standard,
    )
    max_len = max(float(i["外尺寸_mm"]["长"]) for i in trial)
    if max_len + CLEARANCE_MM > inner["长"] + 1e-6:
        return False
    vol_items = sum(
        i["外尺寸_mm"]["长"] * i["外尺寸_mm"]["宽"] * i["外尺寸_mm"]["高"] * i["数量"]
        for i in trial
    )
    vol_box = inner["长"] * inner["宽"] * inner["高"]
    # dense 贴货后内腔紧，允许更高填充率
    fill_cap = 0.995 if dense else (0.98 if aggressive else 0.85)
    if vol_box > 0 and vol_items > vol_box * fill_cap:
        return False

    trial_struct = run_structure_calc(
        box_type=box_name,
        outer_mm=outer,
        inner_mm=inner,
        tare_kg=float(spec["自重_kg"]),
        max_payload_kg=float(spec["最大载荷_kg"]),
        is_steel_frame=bool(spec.get("铁架")),
        items=trial,
    )
    if not trial_struct.get("几何", {}).get("尺寸适配"):
        return False
    conclusion = trial_struct.get("结论") or "不通过"
    if conclusion == "不通过":
        return False
    if conclusion == "需加强" and not (allow_reinforce or aggressive):
        return False
    return True


def _bin_net_kg(b: Dict[str, Any]) -> float:
    return sum(float(x.get("总重_kg") or 0) for x in (b.get("items") or []))


def _bin_max_len(b: Dict[str, Any]) -> float:
    items = b.get("items") or []
    if not items:
        return 0.0
    return max(float(x["外尺寸_mm"]["长"]) for x in items)


def _band_merge_net_cap(band: str, *, standard: bool = False) -> float:
    """同长度档再合并时的单箱净重上限（结构可过的实务值）。"""
    if standard:
        # 标准跨距挠度更紧，合箱净重更保守
        return {
            "6m": 480.0,
            "4m": 560.0,
            "3m": 900.0,
            "2m": 1400.0,
            "1m": 1800.0,
        }.get(band, 1000.0)
    return {
        "6m": 580.0,   # 约 60 支×9.5kg 级，已实测可过
        "4m": 1200.0,
        "3m": 1600.0,
        "2m": 1800.0,
        "1m": 2000.0,
    }.get(band, 1500.0)


def _cargo_envelope_mm(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """件体外包络（长=最长件，截面积货架堆码）。"""
    from packing_assistant.tools.structure_calc import cargo_envelope

    return cargo_envelope(items)


def _snap_module(val: float, modules: List[float], lo: float, hi: float) -> float:
    v = max(lo, min(float(val), hi))
    for m in modules:
        if v <= m <= hi:
            return float(m)
    return v


def _fit_outer_to_cargo(
    base_outer: Dict[str, float],
    wall_mm: float,
    items: List[Dict[str, Any]],
    *,
    aggressive: bool = True,
    container_type: str = "40HQ",
    dense: bool = False,
    standard: bool = False,
) -> Tuple[Dict[str, float], Dict[str, float], bool]:
    """
    确定箱外廓。

    - standard：锁定标准箱库外廓（知识库 1.1/2/3/4/6 米铁架等），仅超标长时放长。
    - aggressive：卡拼柜模块（宽1150 / 层高1100~1200），便于二层对齐。
    - dense：外廓贴货（薄板密装），短件可缩小外廓。
    """
    env = _cargo_envelope_mm(items)
    gap = float(CLEARANCE_MM)
    wall = float(wall_mm or 40)
    need_L = float(env.get("长") or 0) + gap + 2 * wall
    need_W = float(env.get("宽") or 0) + gap + 2 * wall
    need_H = float(env.get("高") or 0) + gap + 2 * wall
    # 柜内可装上限
    max_L, max_W, max_H = 12000.0, 2300.0, 2650.0
    ct = (container_type or "40HQ").upper()
    # 二层模块高：保证 2 层能进柜
    stack_module_h = 1100.0 if ct in ("20GP", "40GP") else 1200.0
    content_long = max((float(i["外尺寸_mm"]["长"]) for i in items), default=0)

    # —— 标准箱库外廓（优先）——
    if standard:
        outer = {
            "长": float(base_outer.get("长") or 0),
            "宽": float(base_outer.get("宽") or 0),
            "高": float(base_outer.get("高") or 0),
        }
        customized = False
        # 只按「最长单件」决定是否加长，不用多件并排后的 env 长
        # （否则小垫片会把 1.1m 箱虚拉成 2.7m）
        piece_need_L = content_long + gap + 2 * wall
        if piece_need_L > outer["长"] + 1e-6:
            step = 50.0
            outer["长"] = min(math.ceil(piece_need_L / step) * step, max_L)
            customized = True  # 标准加长
        inner = {
            "长": max(outer["长"] - 2 * wall, 0),
            "宽": max(outer["宽"] - 2 * wall, 0),
            "高": max(outer["高"] - 2 * wall, 0),
        }
        return outer, inner, customized

    outer = {
        "长": min(max(need_L, 600.0 if dense else 800.0), max_L),
        "宽": min(max(need_W, 400.0 if dense else 600.0), max_W),
        "高": min(max(need_H, 200.0 if dense else 500.0), max_H),
    }
    customized = True
    # 货高很矮（薄板叠层仍 <400）→ 密装时绝不拉到 1.2m 模块高
    flat_cargo = need_H <= (450.0 if dense else 0.0)

    if aggressive and not dense:
        if need_W <= 1180:
            outer["宽"] = 1150.0
        else:
            outer["宽"] = min(max(need_W, 2200.0), max_W)
        # 二层堆：单层高度 = stack_module_h（可被货高顶高）
        target_h = max(need_H, stack_module_h)
        if content_long >= 5000:
            target_h = min(max(need_H, 1000.0), stack_module_h)
        outer["高"] = min(target_h, stack_module_h if need_H <= stack_module_h else min(need_H, max_H))
        if need_H <= stack_module_h:
            outer["高"] = stack_module_h  # 统一层高，便于二层对齐
        step = 100.0
        outer["长"] = min(math.ceil(max(need_L, outer["长"]) / step) * step, max_L)
        if content_long < 2800:
            outer["长"] = max(outer["长"], min(3000.0, max_L))
        elif content_long < 4000:
            outer["长"] = max(outer["长"], min(4000.0, max_L))
    elif dense:
        # 混合密装：
        # - 超长件(≥5m)：仍用半柜宽+二层模块高（几何/结构需要，否则合箱全炸）
        # - 中长件：半柜宽 + 略矮于模块高
        # - 短件/薄板：真正贴货，缩小外廓以便柜内多件并排/多层
        pad = 40.0
        step = 50.0
        longish = content_long >= 5000
        midlong = content_long >= 3500

        if longish or midlong:
            # ≥3.5m：与 aggressive 同形 1150×模块高（合箱几何/挠度依赖此截面）
            # 仅外长贴货：50mm 步进 + 余量，避免虚拉到标准 6m/4m 整数档
            outer["宽"] = 1150.0 if need_W <= 1180 else min(max(need_W + pad, 2200.0), max_W)
            outer["高"] = min(max(need_H, stack_module_h), max_H)
            if need_H <= stack_module_h:
                outer["高"] = stack_module_h
            # 长：货长+间隙+壁厚+余量；中长不低于 need_L
            base_L = max(need_L, content_long + gap + 2 * wall + 50.0)
            outer["长"] = min(math.ceil(base_L / step) * step, max_L)
            # 短于 2.8m 的中长件仍略抬长便于并排工位（与 aggressive 一致的下限可略降）
            if content_long < 2800:
                outer["长"] = max(outer["长"], min(2800.0, max_L))
        else:
            # 短件/薄板：真正贴货，缩小外廓以便柜内多件并排/多层
            if need_W > 1180:
                outer["宽"] = min(max(need_W + pad, 2200.0), max_W)
            elif need_W >= 900:
                outer["宽"] = 1150.0
            else:
                outer["宽"] = min(
                    math.ceil(max(need_W + pad, 400.0) / step) * step, max_W
                )
            min_h = 220.0 if flat_cargo else 350.0
            outer["高"] = min(max(need_H + pad, min_h), max_H)
            if need_H >= 900:
                outer["高"] = min(max(outer["高"], min(need_H + pad, stack_module_h)), max_H)
            outer["长"] = min(math.ceil(max(need_L, 600.0) / step) * step, max_L)

    outer["长"] = min(max(outer["长"], need_L), max_L)
    outer["宽"] = min(max(outer["宽"], need_W), max_W)
    outer["高"] = min(max(outer["高"], need_H), max_H)

    # 几何兜底：保证 envelope+间隙 能进内腔（含截面旋转判定）
    # 否则 dense 合箱会被 structure 几何直接否掉
    inn_L = max(outer["长"] - 2 * wall, 0)
    inn_W = max(outer["宽"] - 2 * wall, 0)
    inn_H = max(outer["高"] - 2 * wall, 0)
    geo_need_L = float(env.get("长") or 0) + gap
    geo_need_W = float(env.get("宽") or 0) + gap
    geo_need_H = float(env.get("高") or 0) + gap
    if geo_need_L > inn_L + 1e-6:
        outer["长"] = min(math.ceil((geo_need_L + 2 * wall + 20.0) / 50.0) * 50.0, max_L)
        inn_L = max(outer["长"] - 2 * wall, 0)
    # 默认朝向或旋转朝向至少一种通过
    fit_def = geo_need_W <= inn_W + 1e-6 and geo_need_H <= inn_H + 1e-6
    fit_rot = geo_need_W <= inn_H + 1e-6 and geo_need_H <= inn_W + 1e-6
    if not (fit_def or fit_rot):
        # 优先加高使旋转或默认通过
        need_inn_h = max(geo_need_H, min(geo_need_W, max_H - 2 * wall))
        outer["高"] = min(max(outer["高"], need_inn_h + 2 * wall + 20.0), max_H)
        inn_H = max(outer["高"] - 2 * wall, 0)
        fit_def = geo_need_W <= inn_W + 1e-6 and geo_need_H <= inn_H + 1e-6
        fit_rot = geo_need_W <= inn_H + 1e-6 and geo_need_H <= inn_W + 1e-6
        if not (fit_def or fit_rot):
            outer["宽"] = min(max(outer["宽"], geo_need_W + 2 * wall + 20.0), max_W)

    inner = {
        "长": max(outer["长"] - 2 * wall, 0),
        "宽": max(outer["宽"] - 2 * wall, 0),
        "高": max(outer["高"] - 2 * wall, 0),
    }
    return outer, inner, customized


def _display_box_type(base_name: str, outer: Dict[str, float], customized: bool) -> str:
    """
    展示名与真实外长对齐，避免「6米铁架」实际只有 4.3m。
    结构计算仍用 base_name（标准截面库）。
    """
    L = float(outer.get("长") or 0)
    if L >= 5500:
        tier = "6米"
    elif L >= 3500:
        tier = "4米"
    elif L >= 2500:
        tier = "3米"
    elif L >= 1500:
        tier = "2米"
    else:
        tier = "1.1米"
    # 材质后缀
    if "木" in base_name:
        kind = "木箱"
    elif "笼" in base_name:
        kind = "铁笼"
    elif "框" in base_name and "铁架" not in base_name:
        kind = "框"
    else:
        kind = "铁架"
    name = f"{tier}{kind}"
    if customized:
        name = f"{name}(定制)"
    return name


def _build_box(
    box_no: str,
    box_name: str,
    items: List[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    dense: bool = False,
    standard: bool = False,
    design_facts: Optional[Dict[str, Any]] = None,
    _upgrade_depth: int = 0,
    _tried_types: Optional[set] = None,
) -> Dict[str, Any]:
    tried = set(_tried_types or set())
    # 选最近标准型作为结构截面/自重基准；standard 时按货长档选型（可加长）
    if box_name not in STANDARD_BOX_TYPES:
        box_name = (
            _pick_box_type_for_item(items[0], standard=standard)
            if items
            else "4米铁架"
        )
    if standard and items:
        # 每次（含升级重试）按货长档重选型；升级深度>0 时仅允许不短于当前
        picked = _pick_box_type_for_items(items, standard=True)
        if _upgrade_depth == 0:
            box_name = picked
        else:
            # 升级路径：若重选型不短于当前则采用，避免退回过短箱
            cur_L = float(
                (STANDARD_BOX_TYPES.get(box_name) or {}).get("外尺寸_mm", {}).get("长")
                or 0
            )
            pk_L = float(
                (STANDARD_BOX_TYPES.get(picked) or {}).get("外尺寸_mm", {}).get("长")
                or 0
            )
            if pk_L + 1e-6 >= cur_L and picked not in tried:
                box_name = picked
    tried.add(box_name)
    spec = STANDARD_BOX_TYPES[box_name]
    wall = float(spec.get("壁厚_mm") or 40)
    outer, inner, customized = _fit_outer_to_cargo(
        dict(spec["外尺寸_mm"]),
        wall,
        items,
        aggressive=True,
        container_type=container_type,
        dense=dense and not standard,
        standard=standard,
    )
    # 标准模式展示名用库名，仅加长时标注
    if standard and not customized:
        display_type = box_name
    else:
        display_type = _display_box_type(box_name, outer, customized)
        if standard and customized:
            display_type = f"{box_name}(标准加长)"

    tare = float(spec["自重_kg"])
    # 定制加宽/加长时自重略增
    if customized:
        base_v = (
            float(spec["外尺寸_mm"]["长"])
            * float(spec["外尺寸_mm"]["宽"])
            * float(spec["外尺寸_mm"]["高"])
        )
        new_v = outer["长"] * outer["宽"] * outer["高"]
        if base_v > 0 and new_v > base_v:
            tare = round(tare * min(new_v / base_v, 1.8), 1)
    max_payload = float(spec["最大载荷_kg"])
    is_steel = bool(spec.get("铁架"))
    from packing_assistant.knowledge import safety_factor_for_box

    sf = float(spec.get("安全系数") or safety_factor_for_box(box_name, 0))

    struct = run_structure_calc(
        box_type=box_name,
        outer_mm=outer,
        inner_mm=inner,
        tare_kg=tare,
        max_payload_kg=max_payload,
        is_steel_frame=is_steel,
        items=items,
        safety_factor=sf,
        box_id=box_no,
        design_facts=design_facts,
    )
    try:
        from packing_assistant.tools.structure_calc import attach_calc_report_md

        struct = attach_calc_report_md(struct, outer_mm=outer)
    except Exception:
        pass

    weights = struct["重量"]
    special: List[str] = []
    content_max_L = 0.0
    for it in items:
        dims = it.get("外尺寸_mm") or {}
        content_max_L = max(content_max_L, float(dims.get("长") or 0))
    if content_max_L >= 4000 or any(
        "超长" in str(it.get("备注") or "") for it in items
    ):
        # 按内容物长度，而非箱外廓
        special.append("内容物超长")
        special.append("超长")  # 兼容规划/装载旧规则
    if weights["毛重_kg"] > 2000:
        special.append("超重关注")
    if struct["结论"] == "需加强":
        special.append("结构需加强")
    if struct["结论"] == "不通过":
        special.append("结构不通过")
    if struct["结论"] == "待详设":
        special.append("待详设")
        special.append("结构需加强")
    if struct.get("fidelity") == "detailed_design":
        special.append("详设截面")
    if customized and not standard:
        special.append("定制外廓")
    if customized and standard:
        special.append("标准加长")
    if standard:
        special.append("标准箱库")
    if dense and not standard:
        special.append("密装外廓")
    if not struct["几何"]["尺寸适配"]:
        special.append("尺寸紧张")

    # dense 贴货后结构不过：先抬外高（结构截面深度），再升级箱型
    if dense and not standard and struct["结论"] == "不通过":
        for bump_h in (900.0, 1100.0, 1200.0, 1400.0):
            if outer["高"] >= bump_h - 1e-6:
                continue
            outer2 = dict(outer)
            outer2["高"] = min(bump_h, 2650.0)
            inner2 = {
                "长": max(outer2["长"] - 2 * wall, 0),
                "宽": max(outer2["宽"] - 2 * wall, 0),
                "高": max(outer2["高"] - 2 * wall, 0),
            }
            struct2 = run_structure_calc(
                box_type=box_name,
                outer_mm=outer2,
                inner_mm=inner2,
                tare_kg=tare,
                max_payload_kg=max_payload,
                is_steel_frame=is_steel,
                items=items,
                safety_factor=sf,
                box_id=box_no,
                design_facts=design_facts,
            )
            if struct2.get("结论") != "不通过":
                outer, inner, struct = outer2, inner2, struct2
                try:
                    from packing_assistant.tools.structure_calc import attach_calc_report_md

                    struct = attach_calc_report_md(struct, outer_mm=outer)
                except Exception:
                    pass
                weights = struct["重量"]
                special = [s for s in special if s != "结构不通过"]
                if struct["结论"] == "需加强" and "结构需加强" not in special:
                    special.append("结构需加强")
                special.append("密装抬高过结构")
                break

    # 结构/几何不过：尝试换箱（有深度/已试集合，防死循环）
    # 注意：挠度超限时禁止升到更长跨距（4m 货进 6m 箱只会更差）
    risk_txt = " ".join(str(x) for x in (struct.get("风险点") or []))
    deflect_fail = "挠度" in risk_txt
    geo_fail = not bool(struct.get("几何", {}).get("尺寸适配"))
    hard_fail = struct["结论"] == "不通过" or geo_fail
    if _upgrade_depth < 4 and hard_fail:
        upgraded = None
        cur_L = float((STANDARD_BOX_TYPES[box_name]["外尺寸_mm"]).get("长") or 0)
        # 几何不过 → 只试更长/更高的标准箱；挠度不过 → 禁止更长，只试同档替换
        if geo_fail and not deflect_fail:
            upgraded = _upgrade_box(box_name, items)
        if (not upgraded or upgraded in tried) and standard:
            for alt in _BOX_ORDER:
                if alt in tried or alt not in STANDARD_BOX_TYPES:
                    continue
                alt_L = float((STANDARD_BOX_TYPES[alt]["外尺寸_mm"]).get("长") or 0)
                alt_H = float((STANDARD_BOX_TYPES[alt]["外尺寸_mm"]).get("高") or 0)
                cur_H = float((STANDARD_BOX_TYPES[box_name]["外尺寸_mm"]).get("高") or 0)
                if deflect_fail and alt_L > cur_L + 1e-6:
                    continue
                if geo_fail and alt_L < cur_L - 1e-6 and alt_H <= cur_H + 1e-6:
                    continue  # 几何失败至少要更长或更高
                if deflect_fail and alt_L + 1e-6 < cur_L:
                    continue  # 挠度失败不要无下掉到更短箱
                if all(
                    _item_fits_box(it, alt, allow_length_extend=True) for it in items
                ) and _weight_fits(items, alt):
                    upgraded = alt
                    break
        if upgraded and upgraded not in tried:
            return _build_box(
                box_no,
                upgraded,
                items,
                container_type=container_type,
                dense=dense,
                standard=standard,
                design_facts=design_facts,
                _upgrade_depth=_upgrade_depth + 1,
                _tried_types=tried,
            )

    content = [
        {
            "名称": it["名称"],
            "规格": it.get("规格") or "",
            "数量": it["数量"],
            "单重_kg": it["单重_kg"],
            "总重_kg": it.get("总重_kg"),
            "外尺寸_mm": it["外尺寸_mm"],
            "备注": it.get("备注") or "",
            "加工件编号": it.get("加工件编号") or "",
        }
        for it in items
    ]

    # 加固文案：优先 summary.reinforcement_plan
    reinf = ""
    summary = struct.get("summary") or {}
    if summary.get("reinforcement_plan"):
        reinf = "；".join(summary["reinforcement_plan"][:3])
    elif struct.get("section_used"):
        reinf = str((struct.get("section_used") or {}).get("bottom_beam") or "")

    # 箱内货填充率（件体积 / 箱内体积）— 与柜容积利用率区分
    cargo_vol = sum(
        float(it["外尺寸_mm"]["长"])
        * float(it["外尺寸_mm"]["宽"])
        * float(it["外尺寸_mm"]["高"])
        * float(it["数量"])
        for it in items
    )
    outer_vol = float(outer["长"]) * float(outer["宽"]) * float(outer["高"])
    inner_vol = max(inner["长"] * inner["宽"] * inner["高"], 1)
    fill_ratio = min(cargo_vol / inner_vol, 1.0)
    fill_outer = min(cargo_vol / max(outer_vol, 1), 1.0)
    # 订柜有效体积：与 volume_estimate.pack_k_for_fill 统一（按 fill_outer 选 k）
    try:
        from packing_assistant.tools.volume_estimate import pack_k_for_fill

        k_eff = pack_k_for_fill(fill_outer, k_max=1.60)
    except Exception:
        k_eff = 1.35 if fill_outer < 0.20 else (1.50 if fill_outer < 0.35 else 1.60)
    if cargo_vol <= 1e-6:
        booking_vol = outer_vol * 0.45
    else:
        booking_vol = min(outer_vol, cargo_vol * k_eff)

    # 二层堆码：矮箱/非超长可叠；超长仅底层；dense 矮箱可多层
    stackable = bool(
        outer["高"] <= (1500 if dense else 1300)
        and content_max_L < 4000
        and "超长" not in special
        and struct["结论"] != "不通过"
    )
    prefer_bottom = bool(content_max_L >= 4000 or weights["毛重_kg"] >= 2000)
    # max_stack_layers：本箱作为「塔」的层数上限；不可叠则为 1
    # prefer_bottom 仍可承重，不把层数砍成 1（否则压不住上层）
    if not stackable or content_max_L >= 4000 or "超长" in special:
        max_stack_layers = 1
    elif dense and outer["高"] <= 900:
        max_stack_layers = 3
    else:
        max_stack_layers = 2

    return {
        "箱号": box_no,
        "箱型": display_type,
        "外尺寸_mm": {k: round(v, 1) for k, v in outer.items()},
        "内尺寸_mm": {k: round(v, 1) for k, v in inner.items()},
        "净重_kg": weights["净重_kg"],
        "箱自重_kg": weights["箱自重_kg"],
        "毛重_kg": weights["毛重_kg"],
        "设计载荷_kg": max_payload,
        "装载内容": content,
        "特殊属性": special,
        "结构计算": struct,
        "结构结论": struct["结论"],
        "reinforcement": reinf,
        "crate_fill_ratio": round(fill_ratio, 4),
        "fill_outer_ratio": round(fill_outer, 4),
        "content_m3": round(cargo_vol / 1e9, 6),
        "outer_m3": round(outer_vol / 1e9, 6),
        "booking_volume_m3": round(booking_vol / 1e9, 6),
        "customized_outer": customized,
        "dense_outer": bool(dense and not standard),
        "standard_outer": bool(standard),
        "base_box_type": box_name,
        "content_max_length_mm": round(content_max_L, 1),
        "stackable": stackable,
        "prefer_bottom": prefer_bottom,
        "max_stack_layers": max_stack_layers,
        # 新版结构化摘要（API 友好）
        "structure_detail": {
            "safety_factor_gamma": struct.get("safety_factor_gamma"),
            "design_load_kg": struct.get("design_load_kg"),
            "section_used": struct.get("section_used"),
            "bottom_bending": struct.get("bottom_bending"),
            "frame_stability": struct.get("frame_stability"),
            "local_bearing": struct.get("local_bearing"),
            "lifting_points": struct.get("lifting_points"),
            "summary": summary,
        },
    }


def _upgrade_box(current: str, items: List[Dict[str, Any]]) -> Optional[str]:
    try:
        idx = _BOX_ORDER.index(current)
    except ValueError:
        return None
    for name in _BOX_ORDER[idx + 1 :]:
        if _weight_fits(items, name):
            # 几何尽量适配最长件
            longest = max(items, key=lambda x: x["外尺寸_mm"]["长"])
            if _item_fits_box(longest, name):
                return name
            # 仍返回更大箱，让结构计算记录风险
            return name
    return None


def _max_qty_for_crate(item: Dict[str, Any], max_box_net_kg: float) -> int:
    """
    单箱允许件数：净重上限 ∩ 可堆高度/截面启发式。
    长杆沿柜长独排时，截面堆码高度控制在 ~1100mm；薄板叠层同理。
    """
    qty = max(int(item.get("数量") or 1), 1)
    unit = float(item.get("单重_kg") or 0)
    total = float(item.get("总重_kg") or unit * qty)
    if unit <= 0 and qty > 0:
        unit = total / qty
    cap = float(max_box_net_kg or 3200)
    by_w = qty
    if unit > 0 and cap > 0:
        by_w = max(1, int(cap // unit))

    dims = item.get("外尺寸_mm") or {}
    L = float(dims.get("长") or 0)
    W = float(dims.get("宽") or 0)
    H = float(dims.get("高") or 0)
    # 薄板叠高
    th = min(W, H) if W > 0 and H > 0 else max(H, 1)
    face = max(W, H)
    stack_h = 1100.0
    by_geom = qty
    if face >= 400 and th <= 80:
        # 铝板/玻璃：短件允许更高叠层（单箱可高，不必为二层模块砍半）
        panel_stack = 2000.0 if L <= 2200 else stack_h
        by_geom = max(1, int(panel_stack // max(th, 1)))
        if face >= 1000:
            by_geom = min(by_geom, max(1, int(1200 // max(th, 1))))
        if face >= 1100:
            # 大面玻璃仍限层，防木箱超高失稳
            by_geom = min(by_geom, 12)
    elif L >= 3500:
        # 长杆：截面堆码 + 跨距限重（6m 梁挠度敏感，净重宜 ≤800kg 级）
        cross = max(min(W, H), 20)
        n_w = max(1, int(1000 // cross))
        n_h = max(1, int(stack_h // cross))
        by_geom = max(1, n_w * n_h // 2)  # 半满，留绑扎
        # 6m 框：预拆偏轻，便于同长度小箱再合并到 ~580kg
        long_cap = 280.0 if L >= 5000 else 900.0
        if unit > 0:
            by_w = min(by_w, max(1, int(min(cap, long_cap) // unit)))
    else:
        by_geom = max(1, int(stack_h // max(min(W, H), 50)) * 4)

    # 薄板叠层再限净重（板架弯曲）
    if face >= 400 and th <= 80 and unit > 0:
        by_w = min(by_w, max(1, int(min(cap, 1500.0) // unit)))

    return max(1, min(qty, by_w, by_geom))


def _explode_items_by_net_cap(
    items: List[Dict[str, Any]],
    max_box_net_kg: float,
) -> List[Dict[str, Any]]:
    """
    按单箱净重 + 几何可装件数拆分材料行。
    避免 2000+ 件铝型材合成 1 箱 20t / 超高堆 → 结构必败。
    """
    cap = float(max_box_net_kg or 0)
    if cap <= 0:
        return items
    out: List[Dict[str, Any]] = []
    for it in items:
        qty = max(int(it.get("数量") or 1), 1)
        unit = float(it.get("单重_kg") or 0)
        total = float(it.get("总重_kg") or unit * qty)
        if unit <= 0 and qty > 0:
            unit = total / qty
        max_qty = _max_qty_for_crate(it, cap)
        if max_qty >= qty and total <= cap + 1e-6:
            row = dict(it)
            row["总重_kg"] = round(total, 3)
            out.append(row)
            continue
        if max_qty >= qty:
            max_qty = max(1, qty // 2)
        remaining = qty
        part = 0
        base_name = str(it.get("名称") or "材料")
        base_id = str(it.get("加工件编号") or it.get("id") or "M")
        while remaining > 0:
            part += 1
            q = min(max_qty, remaining)
            chunk = dict(it)
            chunk["数量"] = q
            chunk["单重_kg"] = unit
            chunk["总重_kg"] = round(unit * q, 3)
            chunk["名称"] = base_name if part == 1 and q == qty else f"{base_name}(拆{part})"
            chunk["加工件编号"] = f"{base_id}-S{part}"
            chunk["id"] = chunk["加工件编号"]
            chunk["备注"] = (
                str(it.get("备注") or "") + f";split_net<={cap:.0f}kg,q<={max_qty}"
            ).strip(";")
            out.append(chunk)
            remaining -= q
    return out


def _band_rank(band: str) -> int:
    return {"1m": 1, "2m": 2, "3m": 3, "4m": 4, "6m": 5}.get(band, 0)


def _can_cross_band_mix(
    host_max_len: float,
    guest_max_len: float,
    *,
    mix_mode: bool,
) -> bool:
    """
    跨长度档混装规则：
    - mix_mode 关：仅同档（与旧逻辑一致；≥2.5m 不同档禁止）
    - mix_mode 开：短件可塞进更长档标准箱（guest_rank <= host_rank）；
      禁止把更长件硬塞进更短档（除非同档）
    """
    hb = _length_band(host_max_len)
    gb = _length_band(guest_max_len)
    if hb == gb:
        return True
    if not mix_mode:
        # 旧逻辑：短档可互混，长档隔离
        return max(host_max_len, guest_max_len) < 2500
    # 混装：只允许「短 → 长」
    return _band_rank(gb) <= _band_rank(hb)


def run_packing(
    materials: List[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    max_box_net_kg: float = 3200.0,
    revision_mode: bool = False,
    dense_mode: bool = False,
    standard_boxes: bool = True,
    mix_mode: bool = True,
    design_facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    装箱算法入口（含结构计算）。

    输入: materials 列表；container_type 影响二层模块高度
    max_box_net_kg: 单箱净重上限，超则按件数拆分（结构打回后可再降）
    standard_boxes: True（默认）锁知识库标准箱外廓，不贴货定制
    mix_mode: True（默认）允许短件混入更长档标准箱填空
    dense_mode: True 时外廓贴货（与 standard 互斥，standard 优先）
    design_facts: 详设结构事实（截面/γ/图纸）；无则结论「待详设」不可正式出运
    输出: {
      "箱子列表": [... 含 结构计算 ...],
      "结构汇总": {...}
    }
    """
    if not materials:
        return {"箱子列表": [], "结构汇总": _empty_summary()}

    ctype = container_type or "40HQ"
    standard = bool(standard_boxes)
    dense = bool(dense_mode) and not standard
    mix = bool(mix_mode)
    d_facts = design_facts
    # 打回改箱：更严载荷，优先结构通过
    cap = float(max_box_net_kg or 3200.0)
    if revision_mode:
        cap = min(cap, 2500.0)
    items = [_normalize_material(m, i) for i, m in enumerate(materials, start=1)]
    # 标准箱按跨距结构更严：长件单独压低净重上限再拆分，避免 4m 货误装过重
    if standard:
        exploded: List[Dict[str, Any]] = []
        for it in items:
            L = float(it["外尺寸_mm"]["长"])
            # 标准箱截面净空有限，长件/中长件单箱件数（净重）更严
            if L >= 5000:
                local_cap = min(cap, 480.0)
            elif L >= 3500:
                local_cap = min(cap, 560.0)
            elif L >= 2500:
                local_cap = min(cap, 400.0)  # 约 8×45kg，避免截面装不下
            elif L >= 1500:
                local_cap = min(cap, 700.0)
            else:
                local_cap = cap
            exploded.extend(_explode_items_by_net_cap([it], local_cap))
        items = exploded
    else:
        items = _explode_items_by_net_cap(items, cap)
    # 长件优先，但激进合箱
    items_sorted = sorted(items, key=lambda x: (-x["外尺寸_mm"]["长"], -x["总重_kg"]))

    bins: List[Dict[str, Any]] = []

    for it in items_sorted:
        placed = False
        # 超长/超重强制独箱起步，靠后轮合并（避免一次装太满导致挠度）
        solo = (
            it["外尺寸_mm"]["长"] >= 5000
            or it["总重_kg"] >= min(2500.0, cap * 0.9)
        )
        if not solo:
            cand = sorted(
                bins,
                key=lambda b: -sum(float(x.get("总重_kg") or 0) for x in b["items"]),
            )
            for b in cand:
                max_b = max(float(x["外尺寸_mm"]["长"]) for x in b["items"])
                if not _can_cross_band_mix(
                    max_b, it["外尺寸_mm"]["长"], mix_mode=mix
                ):
                    continue
                if _can_merge(
                    b["items"],
                    it,
                    b["box_name"],
                    aggressive=True,
                    dense=dense,
                    standard=standard,
                    container_type=ctype,
                ):
                    b["items"].append(it)
                    placed = True
                    break
                upgraded = _upgrade_box(b["box_name"], b["items"] + [it])
                if upgraded and _can_merge(
                    b["items"],
                    it,
                    upgraded,
                    aggressive=True,
                    dense=dense,
                    standard=standard,
                    container_type=ctype,
                ):
                    b["box_name"] = upgraded
                    b["items"].append(it)
                    placed = True
                    break
        if not placed:
            box_name = _pick_box_type_for_item(it, standard=standard)
            bins.append({"box_name": box_name, "items": [it]})

    bins_before_merge = len(bins)
    # 二轮：同长度档合并
    bins = _aggressive_merge_bins(
        bins,
        same_length_band_only=True,
        dense=dense,
        standard=standard,
        container_type=ctype,
    )
    # 三轮：同长度小箱再合并
    bins = _merge_same_length_small_bins(
        bins, dense=dense, standard=standard, container_type=ctype
    )
    # 四轮：跨长度档混装（短箱并入长箱填空）
    if mix:
        bins = _merge_cross_band_mix(
            bins, dense=dense, standard=standard, container_type=ctype
        )
    bins_after_merge = len(bins)

    force_bt = None
    if isinstance(d_facts, dict):
        force_bt = (d_facts.get("defaults") or {}).get("force_box_type")
    boxes: List[Dict[str, Any]] = []
    for i, b in enumerate(bins, start=1):
        bname = force_bt or b["box_name"]
        boxes.append(
            _build_box(
                f"BOX-{i:02d}",
                bname,
                b["items"],
                container_type=ctype,
                dense=dense,
                standard=standard,
                design_facts=d_facts,
            )
        )

    summary = _structure_summary(boxes)
    try:
        from packing_assistant.tools.design_facts import facts_status_summary

        summary["design_facts_status"] = facts_status_summary(d_facts)
    except Exception:
        pass
    if standard and mix:
        mode = "standard_box_library+cross_length_mix"
    elif standard:
        mode = "standard_box_library"
    elif dense:
        mode = "dense_hug_cargo+same_length_small_merge"
    else:
        mode = "aggressive_fcl_two_layer+same_length_small_merge"
    summary["packing_mode"] = mode
    summary["dense_mode"] = dense
    summary["standard_boxes"] = standard
    summary["mix_mode"] = mix
    summary["container_type_for_module"] = ctype
    summary["max_box_net_kg"] = cap
    summary["revision_mode"] = bool(revision_mode)
    summary["item_chunks_after_split"] = len(items)
    summary["bins_before_merge"] = bins_before_merge
    summary["bins_after_merge"] = bins_after_merge
    summary["merged_away"] = max(0, bins_before_merge - bins_after_merge)
    # 箱外廓体积 vs 货实体体积，便于解释利用率
    outer_vol = sum(
        float(bx["外尺寸_mm"]["长"])
        * float(bx["外尺寸_mm"]["宽"])
        * float(bx["外尺寸_mm"]["高"])
        for bx in boxes
    )
    cargo_vol = sum(
        float(it["外尺寸_mm"]["长"])
        * float(it["外尺寸_mm"]["宽"])
        * float(it["外尺寸_mm"]["高"])
        * float(it["数量"])
        for bx in boxes
        for it in (bx.get("装载内容") or [])
    )
    summary["boxes_outer_volume_m3"] = round(outer_vol / 1e9, 4)
    summary["cargo_item_volume_m3"] = round(cargo_vol / 1e9, 4)
    summary["avg_crate_fill"] = round(
        (cargo_vol / outer_vol) if outer_vol > 0 else 0.0, 4
    )
    # 标准箱型分布
    by_type: Dict[str, int] = {}
    for bx in boxes:
        bt = str(bx.get("base_box_type") or bx.get("箱型") or "?")
        by_type[bt] = by_type.get(bt, 0) + 1
    summary["standard_box_type_counts"] = by_type
    return {"箱子列表": boxes, "结构汇总": summary}


def _length_band(mm: float) -> str:
    if mm >= 5000:
        return "6m"
    if mm >= 3500:
        return "4m"
    if mm >= 2500:
        return "3m"
    if mm >= 1500:
        return "2m"
    return "1m"


def _try_absorb_bin(
    host: Dict[str, Any],
    guest: Dict[str, Any],
    *,
    allow_reinforce: bool = True,
    max_combined_net_kg: Optional[float] = None,
    dense: bool = False,
    standard: bool = False,
    container_type: str = "40HQ",
) -> Optional[Dict[str, Any]]:
    """尝试把 guest 整箱并入 host；成功返回新 bin，失败 None。"""
    trial_items = list(host["items"])
    trial_name = host["box_name"]
    for it in guest["items"]:
        if _can_merge(
            trial_items,
            it,
            trial_name,
            aggressive=True,
            allow_reinforce=allow_reinforce,
            max_combined_net_kg=max_combined_net_kg,
            dense=dense,
            standard=standard,
            container_type=container_type,
        ):
            trial_items.append(it)
            continue
        up = _upgrade_box(trial_name, trial_items + [it])
        if up and _can_merge(
            trial_items,
            it,
            up,
            aggressive=True,
            allow_reinforce=allow_reinforce,
            max_combined_net_kg=max_combined_net_kg,
            dense=dense,
            standard=standard,
            container_type=container_type,
        ):
            trial_name = up
            trial_items.append(it)
            continue
        return None
    return {"box_name": trial_name, "items": trial_items}


def _aggressive_merge_bins(
    bins: List[Dict[str, Any]],
    *,
    same_length_band_only: bool = True,
    dense: bool = False,
    standard: bool = False,
    container_type: str = "40HQ",
) -> List[Dict[str, Any]]:
    """箱间合并：默认只合同长度档，保持多箱并排/堆叠以吃满柜。"""
    if len(bins) <= 1:
        return bins
    changed = True
    guard = 0
    while changed and guard < 12:
        guard += 1
        changed = False
        bins = sorted(bins, key=lambda b: -_bin_net_kg(b))
        out: List[Dict[str, Any]] = []
        used = [False] * len(bins)
        for i, bi in enumerate(bins):
            if used[i]:
                continue
            cur = {"box_name": bi["box_name"], "items": list(bi["items"])}
            max_i = _bin_max_len(cur)
            band_i = _length_band(max_i)
            net_cap = _band_merge_net_cap(band_i, standard=standard)
            for j in range(i + 1, len(bins)):
                if used[j]:
                    continue
                bj = bins[j]
                max_j = _bin_max_len(bj)
                if same_length_band_only and band_i != _length_band(max_j):
                    continue
                if _bin_net_kg(cur) + _bin_net_kg(bj) > net_cap + 1e-6:
                    continue
                merged = _try_absorb_bin(
                    cur,
                    bj,
                    allow_reinforce=True,
                    max_combined_net_kg=net_cap,
                    dense=dense,
                    standard=standard,
                    container_type=container_type,
                )
                if merged:
                    cur = merged
                    max_i = _bin_max_len(cur)
                    band_i = _length_band(max_i)
                    net_cap = _band_merge_net_cap(band_i, standard=standard)
                    used[j] = True
                    changed = True
            used[i] = True
            out.append(cur)
        bins = out
    return bins


def _merge_same_length_small_bins(
    bins: List[Dict[str, Any]],
    *,
    small_net_ratio: float = 0.72,
    max_rounds: int = 16,
    dense: bool = False,
    standard: bool = False,
    container_type: str = "40HQ",
) -> List[Dict[str, Any]]:
    """
    同长度小箱再合并：
    - 仅合同长度档
    - 优先合并「轻箱」（净重 < 档位上限 × small_net_ratio）
    - 合并后净重不超过档位上限
    - 结构「需加强」允许，硬「不通过」不允许
    """
    if len(bins) <= 1:
        return bins

    def is_small(b: Dict[str, Any]) -> bool:
        band = _length_band(_bin_max_len(b))
        cap = _band_merge_net_cap(band, standard=standard)
        return _bin_net_kg(b) <= cap * small_net_ratio + 1e-6

    changed = True
    guard = 0
    while changed and guard < max_rounds:
        guard += 1
        changed = False
        # 轻箱优先做 host，便于吞并其它轻箱
        bins = sorted(bins, key=lambda b: (_bin_net_kg(b), -_bin_max_len(b)))
        out: List[Dict[str, Any]] = []
        used = [False] * len(bins)
        for i, bi in enumerate(bins):
            if used[i]:
                continue
            cur = {"box_name": bi["box_name"], "items": list(bi["items"])}
            band = _length_band(_bin_max_len(cur))
            net_cap = _band_merge_net_cap(band, standard=standard)
            # 非小箱也可作 host 吃小 guest
            for j in range(i + 1, len(bins)):
                if used[j]:
                    continue
                bj = bins[j]
                if _length_band(_bin_max_len(bj)) != band:
                    continue
                # 至少一方是小箱，避免两大箱硬刚
                if not (is_small(cur) or is_small(bj)):
                    continue
                if _bin_net_kg(cur) + _bin_net_kg(bj) > net_cap + 1e-6:
                    continue
                merged = _try_absorb_bin(
                    cur,
                    bj,
                    allow_reinforce=True,
                    max_combined_net_kg=net_cap,
                    dense=dense,
                    standard=standard,
                    container_type=container_type,
                )
                if not merged:
                    # host/guest 对调再试（箱型不同时有时更易过）
                    merged = _try_absorb_bin(
                        {"box_name": bj["box_name"], "items": list(bj["items"])},
                        cur,
                        allow_reinforce=True,
                        max_combined_net_kg=net_cap,
                        dense=dense,
                        standard=standard,
                        container_type=container_type,
                    )
                if merged:
                    cur = merged
                    band = _length_band(_bin_max_len(cur))
                    net_cap = _band_merge_net_cap(band, standard=standard)
                    used[j] = True
                    changed = True
            used[i] = True
            out.append(cur)
        bins = out
    return bins


def _merge_cross_band_mix(
    bins: List[Dict[str, Any]],
    *,
    max_rounds: int = 12,
    dense: bool = False,
    standard: bool = False,
    container_type: str = "40HQ",
) -> List[Dict[str, Any]]:
    """
    跨长度档混装：把更短/更轻的整箱并入更长档标准箱填空。
    例：2m 短支撑 + 垫片 → 并入未满的 4m 铁架。
    """
    if len(bins) <= 1:
        return bins
    changed = True
    guard = 0
    while changed and guard < max_rounds:
        guard += 1
        changed = False
        # host：更长更重优先；guest：更短更轻优先
        bins = sorted(bins, key=lambda b: (-_bin_max_len(b), -_bin_net_kg(b)))
        out: List[Dict[str, Any]] = []
        used = [False] * len(bins)
        for i, bi in enumerate(bins):
            if used[i]:
                continue
            cur = {"box_name": bi["box_name"], "items": list(bi["items"])}
            host_L = _bin_max_len(cur)
            host_band = _length_band(host_L)
            net_cap = _band_merge_net_cap(host_band, standard=standard)
            for j in range(i + 1, len(bins)):
                if used[j]:
                    continue
                bj = bins[j]
                guest_L = _bin_max_len(bj)
                if not _can_cross_band_mix(host_L, guest_L, mix_mode=True):
                    continue
                # 只吸更短或同档的 guest
                if _band_rank(_length_band(guest_L)) > _band_rank(host_band):
                    continue
                if _bin_net_kg(cur) + _bin_net_kg(bj) > net_cap + 1e-6:
                    continue
                # 已较满的 host 不再硬塞（留余量给结构）
                if _bin_net_kg(cur) > net_cap * 0.88:
                    continue
                merged = _try_absorb_bin(
                    cur,
                    bj,
                    allow_reinforce=True,
                    max_combined_net_kg=net_cap,
                    dense=dense,
                    standard=standard,
                    container_type=container_type,
                )
                if merged:
                    cur = merged
                    host_L = _bin_max_len(cur)
                    host_band = _length_band(host_L)
                    net_cap = _band_merge_net_cap(host_band, standard=standard)
                    used[j] = True
                    changed = True
            used[i] = True
            out.append(cur)
        bins = out
    return bins


def _empty_summary() -> Dict[str, Any]:
    return {
        "箱数": 0,
        "通过": 0,
        "需加强": 0,
        "不通过": 0,
        "总净重_kg": 0,
        "总毛重_kg": 0,
        "结论": "无箱子",
    }


def _structure_summary(boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
    cnt = {"通过": 0, "需加强": 0, "不通过": 0}
    net = gross = 0.0
    for b in boxes:
        c = b.get("结构结论") or (b.get("结构计算") or {}).get("结论") or "不通过"
        if c not in cnt:
            c = "不通过"
        cnt[c] += 1
        net += float(b.get("净重_kg") or 0)
        gross += float(b.get("毛重_kg") or 0)

    if cnt["不通过"]:
        overall = "存在结构不通过箱，需改箱型或拆件"
    elif cnt["需加强"]:
        overall = "总体可装，部分箱需按建议加强底梁/绑扎"
    elif boxes:
        overall = "全部箱结构计算通过"
    else:
        overall = "无箱子"

    return {
        "箱数": len(boxes),
        "通过": cnt["通过"],
        "需加强": cnt["需加强"],
        "不通过": cnt["不通过"],
        "总净重_kg": round(net, 2),
        "总毛重_kg": round(gross, 2),
        "结论": overall,
    }
