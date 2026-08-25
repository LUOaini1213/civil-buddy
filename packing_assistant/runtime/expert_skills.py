"""Civil Buddy skill pack (土木版 Codex).

Host = this product, not OpenAI Codex. Format is Agent Skills: one
`.agents/skills/<id>/SKILL.md` per expert. Progressive disclosure:

1. Catalog = name + description (always cheap)
2. Full SKILL.md body loads only after the skill is chosen
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = _ROOT / ".agents" / "skills"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _safe_id(expert_id: str) -> str:
    eid = (expert_id or "").strip().lower()
    if not NAME_RE.match(eid) or "--" in eid:
        return ""
    return eid


def skill_path(expert_id: str) -> Optional[Path]:
    eid = _safe_id(expert_id)
    if not eid:
        return None
    path = SKILLS_DIR / eid / "SKILL.md"
    return path if path.is_file() else None


def split_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    raw = text or ""
    if not raw.startswith("---"):
        return {}, raw
    rest = raw[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return {}, raw
    fm = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in fm.splitlines():
        if ":" not in line or line.startswith(" ") or line.startswith("\t"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        if not key or key == "metadata":
            continue
        val = val.strip().strip('"').strip("'")
        if key and val:
            meta[key] = val
    return meta, body


def load_skill(expert_id: str) -> Optional[Dict[str, Any]]:
    path = skill_path(expert_id)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = split_frontmatter(text)
    name = (meta.get("name") or expert_id).strip()
    return {
        "id": _safe_id(expert_id),
        "name": name,
        "description": (meta.get("description") or "").strip(),
        "body": body.strip(),
        "path": str(path),
        "meta": meta,
    }


def skill_body(expert_id: str) -> str:
    got = load_skill(expert_id)
    return str(got["body"]) if got else ""


def list_expert_skill_ids() -> List[str]:
    if not SKILLS_DIR.is_dir():
        return []
    out: List[str] = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == "civil-buddy":
            continue
        if (child / "SKILL.md").is_file() and NAME_RE.match(child.name) and "--" not in child.name:
            out.append(child.name)
    return out


def prompt_suffix(expert_id: str) -> str:
    body = skill_body(expert_id)
    if not body:
        return ""
    return "\n本岗 Skill（程序记忆，选用本岗才加载全文）：\n" + body + "\n"


# Longest first. Bare 施工/方案/发票/配比 must not steal a turn.
_STRONG = (
    ("专项施工方案", "construction"),
    ("方案讨论提纲", "construction"),
    ("施工方案", "construction"),
    ("专项方案", "construction"),
    ("危大识别", "method-hazard"),
    ("危大工程", "method-hazard"),
    ("判定书", "method-hazard"),
    ("超危", "method-hazard"),
    ("危大", "method-hazard"),
    ("招标解析", "bid-parse"),
    ("解析招标", "bid-parse"),
    ("抽出评分", "bid-parse"),
    ("废标检查", "bid-compliance"),
    ("响应缺口", "bid-compliance"),
    ("技术标", "bid-tech"),
    ("装箱作业", "pack-ship"),
    ("packing-agent", "pack-ship"),
    ("拼柜", "pack-ship"),
    ("成箱", "pack-ship"),
    ("装箱", "pack-ship"),
    ("税务日历", "finance-tax"),
    ("工友白话", "worker-brief"),
    ("班前口播", "worker-brief"),
    ("班前白话", "worker-brief"),
    ("安全交底", "safety-brief"),
    ("施工配合比", "lab-mix"),
    ("见证取样", "lab-sample"),
    ("工程量拆分", "cost"),
)


def catalog() -> List[Dict[str, str]]:
    """Metadata only — what Codex puts in the first 2% of context."""
    rows: List[Dict[str, str]] = []
    for eid in list_expert_skill_ids():
        got = load_skill(eid)
        if not got:
            continue
        rows.append(
            {
                "name": got["name"],
                "description": got["description"][:500],
                "path": got["path"],
            }
        )
    return rows


def catalog_preamble() -> str:
    lines = [
        "Civil Buddy 是土木版 Codex：在作业根里下任务，按 skill 干活。",
        "先只看下面的 name + description。选中后再读该 SKILL.md 全文。不要一次加载全部专家。",
        "显式：`$construction` / `@施工方案` / `召唤危大识别`。隐式：任务对上 description 才选用。",
        "数字走工具。高风险写盘确认句：我明白，将由持证人员签认。submit_blocked=true。",
        "",
        "技能目录：",
    ]
    for row in catalog():
        lines.append(f"- ${row['name']}: {row['description']}")
    return "\n".join(lines)


_EXPLICIT = re.compile(
    r"(?:\$|@|/)(?:skill(?:s)?[:\s]*)?([a-z][a-z0-9-]{1,62})",
    re.I,
)


def parse_explicit(text: str) -> Optional[str]:
    blob = text or ""
    ids = set(list_expert_skill_ids())
    for m in _EXPLICIT.finditer(blob):
        eid = _safe_id(m.group(1))
        if eid in ids:
            return eid
    try:
        from packing_assistant.expert_roster import list_experts

        for e in list_experts():
            labels = [e.id, e.name, *e.aliases]
            for lab in labels:
                if lab and (f"@{lab}" in blob or f"召唤{lab}" in blob or f"${lab}" in blob):
                    return e.id
    except Exception:
        pass
    return None


def match_skill(text: str) -> Optional[str]:
    """Pick at most one skill. Explicit wins. Implicit needs a unique strong hit."""
    blob = (text or "").strip()
    if not blob:
        return None
    hit = parse_explicit(blob)
    if hit:
        return hit
    for phrase, eid in _STRONG:
        if phrase.lower() in blob.lower():
            return eid
    scores: Dict[str, int] = {}
    try:
        from packing_assistant.expert_roster import list_experts

        experts = list_experts()
    except Exception:
        return None
    for e in experts:
        best = 0
        for lab in (e.id, e.name, *e.aliases):
            if not lab or lab not in blob:
                continue
            n = len(lab)
            if n < 4:
                continue
            best = max(best, n)
        if best:
            scores[e.id] = best
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) == 1:
        return ranked[0][0]
    if ranked[0][1] >= ranked[1][1] + 2:
        return ranked[0][0]
    return None
