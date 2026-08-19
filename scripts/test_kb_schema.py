#!/usr/bin/env python3
"""K1/T001: every of 66 roster experts has README, faq, outline, web-knowledge."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KB = ROOT / "demo" / "kb"
REQUIRED = ("README.md", "faq.md", "outline.md", "web-knowledge.md")


def main() -> int:
    from packing_assistant.expert_roster import list_experts

    roster = list_experts()
    assert len(roster) == 66, len(roster)
    ids = [e.id for e in roster]
    assert len(set(ids)) == 66, ids
    sys.path.insert(0, str(ROOT / "demo"))
    from catalog_seed import EXPERTS  # noqa: E402

    cat_ids = [e.id for e in EXPERTS]
    assert len(cat_ids) == 66, len(cat_ids)
    assert set(cat_ids) == set(ids), sorted(set(ids) ^ set(cat_ids))
    missing: list[str] = []
    for exp in roster:
        folder = KB / exp.category / exp.id
        if not folder.is_dir():
            missing.append(f"{exp.id}: no dir {folder.relative_to(ROOT)}")
            continue
        for name in REQUIRED:
            p = folder / name
            if not p.is_file():
                missing.append(f"{exp.id}: missing {name}")
    assert not missing, "\n".join(missing)
    print("PASS kb_schema experts=66 files=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
