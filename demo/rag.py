from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from config import KB_ROOT, REPO_ROOT
from kbio import display_title, file_stat, iter_text_files

logger = logging.getLogger("civil.demo_rag")


@dataclass
class Hit:
    path: str
    layer: str  # expert | category | company
    title: str
    snippet: str
    score: float


def _rag_mode() -> str:
    """CB_RAG=json|fts（默认 fts）；packing_assistant 不可达时保守回 json。"""
    try:
        import os

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from packing_assistant.kb_search import rag_mode

        return rag_mode()
    except Exception:
        raw = (__import__("os").getenv("CB_RAG") or "fts").strip().lower()
        return raw if raw in ("json", "fts") else "fts"


def _iter_md(root: Path) -> list[Path]:
    return iter_text_files(root)


def kb_layers(expert_id: str, category: str) -> list[tuple[str, Path]]:
    return [
        ("expert", KB_ROOT / category / expert_id),
        ("category", KB_ROOT / category / "_shared"),
        ("company", KB_ROOT / "company"),
    ]


def list_kb(expert_id: str, category: str) -> list[dict]:
    rows = []
    for layer, root in kb_layers(expert_id, category):
        for path in _iter_md(root):
            rel = str(path.relative_to(KB_ROOT)).replace("\\", "/")
            st = file_stat(path, rel, layer)
            rows.append(st)
    return rows


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_kb(rel: str) -> tuple[str, str] | None:
    rel = rel.replace("\\", "/").lstrip("/")
    target = (KB_ROOT / rel).resolve()
    try:
        target.relative_to(KB_ROOT.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    return rel, _read(target)


def _tokens(text: str) -> list[str]:
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_\-]{2,}", text.lower())
    return parts


def search_kb(expert_id: str, category: str, query: str, limit: int = 6) -> list[Hit]:
    """Retrieve for a summoned expert. Caller department is not an argument — any user may ask.

    M3 起（data-plan）：默认 CB_RAG=fts —— SQLite kb_fts 粗召回候选，再走原全盘
    扫描同一公式精排（_search_kb_scan 原样保留）；异常/零召回自动回退全盘扫描。
    """
    cand: Optional[Set[str]] = None
    if _rag_mode() == "fts":
        try:
            from packing_assistant.kb_search import demo_candidates

            cand = demo_candidates(expert_id, category, query)
        except Exception:
            logger.warning("demo search_kb FTS 候选召回异常，回退全盘扫描", exc_info=True)
            cand = None
    return _search_kb_scan(expert_id, category, query, limit=limit, _candidate_paths=cand)


def _search_kb_scan(
    expert_id: str,
    category: str,
    query: str,
    limit: int = 6,
    _candidate_paths: Optional[Set[str]] = None,
) -> list[Hit]:
    """原全盘扫描实现（评分公式逐字保留）。_candidate_paths 非 None 时仅对候选
    文件读盘打分（kb_search FTS 粗召回），None=全盘扫描（回滚路径，14ec2bd 等价）。"""
    q = _tokens(query)
    if not q:
        return []
    hits: list[Hit] = []
    for layer, root in kb_layers(expert_id, category):
        for path in _iter_md(root):
            rel = str(path.relative_to(KB_ROOT)).replace("\\", "/")
            if _candidate_paths is not None and rel not in _candidate_paths:
                continue
            text = _read(path)
            toks = _tokens(text)
            if not toks:
                continue
            bag = set(toks)
            score = sum(2.0 if t in bag else 0.0 for t in q)
            # prefer contiguous phrase
            if query.strip() and query.strip() in text:
                score += 8
            name = path.name.lower()
            score += sum(3.0 for t in q if t in name)
            if score <= 0:
                continue
            idx = text.find(q[0]) if q else 0
            start = max(0, text.find(query.strip()[:6]) if query.strip() else idx)
            snippet = re.sub(r"\s+", " ", text[max(0, start) : start + 180]).strip()
            hits.append(Hit(rel, layer, display_title(path.name, text), snippet, score))
    hits.sort(key=lambda h: (-h.score, h.layer != "expert", h.path))
    # drop dup paths
    seen = set()
    uniq: list[Hit] = []
    for h in hits:
        if h.path in seen:
            continue
        seen.add(h.path)
        uniq.append(h)
        if len(uniq) >= limit:
            break
    return uniq
