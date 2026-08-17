from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from catalog import Expert
from config import MAX_AGENT_STEPS, OUT_ROOT
from llm import chat, stream_plain
from rag import list_kb, read_kb, search_kb

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "检索本专家库、本大类共享库、公司硬规则。先检索再写正文。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_kb",
            "description": "按相对路径阅读一条知识库全文，路径来自 search_kb 或 list_kb。",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_kb",
            "description": "列出本专家可见的全部知识文件（专家私库 + 大类共享 + 公司）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_deliverable",
            "description": "把独立完成的成稿落到本会话交付目录。高风险稿须用户已确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "如 专项方案-AI草稿.md"},
                    "markdown": {"type": "string"},
                },
                "required": ["filename", "markdown"],
            },
        },
    },
]


def build_expert_prompt(expert: Expert, confirm_ok: bool) -> str:
    """Shipped system prompt for a summoned expert. Tests must call this."""
    return f"""你是土木企业工作台里的【{expert.name}】专家（大类：{expert.category_name}）。

提问权：全企业任何人都可以向你提问，不限于本部门。施工员可以问财务，商务可以问试验室，工人可以问造价。用户召唤了你，就用你的知识库答。

两类任务同等重要：
A. 问 / 不懂 / 解释 / 科普：用白话讲清楚本专业概念、流程、边界。可以只聊天，不必 write_deliverable。先 search_kb 再答。答完注明依据来自私库还是大类库。
B. 成稿 / 出文件 / 写方案表：按工序独立成稿，写完调用 write_deliverable。高风险且未确认则不要写盘。

问其他人：不要读取其他专家的私库。问题明显属于别的专业时，先答你能答的边界，并请用户在左侧改召唤那位专家。

职责：{expert.title}
默认交付：{expert.delivers}
风险：{expert.risk}
标准工序：{expert.pipeline}

知识分层（必须用工具，不许假装读过）：
1. 你的私库 kb/{expert.category}/{expert.id}/
2. 大类共享库 kb/{expert.category}/_shared/（同类专家共用）
3. 公司库 kb/company/ 与硬规则

硬规则（摘要，细节用 read_kb company/hard-rules.md）：
- 不编条款号、强度、岩土参数、综合单价。
- 引用写 全名+年份+条款；没抽到原文就 unverified / UNSPECIFIED。
- 无来源数字写 [A001] 待填。
- 禁止断言：可交差、可提交专家论证、请监理审核后开工、可以开工、报审通过。
- 产出是内部讨论 AI 草稿，不是法定签认件。
- 辖区 CN/SG/EU/DUAL 禁止静默混用。
- 高风险写盘前确认门。当前 confirm_ok={confirm_ok}。
  若用户要成稿且 risk=high 且 confirm_ok 不为 true：只问用户打出「我明白，将由持证人员签认」，不要 write_deliverable。纯提问（A）不受确认门阻挡。

先 search_kb。中文回答。
"""


def _system(expert: Expert, confirm_ok: bool) -> str:
    return build_expert_prompt(expert, confirm_ok)


def _plain_system() -> str:
    return (
        "你是 DeepSeek，在土木工作台里以「未召唤专家」模式回答。"
        "没有岗位知识库，没有出稿工具。可以科普、讨论、列提纲，"
        "但必须声明：这不是专家稿，条款和数字需要用户自行核对。"
        "不要假装引用了企业规范库。用户若要可核验成稿，请他们在左侧召唤专家。"
    )


def run_plain(history: list[dict[str, str]]) -> Iterator[dict[str, Any]]:
    messages = [{"role": "system", "content": _plain_system()}, *history]
    yield {"event": "status", "data": {"phase": "plain", "text": "未召唤专家 · 普通 DeepSeek"}}
    buf = []
    for piece in stream_plain(messages):
        buf.append(piece)
        yield {"event": "token", "data": {"text": piece}}
    yield {"event": "done", "data": {"mode": "plain", "text": "".join(buf), "citations": [], "deliverables": []}}


def run_expert(
    expert: Expert,
    history: list[dict[str, str]],
    *,
    confirm_ok: bool,
    session_id: str,
) -> Iterator[dict[str, Any]]:
    yield {
        "event": "status",
        "data": {
            "phase": "summon",
            "text": f"已召唤 {expert.category_name} / {expert.name} · 独立收工",
            "expert": expert.id,
        },
    }
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system(expert, confirm_ok)},
        *history,
    ]
    citations: list[dict[str, Any]] = []
    deliverables: list[dict[str, str]] = []
    out_dir = OUT_ROOT / session_id / expert.id
    out_dir.mkdir(parents=True, exist_ok=True)

    def _exec(name: str, args: dict[str, Any]) -> str:
        nonlocal citations, deliverables
        if name == "search_kb":
            hits = search_kb(expert.id, expert.category, str(args.get("query") or ""))
            citations.extend(
                {"path": h.path, "layer": h.layer, "title": h.title, "snippet": h.snippet}
                for h in hits
            )
            return json.dumps(
                [{"path": h.path, "layer": h.layer, "snippet": h.snippet} for h in hits],
                ensure_ascii=False,
            )
        if name == "list_kb":
            return json.dumps(list_kb(expert.id, expert.category), ensure_ascii=False)
        if name == "read_kb":
            got = read_kb(str(args.get("path") or ""))
            if not got:
                return "文件不存在或越权"
            rel, text = got
            return f"# {rel}\n\n{text[:8000]}"
        if name == "write_deliverable":
            if expert.risk == "high" and not confirm_ok:
                return "拒绝写盘：高风险稿需要用户确认句「我明白，将由持证人员签认」。"
            raw_name = Path(str(args.get("filename") or "draft.md")).name
            if not raw_name.endswith((".md", ".txt")):
                raw_name += ".md"
            path = out_dir / raw_name
            path.write_text(str(args.get("markdown") or ""), encoding="utf-8")
            item = {"expert": expert.id, "name": raw_name, "path": str(path)}
            deliverables.append(item)
            return f"已写入 {path}"
        return f"未知工具 {name}"

    final_text = ""
    for step in range(MAX_AGENT_STEPS):
        yield {"event": "status", "data": {"phase": "think", "text": f"{expert.name} 步骤 {step + 1}/{MAX_AGENT_STEPS}"}}
        msg = chat(messages, tools=TOOLS)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final_text = msg.get("content") or ""
            break
        messages.append(msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except json.JSONDecodeError:
                args = {}
            yield {"event": "status", "data": {"phase": name, "text": f"{expert.name} · {name} {args.get('query') or args.get('path') or args.get('filename') or ''}"}}
            result = _exec(name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "content": result[:12000],
                }
            )
    else:
        final_text = final_text or "（达到步数上限，请把任务拆小或再发一次）"

    if not final_text:
        final_text = "已完成检索，但模型没有返回正文。请再试一次。"

    # stream the final as tokens for the same UI
    for i in range(0, len(final_text), 40):
        yield {"event": "token", "data": {"text": final_text[i : i + 40]}}

    # unique citations
    uniq = []
    seen = set()
    for c in citations:
        if c["path"] in seen:
            continue
        seen.add(c["path"])
        uniq.append(c)

    yield {
        "event": "done",
        "data": {
            "mode": "expert",
            "expert": expert.id,
            "text": final_text,
            "citations": uniq,
            "deliverables": deliverables,
            "stamp": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        },
    }
