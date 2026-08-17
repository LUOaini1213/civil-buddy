"""Drive shipped prompt-builder and retrieval. Run from demo/: python -m pytest tests/test_kb_prompt.py -q"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import build_expert_prompt  # noqa: E402
from catalog_seed import CATEGORIES, EXPERTS  # noqa: E402
from config import KB_ROOT  # noqa: E402
from rag import search_kb  # noqa: E402


def _exp(eid: str):
    return next(e for e in EXPERTS if e.id == eid)


def test_sixteen_categories():
    ids = [c["id"] for c in CATEGORIES]
    assert len(ids) == 16
    assert len(set(ids)) == 16


def test_qa_prompt_allows_ask_and_other_depts():
    prompt = build_expert_prompt(_exp("structure"), confirm_ok=False)
    assert "不懂" in prompt or "提问" in prompt
    assert "全企业任何人都可以向你提问" in prompt
    assert "不要只聊天不交稿" not in prompt
    assert "可以只聊天" in prompt
    assert "改召唤那位专家" in prompt


def test_high_risk_deliverable_still_gated():
    prompt = build_expert_prompt(_exp("construction"), confirm_ok=False)
    assert "我明白，将由持证人员签认" in prompt
    assert "纯提问（A）不受确认门阻挡" in prompt


def test_retrieve_not_tied_to_caller_department():
    # finance asking structure — still searches structure's trees only
    hits = search_kb("structure", "design", "荷载")
    assert isinstance(hits, list)
    for h in hits:
        assert h.layer in {"expert", "category", "company"}
        if h.layer == "expert":
            assert h.path.startswith("design/structure/")


def test_switch_expert_hits_new_private_and_shared():
    a = search_kb("architecture", "design", "防火分区")
    b = search_kb("lab-mix", "lab", "配合比")
    a_priv = [h for h in a if h.layer == "expert"]
    b_priv = [h for h in b if h.layer == "expert"]
    for h in a_priv:
        assert "/architecture/" in h.path.replace("\\", "/")
    for h in b_priv:
        assert "/lab-mix/" in h.path.replace("\\", "/")
    b_shared = [h for h in b if h.layer == "category"]
    for h in b_shared:
        assert h.path.replace("\\", "/").startswith("lab/_shared/")


def test_every_expert_private_and_category_shared_nonstub():
    assert len(CATEGORIES) == 16
    for e in EXPERTS:
        priv = KB_ROOT / e.category / e.id
        shared = KB_ROOT / e.category / "_shared"
        assert priv.is_dir(), e.id
        assert shared.is_dir(), e.category
        body = [
            p
            for p in priv.iterdir()
            if p.is_file()
            and p.suffix.lower() in {".md", ".txt"}
            and p.name.lower() != "readme.md"
        ]
        assert body, e.id
        assert sum(p.stat().st_size for p in body) >= 400, e.id
        ask = shared / "ask-from-others.md"
        assert ask.is_file(), e.category
