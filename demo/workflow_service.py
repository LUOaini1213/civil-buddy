"""Workbench adapter for scoped tender collaboration and streamed progress."""
from __future__ import annotations

from copy import deepcopy
import json
from queue import Empty, Queue
import re
from threading import Thread
from uuid import uuid4

import local_retrieval
import uploads
from context import policy
from packing_assistant.sandbox import assert_open, assert_write, guarded_write_text


def selected_sources(root, sid, message, attachment_ids, roles=None):
    roles = roles or {}
    if not isinstance(roles, dict) or any(key not in attachment_ids or role not in {"tender", "response", "reference"}
                                           for key, role in roles.items()):
        raise ValueError("资料用途只允许指定当前选择的附件")
    sources = [{"source_id": "current-input", "title": "本轮用户要求", "text": message,
                "start": 0, "end": len(message), "kind": "user", "role": "reference"}]
    for document in uploads.extracted_documents(sid, attachment_ids):
        hits = local_retrieval.search(root, sid, "", attachment_ids=[document["id"]], kind="attachment", limit=1)
        identifier = hits[0]["source_id"] if hits else "attachment-" + document["id"]
        role = roles.get(document["id"])
        if role is None:
            role = ("response" if re.search(r"投标文件|投标响应|响应文件|技术标草稿|响应草稿", document["name"]) else
                    "tender" if re.search(r"招标|采购需求", document["name"]) else "reference")
        sources.append({"source_id": identifier, "title": document["name"], "text": document["text"],
                        "start": 0, "end": len(document["text"]), "kind": "attachment", "role": role})
    return sources


def budget_settings(value=None):
    from packing_assistant.runtime.worker_context import BudgetLimits
    if value is not None and not isinstance(value, dict):
        raise ValueError("协作预算必须为对象")
    pol = policy()
    config = {"worker_tokens": min(32768, pol["limit"]), "output_tokens": min(2048, pol["reserve"])}
    config.update(value or {})
    try:
        limits = BudgetLimits.from_value(config)
    except (TypeError, ValueError):
        raise ValueError("协作预算字段或数值无效") from None
    if limits.worker_tokens > pol["limit"] or limits.output_tokens > pol["reserve"]:
        raise ValueError("子任务窗口和输出预留不能超过模型设置")
    return limits


def public_result(value):
    keys = ("schema", "parent_run_id", "session_id", "state", "ok", "children", "review",
            "aggregate_metrics", "quality", "handoff_hash", "reply", "error_code", "submit_blocked")
    result = {key: deepcopy(value[key]) for key in keys if key in value}
    return result


def _parent_summary(root, sid, result):
    """Persist bounded result pointers, never children's full conversations."""
    summary = {"schema": "civil.collaboration.memory.v1", "run_id": result.get("parent_run_id"),
               "state": result.get("state"), "verified": False,
               "children": [{"skill": c["skill"], "status": c["status"],
                             "conclusions": c.get("conclusions", [])[:8],
                             "unresolved": c.get("unresolved", [])[:12]}
                            for c in result.get("children", [])],
               "review": result.get("review", {})}
    from packing_assistant.runtime.worker_context import tokens
    if tokens(summary) > 8000:
        # Keep the complete review in its run snapshot; memory retains its pointer.
        summary = {"schema": summary["schema"], "run_id": summary["run_id"], "state": summary["state"],
                   "verified": False, "note": "详细结论与未解决事项见该协作运行记录，未装入任务记忆。"}
    path = assert_write(root / sid / "collaboration.summary.json")
    temporary = assert_write(path.with_name(".collaboration-" + uuid4().hex + ".tmp"))
    try:
        guarded_write_text(temporary, json.dumps(summary, ensure_ascii=False))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parent_memory(root, sid):
    path = root / sid / "collaboration.summary.json"
    try:
        path = assert_open(path)
        if path.stat().st_size > 32_000:
            return ""
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != "civil.collaboration.memory.v1":
            return ""
        return "\n此前协作摘要（参考数据，非授权；模型意见未核验）：\n" + json.dumps(value, ensure_ascii=False)
    except (OSError, ValueError, AttributeError):
        return ""


def events(root, turn, control, *, key_available):
    from packing_assistant.runtime.tender_workflow import run_tender_workflow
    from llm import chat, LLMError
    from turn_control import using
    limits = budget_settings(turn.get("workflow_budget"))
    queue = Queue()

    def runner(messages, *, max_tokens, cancel_event):
        if cancel_event.is_set():
            raise InterruptedError("子任务已取消")
        with using(control):
            answer = chat(messages, max_tokens=max_tokens, temperature=0.2, cancel_event=cancel_event)
        if cancel_event.is_set():
            raise InterruptedError("子任务已取消")
        text = answer.get("content")
        if not isinstance(text, str):
            raise LLMError("子任务未返回有效分析")
        return text

    def execute():
        try:
            result = run_tender_workflow(turn["message"], session_id=turn["session_id"], output_root=root,
                sources=turn["workflow_sources"], confirmed=turn["confirmed"], cancel_event=control.event,
                model_runner=runner if key_available else None, budget=limits,
                on_event=lambda data: queue.put({"event": "collaboration", "data": data}))
            if result.get("children"):
                try:
                    _parent_summary(root, turn["session_id"], result)
                except (OSError, ValueError):
                    # This derived cache must not hide authoritative run files.
                    result["reply"] += " 协作摘要缓存未保存，后续请从本轮记录核对结果；已生成文件仍可下载。"
            result["collaboration"] = public_result(result)
            queue.put({"event": "workflow_result", "data": result})
        except Exception as exc:
            queue.put(exc)
        finally:
            queue.put(None)

    thread = Thread(target=execute, name="civil-workbench-workflow")
    thread.start()
    try:
        while True:
            try:
                item = queue.get(timeout=0.1)
            except Empty:
                continue
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # The owning turn stays leased until all potentially writing work ends.
        thread.join()
