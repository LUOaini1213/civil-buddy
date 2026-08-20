#!/usr/bin/env python3
"""Desktop launcher exists and refuses D:\\layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "civil-buddy-desktop.ps1"
BAT = ROOT / "scripts" / "civil-buddy-desktop.bat"


def main() -> int:
    assert PS1.is_file(), PS1
    assert BAT.is_file(), BAT
    text = PS1.read_text(encoding="utf-8")
    assert "127.0.0.1" in text
    assert "--app=" in text
    assert r"D:\layout" in text
    assert "WorkBuddy" in text or "腾讯" in text
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
            "-JobRoot",
            r"D:\layout",
            "-NoWindow",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    blob = ((proc.stdout or "") + (proc.stderr or "")).lower()
    assert proc.returncode != 0, blob
    assert "layout" in blob or "forbidden" in blob, blob[:800]
    print("PASS desktop_launcher")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
