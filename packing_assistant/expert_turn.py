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


_SCHEME_CHAPTERS = (
    "封面与文件控制",
    "草稿与责任声明",
    "工程概况",
    "编制依据",
    "施工部署与工艺",
    "质量",
    "安全与应急",
    "环保与文明施工",
    "资源计划",
    "验收与资料",
    "附录",
)


def _construction_eleven(text: str) -> str:
    lines = [
        "# 专项施工方案讨论提纲（AI 草稿）",
        "",
        DISCLAIMER,
        "",
        "不是法定专项方案，不是签认件。缺数 [A001]。条款 UNSPECIFIED。",
        "",
        "## 用户原文",
        "",
        (text or "").strip() or "（未提供）",
        "",
    ]
    for i, title in enumerate(_SCHEME_CHAPTERS, 1):
        lines.append(f"## {i} {title}")
        lines.append("")
        if i == 2:
            lines.append(DISCLAIMER)
        elif i == 10:
            lines.append("验收结论待持证人员。本页不给合格结论。")
        else:
            lines.append("待按项目 pack / 图纸填写。[A001]")
        lines.append("")
    return "\n".join(lines)


_COVERED = frozenset({"covered", "ok", "done"})
_OPEN = frozenset({"gap", "pending", "missing", "uncovered", "open", "partial", "human_required", "review"})


def _compliance_gaps_md(handoff: Optional[Dict[str, Any]], matrix: Optional[Dict[str, Any]]) -> str:
    rows = (matrix or {}).get("rows") or []
    responded: List[str] = []
    unresponded: List[str] = []
    absent: List[str] = []
    if not rows and not handoff:
        absent.append("本会话无 tender.handoff.json，招标未提供可对照正文。")
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or r.get("exact_text") or r.get("req_id") or "").strip()
        if not title:
            continue
        st = str(r.get("status") or "")
        line = title[:180]
        if st in _COVERED:
            responded.append(line)
        else:
            unresponded.append(line)
    if handoff and not rows:
        for key, label in (("star_items", "★项"), ("scoring_points", "评分点"), ("specials", "专项")):
            items = handoff.get(key) or []
            for it in items:
                text = str((it or {}).get("text") or "")[:180]
                if text:
                    unresponded.append(f"{label}：{text}")
        if not (handoff.get("scoring_points") or handoff.get("star_items") or handoff.get("specials")):
            absent.append("交接在，但未抽出评分点/★/专项；招标未提供这些栏位的正文。")
    lines = [
        "# 废标检查岗 · 三列对照",
        "",
        DISCLAIMER,
        "",
        "不代判废标。须持证人员按招标文件确认。submit_blocked=true。",
        "",
        "## 已响应",
        "",
    ]
    lines.extend([f"- {x}" for x in responded] or ["- （空）"])
    lines.extend(["", "## 未响应", ""])
    lines.extend([f"- {x}" for x in unresponded] or ["- （空）"])
    lines.extend(["", "## 招标未提供", ""])
    lines.extend([f"- {x}" for x in absent] or ["- （本轮无「招标未提供」栏）"])
    lines.extend(["", "条款号 UNSPECIFIED。不判定可投标。", ""])
    return "\n".join(lines)


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
    packing_summary: Optional[Dict[str, Any]] = None,
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
        from packing_assistant.runtime.session_handoff import save_handoff
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        pipe = run_tender_pipeline(text, source="expert-turn", project_name=expert.name)
        path = out_dir / "bid-parse__extract.md"
        guarded_write_text(path, str(pipe.get("extract_table_markdown") or _draft_markdown(expert, "bid-parse__extract", text)))
        files.append({"name": path.name, "path": str(path), "tool": "bid-parse__extract"})
        ran.append("bid-parse__extract")
        ho = pipe.get("handoff") if isinstance(pipe.get("handoff"), dict) else {}
        hp = save_handoff(session_id, ho)
        if hp:
            files.append({"name": hp.name, "path": str(hp), "tool": "tender.handoff"})
            ran.append("tender.handoff")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已按招标解析岗抽出表，并落下 tender.handoff.json 供后岗读。仍是 AI 草稿，submit_blocked=true。",
            "submit_blocked": True,
            "matrix": pipe.get("matrix"),
            "handoff": pipe.get("handoff"),
            "review": pipe.get("review"),
            "submit_block_reason": pipe.get("submit_block_reason"),
        }

    if expert.id == "bid-compliance":
        from packing_assistant.runtime.session_handoff import load_handoff, save_handoff
        from packing_assistant.tools.tender_parse import run_tender_pipeline

        ho = load_handoff(session_id)
        matrix = None
        if text and len(text.strip()) > 40:
            pipe = run_tender_pipeline(text, source="expert-compliance", project_name=expert.name)
            matrix = pipe.get("matrix") if isinstance(pipe.get("matrix"), dict) else None
            if isinstance(pipe.get("handoff"), dict) and pipe.get("handoff"):
                ho = pipe["handoff"]
                save_handoff(session_id, ho)
        md = _compliance_gaps_md(ho, matrix)
        path = out_dir / "bid-compliance__gaps.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "bid-compliance__gaps"})
        ran.append("bid-compliance__gaps")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已按交接/矩阵出三列对照。不代判废标。submit_blocked=true。",
            "submit_blocked": True,
            "handoff": ho,
            "matrix": matrix,
        }

    if expert.id == "bid-tech":
        from packing_assistant.runtime.session_handoff import load_handoff, save_handoff
        from packing_assistant.tools.tender_parse import build_tech_outline_from_handoff, run_tender_pipeline

        ho = load_handoff(session_id)
        if (not ho) and text and len(text.strip()) > 40:
            pipe = run_tender_pipeline(text, source="expert-tech", project_name=expert.name)
            if isinstance(pipe.get("handoff"), dict) and pipe.get("handoff"):
                ho = pipe["handoff"]
                save_handoff(session_id, ho)
        outline = build_tech_outline_from_handoff(ho or {}, project_name=expert.name)
        md = str(outline.get("markdown") or "")
        if not outline.get("from_extracted_scores"):
            md += "\n\n原文未检出评分点。禁止套上个项目技术标目录。条款 UNSPECIFIED。\n"
        path = out_dir / "bid-tech__expand.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "bid-tech__expand"})
        ran.append("bid-tech__expand")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": (
                "已按抽出评分点排技术标目录。"
                if outline.get("from_extracted_scores")
                else "未检出评分点，只出待对照前附表，未套上个项目模板。"
            )
            + " 仍是 AI 草稿，submit_blocked=true。",
            "submit_blocked": True,
            "handoff": ho,
            "tech_outline": outline,
        }

    if expert.id == "pack-ship":
        from packing_assistant.runtime.session_packing import load_packing_snapshot
        from packing_assistant.runtime.tool_engine import get_engine

        snap = packing_summary if isinstance(packing_summary, dict) else load_packing_snapshot(session_id)
        connected = bool(snap)
        eng = get_engine()
        health = eng.execute(
            "pack-ship__health",
            {"solver": snap},
            expert_id="pack-ship",
            intent="run",
        )
        listed = eng.execute("pack-ship__list", {}, expert_id="pack-ship", intent="run")
        plan = eng.execute(
            "pack-ship__plan",
            {"solver": snap, "connected": connected, "materials": text},
            expert_id="pack-ship",
            intent="run",
        )
        exported = eng.execute(
            "pack-ship__export",
            {"solver": snap, "connected": connected},
            expert_id="pack-ship",
            intent="run",
        )
        md = str((exported.get("data") or exported).get("markdown") or exported.get("markdown") or "")
        path = out_dir / "pack-ship__export.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "pack-ship__export"})
        ran.extend(["pack-ship__health", "pack-ship__list", "pack-ship__plan", "pack-ship__export"])
        src = "solver" if connected else "disconnected"
        reply = (
            "装柜证据只抄 solver 快照，未重算 xyz。"
            if connected
            else "装柜证据只抄 solver；本轮未接通，utilization/can_fit/mid50/系固待办 为 UNSPECIFIED。"
        )
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": reply,
            "submit_blocked": True,
            "pack_ship": {
                "source": src,
                "health": health,
                "list": (listed.get("data") or listed).get("names") if isinstance(listed.get("data") or listed, dict) else listed.get("names"),
                "plan": plan.get("data") or plan,
                "export": exported.get("data") or exported,
            },
        }

    if expert.id == "construction":
        md = _construction_eleven(text)
        from packing_assistant.tools.tender_review import forbidden_hits

        hits = forbidden_hits(md)
        if hits:
            return {
                "wrote": False,
                "hitl_pending": False,
                "files": [],
                "tools_run": [],
                "reply": "禁语扫描命中，未报成功：" + "、".join(hits),
                "submit_blocked": True,
                "p0_reject_scan": {"hits": hits},
            }
        path = out_dir / "construction__scheme_draft.md"
        guarded_write_text(path, md)
        files.append({"name": path.name, "path": str(path), "tool": "construction__scheme_draft"})
        ran.append("construction__scheme_draft")
        return {
            "wrote": True,
            "hitl_pending": False,
            "files": files,
            "tools_run": ran,
            "reply": "已出十一章讨论提纲（docx_pending）。不是法定专项，submit_blocked=true。",
            "submit_blocked": True,
            "docx_pending": True,
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
    packing_summary: Optional[Dict[str, Any]] = None,
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
    from packing_assistant.runtime.scheduler import get_scheduler

    sid = session_id or f"turn-{uuid4().hex[:8]}"
    sched = get_scheduler()
    run = sched.create_run(sid, expert_id=exp.id, intent=intent)
    sched.transition(run, "planning")
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
        "run_id": run.run_id,
        "state": run.state,
        "session_id": sid,
    }
    if intent == "chat":
        sched.transition(run, "done")
        sched.release(sid)
        base["reply"] = explain_expert(exp, text)
        base["state"] = run.state
        return base
    ran = _run_exclusive(
        exp, text, confirm_ok=confirm_ok, session_id=sid, packing_summary=packing_summary
    )
    if ran.get("hitl_pending"):
        sched.transition(run, "waiting_hitl")
    else:
        sched.transition(run, "acting")
        if run.cancelled:
            ran["wrote"] = False
            ran["files"] = []
            ran["reply"] = "run cancelled"
        else:
            sched.transition(run, "done")
    sched.release(sid)
    if intent == "both" and not ran.get("hitl_pending"):
        ran["reply"] = explain_expert(exp, text) + "\n\n" + str(ran.get("reply") or "")
    base.update(ran)
    base["session_id"] = sid
    base["run_id"] = run.run_id
    base["state"] = run.state
    return base
