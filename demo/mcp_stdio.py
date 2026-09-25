#!/usr/bin/env python3
"""Newline JSON-RPC MCP stdio. Same names as civil-mcp; no MSVC required.

  python demo/mcp_stdio.py --pack bid
  python demo/mcp_stdio.py --expert pack-ship
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent
for p in (DEMO, ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from mcp_surface import (  # noqa: E402
    call_tool,
    get_prompt,
    initialize_capabilities,
    list_prompts,
    list_resources,
    list_tools,
    read_resource,
)


def _scope(pack: str | None, expert: str | None) -> tuple[str, str]:
    from mcp_surface import _scope as surface_scope

    eid, cat, _rec = surface_scope(expert, pack)
    return eid, cat


def handle(msg: dict[str, Any], *, pack: str | None = None, expert: str | None = None) -> dict[str, Any] | None:
    method = str(msg.get("method") or "")
    if not method or method.startswith("notifications/"):
        return None
    rid = msg.get("id")
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    eid, cat = _scope(pack, expert)

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": "2025-03-26",
                "capabilities": initialize_capabilities(),
                "serverInfo": {"name": "civil-buddy", "version": "1.0"},
            }
        )
    if method == "tools/list":
        return ok({"tools": list_tools(expert_id=expert or eid or None, pack=pack or None)})
    if method == "tools/call":
        name = str(params.get("name") or "")
        if params.get("arguments") is not None and not isinstance(params["arguments"], dict):
            return err(-32602, "arguments must be an object")
        args = params.get("arguments") or {}
        out = call_tool(name, args, expert_id=expert, pack=pack)  # --pack alone is a pack scope, not a pinned post
        text = json.dumps(out, ensure_ascii=False, default=str)
        return ok({"content": [{"type": "text", "text": text}], "isError": not out.get("ok", True)})
    if method == "resources/list":
        if not eid or not cat:
            return ok({"resources": []})
        return ok({"resources": list_resources(eid, cat)})
    if method == "resources/read":
        uri = str(params.get("uri") or "")
        if not eid or not cat:
            return err(-32602, "missing expert/pack")
        return ok(read_resource(eid, cat, uri))
    if method == "prompts/list":
        return ok({"prompts": list_prompts(expert_id=expert or None, pack=pack or None)})
    if method == "prompts/get":
        return ok(
            get_prompt(
                str(params.get("name") or ""),
                params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                expert_id=expert or None,
                pack=pack or None,
            )
        )
    return err(-32601, f"Method not found: {method}")


def main() -> int:
    # 工具描述与拒绝语都是中文，而协议帧直接写 sys.stdout。POSIX/C locale 下
    # （systemd、Docker）默认编码不是 UTF-8，第一条含中文的响应就会
    # UnicodeEncodeError，服务器死在半条消息上。
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="")
    ap.add_argument("--expert", default="")
    ns = ap.parse_args()
    pack = ns.pack.strip() or None
    expert = ns.expert.strip() or None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        resp = handle(msg, pack=pack, expert=expert)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
