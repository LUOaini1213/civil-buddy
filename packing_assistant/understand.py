"""Understand first. Same chat / run / both rules as workbench/src/agent.rs.

Pure function: no I/O, no writes. Default is chat.
"""

from __future__ import annotations

from typing import Literal

Intent = Literal["chat", "run", "both"]

_PACKISH = ("成套", "易标", "一人公司", "完整方案", "整套标")
_PHRASE_WRITE = (
    "写一份",
    "出一份",
    "做一份",
    "出稿",
    "成稿",
    "编制",
    "起草",
    "抽出",
    "扩写",
    "落盘",
    "出判定",
    "出清单",
    "出作业单",
    "帮我写",
    "请写",
    "生成一份",
    "写个",
    "解析招标",
    "进矩阵",
)
_WRITE_NOUNS = ("方案", "提纲", "草稿", "清单", "纪要", "台账", "日历", "交底", "作业单")
_ASK = (
    "什么是",
    "是什么",
    "怎么理解",
    "如何理解",
    "解释",
    "科普",
    "区别",
    "为什么",
    "怎么看",
    "先聊聊",
    "先别写",
    "只是问问",
    "算不算",
    "要不要",
    "能不能",
    "可不可以",
    "行不行",
    "对不对",
)
_TENDER = ("招标", "ITT", "评标", "Two Envelope", "双信封", "workhead", "必须编制")


def is_packish(blob: str) -> bool:
    return any(k in blob for k in _PACKISH)


def _has_any(s: str, keys: tuple[str, ...]) -> bool:
    return any(k in s for k in keys)


def understand(blob: str) -> Intent:
    t = (blob or "").strip()
    if not t:
        return "chat"
    if is_packish(t):
        return "run"
    phrase_write = _has_any(t, _PHRASE_WRITE)
    write = phrase_write or ("写" in t and _has_any(t, _WRITE_NOUNS))
    ask = _has_any(t, _ASK)
    qmark = "？" in t or "?" in t or t.endswith("吗")
    tender = len(t) > 80 and _has_any(t, _TENDER)
    if write and (ask or qmark):
        return "both"
    if write or tender:
        return "run"
    return "chat"


def is_explain_only(blob: str) -> bool:
    return understand(blob) == "chat"
