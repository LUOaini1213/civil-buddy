#!/usr/bin/env python3
"""S2: construction chat no write; HITL without confirm; 11 chapters after confirm."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHAPTERS = (
    "封面与文件控制",
    "草稿与责任声明",
    "工程概况",
    "编制依据",
    "施工部署与工艺",
    "质量",
    "安全与应急",
    "环保与文明施工",
    "资源计划",
    "验收与资料",
    "附录",
)


def main() -> int:
    from packing_assistant.expert_turn import run_expert_turn

    chat = run_expert_turn("临边防护算不算危大？", "construction")
    assert chat["intent"] == "chat" and chat["wrote"] is False

    blocked = run_expert_turn("写一份专项方案讨论提纲", "construction", confirm_ok=False, force_intent="run")
    assert blocked["wrote"] is False and blocked.get("hitl_pending") is True

    ok = run_expert_turn(
        "写临边防护方案讨论提纲",
        "construction",
        confirm_ok=True,
        force_intent="run",
        session_id="scheme-s2",
    )
    assert ok["wrote"] is True
    assert "construction__scheme_draft" in (ok.get("tools_run") or [])
    path = Path(ok["files"][0]["path"])
    text = path.read_text(encoding="utf-8")
    for i, title in enumerate(CHAPTERS, 1):
        assert f"## {i} {title}" in text, title
    assert "可以开工" not in text
    assert "可以投标" not in text
    print("PASS construction_skill_path chapters=11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
