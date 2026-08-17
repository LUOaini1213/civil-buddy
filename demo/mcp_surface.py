"""MCP resources + prompts for the Python workbench.

Same URI / prompt names as workbench/src/mcp.rs so hosts can switch
civil-mcp (Rust) without renaming. Tests drive this module; Rust needs MSVC.
"""

from __future__ import annotations

from typing import Any

from rag import list_kb, read_kb

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
]


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


def get_prompt(name: str, arguments: dict | None = None, *, expert_id: str | None = None) -> dict[str, Any]:
    allowed = {p["name"] for p in list_prompts(expert_id=expert_id)}
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
            "你是装箱拼柜岗。柜数/N0/xyz 只抄工具；未接通写 UNSPECIFIED。禁止编 CTU 条款号。"
            f"物料：\n{args.get('materials') or '（未提供）'}"
        )
    else:
        return {"description": "未知 prompt", "messages": []}
    return {
        "description": name,
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }
