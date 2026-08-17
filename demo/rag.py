from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config import KB_ROOT
from kbio import display_title, file_stat, iter_text_files


@dataclass
class Hit:
    path: str
    layer: str  # expert | category | company
    title: str
    snippet: str
    score: float


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
    """Retrieve for a summoned expert. Caller department is not an argument — any user may ask."""
    q = _tokens(query)
    if not q:
        return []
    hits: list[Hit] = []
    for layer, root in kb_layers(expert_id, category):
        files = _iter_md(root)
        for path in files:
            text = _read(path)
            toks = _tokens(text)
            if not toks:
                continue
            bag = set(toks)
            score = sum(2.0 if t in bag else 0.0 for t in q)
            # prefer contiguous phrase
            if query.strip() and query.strip() in text:
                score += 8
            if score <= 0:
                continue
            rel = str(path.relative_to(KB_ROOT)).replace("\\", "/")
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
