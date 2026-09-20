"""把 pack-ship MCP 工具面接到真实装箱引擎。

在此之前 pack_ship_mcp 只做投影：调用方自己带来一份 solver 快照，它把其中
四个字段抄出来，没带就一律 UNSPECIFIED。也就是说任何 MCP 宿主挂上来之后，
拿到的都是 solver_connected=false，而装箱表连 schema 校验都过不去。

这里补上缺的那一段，并且刻意不另起一条装箱路径：走的就是工作台在用的两个
agent —— agent_box_scheme 出箱，agent_loader 拼柜。自己串 run_packing /
pack_with_auto_containers 看似更直接，实测会得出自相矛盾的结果（n0=6 却
containers_used=1、利用率恒为 0），因为引擎吃的是 material_api_to_internal
之后的内部表示，且真实参数准备有上百行。两条路径迟早会给出两个答案，而这个
项目的全部卖点就是数字只有一个出处。

确定性链路，不触发任何模型调用，实测约 1.4 秒（其中解析占 1.0 秒）。
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence

UNSPECIFIED = "UNSPECIFIED"

#: 缺重量的行不参与装箱。0 公斤不是"很轻"，是"不知道"——照 0 算会得到一个
#: 建立在零质量上的方案，N0 按重、载重余量与 VGM 全部失真且没有任何告警。
NEEDS_HUMAN_MISSING_WEIGHT = "missing_weight"


def _weight_cell(value: Any) -> Optional[float]:
    """一格重量 → float。没填（None / ""）返回 None；填了但不能用（非数值、布尔、NaN、inf）返回 NaN。"""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def rows_needing_human(materials: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """没有可用重量的行。与 adapters.material_api_to_internal 同口径：单重或总重任一为正即可
    （总重写 0 等于没写，引擎会退回 单重 × 数量）；但写了却不能用的那一格不因为另一格正常就放过——
    `单重 12.5 + 总重 'abc'` 引擎会崩，`单重 12.5 + 总重 -3` 引擎会拿 -3 当总重。
    """
    out: List[Dict[str, Any]] = []
    for m in materials or []:
        meta = m.get("meta") or {}
        cells = [c for c in (_weight_cell(m.get("weight_kg")), _weight_cell(m.get("total_weight_kg"))) if c is not None]
        unusable = any(math.isnan(c) or c < 0 for c in cells)
        has_weight = any(c > 0 for c in cells if not math.isnan(c))
        if meta.get("weight_missing") or unusable or not has_weight:
            out.append(
                {
                    "id": m.get("id") or "",
                    "name": m.get("name") or "",
                    "reason": NEEDS_HUMAN_MISSING_WEIGHT,
                    "ask": "这一行没有有效重量，请补一个大于 0 的毛重（kg 或 t），或确认它不参与装箱。",
                }
            )
    return out


def load_materials(
    materials: Any = None,
    file_path: str = "",
) -> Dict[str, Any]:
    """装箱表 → materials 列表 + 解析台账。

    materials 可以是已经解析好的行数组；file_path 走与工作台上传同一个解析器。
    自由文本字符串不在这里猜——猜出来的行会一路变成看似确定的柜数。
    """
    from packing_assistant.tools.table_mapper import parse_table_file

    if file_path:
        pr = parse_table_file(file_path)
        mats = pr.get("materials") or []
        return {
            "ok": bool(pr.get("ok")) and bool(mats),
            "materials": mats,
            "column_map": pr.get("column_map") or {},
            "stats": pr.get("stats") or {},
            "errors": pr.get("errors") or [],
            "source": "file",
        }
    if isinstance(materials, list):
        return {
            "ok": bool(materials),
            "materials": list(materials),
            "column_map": {},
            "stats": {"n_rows": len(materials)},
            "errors": [],
            "source": "array",
        }
    return {
        "ok": False,
        "materials": [],
        "column_map": {},
        "stats": {},
        "errors": ["需要 file_path，或一个已解析的 materials 数组；自由文本无法解析成装箱行。"],
        "source": "text" if materials else "none",
    }


#: 缺外形尺寸与缺重量同理：0×0×0 不是"很小"，是"不知道"。引擎拿到这种行一个箱
#: 都出不了，方案会以 ok=True、0 个柜收场——看起来像成功，其实什么都没装。
NEEDS_HUMAN_MISSING_DIMENSIONS = "missing_dimensions"

#: 引擎没有产出任何箱。闸门之后仍可能发生（例如整表被成箱规则拒收），不能算成功。
NO_BOXES = "no_boxes"

_DIMENSION_SOURCES = (
    ("length_mm", "l", "长"),
    ("width_mm", "w", "宽"),
    ("height_mm", "h", "高"),
)


def _dimension_mm(row: Dict[str, Any], key: str, short: str, cn: str) -> Optional[float]:
    """引擎将会用到的那个边长；取不到或不可用返回 None。

    取值与 adapters.material_api_to_internal 是同一条 `or` 链（length_mm →
    sizeMm → 外尺寸_mm，取第一个真值），这样闸门判的就是引擎实际拿到的数，
    而不是"表里某处有个数"。
    """
    size = row.get("sizeMm") if isinstance(row.get("sizeMm"), dict) else {}
    outer = row.get("外尺寸_mm") if isinstance(row.get("外尺寸_mm"), dict) else {}
    value = row.get(key) or size.get(short) or outer.get(cn)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def rows_missing_dimensions(materials: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in materials or []:
        missing = [key for key, short, cn in _DIMENSION_SOURCES if _dimension_mm(m, key, short, cn) is None]
        if missing:
            out.append(
                {
                    "id": m.get("id") or "",
                    "name": m.get("name") or "",
                    "reason": NEEDS_HUMAN_MISSING_DIMENSIONS,
                    "missing": missing,
                    "ask": "这一行缺少外形尺寸（" + "、".join(missing) + "），请补齐长宽高（mm），或确认它不参与装箱。",
                }
            )
    return out


#: 数量写了但不能用。引擎的读法是 int(x or 1)：0 和 False 变成 1 件，-3 变成 1 件，
#: 2.7 变成 2 件，NaN / inf 直接崩在 adapters 里——没有一种是装箱单上写的那个意思。
#: 没写数量（None / ""）仍按 1 件，这是装箱单逐箱列行时的通行写法。
NEEDS_HUMAN_INVALID_QUANTITY = "invalid_quantity"

#: 这一件任何朝向都进不了所选柜型。引擎会把箱外廓钳到柜内净空再报 can_fit=True：
#: 箱进得了柜，货其实进不了箱。
NEEDS_HUMAN_OVERSIZE = "oversize_for_container"

#: 不认识的柜型。引擎查不到净空时退回 40HQ 的数，方案照出、ok=True，柜型却不是用户要的那个。
UNKNOWN_CONTAINER_TYPE = "unknown_container_type"


def rows_invalid_quantity(materials: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """数量不可用的行。文件路径上的行到这里已经过解析器，原始格只剩 meta.quantity_invalid /
    quantity_raw 这个标记（解析器此前把 2.7 写成 2、"abc" 写成 1，闸门无从得知）。"""
    out: List[Dict[str, Any]] = []
    for m in materials or []:
        meta = m.get("meta") if isinstance(m.get("meta"), dict) else {}
        cells = [m.get(key) for key in ("quantity", "数量", "qty") if m.get(key) not in (None, "")]
        bad = bool(meta.get("quantity_invalid"))
        for value in cells:
            if isinstance(value, bool):
                bad = True
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                bad = True
                continue
            if not math.isfinite(number) or number < 1 or number != int(number):
                bad = True
        if bad:
            row = {
                "id": m.get("id") or "",
                "name": m.get("name") or "",
                "reason": NEEDS_HUMAN_INVALID_QUANTITY,
                "ask": "这一行的数量不是正整数，请改成实际件数，或确认它不参与装箱。",
            }
            if meta.get("quantity_invalid") and meta.get("quantity_raw") not in (None, ""):
                row["raw"] = str(meta["quantity_raw"])
                row["ask"] = f"这一行的数量写的是「{row['raw']}」，不是正整数，请改成实际件数，或确认它不参与装箱。"
            out.append(row)
    return out


def known_container_types() -> List[str]:
    from packing_assistant.knowledge import container_inner_mm

    return sorted(container_inner_mm())


def rows_oversize_for_container(
    materials: Sequence[Dict[str, Any]], container_type: str
) -> List[Dict[str, Any]]:
    """任何轴向摆法都进不了柜的行：三边从大到小逐一比柜内净空的三边。"""
    from packing_assistant.agents.box_scheme import effective_container_type
    from packing_assistant.knowledge import container_inner_mm

    inner_all = container_inner_mm()
    ctype = str(effective_container_type(list(materials or []), container_type) or "").upper()
    inner = inner_all.get(ctype)
    if not inner:
        return []
    cab = sorted((inner["L"], inner["W"], inner["H"]), reverse=True)
    out: List[Dict[str, Any]] = []
    for m in materials or []:
        dims = [_dimension_mm(m, key, short, cn) for key, short, cn in _DIMENSION_SOURCES]
        if any(d is None for d in dims):
            continue  # 缺尺寸由 rows_missing_dimensions 去问
        dims = sorted(dims, reverse=True)
        if all(d <= c + 1e-6 for d, c in zip(dims, cab)):
            continue
        longer = [t for t, spec in sorted(inner_all.items())
                  if all(d <= c + 1e-6 for d, c in zip(dims, sorted((spec["L"], spec["W"], spec["H"]), reverse=True)))]
        hint = f"可改用 {' / '.join(longer)}，" if longer else "现有柜型都装不下，需框架柜 / 平板柜 / 散杂货，"
        out.append(
            {
                "id": m.get("id") or "",
                "name": m.get("name") or "",
                "reason": NEEDS_HUMAN_OVERSIZE,
                "size_mm": dims,
                "container_inner_mm": cab,
                "ask": (f"这一件 {'×'.join(f'{d:g}' for d in dims)} mm，{ctype} 柜内净空 "
                        f"{'×'.join(f'{c:g}' for c in cab)} mm，任何摆法都进不去；{hint}或拆解后重报尺寸。"),
            }
        )
    return out


def rows_blocking_plan(
    materials: Sequence[Dict[str, Any]], container_type: str = ""
) -> List[Dict[str, Any]]:
    """出方案之前必须由人处理的全部行：缺重量、缺尺寸、数量不可用，一次问完；
    给了柜型时再加上进不了该柜的超限件。"""
    rows = rows_needing_human(materials) + rows_missing_dimensions(materials) + rows_invalid_quantity(materials)
    if container_type:
        rows += rows_oversize_for_container(materials, container_type)
    return rows


def _unknown_container(container_type: str) -> Optional[Dict[str, Any]]:
    known = known_container_types()
    if str(container_type or "").upper() in known:
        return None
    return {
        "ok": False,
        "solver_connected": False,
        "source": "rejected",
        "error": UNKNOWN_CONTAINER_TYPE,
        "detail": f"不认识的柜型 {container_type!r}；引擎只有这些柜型的净空与载重：{'、'.join(known)}。",
        "container_type": container_type,
        "supported_container_types": known,
    }


def _not_conserved(solved: Dict[str, Any], n_rows: int) -> Optional[Dict[str, Any]]:
    """成箱结果与装箱单对不上就不出方案：柜数、N0、VGM 都建立在箱上，箱里的货不对，后面全错。"""
    from packing_assistant.tools.cargo_conservation import NOT_CONSERVED, violation_sentences

    conservation = solved.get("conservation") or {}
    if conservation.get("ok", True):
        return None
    return {
        "ok": False,
        "solver_connected": True,
        "source": "solver",
        "error": NOT_CONSERVED,
        "detail": violation_sentences(conservation),
        "conservation": conservation,
        "n_rows": n_rows,
    }


def _no_boxes(n_rows: int) -> Dict[str, Any]:
    return {
        "ok": False,
        "solver_connected": True,
        "source": "solver",
        "error": NO_BOXES,
        "detail": "引擎没有从这些行产出任何箱，因此没有柜数可报；请检查尺寸、重量与品类。",
        "n_rows": n_rows,
    }


def run_plan(
    *,
    materials: Any = None,
    file_path: str = "",
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """装箱表 → 成箱 → 拼柜，全部由确定性工具算出。

    返回结构同时喂给 pack_ship_mcp.project_evidence（utilization / can_fit /
    mid50 / 系固待办），并带上柜数、N0 与载重校验，便于逐个数字回溯到工具。
    """
    t0 = time.time()
    loaded = load_materials(materials, file_path)
    mats = loaded["materials"]
    if not loaded["ok"]:
        return {
            "ok": False,
            "solver_connected": False,
            "source": "unparsed",
            "error": "no_materials",
            "detail": loaded["errors"],
            "parse": {k: loaded[k] for k in ("column_map", "stats", "source")},
        }

    unknown = _unknown_container(container_type)
    if unknown:
        unknown["parse"] = {k: loaded[k] for k in ("column_map", "stats", "source")}
        return unknown

    needs_human = rows_blocking_plan(mats, container_type)
    if needs_human:
        # 硬闸门：有行不知道重量或尺寸就不出方案。宁可停下来问，也不给一个
        # 看起来可以直接拿去订舱、实际算在零质量或零体积上的柜型结论。
        return {
            "ok": False,
            "solver_connected": False,
            "source": "needs_human",
            "error": needs_human[0]["reason"],
            "needs_human": needs_human,
            "n_rows": len(mats),
            "parse": {k: loaded[k] for k in ("column_map", "stats", "source")},
            "elapsed_s": round(time.time() - t0, 3),
        }

    solved = _solve_boxes(
        mats, container_type=container_type, max_containers=max_containers,
        packing_options=packing_options,
    )
    boxes = solved["boxes"]
    plan = solved["plan"]
    booking = solved["booking"]
    feasibility = solved["feasibility"]
    if not boxes:
        failed = _no_boxes(len(mats))
        failed["parse"] = {k: loaded[k] for k in ("column_map", "stats", "source")}
        failed["elapsed_s"] = round(time.time() - t0, 3)
        return failed
    lost = _not_conserved(solved, len(mats))
    if lost:
        lost["parse"] = {k: loaded[k] for k in ("column_map", "stats", "source")}
        lost["elapsed_s"] = round(time.time() - t0, 3)
        return lost
    conservation = solved["conservation"]

    return {
        "ok": bool(plan),
        "solver_connected": True,
        "source": "solver",
        # project_evidence 抄的四个字段
        "utilization": plan.get("space_utilization", UNSPECIFIED),
        "can_fit": plan.get("can_fit", UNSPECIFIED),
        "mid50": plan.get("worst_mid50", UNSPECIFIED),
        "系固待办": plan.get("系固待办", solved["state"].get("系固待办", UNSPECIFIED)),
        # 真实数字
        "containers_used": plan.get("containers_used", UNSPECIFIED),
        "container_type": plan.get("container_type", container_type),
        "n0": booking.get("n0", plan.get("n0", UNSPECIFIED)),
        "binding_constraint": booking.get("binding_constraint", UNSPECIFIED),
        "weight_utilization": plan.get("weight_utilization", UNSPECIFIED),
        "floor_utilization_avg": plan.get("floor_utilization_avg", UNSPECIFIED),
        "n_materials": len(mats),
        "n_boxes": len(boxes),
        # 每次求解后独立核对过的账：装箱单上的件数与净重，全部在箱里
        "conservation": {**{k: conservation[k] for k in
                            ("ok", "pieces_in", "pieces_out", "kg_in", "kg_out", "per_row_checked", "mass_split_rows")},
                         # 货的截面大于所在箱外廓的条数：成箱策略的既有问题，只记数、不判失败
                         "section_warnings": len(conservation["warnings"])},
        "cargo_feasibility": {
            "failure_class": feasibility.get("failure_class", UNSPECIFIED),
            "payload_kg": feasibility.get("payload_kg", UNSPECIFIED),
            "safe_cap_kg": feasibility.get("safe_cap_kg", UNSPECIFIED),
            "margin": feasibility.get("margin", UNSPECIFIED),
        },
        "parse": {k: loaded[k] for k in ("column_map", "stats", "source")},
        # 单一箱型 × N。引擎不支持混柜（recommend_container 只回一种箱型，
        # pack_with_auto_containers 装 N 个同型柜），不要说成"箱型组合"。
        "container_mix_supported": False,
        "elapsed_s": round(time.time() - t0, 3),
    }


def plan_report_md(result: Dict[str, Any], file_name: str) -> str:
    """run_plan 的结果写成带中文标签的报告：数字只抄不算，每个数都说清是什么。

    给人看，也给模型看。实测小模型会把裸键 payload_kg（柜体额定载重）读成「货物总重」，
    所以凡是要交给模型转述的地方都用这份报告，不给裸键。
    """
    def value(key: str) -> str:
        return str(result.get(key, UNSPECIFIED))

    lines = ["# 装柜方案（装箱引擎结果）", "",
             "内部讨论 AI 草稿。柜数与利用率由装箱引擎算出，未经人工复核，不可直接订舱；系固与 VGM 另行签认。", "",
             f"- 装箱单：{file_name}"]
    if not result.get("ok"):
        lines += [f"- 结果：未出方案（{value('error')}）"]
        for row in (result.get("needs_human") or [])[:20]:
            lines.append(f"  - {row.get('name') or row.get('id') or '（未命名行）'}：{row.get('ask') or row.get('reason')}")
        if not result.get("needs_human"):
            detail = result.get("detail")
            for sentence in (detail if isinstance(detail, list) else [detail] if detail else [])[:20]:
                lines.append(f"  - {sentence}")
        return "\n".join(lines) + "\n"
    lines += [f"- 柜型：{value('container_type')}（单一柜型 × N；引擎不支持混柜）",
              f"- 物料行：{value('n_materials')} · 成箱：{value('n_boxes')}",
              f"- 用柜数：{value('containers_used')} · 订柜下限 N0：{value('n0')}",
              f"- can_fit：{value('can_fit')}",
              f"- 空间利用率：{value('utilization')} · 载重利用率：{value('weight_utilization')} · 地板利用率：{value('floor_utilization_avg')}",
              f"- 约束：{value('binding_constraint')} · mid50：{value('mid50')}",
              f"- 系固待办：{value('系固待办')}"]
    kept = result.get("conservation") or {}
    if kept:
        lines.append(f"- 货物核对（装箱单 → 箱内）：件数 {kept.get('pieces_in')} → {kept.get('pieces_out')} · "
                     f"净重 {kept.get('kg_in')} → {kept.get('kg_out')} kg")
        for row in (kept.get("mass_split_rows") or [])[:10]:
            lines.append(f"  - {row.get('name') or row.get('id')}：{row.get('units')} 件单件重超过所选箱型的净重上限，"
                         f"每件按质量切成 {row.get('parts_per_unit')} 份分箱（共 {row.get('parts')} 份）。"
                         "这是计算上的拆分，实物不可切时箱型需人工确认。")
    limits = result.get("cargo_feasibility") or {}
    if limits:
        lines.append(f"- 柜体额定载重（不是货重）：{limits.get('payload_kg', UNSPECIFIED)} kg · "
                     f"单箱安全上限（额定载重 × 安全系数 {limits.get('margin', UNSPECIFIED)}）：{limits.get('safe_cap_kg', UNSPECIFIED)} kg"
                     f" · 超限判定：{limits.get('failure_class', UNSPECIFIED)}")
    return "\n".join(lines) + "\n"


_RECORD_KEYS = ("ok", "source", "error", "n_rows", "can_fit", "containers_used", "container_type", "n0", "utilization",
                "weight_utilization", "floor_utilization_avg", "binding_constraint", "mid50", "n_materials", "n_boxes",
                "conservation", "detail", "cargo_feasibility", "container_mix_supported", "elapsed_s")


def plan_record_json(result: Dict[str, Any], file_name: str) -> str:
    """What the engine returned, as it returned it — saved beside pack-plan.md as pack-plan.json.

    The report's numbers come from a computation, not from any file in the job folder, so a reviewer
    (`civil review`) reading only the folder's material would call every one of them unsourced. The
    record is that source: a tool result, kept.
    """
    import json

    record = {"schema": "pack-ship.plan.record.v1", "packing_list": file_name,
              **{key: result[key] for key in _RECORD_KEYS if key in result}}
    return json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n"


def plan_reply(result: Dict[str, Any], file_name: str) -> str:
    """一句话交代：算出了什么，或者为什么没算。数字同样只抄。"""
    if result.get("ok") and result.get("can_fit") is False:
        # can_fit=False 是失败，不是「方案已出」：柜数此时只是引擎停手时的数，不能拿去订舱。
        return (f"装箱引擎按 {file_name} 算过了，但判定装不下（can_fit=False，约束：{result.get('binding_constraint', UNSPECIFIED)}）。"
                f"这不是可用方案；引擎停手时用了 {result.get('containers_used', UNSPECIFIED)} 个 "
                f"{result.get('container_type', UNSPECIFIED)}。明细见 pack-plan.md，请核对超限件或换柜型后再算。")
    if result.get("ok"):
        return (f"装箱引擎已按 {file_name} 算出方案：{result.get('containers_used', UNSPECIFIED)} 个 "
                f"{result.get('container_type', UNSPECIFIED)}，订柜下限 N0={result.get('n0', UNSPECIFIED)}，"
                f"can_fit={result.get('can_fit', UNSPECIFIED)}，空间利用率 {result.get('utilization', UNSPECIFIED)}、"
                f"载重利用率 {result.get('weight_utilization', UNSPECIFIED)}。明细见 pack-plan.md。内部草稿，不可直接订舱。")
    rows = result.get("needs_human") or []
    if rows:
        asks = "\n".join(f"- {row.get('name') or row.get('id') or '（未命名行）'}：{row.get('ask') or row.get('reason')}" for row in rows[:20])
        return f"{file_name} 里有 {len(rows)} 行缺重量或尺寸，引擎没有出方案，也就没有柜数可报。请补齐后再算：\n{asks}"
    detail = result.get("detail")
    detail = "；".join(str(item) for item in detail) if isinstance(detail, list) else str(detail or "")
    return f"{file_name} 没有算出方案（{result.get('error', UNSPECIFIED)}）。{detail}".strip()


def _solve_boxes(
    materials: Sequence[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
    packing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """跑工作台那两个 agent，返回原始产物（boxes / container_plan / booking）。"""
    from packing_assistant.agents.box_scheme import agent_box_scheme
    from packing_assistant.agents.loader import agent_loader

    state: Dict[str, Any] = {
        "materials": list(materials),
        "container_type": container_type,
        "packing_options": dict(packing_options or {}),
    }
    if max_containers:
        # 拼柜器读的是 state.max_containers（用户封顶）；原先写进 packing_options.n_max，没有任何代码读它。
        state["max_containers"] = int(max_containers)

    scheme = agent_box_scheme(state)
    after_boxes = dict(state)
    after_boxes.update(scheme)
    loaded_plan = agent_loader(after_boxes)

    plan = loaded_plan.get("container_plan") or {}
    merged = dict(after_boxes)
    merged.update(loaded_plan)
    merged["container_plan"] = plan
    from packing_assistant.tools.cargo_conservation import check_conservation

    return {
        "conservation": check_conservation(materials, scheme.get("boxes") or []),
        "boxes": scheme.get("boxes") or [],
        "plan": plan,
        "booking": loaded_plan.get("booking") or plan.get("booking") or {},
        "feasibility": scheme.get("cargo_feasibility") or {},
        "state": merged,
    }


def _prepared(materials: Any, file_path: str, container_type: str = "40HQ") -> Dict[str, Any]:
    """解析 + 闸门，两个草稿工具共用。失败时返回 run_plan 同形状的错误。"""
    loaded = load_materials(materials, file_path)
    mats = loaded["materials"]
    if not loaded["ok"]:
        return {"ok": False, "error": "no_materials", "detail": loaded["errors"],
                "solver_connected": False, "source": "unparsed"}
    unknown = _unknown_container(container_type)
    if unknown:
        return unknown
    needs = rows_blocking_plan(mats, container_type)
    if needs:
        return {"ok": False, "error": needs[0]["reason"], "needs_human": needs,
                "solver_connected": False, "source": "needs_human", "n_rows": len(mats)}
    return {"ok": True, "materials": mats}


def draft_vgm(
    *,
    materials: Any = None,
    file_path: str = "",
    container_type: str = "40HQ",
) -> Dict[str, Any]:
    """SOLAS 方法二 VGM 草稿。只起草，auto_submit_forbidden 由引擎自己设。"""
    prep = _prepared(materials, file_path, container_type)
    if not prep["ok"]:
        return prep
    from packing_assistant.tools.vgm_draft import draft_vgm_method2

    solved = _solve_boxes(prep["materials"], container_type=container_type)
    if not solved["boxes"]:
        return _no_boxes(len(prep["materials"]))
    lost = _not_conserved(solved, len(prep["materials"]))
    if lost:
        return lost
    draft = draft_vgm_method2(solved["plan"], solved["boxes"])
    out = {"ok": True, "solver_connected": True, "source": "solver",
           "container_type": container_type, "n_boxes": len(solved["boxes"])}
    out.update(draft)
    # 对账口径：与装箱单行重 + 皮重 + 包装系数对账，不是与地磅比对。
    out.setdefault("reconciled_against", "packing_list_lines+tare+packaging_factor")
    return out


def draft_booking(
    *,
    materials: Any = None,
    file_path: str = "",
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
) -> Dict[str, Any]:
    """订舱请求草稿（dry run）。生成文件，不替人发出。"""
    prep = _prepared(materials, file_path, container_type)
    if not prep["ok"]:
        return prep
    from packing_assistant.tms_booking import build_booking_request

    solved = _solve_boxes(
        prep["materials"], container_type=container_type, max_containers=max_containers
    )
    if not solved["boxes"]:
        return _no_boxes(len(prep["materials"]))
    lost = _not_conserved(solved, len(prep["materials"]))
    if lost:
        return lost
    req = build_booking_request(solved["state"])
    return {
        "ok": True,
        "solver_connected": True,
        "source": "solver",
        "dry_run": True,
        "submitted": False,
        "note": "草稿只落盘，不向承运人提交；提交需人工签认。",
        "booking_request": req,
        "containers_used": solved["plan"].get("containers_used", UNSPECIFIED),
        "n0": solved["booking"].get("n0", UNSPECIFIED),
        "container_mix_supported": False,
    }
