"""Understand first. Same chat / run / both rules as workbench/src/agent.rs.

Pure function: no I/O, no writes. Default is chat.

词表单源：全部从 contract/intents.v1.json 加载（见 packing_assistant/intent_contract.py），
本文件不再内联任何词表字面量。
"""

from __future__ import annotations

import re
from typing import Literal

from packing_assistant.intent_contract import (
    contract_list,
    contract_pack_action_en_pattern,
)

Intent = Literal["chat", "run", "both"]

_PACKISH = contract_list("packish")
# pack 一句话动作：装箱/装柜/拼柜是引擎本体动作；英文 pack 判定模式来自契约 pack_action_en.python。
# parity:pack-action-en — 英文 pack 判定与 workbench/src/agent.rs（非字母数字切词后
# eq_ignore_ascii_case("pack")）语义等价；两侧机制不同，契约只记录不互译，
# 锚点由 scripts/test_stack_parity.py 成对校验。
_PACK_ACTION_ZH = contract_list("pack_action_zh")
_PACK_ACTION_EN = re.compile(contract_pack_action_en_pattern(), re.IGNORECASE)
_PHRASE_WRITE = contract_list("phrase_write")
_WRITE_NOUNS = contract_list("write_nouns")
_ASK = contract_list("ask")
_TENDER = contract_list("tender")


def is_packish(blob: str) -> bool:
    return any(k in blob for k in _PACKISH)


def is_pack_action(blob: str) -> bool:
    """pack 一句话动作（装柜/装箱/拼柜/pack）：与 workbench/src/agent.rs 保持一致。"""
    t = (blob or "").strip()
    if not t:
        return False
    if is_packish(t):
        return True
    if _has_any(t, _PACK_ACTION_ZH):
        return True
    return _PACK_ACTION_EN.search(t) is not None


def _has_any(s: str, keys: tuple[str, ...]) -> bool:
    return any(k in s for k in keys)


def understand(blob: str) -> Intent:
    t = (blob or "").strip()
    if not t:
        return "chat"
    pack_action = is_pack_action(t)
    if is_packish(t):
        return "run"
    phrase_write = _has_any(t, _PHRASE_WRITE)
    write = phrase_write or ("写" in t and _has_any(t, _WRITE_NOUNS))
    ask = _has_any(t, _ASK)
    qmark = "？" in t or "?" in t or t.endswith("吗")
    tender = len(t) > 80 and _has_any(t, _TENDER)
    if (write or pack_action) and (ask or qmark):
        return "both"
    if (ask or qmark) and not write and not pack_action:
        return "chat"
    if pack_action or write or tender:
        return "run"
    return "chat"


def is_explain_only(blob: str) -> bool:
    return understand(blob) == "chat"
