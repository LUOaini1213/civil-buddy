from __future__ import annotations

import os
from typing import Any

COMPRESS_MARK = "【对话压缩】"


def _env_int(key: str, default: int) -> int:
    try:
        n = int(os.environ.get(key, "") or default)
        return n if n > 0 else default
    except ValueError:
        return default


def policy() -> dict[str, Any]:
    limit = _env_int("CIVIL_CONTEXT_LIMIT", 1_000_000)
    reserve = _env_int("CIVIL_CONTEXT_RESERVE", 4_096)
    compress_pct = min(99, max(1, _env_int("CIVIL_CONTEXT_COMPRESS_PCT", 70)))
    keep = max(2, _env_int("CIVIL_CONTEXT_KEEP_RECENT", 4))
    usable = max(1, limit - reserve)
    return {
        "limit": limit,
        "reserve": reserve,
        "usable": usable,
        "compress_pct": compress_pct,
        "warn_pct": 50,
        "keep_recent": keep,
        "compress_at": usable * compress_pct // 100,
    }


def estimate_tokens(text: str) -> int:
    cjk = 0
    other = 0
    for ch in text or "":
        if ch.isspace():
            continue
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4


def messages_tokens(msgs: list[dict]) -> int:
    total = 0
    for m in msgs:
        total += estimate_tokens(str(m.get("role") or ""))
        total += estimate_tokens(str(m.get("content") or ""))
        total += 4
    return total


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"


def _fold(old: list[dict]) -> str:
    lines = [
        f"{COMPRESS_MARK}更早 {len(old)} 条原文已不再进入模型。下面是摘录。缺的事实标 [A001] / UNSPECIFIED，不要假装读过被丢掉的细节。"
    ]
    for i, m in enumerate(old, 1):
        who = "你" if m.get("role") == "user" else "助手"
        content = str(m.get("content") or "").replace("\n", " ")
        lines.append(f"{i}. {who}：{_clip(content, 80)}")
    return "\n".join(lines)


def _report(used: int, pol: dict, compressed: bool, folded: int, kept: int) -> dict:
    usable = pol["usable"]
    pct = min(100, (min(used, usable) * 100) // usable)
    if pct >= 90:
        zone = "full"
    elif compressed or pct >= pol["compress_pct"]:
        zone = "compact"
    elif pct >= pol["warn_pct"]:
        zone = "warn"
    else:
        zone = "room"
    keep = pol["keep_recent"]
    at = pol["compress_at"]
    if compressed:
        note = (
            f"已压缩：更早 {folded} 条折成摘要，近 {kept} 条原文仍在。"
            f"当前约 {used} / {pol['limit']} token（{pct}%）。按字数估算，不是官方精确计数。"
        )
    elif pct >= 90:
        note = f"上下文快满（约 {used} / {pol['limit']}，{pct}%）。再发可能只留最近 {keep} 条原文。"
    elif pct >= pol["warn_pct"]:
        note = (
            f"已过半（约 {used} / {pol['limit']}，{pct}%）。"
            f"用到 {at} token（{pol['compress_pct']}%）会把更早对话压成摘要，近 {keep} 条原文保留。"
        )
    else:
        note = (
            f"还很宽裕（约 {used} / {pol['limit']}，{pct}%）。"
            f"用到 {at} token（{pol['compress_pct']}%）会压缩更早对话，近 {keep} 条原文保留。"
        )
    return {
        "used": used,
        "limit": pol["limit"],
        "usable": usable,
        "pct": pct,
        "zone": zone,
        "compressed": compressed,
        "folded": folded,
        "kept": kept,
        "keep_recent": keep,
        "compress_at": at,
        "note": note,
        "estimated": True,
    }


def prepare_history(history: list[dict]) -> tuple[list[dict], dict]:
    pol = policy()
    keep = min(pol["keep_recent"], max(len(history), 1))
    compressed = False
    folded = 0
    out = list(history)
    if len(out) > keep and messages_tokens(out) >= pol["compress_at"]:
        old, out = out[:-keep], out[-keep:]
        folded = len(old)
        compressed = True
        out = [{"role": "user", "content": _fold(old)}, *out]
    if len(out) > 2 and messages_tokens(out) >= pol["usable"] * 90 // 100:
        old, out = out[:-2], out[-2:]
        folded += len(old)
        compressed = True
        out = [{"role": "user", "content": _fold(old)}, *out]
    used = messages_tokens(out)
    kept = len(out) - 1 if compressed else len(out)
    return out, _report(used, pol, compressed, folded, kept)
