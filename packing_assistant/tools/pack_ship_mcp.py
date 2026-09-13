"""Discoverable pack-ship MCP tools: list / plan / export.

Projection only. Utilization, can_fit, mid50, 系固待办 are copied from an
in-repo solver snapshot. Missing / disconnected → literal UNSPECIFIED.
Never invents xyz / N0 / 条款号. Never re-packs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

UNSPECIFIED = "UNSPECIFIED"

TOOL_LIST = "pack-ship__list"
TOOL_PLAN = "pack-ship__plan"
TOOL_EXPORT = "pack-ship__export"
TOOL_HEALTH = "pack-ship__health"
TOOL_INGEST = "pack-ship__ingest"
TOOL_NAMES = (TOOL_LIST, TOOL_PLAN, TOOL_EXPORT, TOOL_HEALTH, TOOL_INGEST)

EVIDENCE_FIELDS = ("utilization", "can_fit", "mid50", "系固待办")

_ALIASES = {
    "list": TOOL_LIST,
    "plan": TOOL_PLAN,
    "export": TOOL_EXPORT,
    "civil.pack-ship.list": TOOL_LIST,
    "civil.pack-ship.plan": TOOL_PLAN,
    "civil.pack-ship.export": TOOL_EXPORT,
    "health": TOOL_HEALTH,
    "civil.pack-ship.health": TOOL_HEALTH,
    "ingest": TOOL_INGEST,
    "civil.pack-ship.ingest": TOOL_INGEST,
}

_UTIL_KEYS = ("utilization", "util", "volume_util", "volume_utilization", "util_ratio")
_FIT_KEYS = ("can_fit",)
_MID_KEYS = ("mid50", "mass_in_mid50_ratio", "worst_mid50")
_LASH_KEYS = ("系固待办", "lashing_todo", "lashing_pending", "secure_todo")


def _copy_field(solver: Optional[Dict[str, Any]], keys: Iterable[str]) -> Any:
    if not isinstance(solver, dict):
        return UNSPECIFIED
    for key in keys:
        if key in solver and solver[key] is not None and solver[key] != "":
            return solver[key]
    return UNSPECIFIED


def solver_connected(solver: Any, *, connected: Optional[bool] = None) -> bool:
    if connected is False:
        return False
    if connected is True and isinstance(solver, dict):
        return True
    return isinstance(solver, dict) and bool(solver)


def project_evidence(
    solver: Optional[Dict[str, Any]] = None,
    *,
    connected: Optional[bool] = None,
) -> Dict[str, Any]:
    """Copy the four evidence fields. No second packing run."""
    if not solver_connected(solver, connected=connected):
        ev = {k: UNSPECIFIED for k in EVIDENCE_FIELDS}
        ev["lashing_todo"] = UNSPECIFIED
        ev["source"] = "disconnected"
        ev["solver_connected"] = False
        return ev
    ev = {
        "utilization": _copy_field(solver, _UTIL_KEYS),
        "can_fit": _copy_field(solver, _FIT_KEYS),
        "mid50": _copy_field(solver, _MID_KEYS),
        "系固待办": _copy_field(solver, _LASH_KEYS),
    }
    ev["lashing_todo"] = ev["系固待办"]
    ev["source"] = "solver"
    ev["solver_connected"] = True
    return ev


def list_pack_ship_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": TOOL_LIST,
            "description": "列出 pack-ship 可发现工具（list / plan / export）。不含数字。",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": TOOL_PLAN,
            "description": (
                "装柜计划。给 file_path 或已解析的 materials 数组即真算："
                "柜数/N0/利用率/载重校验全部来自确定性工具。"
                "只给 solver 快照时退回投影；都没有则 UNSPECIFIED。单一箱型 × N，不支持混柜。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "装箱表路径（xlsx/csv）"},
                    "materials": {"type": ["string", "array", "null"], "description": "已解析的行数组"},
                    "container_type": {"type": "string", "description": "默认 40HQ"},
                    "max_containers": {"type": ["integer", "null"]},
                    "solver": {"type": "object", "description": "本仓 solver 回传快照（旧投影路径）"},
                    "connected": {"type": "boolean"},
                },
            },
        },
        {
            "name": TOOL_INGEST,
            "description": (
                "读装箱表，只解析不装箱：返回行数、字段映射与缺字段台账。"
                "缺重量的行会被列进 needs_human，必须人工补齐后才能出方案。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "materials": {"type": ["string", "array", "null"]},
                },
            },
        },
        {
            "name": TOOL_HEALTH,
            "description": "探测本仓 solver 快照是否可用。不编数字。",
            "inputSchema": {"type": "object", "properties": {"solver": {"type": "object"}}},
        },
        {
            "name": TOOL_EXPORT,
            "description": "导出装柜证据表。字段只抄 plan 同源 solver，不重算 xyz。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "solver": {"type": "object"},
                    "connected": {"type": "boolean"},
                },
            },
        },
    ]


def list_tool() -> Dict[str, Any]:
    tools = list_pack_ship_tools()
    return {
        "schema": "pack-ship.list.v1",
        "ok": True,
        "tools": tools,
        "names": [t["name"] for t in tools],
        "list": TOOL_LIST,
        "plan": TOOL_PLAN,
        "export": TOOL_EXPORT,
        "health": TOOL_HEALTH,
        "ingest": TOOL_INGEST,
    }


def health_tool(solver: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    connected = solver_connected(solver)
    return {
        "schema": "pack-ship.health.v1",
        "ok": True,
        "tool": TOOL_HEALTH,
        "solver": "in-repo-projection",
        "connected": connected,
        "xyz": UNSPECIFIED,
    }


def plan_tool(
    solver: Optional[Dict[str, Any]] = None,
    *,
    connected: Optional[bool] = None,
    materials: Any = None,
    file_path: str = "",
    container_type: str = "40HQ",
    max_containers: Optional[int] = None,
) -> Dict[str, Any]:
    # 有表就真算：走工作台在用的那两个 agent，柜数与利用率都有出处。
    if file_path or isinstance(materials, list):
        from packing_assistant.tools.pack_ship_solve import run_plan

        solved = run_plan(
            materials=materials,
            file_path=file_path,
            container_type=container_type,
            max_containers=max_containers,
        )
        out = {"schema": "pack-ship.plan.v1", "tool": TOOL_PLAN, "xyz": UNSPECIFIED}
        out.update(solved)
        out.setdefault("can_fit", UNSPECIFIED)
        return out

    # 没有表：维持旧的投影行为，只抄调用方给的快照，绝不自己编。
    ev = project_evidence(solver, connected=connected)
    return {
        "schema": "pack-ship.plan.v1",
        "ok": True,
        "tool": TOOL_PLAN,
        "materials": materials or None,
        "xyz": UNSPECIFIED,
        "n0": UNSPECIFIED if ev["source"] == "disconnected" else _copy_field(solver, ("n0", "N0", "n0_star")),
        **ev,
    }


def ingest_tool(materials: Any = None, file_path: str = "") -> Dict[str, Any]:
    """只解析不装箱：行数、字段映射、以及必须人工补齐的行。"""
    from packing_assistant.tools.pack_ship_solve import load_materials, rows_needing_human

    loaded = load_materials(materials, file_path)
    mats = loaded["materials"]
    needs = rows_needing_human(mats)
    if needs:
        nxt = "先补齐 needs_human 里这些行的重量，再调 pack-ship__plan。"
    elif mats:
        nxt = "全部行都有重量，可以调 pack-ship__plan 出方案。"
    else:
        nxt = "没有解析出任何行；确认表头与文件格式。"
    return {
        "schema": "pack-ship.ingest.v1",
        "ok": bool(loaded["ok"]) and not needs,
        "tool": TOOL_INGEST,
        "n_rows": len(mats),
        "column_map": loaded["column_map"],
        "stats": loaded["stats"],
        "needs_human": needs,
        "errors": loaded["errors"],
        "next": nxt,
    }


def export_tool(
    solver: Optional[Dict[str, Any]] = None,
    *,
    connected: Optional[bool] = None,
) -> Dict[str, Any]:
    ev = project_evidence(solver, connected=connected)
    md = "\n".join(
        [
            "# pack-ship export",
            "",
            f"- utilization: {ev['utilization']}",
            f"- can_fit: {ev['can_fit']}",
            f"- mid50: {ev['mid50']}",
            f"- 系固待办: {ev['系固待办']}",
            f"- source: {ev['source']}",
            "",
            "柜数/xyz 未在 solver 快照中则 UNSPECIFIED。禁止编 CTU 条款号。",
        ]
    )
    return {
        "schema": "pack-ship.export.v1",
        "ok": True,
        "tool": TOOL_EXPORT,
        "markdown": md,
        "xyz": UNSPECIFIED,
        **ev,
    }


def normalize_tool_name(name: str) -> str:
    raw = (name or "").strip()
    return _ALIASES.get(raw, raw)


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    args = arguments or {}
    tool = normalize_tool_name(name)
    solver = args.get("solver")
    if solver is not None and not isinstance(solver, dict):
        solver = None
    connected = args.get("connected")
    if isinstance(connected, str):
        connected = connected.lower() in {"1", "true", "yes"}
    if tool == TOOL_LIST:
        return list_tool()
    if tool == TOOL_INGEST:
        return ingest_tool(args.get("materials"), str(args.get("file_path") or ""))
    if tool == TOOL_PLAN:
        mats = args.get("materials")
        if not isinstance(mats, list):
            mats = str(mats or "")
        max_c = args.get("max_containers")
        return plan_tool(
            solver,
            connected=connected,
            materials=mats,
            file_path=str(args.get("file_path") or ""),
            container_type=str(args.get("container_type") or "40HQ"),
            max_containers=int(max_c) if isinstance(max_c, int) else None,
        )
    if tool == TOOL_EXPORT:
        return export_tool(solver, connected=connected)
    if tool == TOOL_HEALTH:
        return health_tool(solver)
    return {"ok": False, "error": f"unknown pack-ship tool: {name}", "names": list(TOOL_NAMES)}
