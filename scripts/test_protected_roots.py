#!/usr/bin/env python3
"""Production-data roots are configured per machine (CIVIL_PROTECTED_ROOTS), not hard-coded.

Checks the three places that consult them: the policy engine's deny_production rule, the job-root guard
(office_job.is_forbidden_layout / job_root) and the sandbox's write roots. A folder named ``prod`` stays
protected with no configuration at all.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["CIVIL_SANDBOX"] = "workspace-write"
    from packing_assistant.office_job import is_forbidden_layout, job_root
    from packing_assistant.protected_roots import ENV, is_protected, protected_roots
    from packing_assistant.runtime.policy import CODE_PRODUCTION, evaluate
    from packing_assistant.sandbox import default_profile

    spec = SimpleNamespace(writes=True, expert_id="")
    tmp = Path(tempfile.mkdtemp(prefix="civil-protected-"))
    try:
        site = tmp / "site-data"
        site.mkdir()
        target = site / "drawing.xlsx"

        # 1. Nothing is protected by default: no personal folder names ship with the repository.
        os.environ.pop(ENV, None)
        assert protected_roots() == []
        assert not is_protected(site)
        d = evaluate(tool="write_deliverable", spec=spec, args={"path": str(target)})
        assert d.code != CODE_PRODUCTION, d.to_dict()

        # 2. Declared protected: the policy engine refuses the write with deny_production.
        os.environ[ENV] = os.pathsep.join([str(tmp / "unrelated"), str(site)])
        assert is_protected(site) and is_protected(target)
        assert not is_protected(tmp / "site-data-2"), "a sibling with a common prefix is not inside the root"
        d = evaluate(tool="write_deliverable", spec=spec, args={"path": str(target)})
        assert not d.allow and d.code == CODE_PRODUCTION, d.to_dict()
        assert "CIVIL_PROTECTED_ROOTS" in d.reason, d.reason

        # 3. ... and the same folder is never a job root or a sandbox write root.
        os.environ["CIVIL_JOB_ROOT"] = str(site)
        assert is_forbidden_layout(site)
        assert Path(job_root()).resolve() != site.resolve()
        roots = {Path(r).resolve() for r in default_profile().allowed_write_roots}
        assert site.resolve() not in roots, roots

        # 4. A folder literally named prod is production data with or without the list.
        os.environ.pop(ENV, None)
        os.environ.pop("CIVIL_JOB_ROOT", None)
        d = evaluate(tool="write_deliverable", spec=spec, args={"path": str(tmp / "prod" / "x.md")})
        assert not d.allow and d.code == CODE_PRODUCTION, d.to_dict()
    finally:
        os.environ.pop(ENV, None)
        os.environ.pop("CIVIL_JOB_ROOT", None)
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS protected_roots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
