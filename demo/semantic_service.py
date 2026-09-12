"""Optional, bounded semantic compaction before read-only model conversation.

Only this turn's producer can validate/persist the returned summary. Detached
transport work is read-only, so a late reply cannot update memory after cancel.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from queue import Empty, Queue
from threading import Thread
import time
from uuid import uuid4

import context
from packing_assistant.sandbox import assert_open, assert_write, guarded_write_text
import turn_control

SUMMARY_TIMEOUT_SECONDS = 12.0
RETRY_SECONDS = 60.0


class _Stop:
    def __init__(self, control):
        self.control = control
        self.deadline = time.monotonic() + SUMMARY_TIMEOUT_SECONDS

    def is_set(self):
        return self.control.event.is_set() or time.monotonic() >= self.deadline

    def check(self):
        self.control.check()
        if time.monotonic() >= self.deadline:
            raise TimeoutError("semantic summary deadline")


def _answer(messages, output_budget, control):
    """Bound even a non-cooperative adapter; real HTTP also closes on deadline."""
    from llm import chat
    stop, queue = _Stop(control), Queue(maxsize=1)

    def request():
        try:
            with turn_control.using(control):
                stop.check()
                result = chat(messages, temperature=0.1, max_tokens=output_budget, cancel_event=stop)
            queue.put((True, result))
        except Exception as exc:
            queue.put((False, exc))

    stop.check()
    Thread(target=request, name="civil-semantic-model-" + control.session, daemon=True).start()
    while True:
        stop.check()
        try:
            success, value = queue.get(timeout=.05)
        except Empty:
            continue
        stop.check()
        if not success:
            raise value
        if not isinstance(value, dict) or not isinstance(value.get("content"), str):
            raise ValueError("invalid summary response")
        return value["content"]


def _attempt_path(root, sid):
    from chat_service import valid_session
    valid_session(sid)
    if (root / sid).resolve().parent != root.resolve():
        raise ValueError("invalid summary session")
    return root / sid / "semantic.attempt.json"


def _cooldown(root, sid, digest):
    try:
        path = assert_open(_attempt_path(root, sid))
        if path.stat().st_size > 2048:
            return False
        previous = json.loads(path.read_text(encoding="utf-8"))
        elapsed = time.time() - previous["failed_at"]
        return previous.get("digest") == digest and 0 <= elapsed < RETRY_SECONDS
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _failed_attempt(root, sid, digest):
    """Failure metadata contains no submitted text, endpoint, or credentials."""
    target = assert_write(_attempt_path(root, sid))
    temporary = assert_write(target.with_name(".semantic-attempt-" + uuid4().hex + ".tmp"))
    try:
        guarded_write_text(temporary, json.dumps({"digest": digest, "failed_at": time.time()}))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _report(turn, report):
    requests = list(turn["requests"].values())
    report["answer_requests"] = len(requests)
    report["turn_reserved_tokens"] = (report["input_tokens"] + report["output_reserve"] +
        sum(r["context"]["used"] + r["context"]["reserve"] for r in requests))
    report["estimated"] = True
    turn["context"]["semantic"] = report
    return {"event": "context", "data": deepcopy(turn["context"])}


def _citations(sid, rendered):
    from local_retrieval import _source_id
    from session_context import citation
    refs = {}
    for entry in reversed(rendered.get("items", [])):
        for item in entry.get("evidence", []):
            refs.setdefault(json.dumps(item, sort_keys=True, ensure_ascii=False), item)
    return [citation(sid, {"source_id": _source_id(sid, "history", item["message_id"]),
                           "title": "语义摘要原文 · " + item["message_id"], "kind": "history",
                           "start": item["start"], "end": item["end"], "text": item["quote"]})
            for item in list(refs.values())[:12]], max(0, len(refs) - 12)


def events(root, turn, control, *, key_available):
    """Update only model requests; deterministic material and rule facts stay intact."""
    report = {"status": "disabled", "model_calls": 0, "input_tokens": 0,
              "output_reserve": 0, "output_tokens": 0, "covered_messages": 0,
              "note": "语义摘要未启用；使用规则记忆与检索。"}
    if not context.semantic_summary_enabled():
        yield _report(turn, report)
        return
    if turn["intent"] != "chat" or turn["route"].get("ambiguous") or turn["route"].get("workflow"):
        report.update(status="not_applicable", note="本轮无需模型问答；语义摘要不会参与业务字段或签认。")
        yield _report(turn, report)
        return
    if not key_available:
        report.update(status="unconfigured", note="未配置模型，沿用本地规则记忆与检索。")
        yield _report(turn, report)
        return
    prepared = turn["prepared_context"]
    import task_memory
    items = [item for section in task_memory.SECTIONS for item in prepared["summary"].get(section, [])]
    current = [item for item in items if item.get("source", {}).get("message_id") == "current"
               and item.get("source", {}).get("role") == "user"]
    current_keys = {item.get("key") for item in current}
    changed_fields = (any(item.get("supersedes") for item in current)
                      or any(item.get("key") in current_keys and item.get("status") == "superseded" for item in items))
    if changed_fields or re.search(r"更正|纠正|修正|更新|改为|改成|调整为|作废|撤销|取消此前|不是.{0,30}而是", turn["message"]):
        report.update(status="current_override", note="本轮更正优先，暂不加载旧语义摘要；使用当前原文与规则记忆。")
        yield _report(turn, report)
        return
    import semantic_memory
    sid, prepared = turn["session_id"], turn["prepared_context"]
    history = [h for h in prepared["draft_history"] if not str(h.get("id", "")).startswith("client-")]
    pol = context.policy()
    cache = None
    digest = ""
    try:
        control.check()
        if semantic_memory.current_revision(history, turn["message"]):
            report.update(status="current_override", note="本轮更正优先，暂不加载旧语义摘要；使用当前原文与规则记忆。")
            yield _report(turn, report)
            return
        cache = semantic_memory.load(root, sid, history=history, keep_recent=4)
        pressure = any(r["context"].get("folded", 0) or r["context"]["used"] >= pol["compress_at"]
                       for r in turn["requests"].values())
        plan = (semantic_memory.prepare(root, sid, history,
                    input_budget=min(8192, pol["usable"] // 3), output_budget=min(1024, pol["reserve"]), keep_recent=4)
                if pressure else None)
        if plan:
            messages = semantic_memory.messages(plan)
            digest = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if _cooldown(root, sid, digest):
                report.update(status="cooldown", note="相同资料的摘要暂缓重试；使用已有摘要、规则记忆与检索。")
            else:
                report.update(status="generating", note="正在整理较早对话的语义摘要，完整原文仍保留。",
                    input_tokens=context.messages_tokens(messages), output_reserve=min(1024, pol["reserve"]))
                if report["input_tokens"] > min(8192, pol["usable"] // 3):
                    raise ValueError("summary request exceeds budget")
                context.validate_request(messages)
                yield {"event": "status", "data": {"phase": "compacting", "text": report["note"]}}
                yield _report(turn, report)
                report["model_calls"] = 1
                answer = _answer(messages, report["output_reserve"], control)
                report["output_tokens"] = context.estimate_tokens(answer)
                validated = semantic_memory.accept(plan, answer)
                control.check()
                cache = semantic_memory.persist(root, sid, validated)
                report.update(status="generated", note="已生成部分历史的语义摘要；有原文依据，内容仍待核验。")
        else:
            report.update(status="cached" if cache else "not_needed",
                note="复用本任务已核对来源的语义摘要，内容仍待核验。" if cache else "当前无需新增语义摘要；原文和规则记忆保留。")
    except turn_control.TurnCancelled:
        report.update(status="cancelled", note="本轮摘要已停止，迟到回复不会写入任务记忆。")
        _report(turn, report)
        raise
    except Exception as exc:
        control.check()
        report.update(status="fallback", error_code="timeout" if isinstance(exc, TimeoutError) else "summary_unavailable",
                      note="语义摘要未生成或未通过校验，本轮沿用规则记忆与检索。")
        if digest and report["model_calls"]:
            try:
                _failed_attempt(root, sid, digest)
            except (OSError, ValueError):
                pass
    if cache:
        try:
            from chat_service import _chat_request
            report.update({key: cache[key] for key in ("covered_messages", "remaining_messages", "eligible_messages", "retained_coverage_complete") if key in cache})
            value = semantic_memory.render(cache, max_chars=min(6000, max(300, pol["usable"] // 5)))
            if value:
                # A bounded rendering can omit whole items even when the disk
                # cache covers the prefix. Only the actual prompt may replace it.
                try:
                    rendered = json.loads(value)
                except (ValueError, TypeError):
                    rendered = {}
                if not isinstance(rendered, dict):
                    rendered = {}
                complete = (isinstance(rendered, dict) and rendered.get("coverage_complete") is True
                            and rendered.get("omitted_items") == 0 and bool(rendered.get("items")))
                replaced = (cache.get("covered_messages", 0) if complete
                            and cache.get("retained_coverage_complete") and not cache.get("skipped_messages") else 0)
                citations, omitted_citations = _citations(sid, rendered)
                adapted = {**prepared, "semantic_memory": value, "semantic_covered_count": replaced,
                           "semantic_citations": citations}
                refreshed = {eid: _chat_request(eid, adapted, turn["message"], sid) for eid in turn["requests"]}
                control.check()
                turn["requests"] = refreshed
                selected = max((r["context"] for r in refreshed.values()), key=lambda r: r["used"])
                turn["context"].update(selected)
                report["included"] = any("semantic-memory" in r["context"]["sources_used"] for r in refreshed.values())
                report["omitted_citations"] = omitted_citations
                if omitted_citations:
                    report["note"] += f" 原文链接展示最近 12 处，其余 {omitted_citations} 处位置保留在摘要中。"
                if not report["included"]:
                    report["note"] += " 摘要因本轮输入预算未加入，原文可检索。"
            else:
                report.update(included=False, note="摘要暂无可用条目或无法在预算内完整展示，本轮使用规则记忆与检索。")
        except turn_control.TurnCancelled:
            report.update(status="cancelled", note="本轮已停止，摘要未加入新的问答请求。")
            _report(turn, report)
            raise
        except Exception:
            report.update(included=False, note=report["note"] + " 摘要未加入本轮问答，继续使用规则记忆与检索。")
    yield _report(turn, report)
