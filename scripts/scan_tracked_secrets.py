#!/usr/bin/env python3
"""Fail if git-tracked files look like secrets. Used by npm run check."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED_NAME = re.compile(
    r"(?:^|/)\.env$|(?:^|/)deepseek api\.txt$|(?:^|/)[^/]*apikey[^/]*$|\.pem$|\.p12$",
    re.I,
)
ALLOW_NAME = re.compile(r"\.env\.example$|env\.example")
PRIVATE_KEY = re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY")
KEY_ASSIGN = re.compile(
    r"(?:DEEPSEEK_API_KEY|OPENAI_API_KEY|CIVIL_API_KEY)\s*=\s*(\S+)",
    re.I,
)
PLACEHOLDER = re.compile(r"^(sk-xxx|xxx+|changeme|<[^>]+>|your[-_].*|dummy)?$", re.I)
LIVE_TOKEN = re.compile(r"\bsk-(?:proj|or|ant|live|svcacct)-[A-Za-z0-9_-]{16,}")
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".exe", ".dll")


def _tracked() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(ROOT),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    raw = proc.stdout.split(b"\0")
    out = []
    for b in raw:
        if not b:
            continue
        out.append(b.decode("utf-8", errors="replace"))
    return out


def main() -> int:
    bad: list[str] = []
    files = _tracked()
    if not files:
        print("PASS scan_tracked_secrets (not a git checkout; skipped list)")
        return 0
    for rel in files:
        name = rel.replace("\\", "/")
        if ALLOW_NAME.search(name):
            continue
        if BANNED_NAME.search(name):
            bad.append(f"name {name}")
            continue
        path = ROOT / rel
        if not path.is_file() or name.lower().endswith(SKIP_SUFFIX):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if PRIVATE_KEY.search(text) or LIVE_TOKEN.search(text):
            bad.append(f"body {name}")
            continue
        for m in KEY_ASSIGN.finditer(text):
            val = (m.group(1) or "").strip().strip('"').strip("'")
            if PLACEHOLDER.match(val) or "你的" in val or val.lower().startswith("your"):
                continue
            if val.startswith("sk-") and val not in {"sk-xxx", "sk-your-key"} and len(val) >= 20:
                bad.append(f"assign {name}")
                break
    if bad:
        print("FAIL secrets:", *bad[:20], sep="\n  ")
        return 1
    print("PASS scan_tracked_secrets files", len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
