"""Worktree / job-root for a single run. ContextVar so /bg does not leak into main tree."""

from __future__ import annotations

import os
import subprocess
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
_WORKTREE: ContextVar[str] = ContextVar("civil_worktree", default="")


def repo_root() -> Path:
    return _ROOT


def set_worktree(path: str) -> None:
    _WORKTREE.set((path or "").strip())


def current_worktree() -> str:
    return _WORKTREE.get() or (os.getenv("CIVIL_WORKTREE_ROOT") or "").strip()


def deliverable_root() -> Path:
    wt = current_worktree()
    if wt:
        p = Path(wt) / ".civil-buddy" / "out"
        p.mkdir(parents=True, exist_ok=True)
        return p
    return _ROOT / "demo" / "out"


def add_git_worktree(dest: Path, *, repo: Optional[Path] = None) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cwd = str(repo or _ROOT)
    proc = subprocess.run(
        ["git", "worktree", "add", "--detach", str(dest)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "git worktree add failed")
    return dest.resolve()


def remove_git_worktree(dest: Path, *, repo: Optional[Path] = None) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(dest)],
        cwd=str(repo or _ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
