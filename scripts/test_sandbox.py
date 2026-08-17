#!/usr/bin/env python3
"""Drive shipped sandbox policy: allow/deny write, secret, generic spawn."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packing_assistant.sandbox import (
        SandboxProfile,
        check_open,
        check_write,
        guarded_open_read,
        guarded_write_text,
        request_spawn,
    )

    allowed = ROOT / "output" / "sandbox-test"
    allowed.mkdir(parents=True, exist_ok=True)
    profile = SandboxProfile(allowed_write_roots=[allowed])

    outside = ROOT / "docs" / "sandbox-should-not-write.txt"
    d_out = check_write(outside, profile=profile)
    assert d_out.allowed is False, d_out
    o_out = check_open(outside, profile=profile)
    assert o_out.allowed is False, o_out

    inside = allowed / "ok.txt"
    guarded_write_text(inside, "ok", profile=profile)
    assert inside.read_text(encoding="utf-8") == "ok"
    assert check_write(inside, profile=profile).allowed is True
    assert guarded_open_read(inside, profile=profile) == "ok"

    envp = allowed / ".env"
    assert check_write(envp, profile=profile).allowed is False
    assert check_open(envp, profile=profile).allowed is False
    keyp = allowed / "api_key.txt"
    assert check_write(keyp, profile=profile).allowed is False
    secp = allowed / "secret.json"
    assert check_write(secp, profile=profile).allowed is False

    gen = request_spawn(["cmd", "/c", "dir"], kind="generic")
    assert gen.allowed is False, gen
    assert "generic spawn" in gen.reason
    sh = request_spawn(["powershell", "-Command", "Get-ChildItem"])
    assert sh.allowed is False, sh

    # shipped write site
    from packing_assistant.run_artifacts import _write_json

    artifact = ROOT / "output" / "runs" / "sandbox-probe" / "probe.json"
    _write_json(artifact, {"ok": True})
    assert artifact.is_file()

    print(
        "PASS sandbox",
        f"outside={d_out.reason!r}",
        f"inside={inside.name}",
        f"env_denied={check_write(envp, profile=profile).reason!r}",
        f"spawn={gen.reason!r}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
