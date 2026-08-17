"""Require out_dir under <root>/.civil-buddy/out/ and only allowlisted names."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paths import ALLOWED_OUT_NAMES, slash

SKIP_DIR_NAMES = frozenset({"__pycache__", ".git"})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir.resolve()
    expected_prefix = slash(root / ".civil-buddy" / "out")
    out_s = slash(out_dir)
    if not (out_s == expected_prefix or out_s.startswith(expected_prefix + "/")):
        sys.stderr.write(f"out_dir not under {expected_prefix}: {out_s}\n")
        return 1
    if not out_dir.is_dir():
        sys.stderr.write(f"out_dir missing: {out_dir}\n")
        return 1

    bad: list[str] = []
    for path in out_dir.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_dir():
            continue
        if path.name not in ALLOWED_OUT_NAMES:
            bad.append(str(path))
    if bad:
        sys.stderr.write("files outside allowlist:\n")
        for item in bad:
            sys.stderr.write(f"  {item}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
