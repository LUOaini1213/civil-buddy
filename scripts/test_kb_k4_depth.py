#!/usr/bin/env python3
"""K4: every of 66 roster posts can answer ≥5 questions, has README field table, outline gaps.

Drives shipped demo.rag.search_kb / list_kb (not a reimplementation).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
KB = DEMO / "kb"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DEMO))

from rag import list_kb, search_kb  # noqa: E402

_Q_RE = re.compile(
    r"(?m)(?:^问[：:]|^[-*]\s*问[：:]|^## Q\s|^\*\*[^*\n]{2,80}？\*\*)"
)
_ASSERT_OK = (
    "禁止",
    "不写",
    "不得",
    "不准",
    "不是",
    "不要",
    "不能",
    "不下",
    "不等于",
    "不宣称",
    "不说",
    "不把",
    "勿",
)


def count_questions(text: str) -> int:
    return len(_Q_RE.findall(text or ""))


def outline_blob(folder: Path, outline: str) -> str:
    bits = [outline or ""]
    if "scheme-11.md" in (outline or "") and (folder / "scheme-11.md").is_file():
        bits.append((folder / "scheme-11.md").read_text(encoding="utf-8"))
    if "judge-card.md" in (outline or "") and (folder / "judge-card.md").is_file():
        bits.append((folder / "judge-card.md").read_text(encoding="utf-8"))
    return "\n".join(bits)


def assertive_forbidden(text: str, phrase: str) -> list[str]:
    hits = []
    for i, line in enumerate((text or "").splitlines(), 1):
        if phrase not in line:
            continue
        if any(k in line for k in _ASSERT_OK):
            continue
        hits.append(f"L{i}:{line.strip()[:80]}")
    return hits


def main() -> int:
    from packing_assistant.expert_roster import list_experts

    roster = list_experts()
    assert len(roster) == 66, len(roster)
    fails: list[str] = []
    n_q = n_fields = n_gap = n_hit = 0

    by_cat: dict[str, list[str]] = {}
    for e in roster:
        by_cat.setdefault(e.category, []).append(e.id)

    for e in roster:
        folder = KB / e.category / e.id
        faq = (folder / "faq.md").read_text(encoding="utf-8")
        readme = (folder / "README.md").read_text(encoding="utf-8")
        outline = (folder / "outline.md").read_text(encoding="utf-8")
        web = (folder / "web-knowledge.md").read_text(encoding="utf-8")
        blob = outline_blob(folder, outline)

        nq = count_questions(faq)
        if nq >= 5:
            n_q += 1
        else:
            fails.append(f"{e.id}: faq questions={nq} want≥5")

        if "| 栏 |" in readme and "字段表" in readme:
            n_fields += 1
        else:
            fails.append(f"{e.id}: README missing 字段表")

        if "[A001]" in blob or "[Axxx]" in blob or "待填" in blob or "信息不足" in blob:
            n_gap += 1
        else:
            fails.append(f"{e.id}: outline has no [A001]/待填/信息不足")

        for phrase in ("可以开工", "可以投标"):
            for label, text in (("faq", faq), ("web", web), ("readme", readme)):
                bad = assertive_forbidden(text, phrase)
                if bad:
                    fails.append(f"{e.id}: {label} assertive {phrase}: {bad[0]}")

        rows = list_kb(e.id, e.category)
        paths = [str(r.get("path") or "").replace("\\", "/") for r in rows]
        if not any(p.startswith(f"{e.category}/{e.id}/") for p in paths):
            fails.append(f"{e.id}: list_kb missing private lib")
        for oid in by_cat.get(e.category) or []:
            if oid == e.id:
                continue
            if any(p.startswith(f"{e.category}/{oid}/") for p in paths):
                fails.append(f"{e.id}: list_kb leaked sibling {oid}")

        hits = search_kb(e.id, e.category, e.name, limit=8)
        hpaths = [h.path.replace("\\", "/") for h in hits]
        if any(p.startswith(f"{e.category}/{e.id}/") for p in hpaths):
            n_hit += 1
        else:
            fails.append(f"{e.id}: search_kb({e.name!r}) missed private lib {hpaths[:4]}")
        for oid in by_cat.get(e.category) or []:
            if oid == e.id:
                continue
            if any(p.startswith(f"{e.category}/{oid}/") for p in hpaths):
                fails.append(f"{e.id}: search_kb leaked sibling {oid}")

    if fails:
        print("FAIL kb_k4_depth")
        print("\n".join(fails[:80]))
        if len(fails) > 80:
            print(f"... +{len(fails) - 80} more")
        return 1
    print(
        "PASS kb_k4_depth",
        f"experts=66 faq5={n_q} fields={n_fields} gaps={n_gap} search_hit={n_hit}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
