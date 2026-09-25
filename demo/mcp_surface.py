"""MCP resources + prompts for the Python workbench.

Same URI / prompt names as workbench/src/mcp.rs so hosts can switch
civil-mcp (Rust) without renaming. Tests drive this module; Rust needs MSVC.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rag import list_kb, read_kb

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PROMPTS: list[dict[str, Any]] = [
    {
        "name": "civil.bid.parse",
        "description": "招标解析：只抄原文成表，评分点交 bid-tech，★/废标交 bid-compliance。不判定可投标。",
        "experts": {"bid-parse"},
        "packs": {"bid"},
    },
    {
        "name": "civil.bid.compliance",
        "description": "P0 废标/资格/★ 扫描。三态：已响应 / 未响应 / 招标未提供正文。",
        "experts": {"bid-compliance"},
        "packs": {"bid"},
    },
    {
        "name": "civil.pack-ship.plan",
        "description": "装箱作业单。柜数/xyz/N0 只抄工具；未接通写 UNSPECIFIED。",
        "experts": {"pack-ship"},
        "packs": {"plant"},
    },
    {
        "name": "civil.pack-ship.list",
        "description": "列出 pack-ship list / plan / export。",
        "experts": {"pack-ship"},
        "packs": {"plant"},
    },
    {
        "name": "civil.pack-ship.export",
        "description": "导出装柜证据。利用率/can_fit/mid50/系固待办只抄 solver。",
        "experts": {"pack-ship"},
        "packs": {"plant"},
    },
    {
        "name": "civil.construction.scheme",
        "description": "专项方案讨论提纲十一章。须确认句。禁止可以开工。不是法定专项。",
        "experts": {"construction"},
        "packs": {"construction"},
    },
    {
        "name": "civil.method-hazard.judge",
        "description": "危大判定讨论卡。SG 默认 WSH/PTW，不套 37 号令。不判定可以开工。",
        "experts": {"method-hazard"},
        "packs": set(),
    },
    {
        "name": "civil.finance.tax-calendar",
        "description": "税务日历草稿。IRAS 页述 GST 9%。税额待持证人员算。",
        "experts": {"finance-tax"},
        "packs": {"finance"},
    },
]

_SHARED = {
    "bid": ["bid__scan_forbidden"],
    "design": ["design__scan_forbidden"],
    "bim": ["bim__scan_forbidden"],
    "planning": ["planning__scan_forbidden"],
    "construction": ["construction__scan_forbidden"],
    "hse": ["hse__scan_forbidden"],
    "commercial": ["commercial__scan_forbidden"],
    "procurement": ["procurement__scan_forbidden"],
    "plant": ["plant__scan_forbidden"],
    "lab": ["lab__scan_forbidden"],
    "finance": ["finance__scan_forbidden"],
    "docs": ["docs__scan_forbidden"],
    "hr": ["hr__scan_forbidden"],
    "admin": ["admin__scan_forbidden"],
    "it": ["it__scan_forbidden"],
    "people": ["people__scan_forbidden"],
}
_DEFAULT_EXPERT = {
    "bid": "bid-parse",
    "plant": "pack-ship",
    "construction": "construction",
    "commercial": "cost",
    "finance": "finance-tax",
}
_COMMON = (
    ("civil.turn", "一轮土木 agent：走同一套 understand → tools → HITL。text 必填。"),
    ("search_kb", "检索当前岗可见知识库。"),
    ("read_kb", "读取 kb:// 或相对路径。越权拒绝。"),
    ("list_kb", "列出当前岗可见知识文件。"),
)
# The caller on MCP is a model: it may ask for a high-risk write, never approve one.
_PERSON_ONLY = ("confirm_ok", "p0_confirmed")
_NEEDS_PERSON = "高风险写盘须由本人在工作台、终端或桌面端键入确认句；MCP 调用方不能代为确认。本次未写盘。"


def _scope(expert_id: str | None, pack: str | None):
    from packing_assistant.expert_roster import get_expert, list_experts

    eid = (expert_id or "").strip()
    if eid:
        rec = get_expert(eid)
        if rec:
            return rec.id, rec.category, rec
        return eid, (pack or "").strip(), None
    p = (pack or "").strip()
    if p:
        rec = get_expert(_DEFAULT_EXPERT.get(p) or "")
        if rec is None:
            rec = next((e for e in list_experts() if e.category == p), None)
        return (rec.id if rec else ""), p, rec
    return "", "", None


def _spec(name: str, description: str, extra: dict | None = None) -> dict[str, Any]:
    from packing_assistant.runtime.tool_engine import get_engine
    from packing_assistant.runtime.tool_contracts import contract_for
    from copy import deepcopy
    spec = get_engine().tools.get(name)
    contract = contract_for(name, exclusive=bool(spec and spec.expert_id))
    schema = deepcopy(spec.input_schema) if spec and spec.input_schema else contract["input_schema"]
    if extra:
        schema["properties"].update(extra)
    for key in _PERSON_ONLY:
        (schema.get("properties") or {}).pop(key, None)
    return {"name": name, "description": description, "inputSchema": schema,
            "outputSchema": deepcopy(spec.output_schema) if spec and spec.output_schema else contract["output_schema"]}


def initialize_capabilities() -> dict[str, Any]:
    return {"tools": {}, "resources": {}, "prompts": {}}


def list_resources(expert_id: str, category: str) -> list[dict[str, Any]]:
    rows = []
    for row in list_kb(expert_id, category):
        rel = str(row.get("path") or "")
        if not rel:
            continue
        rows.append(
            {
                "uri": f"kb://{rel}",
                "name": row.get("title") or rel,
                "description": f"{row.get('layer') or ''} · {rel}",
                "mimeType": "text/markdown",
            }
        )
    return rows


def read_resource(expert_id: str, category: str, uri: str) -> dict[str, Any]:
    rel = uri[5:] if uri.startswith("kb://") else uri
    allowed = {str(r.get("path") or "") for r in list_kb(expert_id, category)}
    if rel not in allowed:
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "拒绝：该知识不在当前专家可见层（私库 / 大类共享 / 公司）。",
                }
            ]
        }
    got = read_kb(rel)
    if not got:
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "拒绝：文件不存在或越权。",
                }
            ]
        }
    _, text = got
    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}


def list_prompts(*, expert_id: str | None = None, pack: str | None = None) -> list[dict[str, Any]]:
    out = []
    for p in PROMPTS:
        if expert_id and expert_id not in p["experts"]:
            continue
        if pack and pack not in p["packs"] and not expert_id:
            continue
        out.append({"name": p["name"], "description": p["description"]})
    return out


def get_prompt(
    name: str,
    arguments: dict | None = None,
    *,
    expert_id: str | None = None,
    pack: str | None = None,
) -> dict[str, Any]:
    allowed = {p["name"] for p in list_prompts(expert_id=expert_id, pack=pack)}
    if expert_id and name not in allowed:
        return {"description": "拒绝：当前专家看不见该 prompt", "messages": []}
    args = arguments or {}
    if name == "civil.bid.parse":
        text = (
            "你是 Civil Buddy 招标解析岗。天数/分值/workhead 只抄用户正文。"
            "不要判定可投标。评分点交给 bid-tech，★/废标交给 bid-compliance。"
            f"辖区={args.get('jurisdiction') or 'SG'}。正文：\n{args.get('tender_text') or '（未提供）'}"
        )
    elif name == "civil.bid.compliance":
        text = (
            "你是废标检查岗。只打 已响应/未响应/招标未提供正文。不要编造否决依据。"
            f"正文：\n{args.get('tender_text') or '（未提供）'}"
        )
    elif name == "civil.pack-ship.plan":
        text = (
            "你是装箱拼柜岗。先 pack-ship__list，再 pack-ship__plan，再 pack-ship__export。"
            "柜数/N0/xyz 只抄工具；未接通写 UNSPECIFIED。禁止编 CTU 条款号。"
            f"物料：\n{args.get('materials') or '（未提供）'}"
        )
    elif name == "civil.pack-ship.list":
        text = "列出 pack-ship__list / pack-ship__plan / pack-ship__export。不要编数字。"
    elif name == "civil.pack-ship.export":
        text = "导出装柜证据。utilization / can_fit / mid50 / 系固待办只抄 solver；未接通写 UNSPECIFIED。"
    elif name == "civil.construction.scheme":
        text = (
            "你是施工方案岗。出十一章讨论提纲，不是法定专项。"
            "写盘前须确认句「我明白，将由持证人员签认」。禁止断言可以开工。"
            f"任务：\n{args.get('task') or args.get('text') or '（未提供）'}"
        )
    elif name == "civil.method-hazard.judge":
        text = (
            "你是危大识别岗。SG 默认 WSH/PTW 标题，不套住建部令第 37 号到 SG。"
            "只判定讨论，不签发，不判定可以开工。"
            f"现场：\n{args.get('text') or '（未提供）'}"
        )
    elif name == "civil.finance.tax-calendar":
        text = (
            "你是税务日历岗。IRAS Current GST rates 页述 9%。税额待持证办税人员算。不要编税率。"
            f"任务：\n{args.get('text') or '（未提供）'}"
        )
    else:
        return {"description": "未知 prompt", "messages": []}
    return {
        "description": name,
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }


def list_tools(*, expert_id: str | None = None, pack: str | None = None) -> list[dict[str, Any]]:
    eid, cat, rec = _scope(expert_id, pack)
    names: list[tuple[str, str]] = list(_COMMON)
    if cat:
        for n in _SHARED.get(cat) or []:
            names.append((n, f"{cat} 大类禁语扫描。命中不得报成功。"))
    if cat == "bid" or (rec and rec.category == "bid"):
        names.append(("tender.parse", "招标进矩阵。submit_blocked=true。不判定可投标。"))
        names.append(("tender.review", "成稿后再审。不改 can_fit，不填业绩。"))
    if rec:
        for n in rec.exclusive:
            names.append((n, f"岗独有 {n}。兄弟调用拒绝。"))
        names.append(("write_deliverable", "沙箱写盘。chat 拒绝。"))
    elif cat == "bid":
        names.append(("write_deliverable", "沙箱写盘。chat 拒绝。"))
    show_pack = (rec and rec.id == "pack-ship") or (cat == "plant" and not (expert_id or "").strip())
    if show_pack or (not eid and not cat):
        from packing_assistant.tools.pack_ship_mcp import list_pack_ship_tools

        extra = list_pack_ship_tools()
    else:
        extra = []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n, d in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(_spec(n, d))
    for t in extra:
        n = str(t.get("name") or "")
        if n and n not in seen:
            seen.add(n)
            out.append(t)
    return out


def _visible_names(expert_id: str | None, pack: str | None) -> set[str]:
    return {str(t.get("name") or "") for t in list_tools(expert_id=expert_id, pack=pack)}


def _needs_person(out: dict[str, Any]) -> dict[str, Any]:
    """A write waiting for the sentence is not a success the host may report as done."""
    if out.get("hitl_pending"):
        return {**out, "ok": False, "error_code": "approval_required", "reason": _NEEDS_PERSON}
    return out


def _turn_expert(asked: str, expert_id: str | None, pack: str | None, eid: str, cat: str) -> str | None:
    """The post civil.turn may run: --expert pins that post, --pack its posts; None = outside the launch scope."""
    if (expert_id or "").strip():
        return eid if asked in {"", eid} else None
    if (pack or "").strip():
        from packing_assistant.expert_roster import get_expert

        rec = get_expert(asked) if asked else None
        if asked and not (rec and rec.category == cat):
            return None
        return (rec.id if rec else eid) or None
    return asked


def _write_needs_person(tool: str, risk: str, intent: str) -> dict[str, Any] | None:
    """The approval_required answer when the gate holds this write for a person; None when it may run."""
    from packing_assistant.runtime.civil_config import decide_gate
    from packing_assistant.runtime.tool_engine import get_engine

    spec = get_engine().tools.get(tool)
    if spec is None or not spec.writes or decide_gate(intent=intent, risk=risk, confirmed=False) != "hitl":
        return None
    return _needs_person({"name": tool, "wrote": False, "files": [], "hitl_pending": True, "submit_blocked": True})


def _engine_call(tool: str, args: dict[str, Any], *, expert_id: str, risk: str, intent: str) -> dict[str, Any]:
    from packing_assistant.runtime.tool_engine import get_engine

    held = _write_needs_person(tool, risk, intent)
    return held or _needs_person(get_engine().execute(tool, args, expert_id=expert_id, intent=intent))


def call_tool(
    name: str,
    arguments: dict | None = None,
    *,
    expert_id: str | None = None,
    pack: str | None = None,
    intent: str = "run",
) -> dict[str, Any]:
    from packing_assistant.runtime.tool_contracts import validate
    if arguments is not None and not isinstance(arguments, dict):
        return {"ok": False, "error_code": "invalid_args", "error": "参数必须为对象", "content": []}
    args = dict(arguments or {})
    intent = str(args.get("intent") or intent or "run")
    eid, cat, rec = _scope(expert_id, pack)
    from packing_assistant.tools.pack_ship_mcp import TOOL_NAMES, call_tool as _pack, normalize_tool_name

    tool = normalize_tool_name(name)
    visible = _visible_names(eid or None, pack or cat or None)
    if tool not in visible and tool not in TOOL_NAMES:
        return {"ok": False, "error": f"未知工具 {name}", "content": []}
    if tool not in visible:
        return {"ok": False, "error": "拒绝：当前专家看不见该工具", "content": []}
    if any(key in args for key in _PERSON_ONLY):
        return {"ok": False, "error_code": "invalid_args", "error": "confirm_ok / p0_confirmed 不接受：" + _NEEDS_PERSON,
                "content": []}
    schema = next((s["inputSchema"] for s in list_tools(expert_id=expert_id, pack=pack) if s["name"] == tool), {})
    problem = validate(args, schema)
    if problem:
        return {"ok": False, "error_code": "invalid_args", "error": problem, "content": []}

    if tool in {"civil.turn", "agent.turn"}:
        from packing_assistant.runtime.agent_loop import run_agent

        asked = str(args.get("skill") or args.get("expert_id") or "").strip()
        post = _turn_expert(asked, expert_id, pack, eid, cat)
        if post is None:
            return {"ok": False, "error_code": "permission_denied",
                    "error": f"拒绝：本 MCP 服务的启动范围看不见岗位 {asked or '（未点名）'}", "content": []}
        sid = str(args.get("session_id") or "mcp-turn")
        return _needs_person(run_agent(str(args.get("text") or args.get("task") or ""), session_id=sid,
                                       expert_id=post, p0_confirmed=False))

    if tool in TOOL_NAMES:
        if rec and rec.id not in {"pack-ship", ""} and cat != "plant":
            return {"ok": False, "error": "拒绝：当前专家看不见该工具", "content": []}
        from packing_assistant.runtime.tool_engine import get_engine

        # 与其他工具同一道契约 + 策略闸；不走 execute、也不读熔断：缺重量这类业务上的 ok=False 不该把全进程的工具熔断。
        _, refused = get_engine().admit(tool, args, expert_id="pack-ship", intent=intent, circuit=False)
        held = refused or _write_needs_person(tool, rec.risk if rec else "low", intent)
        if held:
            return held
        out = _pack(tool, args)
        return {"ok": bool(out.get("ok", True)), "name": tool, **out}

    if tool in {"search_kb", "read_kb", "list_kb"}:
        if not eid or not cat:
            return {"ok": False, "error": "缺少 expert_id", "content": []}
        if tool == "list_kb":
            return {"ok": True, "name": tool, "files": list_kb(eid, cat)}
        if tool == "search_kb":
            from rag import search_kb

            hits = search_kb(eid, cat, str(args.get("query") or args.get("q") or ""))
            return {
                "ok": True,
                "name": tool,
                "hits": [{"path": h.path, "title": h.title, "snippet": h.snippet, "score": h.score} for h in hits],
            }
        rel = str(args.get("path") or args.get("uri") or "")
        got = read_resource(eid, cat, rel if rel.startswith("kb://") else f"kb://{rel}")
        text = got["contents"][0]["text"]
        ok = not str(text).startswith("拒绝")
        return {"ok": ok, "name": tool, "text": text}

    if tool in {"tender.parse", "tender.review", "write_deliverable"}:
        from packing_assistant.expert_roster import list_experts

        risk = rec.risk if rec else "low"
        # A --pack scope writes for every post in it, so it is gated at the riskiest one, not the default post.
        if not (expert_id or "").strip() and cat and any(e.risk == "high" for e in list_experts() if e.category == cat):
            risk = "high"
        return _engine_call(tool, args, expert_id=eid or "", risk=risk, intent=intent)
    if tool.endswith("__scan_forbidden") or tool == "scan_forbidden":
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(str(args.get("text") or args.get("draft") or ""))
        return {"ok": True, "name": tool, "hits": hits, "n": len(hits)}
    if rec and tool in rec.exclusive:
        args.setdefault("session_id", "mcp")
        return _engine_call(tool, args, expert_id=rec.id, risk=rec.risk, intent=intent)
    return {"ok": False, "error": f"未知工具 {name}", "content": []}
