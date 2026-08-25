#!/usr/bin/env python3
"""66 workbench experts are Codex skills: frontmatter + runtime inject."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def main() -> int:
    from catalog_seed import EXPERTS
    from packing_assistant.runtime.expert_skills import (
        SKILLS_DIR,
        list_expert_skill_ids,
        load_skill,
        prompt_suffix,
        split_frontmatter,
    )

    assert len(EXPERTS) == 66, len(EXPERTS)
    ids = {e.id for e in EXPERTS}
    found = set(list_expert_skill_ids())
    assert found == ids, f"skill ids != catalog: missing={ids - found} extra={found - ids}"

    for e in EXPERTS:
        assert NAME_RE.match(e.id) and "--" not in e.id, e.id
        got = load_skill(e.id)
        assert got, e.id
        assert got["name"] == e.id, (e.id, got["name"])
        desc = got["description"]
        assert 1 <= len(desc) <= 500, (e.id, len(desc))
        assert "\n" not in desc, e.id
        path = SKILLS_DIR / e.id / "SKILL.md"
        assert path.is_file(), e.id
        raw = path.read_text(encoding="utf-8")
        meta, body = split_frontmatter(raw)
        assert meta.get("name") == e.id
        assert e.name in body
        assert "程序记忆" in body
        mirror = ROOT / ".codex" / "skills" / e.id / "SKILL.md"
        assert mirror.is_file(), e.id
        assert mirror.read_text(encoding="utf-8") == raw

    router = load_skill("civil-buddy")
    assert router and router["name"] == "civil-buddy"
    assert "bid-parse" in router["body"] and "pack-ship" in router["body"]
    assert "不要把 66 份人格读进同一次上下文" in router["body"]

    cons = load_skill("construction")
    assert cons and "11 章" in cons["body"]
    assert "construction__scheme_draft" in cons["body"]
    pack = load_skill("pack-ship")
    assert pack and "UNSPECIFIED" in pack["body"]
    assert "xyz" in pack["body"]
    bid = load_skill("bid-parse")
    assert bid and "submit_blocked" in bid["body"]

    from agent import build_expert_prompt
    from catalog_seed import EXPERTS as E

    construction = next(x for x in E if x.id == "construction")
    prompt = build_expert_prompt(construction, confirm_ok=False)
    assert "全企业任何人都可以向你提问" in prompt
    assert "可以只聊天" in prompt
    assert "我明白，将由持证人员签认" in prompt
    assert "纯提问（A）不受确认门阻挡" in prompt
    assert "本岗 Skill" in prompt
    assert "construction__scheme_draft" in prompt
    assert prompt_suffix("construction") in prompt

    print("PASS test_codex_expert_skills experts=66")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
