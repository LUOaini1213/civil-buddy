#!/usr/bin/env python3
"""Background run writes into a git worktree, not the main demo/out tree."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.runtime.threads import spawn, thread_status
    from packing_assistant.runtime.workspace_ctx import add_git_worktree, remove_git_worktree

    dest = ROOT / "output" / "worktrees" / "bg-wt"
    if dest.exists():
        remove_git_worktree(dest)
    wt = add_git_worktree(dest)
    marker_main = ROOT / "demo" / "out" / "wt-should-not.md"
    if marker_main.exists():
        marker_main.unlink()
    try:
        got = spawn(
            "出一份税务日历",
            skill="finance-tax",
            title="wt-tax",
            worktree=str(wt),
        )
        tid = str(got.get("thread_id") or "")
        assert tid
        deadline = time.time() + 30
        info = {}
        while time.time() < deadline:
            info = thread_status(tid)
            if not info.get("running") and info.get("state") not in {"idle", "running", ""}:
                break
            time.sleep(0.2)
        wrote_under = list((wt / ".civil-buddy" / "out").rglob("*.md")) if (wt / ".civil-buddy").exists() else []
        arts = [Path(a) for a in (info.get("artifacts") or [])]
        under_wt = [p for p in arts if str(wt) in str(p)]
        print("state", info.get("state"), "wrote", info.get("wrote"), "n_md", len(wrote_under), "arts", arts[:3])
        assert wrote_under or under_wt, info
        hit = (wrote_under or under_wt)[0]
        assert str(wt) in str(hit)
        main_copy = ROOT / "demo" / "out" / tid / "finance-tax" / "finance-tax__calendar.md"
        assert not main_copy.is_file(), main_copy
        print("PASS worktree", tid, "files", len(wrote_under or under_wt))
        return 0
    finally:
        remove_git_worktree(dest)


if __name__ == "__main__":
    raise SystemExit(main())
