"""civil works in the folder it is started in, the way Codex works in the repository it is started in.

A job folder is a directory that holds a ``CIVIL.md`` (``civil init`` writes one), or the
directory named with ``civil -C``. Activating it:

- authorizes it as the job root (``CIVIL_JOB_ROOT``), so job files can be read and Office
  exports land next to the user's own files, under the rules ``office_job`` already enforces;
- moves this process's session state — thread snapshots, session slots, tender hand-offs,
  packing snapshots and drafted deliverables — from the repository's ``demo/out`` into
  ``<job>/.civil-buddy/out``.

Nothing is activated when civil runs outside a job folder, so the workbench and every
existing caller keep writing where they always did.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

MARKER = "CIVIL.md"
STATE_DIR = ".civil-buddy"

# (module, attribute, sub-directory of <job>/.civil-buddy/out). These are the module-level
# roots the runtime writes session state under; the tests rebind the same names.
_TARGETS = (
    ("packing_assistant.runtime.agent_loop", "_OUT", ""),
    ("packing_assistant.runtime.memory", "_OUT", ""),
    ("packing_assistant.expert_turn", "_OUT", ""),
    ("packing_assistant.runtime.session_handoff", "_DIR", ""),
    ("packing_assistant.runtime.session_packing", "_DIR", ""),
    ("packing_assistant.runtime.threads", "_DIR", "_threads"),
)

_ACTIVE: Optional[Path] = None
_ORIGINAL: Dict[tuple, Any] = {}
_ORIGINAL_ENV: Dict[str, Optional[str]] = {}


def find_job_root(start: Optional[Path] = None) -> Optional[Path]:
    """The nearest directory at or above ``start`` that holds a CIVIL.md, or None."""
    here = Path(start or Path.cwd())
    try:
        here = here.resolve()
    except OSError:
        return None
    home = Path.home()
    for folder in (here, *here.parents):
        if (folder / MARKER).is_file():
            return folder
        if folder == home:
            break
    return None


def state_root(job: Path) -> Path:
    return Path(job) / STATE_DIR / "out"


def active() -> Optional[Path]:
    return _ACTIVE


def _forget_plugins() -> None:
    from packing_assistant.runtime import plugins

    plugins.reload()        # a job folder may carry its own plugins: the roster is rebuilt when the folder changes


def activate(job: Path) -> Path:
    """Make ``job`` the working folder of this process. Idempotent; raises on a forbidden path."""
    from packing_assistant.office_job import is_forbidden_layout

    global _ACTIVE
    job = Path(job).expanduser().resolve()
    if not job.is_dir():
        raise NotADirectoryError(f"不是文件夹：{job}")
    if is_forbidden_layout(job):
        raise PermissionError(f"禁止把 {job} 作为作业文件夹")
    if _ACTIVE == job:
        return job
    if _ACTIVE is not None:
        deactivate()
    root = state_root(job)
    root.mkdir(parents=True, exist_ok=True)
    for module_name, attribute, sub in _TARGETS:
        module = importlib.import_module(module_name)
        _ORIGINAL[(module_name, attribute)] = getattr(module, attribute)
        setattr(module, attribute, root / sub if sub else root)
    _ORIGINAL_ENV["CIVIL_JOB_ROOT"] = os.environ.get("CIVIL_JOB_ROOT")
    os.environ["CIVIL_JOB_ROOT"] = str(job)
    _ACTIVE = job
    _forget_plugins()
    return job


def deactivate() -> None:
    """Undo ``activate``. Used by tests and when a process switches job folders."""
    global _ACTIVE
    for (module_name, attribute), value in _ORIGINAL.items():
        setattr(importlib.import_module(module_name), attribute, value)
    _ORIGINAL.clear()
    for key, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    _ORIGINAL_ENV.clear()
    _ACTIVE = None
    _forget_plugins()


def describe() -> Dict[str, Any]:
    """What /status prints about the workspace."""
    from packing_assistant.runtime.project_instructions import load

    job = active()
    instructions = load(job)
    return {
        "job_root": str(job) if job else "",
        "state_root": str(state_root(job)) if job else "",
        "instruction_files": [str(p) for p in instructions.files],
        "slots": dict(instructions.slots),
        "truncated": instructions.truncated,
    }
