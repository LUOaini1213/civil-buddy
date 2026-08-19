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
TOOL_NAMES = (TOOL_LIST, TOOL_PLAN, TOOL_EXPORT, TOOL_HEALTH)

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
            "description": "装柜计划投影。利用率/can_fit/mid50/系固待办只抄 solver；未接通写 UNSPECIFIED。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "solver": {"type": "object", "description": "本仓 solver 回传快照"},
                    "connected": {"type": "boolean"},
                    "materials": {"type": "string"},
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
    materials: str = "",
) -> Dict[str, Any]:
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
    if tool == TOOL_PLAN:
        return plan_tool(solver, connected=connected, materials=str(args.get("materials") or ""))
    if tool == TOOL_EXPORT:
        return export_tool(solver, connected=connected)
    if tool == TOOL_HEALTH:
        return health_tool(solver)
    return {"ok": False, "error": f"unknown pack-ship tool: {name}", "names": list(TOOL_NAMES)}
