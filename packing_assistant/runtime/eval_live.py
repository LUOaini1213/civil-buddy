"""Python GET /api/eval/live: offline official-title needles + agent loop smoke.

Does not scrape IRAS. If a KB file has 9%, the needle is pass — never claim
the official page omitted 9% from a failed scrape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parents[2]

NEEDLES = (
    {
        "id": "gst-9",
        "path": "demo/kb/finance/finance-tax/web-knowledge.md",
        "must": ("9%", "Current GST rates"),
        "note": "IRAS 页述 GST 9%；离线闸抄 KB，不改口「官方没写」。",
    },
    {
        "id": "fire-code",
        "path": "demo/kb/company/web-portals.md",
        "must": ("Fire Code 2023",),
        "note": "SCDF 官方标题。条款 UNSPECIFIED。",
    },
    {
        "id": "ctu-2014",
        "path": "demo/kb/plant/pack-ship/web-knowledge.md",
        "must": ("CTU Code", "2014"),
        "note": "IMO/ILO/UNECE CTU Code 2014。不编条款号。",
    },
    {
        "id": "gebiz-not-scoring",
        "path": "demo/kb/company/web-portals.md",
        "must": ("GeBIZ", "不是评分"),
        "note": "GeBIZ 是门户不是评分办法。",
    },
)


def _needle(row: Dict[str, Any]) -> Dict[str, Any]:
    path = _ROOT / str(row["path"])
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    missing = [m for m in row["must"] if m not in text]
    snippet = ""
    if text and not missing:
        key = row["must"][0]
        i = text.find(key)
        snippet = text[max(0, i - 40) : i + 80].replace("\n", " ").strip()
    return {
        "id": row["id"],
        "path": row["path"],
        "found": path.is_file() and not missing,
        "missing": missing,
        "snippet": snippet,
        "note": row["note"],
        "live_web": False,
    }


def live_eval() -> Dict[str, Any]:
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.sandbox import check_write, request_spawn
    from packing_assistant.understand import understand

    needles = [_needle(n) for n in NEEDLES]
    u_chat = understand("什么是 GST")
    u_run = understand("写临边防护方案讨论提纲")
    chat = run_agent("什么是 GST", session_id="eval-live-chat", force_intent="chat")
    env_path = _ROOT / "demo" / "out" / ".env"
    env_deny = check_write(env_path)
    spawn_deny = request_spawn(["cmd", "/c", "dir"], kind="generic")

    needle_ok = all(n["found"] for n in needles)
    chat_ok = (
        chat.get("intent") == "chat"
        and chat.get("wrote") is False
        and "9%" in str(chat.get("reply") or "")
        and "可以投标" not in str(chat.get("reply") or "")
    )
    gates = {
        "understand_chat": u_chat == "chat",
        "understand_run": u_run == "run",
        "agent_chat_no_write": chat_ok,
        "sandbox_env_denied": env_deny.allowed is False,
        "sandbox_generic_spawn_denied": spawn_deny.allowed is False,
        "needles": needle_ok,
    }
    ok = all(gates.values())
    return {
        "ok": ok,
        "schema": "civil.eval.live.v1",
        "live_web": False,
        "verdict": "offline_gate_pass" if ok else "offline_gate_fail",
        "note": "发版前可另开联网评测。日常闸不抓 IRAS。官方页有 9% 时不得改口「官方没写」。",
        "understand": {"chat": u_chat, "run": u_run},
        "needles": needles,
        "agent": {
            "run_id": chat.get("run_id"),
            "intent": chat.get("intent"),
            "wrote": chat.get("wrote"),
            "has_gst_9": "9%" in str(chat.get("reply") or ""),
        },
        "sandbox": {
            "env": env_deny.to_dict(),
            "generic_spawn": spawn_deny.to_dict(),
        },
        "gates": gates,
        "submit_blocked_policy": True,
    }
