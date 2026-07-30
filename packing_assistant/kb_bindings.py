"""Agent → knowledge_base 窄接绑定。

配置：knowledge_base/05_multi_agent/agent_kb_bindings.yaml
检索：search_for_agent / filter_docs_for_agent
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_ROOT = Path(__file__).resolve().parents[1]
_BINDINGS_PATH = (
    _ROOT / "knowledge_base" / "05_multi_agent" / "agent_kb_bindings.yaml"
)


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """极简 YAML 子集：映射 / 列表 / 标量（无锚点、无多行复杂结构）。"""
    # Prefer PyYAML if present
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    root: Dict[str, Any] = {}
    stack: List[tuple] = [(-1, root)]  # indent, container
    list_key_stack: List[Optional[str]] = [None]
    pending_key: Optional[str] = None
    pending_indent = 0

    def current_container():
        return stack[-1][1]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        # pop stack
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
            if len(list_key_stack) > len(stack):
                list_key_stack.pop()

        # list item
        if line.startswith("- "):
            item = line[2:].strip()
            cont = current_container()
            if isinstance(cont, list):
                if ":" in item and not item.startswith("["):
                    # inline map start not supported in list of scalars; treat as scalar
                    cont.append(_scalar(item))
                else:
                    cont.append(_scalar(item))
            elif isinstance(cont, dict) and pending_key:
                # shouldn't happen often
                pass
            continue

        if ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            cont = current_container()
            if not isinstance(cont, dict):
                continue
            if rest == "" or rest == "|" or rest == ">":
                # nested map or list follows
                # peek: we create dict by default; list if next lines are -
                cont[key] = {}
                stack.append((indent, cont[key]))
                pending_key = key
                pending_indent = indent
            elif rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if not inner:
                    cont[key] = []
                else:
                    cont[key] = [_scalar(x.strip()) for x in inner.split(",")]
            else:
                cont[key] = _scalar(rest)
        # convert empty dict to list if subsequent list items — handled below on next lines poorly
        # fix: re-scan for list under empty dicts in postprocess

    # Second pass: fix dicts that should be lists (children only came as "- " under wrong parent)
    # Our parser creates {} for empty rest; list items with "- " need parent to be list.
    # Re-parse with list-aware approach.
    return _parse_yaml_list_aware(text)


def _scalar(s: str) -> Any:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1]
    if s.lower() in ("true", "yes", "on"):
        return True
    if s.lower() in ("false", "no", "off"):
        return False
    if s.lower() in ("null", "~", ""):
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _parse_yaml_list_aware(text: str) -> Dict[str, Any]:
    """Line-based parser: supports nested maps and list of scalars under a key."""
    root: Dict[str, Any] = {}
    # stack of (indent, container_ref, type) type=dict|list
    stack: List[Any] = [( -1, root, "dict")]

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent_indent, parent, ptype = stack[-1]

        if line.startswith("- "):
            val = _scalar(line[2:].strip())
            if ptype == "list":
                parent.append(val)
            elif ptype == "dict":
                # malformed; ignore
                pass
            continue

        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if ptype != "dict":
            continue

        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            parent[key] = (
                []
                if not inner
                else [_scalar(x.strip()) for x in _split_csv(inner)]
            )
        elif rest != "":
            parent[key] = _scalar(rest)
        else:
            # look ahead: list or map?
            j = i
            is_list = False
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip() or nxt.lstrip().startswith("#"):
                    j += 1
                    continue
                nindent = len(nxt) - len(nxt.lstrip(" "))
                if nindent <= indent:
                    break
                if nxt.strip().startswith("- "):
                    is_list = True
                break
            if is_list:
                parent[key] = []
                stack.append((indent, parent[key], "list"))
            else:
                parent[key] = {}
                stack.append((indent, parent[key], "dict"))

    return root


def _split_csv(s: str) -> List[str]:
    """Split on commas not inside quotes (simple)."""
    parts: List[str] = []
    cur = []
    in_q = False
    for ch in s:
        if ch in ("'", '"'):
            in_q = not in_q
            cur.append(ch)
        elif ch == "," and not in_q:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


@lru_cache(maxsize=1)
def load_bindings(force: bool = False) -> Dict[str, Any]:
    if force:
        load_bindings.cache_clear()  # type: ignore[attr-defined]
    path = _BINDINGS_PATH
    if not path.exists():
        return {"version": 0, "agents": {}, "default": {}}
    text = path.read_text(encoding="utf-8")
    data = _parse_yaml_list_aware(text)
    if not isinstance(data, dict):
        return {"version": 0, "agents": {}, "default": {}}
    # ensure agents is dict
    agents = data.get("agents") or {}
    if not isinstance(agents, dict):
        data["agents"] = {}
    return data


def list_agent_ids() -> List[str]:
    data = load_bindings()
    return sorted((data.get("agents") or {}).keys())


def get_binding(agent_id: str) -> Dict[str, Any]:
    data = load_bindings()
    agents = data.get("agents") or {}
    default = data.get("default") or {}
    b = agents.get(agent_id)
    if not b:
        return {
            "agent_id": agent_id,
            "name": agent_id,
            "team": "unknown",
            "allow_search": False,
            "inject_mode": "never",
            "categories": [],
            "path_prefixes": list(default.get("fallback_path_prefixes") or []),
            "tags": [],
            "trajectories": [],
            "limit": int(default.get("limit") or 4),
            "deny_coordinates": bool(default.get("deny_coordinates", True)),
            "missing": True,
        }
    out = dict(b)
    out["agent_id"] = agent_id
    out.setdefault("allow_search", default.get("allow_search", True))
    out.setdefault("limit", default.get("limit", 4))
    out.setdefault("deny_coordinates", default.get("deny_coordinates", True))
    out.setdefault("inject_mode", "on_demand")
    out.setdefault("path_prefixes", [])
    out.setdefault("categories", [])
    out.setdefault("tags", [])
    out.setdefault("trajectories", [])
    return out


def path_allowed(path: str, binding: Dict[str, Any]) -> bool:
    """path 相对 knowledge_base 的 posix。"""
    prefixes = binding.get("path_prefixes") or []
    if not prefixes:
        return True
    p = path.replace("\\", "/")
    for pref in prefixes:
        pref = str(pref).replace("\\", "/")
        if p == pref or p.startswith(pref) or pref.rstrip("/") == p:
            return True
        # allow prefix as file stem match
        if pref.endswith(".md") and p.endswith(pref.split("/")[-1]):
            return True
        # prefix like 02_tools/cog_ matches cog_primary.md
        if pref.endswith("_") and p.startswith(pref):
            return True
        if "/cog_" in pref or pref.endswith("cog_"):
            if "cog_" in p and p.startswith("02_tools/"):
                return True
    return False


def filter_hit_paths(
    hits: List[Dict[str, Any]], binding: Dict[str, Any]
) -> List[Dict[str, Any]]:
    return [h for h in hits if path_allowed(str(h.get("path") or ""), binding)]


def search_for_agent(
    agent_id: str,
    q: str = "",
    *,
    limit: Optional[int] = None,
    force_search: bool = False,
) -> Dict[str, Any]:
    """按 agent 绑定表过滤的知识检索。"""
    from packing_assistant.tools.search_knowledge import search_knowledge

    binding = get_binding(agent_id)
    allow = bool(binding.get("allow_search"))
    if not allow and not force_search:
        return {
            "ok": True,
            "agent_id": agent_id,
            "skipped": True,
            "reason": "allow_search=false (e.g. loader uses tools only)",
            "binding": {
                "name": binding.get("name"),
                "team": binding.get("team"),
                "inject_mode": binding.get("inject_mode"),
                "note": binding.get("note"),
            },
            "hits": [],
            "n_hits": 0,
        }

    lim = int(limit or binding.get("limit") or 4)
    # Broad search then filter by path_prefixes (more reliable than category alone)
    tags = binding.get("tags") or []
    tag_list = [str(t) for t in tags] if tags else None
    # Use query; if empty, use tags joined
    query = (q or "").strip() or " ".join(tag_list or ["规则"])
    raw = search_knowledge(query, tags=None, limit=max(lim * 5, 15))
    hits = filter_hit_paths(list(raw.get("hits") or []), binding)

    # If too few hits, try path-prefix document titles via second pass on all docs
    if len(hits) < lim:
        from packing_assistant.tools.search_knowledge import load_kb

        extra = []
        for doc in load_kb():
            if not path_allowed(doc.path, binding):
                continue
            if any(h.get("path") == doc.path for h in hits):
                continue
            # light score if query tokens in path/title
            blob = (doc.path + " " + doc.title + " " + doc.body[:500]).lower()
            score = 0.5
            for t in re.findall(r"[\w\u4e00-\u9fff]+", query.lower()):
                if len(t) >= 2 and t in blob:
                    score += 1.0
            extra.append(
                {
                    "path": doc.path,
                    "title": doc.title,
                    "score": round(score, 3),
                    "snippet": (doc.body.strip().splitlines() or [""])[0][:200],
                    "frontmatter": {
                        k: doc.frontmatter.get(k)
                        for k in ("category", "priority", "tags")
                        if k in doc.frontmatter
                    },
                }
            )
        extra.sort(key=lambda x: -float(x.get("score") or 0))
        hits.extend(extra)

    hits = hits[:lim]
    return {
        "ok": True,
        "agent_id": agent_id,
        "q": query,
        "n_hits": len(hits),
        "hits": hits,
        "binding": {
            "name": binding.get("name"),
            "team": binding.get("team"),
            "inject_mode": binding.get("inject_mode"),
            "path_prefixes": binding.get("path_prefixes"),
            "allow_search": binding.get("allow_search"),
            "numeric_kb": binding.get("numeric_kb"),
            "note": binding.get("note"),
        },
        "note": "filtered by agent_kb_bindings; coordinates never from KB",
    }


def brief_evidence(agent_id: str, q: str, *, max_snips: int = 3) -> List[Dict[str, str]]:
    """给 finalize/critic 用的短证据列表。"""
    res = search_for_agent(agent_id, q, limit=max_snips, force_search=True)
    out = []
    for h in res.get("hits") or []:
        out.append(
            {
                "path": str(h.get("path") or ""),
                "title": str(h.get("title") or ""),
                "snippet": str(h.get("snippet") or "")[:180],
            }
        )
    return out


def bindings_summary() -> Dict[str, Any]:
    data = load_bindings()
    rows = []
    for aid in list_agent_ids():
        b = get_binding(aid)
        rows.append(
            {
                "id": aid,
                "name": b.get("name"),
                "team": b.get("team"),
                "allow_search": b.get("allow_search"),
                "inject_mode": b.get("inject_mode"),
                "n_prefixes": len(b.get("path_prefixes") or []),
            }
        )
    return {
        "version": data.get("version"),
        "harness": data.get("harness"),
        "path": str(_BINDINGS_PATH.relative_to(_ROOT)).replace("\\", "/"),
        "agents": rows,
    }
