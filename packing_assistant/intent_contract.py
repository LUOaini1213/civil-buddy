"""意图契约单源加载器。

唯一真源：contract/intents.v1.json（见 contract/README.md）。
understand.py 与 runtime/expert_skills.py 从这里取词表，仓库内不允许再出现
第二份手工维护的意图词表副本。

加载为一次性模块级缓存；JSON 缺失/损坏/字段缺失/类型错误时 fail-fast 抛错，
不允许静默回退到任何内联旧词表（那是本模块要消灭的漂移源头）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contract" / "intents.v1.json"

REQUIRED_KEYS = (
    "version",
    "pack_action_zh",
    "packish",
    "phrase_write",
    "write_nouns",
    "ask",
    "tender",
    "strong_match",
)

# 语义词表键（值必须是 str 数组，且非空）
_LIST_KEYS = ("pack_action_zh", "packish", "phrase_write", "write_nouns", "ask", "tender")

_cache: dict[str, Any] | None = None


def _fail(msg: str) -> None:
    raise RuntimeError(f"意图契约加载失败（fail-fast，禁止静默回退内联词表）: {msg}")


def _load() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    if not CONTRACT_PATH.is_file():
        _fail(f"契约文件缺失 {CONTRACT_PATH}（应从仓库根运行，或补齐该文件）")
    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _fail(f"{CONTRACT_PATH} 不可读或非法 JSON: {e}")
    if not isinstance(data, dict):
        _fail(f"{CONTRACT_PATH} 顶层必须是对象")
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        _fail(f"契约缺字段: {missing}")
    for key in _LIST_KEYS:
        vals = data[key]
        if (
            not isinstance(vals, list)
            or not vals
            or not all(isinstance(v, str) and v for v in vals)
        ):
            _fail(f"契约字段 {key} 必须是非空字符串数组，实为 {vals!r}")
    strong = data["strong_match"]
    if not isinstance(strong, list) or not strong:
        _fail(f"契约字段 strong_match 必须是非空 [phrase, expert_id] 数组，实为 {strong!r}")
    for i, item in enumerate(strong):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(x, str) and x for x in item)
        ):
            _fail(f"契约 strong_match[{i}] 必须是 [phrase, expert_id]，实为 {item!r}")
    if not isinstance(data.get("version"), str) or not data["version"]:
        _fail("契约 version 必须是非空字符串")
    _cache = data
    return data


def contract_list(key: str) -> tuple[str, ...]:
    """取一个语义词表（保序 tuple）。"""
    return tuple(_load()[key])


def contract_strong() -> tuple[tuple[str, str], ...]:
    """取 strong_match 全表，保序转为 (phrase, expert_id) tuple（对齐 Python _STRONG 语义）。"""
    return tuple((phrase, eid) for phrase, eid in _load()["strong_match"])


def contract_pack_action_en_pattern() -> str:
    """英文 pack 的 Python 侧正则模式串（机制差异记录在契约 pack_action_en）。"""
    pat = _load()["pack_action_en"].get("python")
    if not isinstance(pat, str) or not pat:
        _fail("契约 pack_action_en.python 必须是非空正则字符串")
    return pat


def contract_version() -> str:
    return str(_load()["version"])
