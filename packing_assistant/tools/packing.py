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


def _item_fits_box(item: Dict[str, Any], box_name: str) -> bool:
    spec = STANDARD_BOX_TYPES[box_name]
    inner = _inner_dims(spec)
    d = item["外尺寸_mm"]
    need_L = d["长"] + CLEARANCE_MM
    need_a = d["宽"] + CLEARANCE_MM
    need_b = d["高"] + CLEARANCE_MM
    inn_L, inn_W, inn_H = inner["长"], inner["宽"], inner["高"]
    if need_L > inn_L:
        return False
    # 单件截面两种朝向
    return (need_a <= inn_W and need_b <= inn_H) or (
        need_a <= inn_H and need_b <= inn_W
    )


def _weight_fits(items: List[Dict[str, Any]], box_name: str) -> bool:
    net = sum(float(i.get("总重_kg") or 0) for i in items)
    return net <= float(STANDARD_BOX_TYPES[box_name]["最大载荷_kg"]) + 1e-6


def _pick_box_type_for_item(item: Dict[str, Any]) -> str:
    """选能装下单件几何 + 重量的最小箱型；都不行则用最大并交结构计算暴露问题。"""
    rules = merge_rules()
    L = float(item.get("外尺寸_mm", {}).get("长") or 0)
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


def _can_merge(
    existing: List[Dict[str, Any]],
    new_item: Dict[str, Any],
    box_name: str,
    *,
    aggressive: bool = True,
) -> bool:
    """合箱前做重量 + 结构几何试算；aggressive 时放宽填充率与试算箱外廓。"""
    trial = existing + [new_item]
    if not _weight_fits(trial, box_name):
        return False
    spec = STANDARD_BOX_TYPES[box_name]
    wall = float(spec.get("壁厚_mm") or 40)
    # 激进合箱：允许用「货包络定制外廓」做几何判定，不困在标准内尺寸
    outer, inner, _ = _fit_outer_to_cargo(dict(spec["外尺寸_mm"]), wall, trial)
    max_len = max(float(i["外尺寸_mm"]["长"]) for i in trial)
    if max_len + CLEARANCE_MM > inner["长"] + 1e-6:
        return False
    vol_items = sum(
        i["外尺寸_mm"]["长"] * i["外尺寸_mm"]["宽"] * i["外尺寸_mm"]["高"] * i["数量"]
        for i in trial
    )
    vol_box = inner["长"] * inner["宽"] * inner["高"]
    fill_cap = 0.98 if aggressive else 0.85
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
    if trial_struct.get("结论") == "不通过":
        return False
    return True


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
) -> Tuple[Dict[str, float], Dict[str, float], bool]:
    """
    按货包络定制外廓；激进模式卡拼柜模块（2 列宽 / 二层可堆高度）。
    二层模块高：20GP/40GP 用 1100（2×1100=2200<2385）；40HQ 用 1200（2×1200=2400<2698）。
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

    outer = {
        "长": min(max(need_L, 800.0), max_L),
        "宽": min(max(need_W, 600.0), max_W),
        "高": min(max(need_H, 500.0), max_H),
    }
    customized = True

    if aggressive:
        content_long = max((float(i["外尺寸_mm"]["长"]) for i in items), default=0)
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

    outer["长"] = min(max(outer["长"], need_L), max_L)
    outer["宽"] = min(max(outer["宽"], need_W), max_W)
    outer["高"] = min(max(outer["高"], need_H), max_H)

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
) -> Dict[str, Any]:
    # 选最近标准型作为结构截面/自重基准，外廓按货适配
    if box_name not in STANDARD_BOX_TYPES:
        box_name = _pick_box_type_for_item(items[0]) if items else "4米铁架"
    spec = STANDARD_BOX_TYPES[box_name]
    wall = float(spec.get("壁厚_mm") or 40)
    outer, inner, customized = _fit_outer_to_cargo(
        dict(spec["外尺寸_mm"]),
        wall,
        items,
        aggressive=True,
        container_type=container_type,
    )
    display_type = _display_box_type(box_name, outer, customized)

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
    if customized:
        special.append("定制外廓")
    if not struct["几何"]["尺寸适配"]:
        special.append("尺寸紧张")

    # 仅在结构不通过且非几何尺寸问题时尝试升级箱型截面库
    if struct["结论"] == "不通过" and "尺寸" not in str(struct.get("风险点") or []):
        upgraded = _upgrade_box(box_name, items)
        if upgraded and upgraded != box_name:
            return _build_box(box_no, upgraded, items, container_type=container_type)

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
    inner_vol = max(inner["长"] * inner["宽"] * inner["高"], 1)
    fill_ratio = min(cargo_vol / inner_vol, 1.0)

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
        "customized_outer": customized,
        "base_box_type": box_name,
        "content_max_length_mm": round(content_max_L, 1),
        # 二层堆码：矮箱/非超长可上二层；超长仅底层
        "stackable": bool(
            outer["高"] <= 1300
            and content_max_L < 4000
            and "超长" not in special
            and struct["结论"] != "不通过"
        ),
        "prefer_bottom": bool(content_max_L >= 4000 or weights["毛重_kg"] >= 800),
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


def run_packing(
    materials: List[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
) -> Dict[str, Any]:
    """
    装箱算法入口（含结构计算）。

    输入: materials 列表；container_type 影响二层模块高度
    输出: {
      "箱子列表": [... 含 结构计算 ...],
      "结构汇总": {...}
    }
    """
    if not materials:
        return {"箱子列表": [], "结构汇总": _empty_summary()}

    ctype = container_type or "40HQ"
    items = [_normalize_material(m, i) for i, m in enumerate(materials, start=1)]
    # 长件优先，但激进合箱
    items_sorted = sorted(items, key=lambda x: (-x["外尺寸_mm"]["长"], -x["总重_kg"]))

    bins: List[Dict[str, Any]] = []

    for it in items_sorted:
        placed = False
        # 仅极端超长/超重强制独箱
        solo = it["外尺寸_mm"]["长"] >= 5800 or it["总重_kg"] >= 2500
        if not solo:
            cand = sorted(
                bins,
                key=lambda b: -sum(float(x.get("总重_kg") or 0) for x in b["items"]),
            )
            for b in cand:
                max_b = max(float(x["外尺寸_mm"]["长"]) for x in b["items"])
                if _length_band(max_b) != _length_band(it["外尺寸_mm"]["长"]):
                    # 不同长度档不合，保留多箱以便并排/堆叠吃柜
                    if max(max_b, it["外尺寸_mm"]["长"]) >= 2500:
                        continue
                if _can_merge(b["items"], it, b["box_name"], aggressive=True):
                    b["items"].append(it)
                    placed = True
                    break
                upgraded = _upgrade_box(b["box_name"], b["items"] + [it])
                if upgraded and _can_merge(b["items"], it, upgraded, aggressive=True):
                    b["box_name"] = upgraded
                    b["items"].append(it)
                    placed = True
                    break
        if not placed:
            box_name = _pick_box_type_for_item(it)
            bins.append({"box_name": box_name, "items": [it]})

    # 二轮：仅合并「同长度档」小箱，避免合成过少箱导致柜内空洞变大
    bins = _aggressive_merge_bins(bins, same_length_band_only=True)

    boxes: List[Dict[str, Any]] = []
    for i, b in enumerate(bins, start=1):
        boxes.append(
            _build_box(
                f"BOX-{i:02d}",
                b["box_name"],
                b["items"],
                container_type=ctype,
            )
        )

    summary = _structure_summary(boxes)
    summary["packing_mode"] = "aggressive_fcl_two_layer"
    summary["container_type_for_module"] = ctype
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


def _aggressive_merge_bins(
    bins: List[Dict[str, Any]],
    *,
    same_length_band_only: bool = True,
) -> List[Dict[str, Any]]:
    """箱间合并：默认只合同长度档，保持多箱并排/堆叠以吃满柜。"""
    if len(bins) <= 1:
        return bins
    changed = True
    guard = 0
    while changed and guard < 12:
        guard += 1
        changed = False
        bins = sorted(
            bins,
            key=lambda b: -sum(float(x.get("总重_kg") or 0) for x in b["items"]),
        )
        out: List[Dict[str, Any]] = []
        used = [False] * len(bins)
        for i, bi in enumerate(bins):
            if used[i]:
                continue
            cur = {"box_name": bi["box_name"], "items": list(bi["items"])}
            max_i = max(float(x["外尺寸_mm"]["长"]) for x in cur["items"])
            for j in range(i + 1, len(bins)):
                if used[j]:
                    continue
                bj = bins[j]
                max_j = max(float(x["外尺寸_mm"]["长"]) for x in bj["items"])
                if same_length_band_only and _length_band(max_i) != _length_band(max_j):
                    continue
                ok = True
                trial_items = list(cur["items"])
                trial_name = cur["box_name"]
                for it in bj["items"]:
                    if _can_merge(trial_items, it, trial_name, aggressive=True):
                        trial_items.append(it)
                        continue
                    up = _upgrade_box(trial_name, trial_items + [it])
                    if up and _can_merge(trial_items, it, up, aggressive=True):
                        trial_name = up
                        trial_items.append(it)
                        continue
                    ok = False
                    break
                if ok:
                    cur["items"] = trial_items
                    cur["box_name"] = trial_name
                    max_i = max(float(x["外尺寸_mm"]["长"]) for x in cur["items"])
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
