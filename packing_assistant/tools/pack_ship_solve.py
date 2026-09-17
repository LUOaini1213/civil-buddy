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


def rows_needing_human(materials: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in materials or []:
        meta = m.get("meta") or {}
        if meta.get("weight_missing"):
            out.append(
                {
                    "id": m.get("id") or "",
                    "name": m.get("name") or "",
                    "reason": NEEDS_HUMAN_MISSING_WEIGHT,
                    "ask": "这一行没有重量，请补一个毛重（kg 或 t），或确认它不参与装箱。",
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


def rows_blocking_plan(materials: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """出方案之前必须由人补齐的全部行：先列缺重量的，再列缺尺寸的，一次问完。"""
    return rows_needing_human(materials) + rows_missing_dimensions(materials)


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

    needs_human = rows_blocking_plan(mats)
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
        state["packing_options"].setdefault("n_max", int(max_containers))

    scheme = agent_box_scheme(state)
    after_boxes = dict(state)
    after_boxes.update(scheme)
    loaded_plan = agent_loader(after_boxes)

    plan = loaded_plan.get("container_plan") or {}
    merged = dict(after_boxes)
    merged.update(loaded_plan)
    merged["container_plan"] = plan
    return {
        "boxes": scheme.get("boxes") or [],
        "plan": plan,
        "booking": loaded_plan.get("booking") or plan.get("booking") or {},
        "feasibility": scheme.get("cargo_feasibility") or {},
        "state": merged,
    }


def _prepared(materials: Any, file_path: str) -> Dict[str, Any]:
    """解析 + 闸门，两个草稿工具共用。失败时返回 run_plan 同形状的错误。"""
    loaded = load_materials(materials, file_path)
    mats = loaded["materials"]
    if not loaded["ok"]:
        return {"ok": False, "error": "no_materials", "detail": loaded["errors"],
                "solver_connected": False, "source": "unparsed"}
    needs = rows_blocking_plan(mats)
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
    prep = _prepared(materials, file_path)
    if not prep["ok"]:
        return prep
    from packing_assistant.tools.vgm_draft import draft_vgm_method2

    solved = _solve_boxes(prep["materials"], container_type=container_type)
    if not solved["boxes"]:
        return _no_boxes(len(prep["materials"]))
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
    prep = _prepared(materials, file_path)
    if not prep["ok"]:
        return prep
    from packing_assistant.tms_booking import build_booking_request

    solved = _solve_boxes(
        prep["materials"], container_type=container_type, max_containers=max_containers
    )
    if not solved["boxes"]:
        return _no_boxes(len(prep["materials"]))
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
