"""Every summoned expert uses the same understand → chat | run | both loop.

Writes only exclusive tools (or HITL pending). No 66 personality prompts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from packing_assistant.expert_roster import ExpertRec, exclusive_tools, get_expert, list_experts
from packing_assistant.sandbox import guarded_write_text
from packing_assistant.understand import understand

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "demo" / "out"
DISCLAIMER = (
    "本文件由 Civil Buddy 根据用户输入生成，仅供内部讨论与起草。"
    "不构成设计文件、法定专项施工方案、交底签认件、监理指令、专家论证材料或开工/竣工验收依据。"
)
CONFIRM = "我明白，将由持证人员签认"
FORBIDDEN = ("可以投标", "可以开工", "中标率")


def _kb_snip(expert: ExpertRec, query: str, limit: int = 900) -> str:
    paths = [
        _ROOT / "demo" / "kb" / expert.category / expert.id / "web-knowledge.md",
        _ROOT / "demo" / "kb" / expert.category / "_shared" / "web-knowledge.md",
    ]
    chunks: List[str] = []
    q = (query or "").strip()
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if q and q in text:
            i = text.find(q)
            chunks.append(text[max(0, i - 80) : i + 400])
        else:
            chunks.append(text[:limit])
        if sum(len(c) for c in chunks) >= limit:
            break
    return "\n".join(chunks)[:limit].strip()


def explain_expert(expert: ExpertRec, text: str) -> str:
    bits = [
        f"本岗：{expert.name}（{expert.category_name} / {expert.id}）。内部讨论 AI 草稿。提问不写盘，不判定可投标。",
        expert.title,
    ]
    blob = text or ""
    if "GST" in blob.upper() or "税率" in blob or expert.id == "finance-tax":
        bits.append(
            "IRAS 页述：The current GST rate in Singapore is 9%（Current GST rates）。税额待持证办税人员按当期文件算。"
        )
    if any(k in blob for k in ("危大", "临边", "专家论证")) or expert.id == "method-hazard":
        bits.append(
            "是否危大、要不要专家论证，须由持证人员按专项目录与现场判定。本岗不判定可以开工。"
        )
    snip = _kb_snip(expert, blob)
    if snip:
        bits.append("本岗可见知识摘录：\n" + snip)
    bits.append("要成稿请明说写/编制/出一份。高风险写盘须确认句：「" + CONFIRM + "」。")
    reply = "\n".join(b for b in bits if b)
    for bad in FORBIDDEN:
        if bad in reply and f"不判定{bad}" not in reply and f"不{bad}" not in reply:
            reply = reply.replace(bad, "（禁止断言）")
    return reply


def _write_tools(expert: ExpertRec) -> List[str]:
    return [t for t in expert.exclusive if "fill_scheme" not in t]


def _draft_markdown(expert: ExpertRec, tool: str, text: str) -> str:
    return (
        f"# {expert.name} · {tool}\n\n{DISCLAIMER}\n\n"
        f"- 专家：{expert.id}\n- 独有工具：{tool}\n- 产出口径：{expert.delivers}\n"
        f"- 缺的数字 [A001] / UNSPECIFIED\n\n"
        f"## 用户原文\n\n{text.strip() or '（未提供）'}\n\n"
        f"## 草稿\n\n按本岗独有工具出内部讨论提纲。规范只写全名，条款 UNSPECIFIED。"
        f"不是签认件，不判定可投标，不判定可以开工。\n"
    )


def _run_exclusive(
    expert: ExpertRec,
    text: str,
    *,
    confirm_ok: bool,
    session_id: str,
) -> Dict[str, Any]:
    tools = _write_tools(expert)
    if expert.risk == "high" and not confirm_ok:
        return {
            "wrote": False,
            "hitl_pending": True,
            "files": [],
            "tools_run": [],
            "reply": f"高风险岗 {expert.name} 写盘须确认句「{CONFIRM}」。本轮未写盘。",
            "submit_blocked": True,
        }
    out_dir = _OUT / session_id / expert.id
    out_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, str]] = []
    ran: List[str] = []

    if expert.id == "bid-parse":
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        pipe = run_tender_pipeline(text, source="expert-turn", project_name=expert.name)
        path = out_dir / "bid-parse__extract.md"
        guarded_write_text(path, str(pipe.get("extract_table_markdown") or _draft_markdown(expert, "bid-parse__extract", text)))
        files.append({"name": path.name, "path": str(path), "tool": "bid-parse__extract"})
        ran.append("bid-parse__extract")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已按招标解析岗抽出表。仍是 AI 草稿，submit_blocked=true。",
            "submit_blocked": True,
            "matrix": pipe.get("matrix"),
            "handoff": pipe.get("handoff"),
            "review": pipe.get("review"),
            "submit_block_reason": pipe.get("submit_block_reason"),
        }

    if expert.id == "pack-ship":
        from packing_assistant.tools.pack_ship_mcp import call_tool

        listed = call_tool("pack-ship__list", {})
        plan = call_tool("pack-ship__plan", {"connected": False, "materials": text})
        exported = call_tool("pack-ship__export", {"connected": False})
        path = out_dir / "pack-ship__export.md"
        guarded_write_text(path, str(exported.get("markdown") or ""))
        files.append({"name": path.name, "path": str(path), "tool": "pack-ship__export"})
        ran.extend(["pack-ship__list", "pack-ship__plan", "pack-ship__export"])
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "装柜证据只抄 solver；本轮未接通，utilization/can_fit/mid50/系固待办 为 UNSPECIFIED。",
            "submit_blocked": True,
            "pack_ship": {"list": listed.get("names"), "plan": plan, "export": exported},
        }

    if not tools:
        tools = [f"{expert.id}__draft"]
    for tool in tools:
        md = _draft_markdown(expert, tool, text)
        path = out_dir / f"{tool}.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": tool})
        ran.append(tool)
    return {
        "wrote": True,
        "hitl_pending": False,
        "files": files,
        "tools_run": ran,
        "reply": f"{expert.name} 已出内部讨论草稿（{', '.join(ran)}）。不可递交。",
        "submit_blocked": True,
    }


def run_expert_turn(
    text: str,
    expert_id: str,
    *,
    confirm_ok: bool = False,
    session_id: str = "",
    force_intent: Optional[str] = None,
) -> Dict[str, Any]:
    exp = get_expert(expert_id)
    if not exp:
        return {
            "ok": False,
            "schema": "civil.expert_turn.v1",
            "error": f"unknown expert: {expert_id}",
            "intent": "chat",
            "wrote": False,
        }
    intent = force_intent if force_intent in {"chat", "run", "both"} else understand(text)
    base: Dict[str, Any] = {
        "ok": True,
        "schema": "civil.expert_turn.v1",
        "intent": intent,
        "expert_id": exp.id,
        "expert_name": exp.name,
        "category": exp.category,
        "exclusive": list(exp.exclusive),
        "risk": exp.risk,
        "wrote": False,
        "hitl_pending": False,
        "files": [],
        "tools_run": [],
        "reply": "",
        "submit_blocked": True,
        "n_experts": len(list_experts()),
    }
    if intent == "chat":
        base["reply"] = explain_expert(exp, text)
        return base
    sid = session_id or f"turn-{uuid4().hex[:8]}"
    ran = _run_exclusive(exp, text, confirm_ok=confirm_ok, session_id=sid)
    if intent == "both":
        ran["reply"] = explain_expert(exp, text) + "\n\n" + str(ran.get("reply") or "")
    base.update(ran)
    base["session_id"] = sid
    return base
