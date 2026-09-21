"""The model-driven turn: what makes civil a Codex for civil work rather than a router.

Codex is a loop — the model reads the task, decides what to look at, calls tools, and
answers — held inside a sandbox and an approval policy. This is that loop for a job folder:

    skills     66 post SOPs with progressive disclosure: the catalog (name + description,
               inside the 8,000-character budget) is in the prompt; the model loads one
               SKILL.md with ``load_skill`` when the task calls for it
    look       ``search_kb`` (the post's knowledge base), ``list_job_files`` / ``read_job_file``
    act        ``run_skill`` drafts through the post's deterministic pipeline (the same
               ``run_agent`` the steps path uses, so the sandbox, the high-risk confirmation
               and the Office exports are unchanged); ``pack_plan`` runs the packing engine on
               a packing list; ``tender_compare`` runs the tender-vs-response workflow
    plan       ``update_plan``, shown to the user as it changes

The product's rule is that tools compute and the model only routes, and the loop holds it
two ways. By construction: ``run_skill`` hands the pipeline the user's own words plus the job
files the model picked — nothing the model wrote reaches a deliverable. By check: the one
place model text does go, the reply, passes ``tools/number_provenance``; a quantity or clause
number the turn never saw gets one rewrite, and whatever survives is listed to the user. The
same pass runs ``tools/verdict_guard``: a verdict the system may not give (可以订舱, 符合招标文件
的要求 — both seen from a live model) gets the same rewrite and, if it survives, is struck.

``agent_mode = "steps"`` (the default) never comes here; see runtime/turn.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from packing_assistant.runtime.bus import get_bus

CONFIRM = "我明白，将由持证人员签认"
MAX_STEPS = 10
_RESULT_CHARS = 6000

Complete = Callable[[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]], Dict[str, Any]]
Approve = Callable[[Dict[str, Any]], bool]


def _tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}


_TEXT = {"type": "string"}
TOOLS: List[Dict[str, Any]] = [
    _tool("update_plan", "列出或更新本次任务的步骤。多步任务先调一次，做完一步更新一次。",
          {"steps": {"type": "array", "items": {"type": "object", "properties": {
              "step": _TEXT, "status": {"type": "string", "enum": ["pending", "in_progress", "done"]}},
              "required": ["step", "status"]}}}, ["steps"]),
    _tool("load_skill", "读取一个岗位技能的完整 SOP（SKILL.md）。任务对得上目录里的某个岗位时先调它。",
          {"skill_id": _TEXT}, ["skill_id"]),
    _tool("search_kb", "在某个岗位的知识库里查资料，返回原文摘录。没查到就是没有，不要凭记忆补条文。",
          {"skill_id": _TEXT, "query": _TEXT}, ["skill_id", "query"]),
    _tool("list_job_files", "列出工地文件夹里可读的资料文件。", {}, []),
    _tool("read_job_file", "读取工地文件夹里的一个文件（xlsx / docx / pdf / csv / txt / md / json）的文字内容。",
          {"name": _TEXT}, ["name"]),
    _tool("run_skill", "要出一份岗位文稿（日报、交底、方案、台账、计划、函件……）时用它：让该岗位按确定性流程出稿"
                       "（Markdown / Word / Excel）。交给流程的是用户的原话，加上 files 里点名的资料文件全文；"
                       "你写的字不会进成稿，所以缺的事实要请用户补，不要自己补。",
          {"skill_id": _TEXT, "files": {"type": "array", "items": _TEXT}}, ["skill_id"]),
    _tool("pack_plan", "只在用户要装柜 / 拼柜 / 订舱方案时用：用装箱引擎给文件夹里已有的一份装箱单（货物清单表，"
                       "xlsx / csv / pdf）算方案。file 必须是 list_job_files 列出过的文件名。柜数、利用率只能来自这个工具。",
          {"file": _TEXT, "container_type": {"type": "string", "enum": ["20GP", "40GP", "40HQ"]}}, ["file"]),
    _tool("tender_compare", "只在用户要核对投标响应时用：对照文件夹里已有的招标文件与投标响应文件，逐条要求找候选响应，"
                       "并指出数值不一致处。两个文件名都必须是 list_job_files 列出过的。",
          {"tender_file": _TEXT, "response_file": _TEXT}, ["tender_file", "response_file"]),
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
#: 解析用户文件或写盘的工具。系统级沙箱开着时，它们在被内核限制的工作进程里执行（runtime/os_sandbox）；
#: 模型对话本身留在宿主进程——它需要网络，工作进程没有。
CONFINED_TOOLS = frozenset({"read_job_file", "run_skill", "pack_plan", "tender_compare"})

SYSTEM = """你是 Civil Buddy（土木版 Codex）：在用户的工地文件夹里，替土木工程师把事情办完的 agent。

怎么干活（先看，再动手，最后交代清楚）：
1. 任务要分几步的，先调 update_plan 列步骤，做完一步更新一次。
2. 选岗位：下面有岗位技能目录（名称 + 说明）。任务对得上某个岗位，就 load_skill 读它的 SOP，照 SOP 办；对不上就直接回答，并说明这不是专家稿。
3. 资料从工具来：search_kb 查岗位知识库；list_job_files / read_job_file 读工地文件夹里的资料。没读过的不要假装读过。
4. 出稿、装箱、对标交给工具：run_skill / pack_plan / tender_compare。你负责选岗位、点名资料文件、核对缺项、把结果讲清楚。

硬规则：
- 数字只能来自工具结果、用户原文、本工程说明（CIVIL.md）或你读过的资料。你自己不算、不估、不凭记忆补数字；没有来源的量写 UNSPECIFIED 或 [A001] 待填。
- 不编条款号、规范条文、单价、坐标。规范只写标题与年份。
- 不下「可以投标 / 可以开工 / 报审通过」这类结论，不代签。所有产出都是内部讨论草稿，不可递交。
- 工具返回 approval_required 或 read_only 时停下来，把原因告诉用户，不要换个工具绕过去。
- 用中文回答：先说结论和文件位置，再说缺项和下一步。"""


@dataclass
class _Turn:
    session_id: str
    run_id: str
    user_text: str
    confirmed: bool
    approve: Optional[Approve]
    cancel_event: Any = None
    evidence: List[str] = field(default_factory=list)
    files: List[Dict[str, str]] = field(default_factory=list)
    tools_run: List[str] = field(default_factory=list)
    plan: List[Dict[str, str]] = field(default_factory=list)
    skill: str = ""
    hitl_pending: bool = False
    wrote: bool = False

    def emit(self, kind: str, payload: Dict[str, Any]) -> None:
        get_bus().emit(self.run_id, kind, payload)

    def add_files(self, rows: Any) -> List[str]:
        from packing_assistant.civil import display_path

        shown = []
        for row in rows or []:
            path = str(row.get("path") or "") if isinstance(row, dict) else str(row)
            if not path:
                continue
            if all(f["path"] != path for f in self.files):
                self.files.append({"name": Path(path).name, "path": path,
                                   "tool": str(row.get("tool") or "") if isinstance(row, dict) else ""})
            shown.append(display_path(path))
        self.wrote = self.wrote or bool(shown)
        return shown


# ---------------------------------------------------------------------------
# the job folder
# ---------------------------------------------------------------------------

def _job_path(name: Any) -> Optional[Path]:
    from packing_assistant.office_job import job_file_by_name

    return job_file_by_name(name)


def job_files() -> List[Dict[str, Any]]:
    from packing_assistant.office_job import job_tree_files

    return [{"name": row["name"], "bytes": row["bytes"]} for row in job_tree_files()]


def _file_text(path: Path, limit: int) -> str:
    from packing_assistant.office_job import read_material

    return read_material(path, limit)


def _not_found(name: Any) -> Dict[str, Any]:
    listed = "、".join(row["name"] for row in job_files()[:12]) or "（空，或还没进入作业文件夹）"
    return {"ok": False, "error_code": "not_found", "reason": f"工地文件夹里没有 {name!r}。现有：{listed}"}


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

def _expert(skill_id: Any):
    from packing_assistant.expert_roster import get_expert

    return get_expert(str(skill_id or "").strip().lstrip("$@"))


def _unknown_skill(skill_id: Any) -> Dict[str, Any]:
    from packing_assistant.runtime.expert_skills import format_catalog_listing

    return {"ok": False, "error_code": "unknown_skill",
            "reason": f"没有岗位 {skill_id!r}。相近的岗位：\n" + format_catalog_listing(str(skill_id or ""), limit=6)}


def _gate(turn: _Turn, *, risk: str, who: str) -> Optional[Dict[str, Any]]:
    """None when the write may go ahead; otherwise the result the model gets instead of the write."""
    from packing_assistant.runtime.civil_config import decide_gate, load_config

    gate = decide_gate(intent="run", risk=risk, confirmed=turn.confirmed, cfg=load_config())
    if gate == "go":
        return None
    if gate == "read_only":
        return {"ok": False, "error_code": "read_only",
                "reason": "sandbox=read-only：本轮只读，不写盘。要成稿请用户改用 /sandbox workspace-write。"}
    request = {"name": who, "risk": risk, "confirm_sentence": CONFIRM}
    turn.emit("hitl", {"required": True, **request})
    if turn.approve is not None and turn.approve(request):
        turn.confirmed = True
        return None
    turn.hitl_pending = True
    return {"ok": False, "error_code": "approval_required", "risk": risk,
            "reason": f"{who} 写盘前需要用户打确认句「{CONFIRM}」。本次未写盘；把这一点告诉用户，不要改用别的工具绕过。"}


def _update_plan(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    steps = []
    for row in (args.get("steps") or [])[:12]:
        if isinstance(row, dict) and str(row.get("step") or "").strip():
            status = str(row.get("status") or "pending")
            steps.append({"step": str(row["step"]).strip()[:200],
                          "status": status if status in {"pending", "in_progress", "done"} else "pending"})
    turn.plan = steps
    turn.emit("plan", {"steps": steps})
    return {"ok": True, "steps": len(steps)}


def _load_skill(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.runtime.expert_skills import skill_body

    exp = _expert(args.get("skill_id"))
    if exp is None:
        return _unknown_skill(args.get("skill_id"))
    turn.skill = exp.id
    turn.emit("skill_loaded", {"id": exp.id, "name": exp.name, "risk": exp.risk})
    return {"ok": True, "skill_id": exp.id, "name": exp.name, "risk": exp.risk,
            "delivers": exp.delivers, "sop": skill_body(exp.id)[:_RESULT_CHARS - 600]}


def _search_kb(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.expert_turn import _kb_snip

    exp = _expert(args.get("skill_id") or turn.skill)
    if exp is None:
        return _unknown_skill(args.get("skill_id"))
    excerpts = _kb_snip(exp, str(args.get("query") or ""), limit=1800)
    return {"ok": True, "skill_id": exp.id, "excerpts": excerpts or "（知识库没有命中；不要凭记忆补条文或数字）"}


def _list_job_files(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.office_job import job_root_granted

    if not job_root_granted():
        return {"ok": False, "error_code": "no_job_folder", "reason": "还没进入作业文件夹（civil init，或 civil -C <文件夹>）。"}
    return {"ok": True, "files": job_files()}


def _read_job_file(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    path = _job_path(args.get("name"))
    if path is None:
        return _not_found(args.get("name"))
    try:
        text = _file_text(path, _RESULT_CHARS - 400)
    except Exception as exc:  # noqa: BLE001 - a damaged workbook is a result, not a crash
        return {"ok": False, "error_code": "unreadable", "reason": f"{path.name} 读不出来：{type(exc).__name__}"}
    return {"ok": True, "name": path.name, "text": text}


def _preview(files: List[Dict[str, str]]) -> str:
    for row in files:
        if str(row.get("path") or "").endswith(".md"):
            try:
                return Path(row["path"]).read_text(encoding="utf-8")[:1500]
            except OSError:
                return ""
    return ""


def _run_skill(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.office_job import named_files_blob
    from packing_assistant.runtime.agent_loop import run_agent

    exp = _expert(args.get("skill_id"))
    if exp is None:
        return _unknown_skill(args.get("skill_id"))
    chosen: List[Path] = []
    for name in args.get("files") or []:
        path = _job_path(name)
        if path is None:
            return _not_found(name)
        chosen.append(path)
    turn.skill = exp.id
    blocked = _gate(turn, risk=exp.risk, who=exp.name)
    if blocked:
        return {**blocked, "skill_id": exp.id}
    # 交给确定性流程的只有用户自己的话和他文件夹里的资料——模型写的字到不了成稿。
    material = named_files_blob(chosen, reader=_file_text)
    text = f"{turn.user_text}\n\n{material}".strip() if material else turn.user_text
    out = run_agent(text, session_id=turn.session_id, expert_id=exp.id, p0_confirmed=turn.confirmed,
                    force_intent="run", cancel_event=turn.cancel_event)
    if out.get("hitl_pending"):
        turn.hitl_pending = True
        return {"ok": False, "error_code": "approval_required", "skill_id": exp.id, "reason": str(out.get("reply") or "")}
    shown = turn.add_files(out.get("files"))
    return {"ok": bool(out.get("ok")), "error_code": out.get("error_code") or "", "skill_id": exp.id,
            "tools_run": out.get("tools_run") or [], "summary": str(out.get("reply") or "")[:600],
            "files": shown, "preview": _preview(out.get("files") or [])}


# 给模型的结果只留含义不会被读错的键，其余的数都放在带中文标签的 report 里。
# 实测（qwen2.5:3b）：裸键 payload_kg（柜体额定载重）被说成了「货物总重」——数字有出处，含义是错的，
# 数字溯源查不出这种错，只能不给它留误读的余地。
_PLAN_KEYS = ("ok", "source", "error", "detail", "needs_human", "n_rows", "can_fit", "containers_used", "container_type",
              "n0", "n_materials", "n_boxes")


def pack_report_md(result: Dict[str, Any], file_name: str) -> str:
    from packing_assistant.tools.pack_ship_solve import plan_report_md

    return plan_report_md(result, file_name)


def _pack_plan(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.runtime import agent_loop
    from packing_assistant.runtime.tool_engine import get_engine
    from packing_assistant.tools.pack_ship_solve import run_plan

    path = _job_path(args.get("file"))
    if path is None:
        return _not_found(args.get("file"))
    exp = _expert("pack-ship")
    turn.skill = turn.skill or "pack-ship"
    result = run_plan(file_path=str(path), container_type=str(args.get("container_type") or "40HQ"))
    report = pack_report_md(result, path.name)
    out = {"file": path.name, **{key: result[key] for key in _PLAN_KEYS if key in result}, "report": report}
    blocked = _gate(turn, risk=exp.risk if exp else "low", who="装柜方案")
    if blocked:
        return {**out, "saved": "未写盘：" + blocked["reason"]}
    target = agent_loop._OUT / agent_loop._safe_sid(turn.session_id) / "pack-ship" / "pack-plan.md"
    saved = get_engine().execute("write_deliverable", {"path": str(target), "text": report}, intent="run", cancelled=False)
    if saved.get("ok"):
        from packing_assistant.tools.pack_ship_solve import plan_record_json

        record = get_engine().execute("write_deliverable", {"path": str(target.with_suffix(".json")),
                                                            "text": plan_record_json(result, path.name)}, intent="run", cancelled=False)
        out["files"] = turn.add_files([{"path": str(saved.get("path") or target), "tool": "pack-ship__plan"}]
                                      + ([{"path": str(record.get("path")), "tool": "pack-ship__plan"}] if record.get("ok") else []))
    else:
        out["saved"] = "未写盘：" + str(saved.get("reason") or saved.get("error_code") or "")
    return out


def _tender_compare(turn: _Turn, args: Dict[str, Any]) -> Dict[str, Any]:
    from packing_assistant.runtime import agent_loop
    from packing_assistant.runtime.tender_workflow import run_tender_workflow

    paths: Dict[str, Path] = {}
    for role in ("tender", "response"):
        path = _job_path(args.get(role + "_file"))
        if path is None:
            return _not_found(args.get(role + "_file"))
        paths[role] = path
    turn.skill = turn.skill or "bid-compliance"
    blocked = _gate(turn, risk="low", who="招标对照")
    if blocked:
        return blocked
    from packing_assistant.office_job import read_material_checked

    texts: Dict[str, str] = {}
    unread: List[Dict[str, str]] = []
    for role, path in paths.items():
        body, why = read_material_checked(path, 2_000_000, reader=_file_text)
        if why:
            unread.append({"title": path.name, "role": role, "reason": why})
        else:
            texts[role] = body
    if "tender" not in texts:
        return {"ok": False, "error_code": "unreadable", "unreadable": unread, "submit_blocked": True,
                "reason": f"招标文件 {paths['tender'].name} 没读出来（{unread[0]['reason']}）。没有招标正文无从对照，未写盘。"}
    sources = [{"source_id": role + "-1", "title": paths[role].name, "text": texts[role], "start": 0,
                "end": len(texts[role]), "role": role, "kind": "job_file"} for role in ("tender", "response") if role in texts]
    result = run_tender_workflow(texts["tender"], session_id=turn.session_id, output_root=agent_loop._OUT,
                                 sources=sources, unreadable=unread, confirmed=turn.confirmed, cancel_event=turn.cancel_event)
    shown = turn.add_files(result.get("files"))
    review = result.get("review") or {}
    rows = [{"ref": row.get("requirement_ref"), "requirement": row.get("requirement"), "status": row.get("status"),
             "response": [e.get("quote") for e in row.get("response_evidence") or []][:3],
             "notes": [c.get("note") for c in row.get("conflicts") or []]}
            for row in review.get("response_comparison") or []]
    return {"ok": bool(result.get("ok")), "error_code": result.get("error_code") or "", "submit_blocked": True,
            "summary": str(result.get("reply") or ""), "rows": rows[:40], "unreadable": unread,
            "conflicts": [c.get("note") for c in review.get("conflicts") or []], "files": shown}


_DISPATCH: Dict[str, Callable[[_Turn, Dict[str, Any]], Dict[str, Any]]] = {
    "update_plan": _update_plan, "load_skill": _load_skill, "search_kb": _search_kb,
    "list_job_files": _list_job_files, "read_job_file": _read_job_file, "run_skill": _run_skill,
    "pack_plan": _pack_plan, "tender_compare": _tender_compare,
}


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

def _dispatch(turn: _Turn, name: str, arguments: Dict[str, Any], worker: Any) -> Dict[str, Any]:
    if worker is None or name not in CONFINED_TOOLS:
        return _DISPATCH[name](turn, arguments)

    def once() -> Dict[str, Any]:
        reply = worker.call("model_tool", name=name, arguments=arguments, session_id=turn.session_id, run_id=turn.run_id,
                            user_text=turn.user_text, confirmed=turn.confirmed)["out"]
        return reply if isinstance(reply.get("result"), dict) else {"result": {"ok": False, "error_code": "worker_failed",
                                                                                "reason": str(reply.get("reply") or reply)[:300]}}

    reply = once()
    if reply["result"].get("error_code") == "approval_required" and turn.approve is not None:
        exp = _expert(arguments.get("skill_id")) if arguments.get("skill_id") else None
        request = {"name": exp.name if exp else name, "risk": reply["result"].get("risk") or "high", "confirm_sentence": CONFIRM}
        if turn.approve(request):       # the question is asked here, in the host; the worker has no terminal
            turn.confirmed = True
            reply = once()
    turn.add_files(reply.get("files"))
    turn.skill = str(reply.get("skill") or turn.skill)
    turn.hitl_pending = bool(reply.get("hitl_pending")) and reply["result"].get("error_code") == "approval_required"
    return reply["result"]


def system_prompt(context_prefix: str = "") -> str:
    from packing_assistant.runtime.expert_skills import catalog_preamble
    from packing_assistant.runtime.project_instructions import load

    parts = [SYSTEM, load().prompt_block(), context_prefix, catalog_preamble()]
    return "\n\n".join(part for part in parts if part)


_SENTENCE_END = re.compile(r"(?<=[。！？!?\n])")


def collapse_repeats(text: str) -> Tuple[str, int]:
    """A sentence said once is enough. Small models loop: a live qwen2.5:3b rewrite repeated
    「订舱后，由用户确认系固方案并完成订舱手续。」 about forty times, up to the token limit.
    Returns the text with every later copy of a sentence (6+ characters) dropped, and how many were dropped.
    """
    seen, kept, dropped = set(), [], 0
    for part in _SENTENCE_END.split(text or ""):
        key = part.strip()
        if len(key) >= 6 and key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(part)
    return "".join(kept).rstrip() if dropped else text, dropped


def _guarded(reply: str, turn: _Turn, messages: List[Dict[str, Any]], complete: Complete) -> Tuple[str, Dict[str, Any]]:
    """The reply, checked twice: every number traced, no verdict stated. One rewrite, then the rest is dealt with.

    An untraced number that survives the rewrite is listed to the user. A verdict that survives
    (可以订舱, 符合招标文件的要求 ...) is struck from the text and listed: a wrong number can be
    checked by the reader, a verdict from the system is the thing the product may not produce.
    """
    from packing_assistant.tools import number_provenance, verdict_guard

    reply, repeats = collapse_repeats(reply)
    numbers = number_provenance.untraced(reply, turn.evidence)
    verdicts = verdict_guard.stated_verdicts(reply)
    report: Dict[str, Any] = {"checked": True, "rewrites": 0, "untraced": [], "verdicts": []}
    if numbers or verdicts:
        turn.emit("guard", {"untraced": [item["text"] for item in numbers], "verdicts": [item["text"] for item in verdicts],
                            "action": "rewrite"})
        asks = []
        if numbers:
            asks.append("这些数字或条款号在本轮的工具结果、用户原文和已读资料里都没有出处："
                        + "、".join(dict.fromkeys(item["text"] for item in numbers))
                        + "。删掉它们，或写成 UNSPECIFIED / [A001] 待填；不要引入任何新数字。")
        if verdicts:
            asks.append("这些话是在下结论，而结论不由你下："
                        + "、".join(dict.fromkeys(item["text"] for item in verdicts))
                        + "。改成陈述工具给出的事实，并说明由谁来判断。")
        retry = messages + [{"role": "assistant", "content": reply},
                            {"role": "user", "content": "【系统核对】" + " ".join(asks) + " 只输出改写后的回复。"}]
        report["model_calls"] = 1
        try:
            rewritten = str(complete(retry, None).get("content") or "").strip()
        except Exception:  # noqa: BLE001 - the first reply is still delivered, guarded below
            rewritten = ""
        if rewritten:
            reply, again = collapse_repeats(rewritten)
            repeats += again
            report["rewrites"] = 1
            numbers = number_provenance.untraced(reply, turn.evidence)
            verdicts = verdict_guard.stated_verdicts(reply)
    tail = []
    if verdicts:
        report["verdicts"] = list(dict.fromkeys(item["text"] for item in verdicts))
        reply = verdict_guard.strike(reply, verdicts)
        tail.append(verdict_guard.notice(verdicts))
    if numbers:
        report["untraced"] = list(dict.fromkeys(item["text"] for item in numbers))
        tail.append(number_provenance.notice(numbers))
    if tail:
        turn.emit("guard", {"untraced": report["untraced"], "verdicts": report["verdicts"], "action": "notice"})
        reply = reply.rstrip() + "\n\n" + "\n".join(tail)
    if repeats:
        report["repeats_dropped"] = repeats
    return reply, report


def run_model_agent(text: str, *, session_id: str = "", expert_id: str = "", p0_confirmed: bool = False,
                    history: Optional[List[Dict[str, str]]] = None, complete: Optional[Complete] = None,
                    approve: Optional[Approve] = None, max_steps: int = MAX_STEPS,
                    cancel_event: Any = None, worker: Any = None) -> Dict[str, Any]:
    from packing_assistant.runtime.agent_loop import _scrub
    from packing_assistant.runtime.civil_config import load_config
    from packing_assistant.runtime.expert_skills import skill_body
    from packing_assistant.runtime.memory import assemble_context, prompt_prefix
    from packing_assistant.runtime.model_client import ModelError, complete as default_complete
    from packing_assistant.runtime.project_instructions import seed_session

    complete = complete or default_complete
    cfg = load_config()
    sid = session_id or f"sess-{uuid4().hex[:8]}"
    seed_session(sid)
    ctx = assemble_context(sid, text=text, p0_confirmed=p0_confirmed or cfg.auto_confirm())
    turn = _Turn(session_id=sid, run_id="run-" + uuid4().hex[:8], user_text=text, approve=approve,
                 cancel_event=cancel_event, confirmed=ctx.get("p0_confirmed") is True)
    system = system_prompt(prompt_prefix(ctx))
    past = [{"role": m["role"], "content": str(m.get("content") or "")} for m in history or []
            if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]
    turn.evidence += [system, text] + [m["content"] for m in past]
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system}, *past]
    pinned = _expert(expert_id) if expert_id else None
    turn.emit("run_started", {"intent": "model", "expert_id": pinned.id if pinned else ""})
    if pinned:    # 用户点名的岗位（$id / --skill）：SOP 直接给，和 Codex 显式 $skill 一样
        loaded = _load_skill(turn, {"skill_id": pinned.id})
        turn.evidence.append(str(loaded.get("sop") or ""))
        messages.append({"role": "system", "content": f"用户点名了岗位 ${pinned.id}（{pinned.name}）。它的 SOP：\n\n{skill_body(pinned.id)[:_RESULT_CHARS]}"})
    messages.append({"role": "user", "content": text})

    out: Dict[str, Any] = {"ok": True, "schema": "civil.agent.v1", "agent_mode": "model", "session_id": sid,
                           "run_id": turn.run_id, "submit_blocked": True, "sandbox_mode": cfg.sandbox,
                           "approval": cfg.approval, "cloud": False, "generic_shell": False, "error_code": ""}
    reply, model_calls, last_call = "", 0, ""
    try:
        for _step in range(max(1, max_steps)):
            if cancel_event is not None and cancel_event.is_set():
                out.update(ok=False, cancelled=True, error_code="cancelled")
                reply = "本轮已取消；已完成的文件保留。"
                turn.emit("cancelled", {"wrote": turn.wrote})
                break
            message = complete(messages, TOOLS)
            model_calls += 1
            calls = message.get("tool_calls") or []
            if not calls:
                reply = str(message.get("content") or "").strip()
                break
            messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}} for c in calls]})
            for call in calls:
                name = str(call.get("name") or "")
                arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
                signature = name + json.dumps(arguments, ensure_ascii=False, sort_keys=True)
                turn.emit("tool_call", {"name": name, "arguments": arguments})
                if name not in _DISPATCH:
                    result: Dict[str, Any] = {"ok": False, "error_code": "unknown_tool",
                                              "reason": f"没有工具 {name}。可用：" + "、".join(sorted(TOOL_NAMES))}
                elif signature == last_call:
                    result = {"ok": False, "error_code": "repeated_call", "reason": "和上一步完全相同的调用。换一种做法，或者直接回答用户。"}
                else:
                    try:
                        result = _dispatch(turn, name, arguments, worker)
                    except Exception as exc:  # noqa: BLE001 - a tool failure is a result the model can react to
                        result = {"ok": False, "error_code": "tool_failed", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
                last_call = signature
                turn.tools_run.append(name)
                content = json.dumps(result, ensure_ascii=False, default=str)[:_RESULT_CHARS]
                turn.evidence.append(content)
                turn.emit("tool_result", {"name": name, "ok": bool(result.get("ok", True)),
                                          "error_code": result.get("error_code") or "ok", "files": result.get("files") or []})
                messages.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": content})
        else:
            reply = "达到本轮步数上限。已完成的部分见文件清单；请把任务拆小，或接着说「继续」。"
            out["error_code"] = "max_steps"
    except ModelError as exc:
        out.update(ok=False, error_code="model_unavailable")
        reply = str(exc)

    provenance: Dict[str, Any] = {"checked": False, "rewrites": 0, "untraced": [], "verdicts": []}
    if out["ok"] and reply and not out["error_code"]:
        reply, provenance = _guarded(reply, turn, messages, complete)
        model_calls += provenance.pop("model_calls", 0)
    # 确认句只有用户亲手输入才算数；模型把它抄进回复（实测 qwen2.5:3b 会）既无效又误导。
    reply = _scrub(reply or "模型没有返回正文；请再说一次，或把任务拆小。").replace(CONFIRM, "（确认句须由用户本人输入）")
    turn.emit("message", {"text": reply})
    exp = _expert(turn.skill) if turn.skill else None
    out.update(reply=reply, intent="run" if turn.wrote else "chat", wrote=turn.wrote, files=turn.files,
               artifacts=[f["path"] for f in turn.files], skill=turn.skill, expert_id=turn.skill,
               expert_name=exp.name if exp else "", tools_run=turn.tools_run, tools_used=list(turn.tools_run),
               skill_source=("given" if pinned and pinned.id == turn.skill else "model") if turn.skill else "",
               hitl_pending=turn.hitl_pending, plan=turn.plan, provenance=provenance,
               usage={"model_calls": model_calls, "tool_calls": len(turn.tools_run)})
    turn.emit("run_ended", {"state": "done" if out["ok"] else "failed", "wrote": turn.wrote})
    out["events"] = [e.to_dict() for e in get_bus().for_run(turn.run_id)]
    return out
