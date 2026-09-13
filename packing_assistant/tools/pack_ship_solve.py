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

    needs_human = rows_needing_human(mats)
    if needs_human:
        # 硬闸门：有行不知道重量就不出方案。宁可停下来问，也不给一个
        # 看起来可以直接拿去订舱、实际算在零质量上的柜型结论。
        return {
            "ok": False,
            "solver_connected": False,
            "source": "needs_human",
            "error": NEEDS_HUMAN_MISSING_WEIGHT,
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
    needs = rows_needing_human(mats)
    if needs:
        return {"ok": False, "error": NEEDS_HUMAN_MISSING_WEIGHT, "needs_human": needs,
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
