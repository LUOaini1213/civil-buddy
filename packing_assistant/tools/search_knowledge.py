"""knowledge_base 关键词检索（无向量库 MVP）。

供 llm_toolcall / critic 文案引用规则与范例；**不返回 3D 坐标**。
数值箱型仍走 packing_knowledge_base.json。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_KB = _ROOT / "knowledge_base"

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_PRIORITY_W = {"high": 3.0, "medium": 1.5, "low": 0.5, "highest": 3.5}

# 禁止出现在检索返回里的坐标类字段名（叙事红线）
_COORD_KEYS = frozenset(
    {"x", "y", "z", "xyz", "position", "positions", "layout_items", "placements"}
)


@dataclass
class KbDoc:
    path: str  # relative posix under knowledge_base
    abs_path: Path
    title: str
    body: str
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)


_CACHE: Dict[str, List[KbDoc]] = {}


def _kb_root(root: Optional[Path] = None) -> Path:
    return Path(root) if root else _DEFAULT_KB


def _parse_frontmatter(raw: str) -> Tuple[Dict[str, Any], str]:
    m = _FM_RE.match(raw.strip() + ("\n" if not raw.endswith("\n") else ""))
    if not m:
        # try without trailing newline force
        m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    fm_text, body = m.group(1), m.group(2)
    meta: Dict[str, Any] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                meta[key] = []
            else:
                meta[key] = [x.strip().strip("'\"") for x in inner.split(",")]
        elif val.lower() in ("true", "false"):
            meta[key] = val.lower() == "true"
        else:
            meta[key] = val.strip("'\"")
    return meta, body


def _tokenize(text: str) -> List[str]:
    """英文词 + 连续中文串 + 中文 bigram（提升短查询召回）。"""
    text = text.lower()
    parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        if re.fullmatch(r"[a-z0-9_]+", p):
            if len(p) >= 2 or p.isdigit():
                out.append(p)
            continue
        # CJK run
        if len(p) >= 2:
            out.append(p)
        for i in range(len(p) - 1):
            out.append(p[i : i + 2])
        if len(p) >= 3:
            for i in range(len(p) - 2):
                out.append(p[i : i + 3])
    # dedupe preserve order
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def load_kb(root: Optional[Path] = None, *, force: bool = False) -> List[KbDoc]:
    kb = _kb_root(root)
    key = str(kb.resolve())
    if not force and key in _CACHE:
        return _CACHE[key]
    docs: List[KbDoc] = []
    if not kb.is_dir():
        _CACHE[key] = docs
        return docs
    for p in sorted(kb.rglob("*.md")):
        if p.name.upper() == "README.MD" and p.parent == kb:
            # keep README indexable for division / anti-patterns
            pass
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _parse_frontmatter(raw)
        if fm.get("status") == "deprecated":
            continue
        title_m = _TITLE_RE.search(body)
        title = title_m.group(1).strip() if title_m else p.stem
        rel = p.relative_to(kb).as_posix()
        blob = f"{title} {body} {' '.join(str(v) for v in fm.values())}"
        docs.append(
            KbDoc(
                path=rel,
                abs_path=p,
                title=title,
                body=body,
                frontmatter=fm,
                tokens=_tokenize(blob),
            )
        )
    _CACHE[key] = docs
    return docs


def _snippet(body: str, query_tokens: List[str], max_len: int = 280) -> str:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return body[:max_len]
    # prefer line containing a query token
    for ln in lines:
        low = ln.lower()
        if any(t in low for t in query_tokens):
            return ln[:max_len]
    return lines[0][:max_len]


def _score(doc: KbDoc, q_tokens: List[str], tags_filter: Optional[List[str]]) -> float:
    if not q_tokens and not tags_filter:
        return 0.0
    score = 0.0
    token_set = set(doc.tokens)
    body_l = (doc.title + "\n" + doc.body).lower()
    path_l = doc.path.lower()
    title_l = doc.title.lower()
    for t in q_tokens:
        if t in token_set:
            score += 1.0
        if t in title_l:
            score += 2.5
        if len(t) >= 2 and t in body_l:
            score += 0.8
        if len(t) >= 2 and t in path_l:
            score += 1.2
    # tags
    doc_tags = doc.frontmatter.get("tags") or []
    if isinstance(doc_tags, str):
        doc_tags = [doc_tags]
    doc_tags_l = [str(x).lower() for x in doc_tags]
    for t in q_tokens:
        if t in doc_tags_l:
            score += 1.5
    if tags_filter:
        for tg in tags_filter:
            if tg.lower() in doc_tags_l:
                score += 2.0
    pr = str(doc.frontmatter.get("priority") or "medium").lower()
    score *= _PRIORITY_W.get(pr, 1.0)
    # category slight boost for rules
    cat = str(doc.frontmatter.get("category") or "")
    if cat == "rules":
        score *= 1.15
    return score


def search_knowledge(
    q: str,
    *,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 5,
    root: Optional[Path] = None,
    agent_id: Optional[str] = None,
    path_prefixes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """检索知识库。返回 hits；不含坐标字段。

    agent_id: 若提供，走 kb_bindings 窄接（推荐）。
    path_prefixes: 可选路径前缀过滤（无 agent_id 时）。
    """
    if agent_id:
        from packing_assistant.kb_bindings import search_for_agent

        return search_for_agent(agent_id, q, limit=limit)

    docs = load_kb(root)
    q_tokens = _tokenize(q or "")
    tags_f = tags or None
    scored: List[Tuple[float, KbDoc]] = []
    for d in docs:
        fm = d.frontmatter
        if category and str(fm.get("category") or "") != category:
            continue
        if priority and str(fm.get("priority") or "").lower() != priority.lower():
            continue
        if path_prefixes:
            ok_p = False
            for pref in path_prefixes:
                pref = str(pref).replace("\\", "/")
                if d.path == pref or d.path.startswith(pref):
                    ok_p = True
                    break
            if not ok_p:
                continue
        s = _score(d, q_tokens, tags_f)
        if s <= 0 and q_tokens:
            continue
        if s <= 0 and not q_tokens:
            # filter-only query
            s = _PRIORITY_W.get(str(fm.get("priority") or "medium").lower(), 1.0)
        scored.append((s, d))
    scored.sort(key=lambda x: (-x[0], x[1].path))
    hits = []
    for s, d in scored[: max(1, min(limit, 20))]:
        hits.append(
            {
                "path": d.path,
                "title": d.title,
                "score": round(s, 3),
                "snippet": _snippet(d.body, q_tokens),
                "frontmatter": {
                    k: d.frontmatter.get(k)
                    for k in (
                        "category",
                        "subcategory",
                        "priority",
                        "type",
                        "tags",
                        "source",
                        "status",
                        "harness",
                    )
                    if k in d.frontmatter
                },
            }
        )
    # narrative guard: strip any accidental coord keys from nested structures
    for h in hits:
        for k in list(h.keys()):
            if k.lower() in _COORD_KEYS:
                del h[k]
    return {
        "ok": True,
        "q": q,
        "n_docs_indexed": len(docs),
        "n_hits": len(hits),
        "hits": hits,
        "note": "rules/tools/trajectories only; coordinates must come from packing tools",
    }


def search_knowledge_tool(
    q: str = "",
    category: str = "",
    priority: str = "",
    tags: str = "",
    limit: int = 5,
    agent_id: str = "",
) -> Dict[str, Any]:
    """Tool-facing wrapper (string tags comma-separated)."""
    if agent_id:
        return search_knowledge(q, agent_id=agent_id, limit=int(limit or 5))
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return search_knowledge(
        q,
        category=category or None,
        priority=priority or None,
        tags=tag_list,
        limit=int(limit or 5),
    )
