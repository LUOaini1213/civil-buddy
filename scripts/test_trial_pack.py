#!/usr/bin/env python3
"""Trial pack: LICENSE, 给试用的人.md, BYO key, no DeepSeek-only install."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in lic, "LICENSE must be MIT"
    assert "LUOaini1213" in lic

    trial = (ROOT / "给试用的人.md").read_text(encoding="utf-8")
    for needle in (
        "安装",
        "CIVIL_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "CIVIL_JOB_ROOT",
        "作业根",
        "写一份",
        "不必 DeepSeek",
        "civil-workbench",
    ):
        assert needle in trial, needle
    assert "必须 DeepSeek" not in trial
    assert "D:\\layout" in trial or "D:\\layout" in trial.replace("/", "\\")

    env_ex = (ROOT / "demo" / ".env.example").read_text(encoding="utf-8")
    assert "CIVIL_API_KEY" in env_ex
    assert "OPENAI_API_KEY" in env_ex

    pkg = (ROOT / "scripts" / "package-workbench-release.ps1").read_text(encoding="utf-8")
    assert "start-workbench.bat" in pkg
    bat = ROOT / "scripts" / "start-workbench.bat"
    assert bat.is_file(), bat
    assert "civil-workbench.exe" in bat.read_text(encoding="utf-8", errors="ignore")
    print("PASS trial_pack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
