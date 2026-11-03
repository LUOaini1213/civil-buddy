#!/usr/bin/env python3
"""No machine-specific home folders in tracked text files.

A tracked file must not name a real user's home folder (Windows ``X:\\Users\\<name>``, Linux ``/home/<name>``,
macOS ``/Users/<name>``). Docs use placeholders (``path\\to\\civil-buddy``, ``<repo>``, ``%USERPROFILE%``,
``C:\\Users\\你\\...``), scripts resolve paths from ``__file__`` or ``Path.home()``. The placeholder user names
below are the only ones allowed; add to ALLOWED only for an obviously fictitious name.

    python scripts/test_no_local_paths.py              # scan git ls-files; exit 1 on a hit
    python scripts/test_no_local_paths.py --self-test  # prove the scanner catches what it should
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 4 * 1024 * 1024
BINARY_EXT = {
    ".pdf", ".xlsx", ".xlsm", ".xls", ".docx", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm",
    ".ico", ".ttf", ".woff", ".woff2", ".db", ".sqlite", ".onnx", ".wav", ".mp3",
}
# Placeholder / test-fixture user names (compared case-insensitively).
ALLOWED = {"nobody", "x", "你", "...", "$env", "o'brien", "public", "default", "me", "you", "username", "user"}

WIN_HOME = re.compile(r"(?i)\b[a-z]:(?:\\\\|\\|/)+users(?:\\\\|\\|/)+([^\\/\s\"`<>|*?:]+)")
NIX_HOME = re.compile(r"(?<![\w.~-])/(?:home|Users)/([A-Za-z0-9._-]+)/")


def hits_in(text: str) -> list[str]:
    out = []
    for rx in (WIN_HOME, NIX_HOME):
        for m in rx.finditer(text):
            raw = m.group(1)
            if raw.lower() not in ALLOWED and raw.rstrip("'.,;)]}").lower() not in ALLOWED:
                out.append(m.group(0))
    return out


def tracked_files() -> list[str]:
    res = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    return [p for p in res.stdout.decode("utf-8").split("\0") if p]


def scan() -> list[str]:
    problems = []
    for rel in tracked_files():
        path = ROOT / rel
        if path.suffix.lower() in BINARY_EXT or not path.is_file() or path.stat().st_size > MAX_BYTES:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for h in hits_in(line):
                problems.append(f"{rel}:{lineno}: {h}")
    return problems


def self_test() -> int:
    must_flag = [
        r"cd C:\Users\alice\civil-buddy",
        r'"cwd": "C:\\Users\\bob\\civil-buddy"',
        "SUB = Path(r'C:/Users/carol/out')",
        "default=r\"D:\\Users\\wenjie.luo\\Downloads\\x.xlsx\"",
        "see /home/dave/civil-buddy/README.md",
        "open /Users/erin/Desktop/x.md",
    ]
    must_pass = [
        r"cd path\to\civil-buddy",
        r"C:\Users\nobody\Desktop\missing.xlsx",
        r"C:\Users\你\Documents\某工地",
        r"C:\Users\$env:USERNAME\tools",
        "https://example.gov.sg/home/civil-defence-shelter/",
        "%USERPROFILE%\\.grok\\skills",
    ]
    bad = [s for s in must_flag if not hits_in(s)] + [s for s in must_pass if hits_in(s)]
    for s in bad:
        print("SELF-TEST WRONG:", s)
    print("self-test", "FAIL" if bad else "PASS", f"({len(must_flag)} flagged, {len(must_pass)} allowed)")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if self_test():
        return 1
    problems = scan()
    for p in problems:
        print("LOCAL PATH:", p)
    print(f"[no-local-paths] {'FAIL' if problems else 'PASS'}: {len(problems)} machine-specific home path(s) in tracked files")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
