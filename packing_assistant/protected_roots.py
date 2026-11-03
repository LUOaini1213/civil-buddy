"""Folders that hold production data on this machine.

No tool may use one as a job root or write into it. The list is per machine:
``CIVIL_PROTECTED_ROOTS`` holds one or more folders separated by ``os.pathsep``
(``;`` on Windows, ``:`` elsewhere), for example ``CIVIL_PROTECTED_ROOTS=D:\\site-data``.
It is empty by default; the repository does not ship any one person's folder names.

Independently of this list, the policy engine treats any folder literally named
``prod`` as production data (runtime/policy.py), and every write still has to pass
the sandbox's write roots (sandbox.check_write).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Union

ENV = "CIVIL_PROTECTED_ROOTS"


def _norm(path: Union[str, Path]) -> str:
    return str(path).replace("/", "\\").rstrip("\\").lower()


def protected_roots() -> List[str]:
    """The configured roots, normalised (backslashes, lower case, no trailing separator)."""
    raw = os.getenv(ENV) or ""
    return [_norm(part.strip()) for part in raw.split(os.pathsep) if part.strip()]


def is_protected(path: Union[str, Path]) -> bool:
    """True when ``path`` is a configured protected root or lies inside one.

    Checked on the path as given and, where it resolves, on its absolute form, so a
    relative path into a protected folder is caught as well."""
    roots = protected_roots()
    if not roots or not str(path or "").strip():
        return False
    forms = {_norm(path)}
    try:
        forms.add(_norm(Path(path).expanduser().resolve()))
    except (OSError, RuntimeError, ValueError):
        pass
    return any(f == r or f.startswith(r + "\\") for f in forms for r in roots)
