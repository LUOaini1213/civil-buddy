"""66-expert roster from the canonical seed; no duplicate tool ownership map."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from packing_assistant.expert_capabilities import load_seed

@dataclass(frozen=True)
class ExpertRec:
    id: str
    name: str
    category: str
    category_name: str
    title: str
    delivers: str
    risk: str
    aliases: tuple[str, ...]
    exclusive: tuple[str, ...]
    aligned: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "category_name": self.category_name,
            "title": self.title,
            "delivers": self.delivers,
            "risk": self.risk,
            "aliases": list(self.aliases),
            "exclusive": list(self.exclusive),
            "aligned": self.aligned,
        }


@lru_cache(maxsize=1)
def _load() -> List[ExpertRec]:
    seed = load_seed()
    cats = {c["id"]: c.get("name") or c["id"] for c in seed.get("categories") or []}
    out: List[ExpertRec] = []
    for e in seed.get("experts") or []:
        out.append(
            ExpertRec(
                id=e["id"],
                name=e.get("name") or e["id"],
                category=e.get("category") or "",
                category_name=e.get("category_name") or cats.get(e.get("category") or "", ""),
                title=e.get("title") or "",
                delivers=e.get("delivers") or "",
                risk=e.get("risk") or "low",
                aliases=tuple(e.get("aliases") or []),
                exclusive=tuple(e["exclusive"]),
                aligned=bool(e["aligned"]),
            )
        )
    return out


def list_experts() -> List[ExpertRec]:
    return list(_load())


def get_expert(expert_id: str) -> Optional[ExpertRec]:
    eid = (expert_id or "").strip()
    for e in _load():
        if e.id == eid:
            return e
    return None


def exclusive_tools(expert_id: str) -> List[str]:
    exp = get_expert(expert_id)
    return list(exp.exclusive) if exp else []


def exclusive_owner(name: str) -> Optional[str]:
    n = (name or "").strip()
    if not n:
        return None
    for e in _load():
        if n in e.exclusive:
            return e.id
    return None


def resolve_expert(blob: str) -> Optional[str]:
    """Only @id / @中文名. Aliases are too wide for the default tender box."""
    t = blob or ""
    for e in _load():
        if f"@{e.id}" in t or f"@{e.name}" in t:
            return e.id
    return None
