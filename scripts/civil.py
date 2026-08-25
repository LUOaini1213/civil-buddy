#!/usr/bin/env python3
"""Thin wrapper: python scripts/civil.py == python -m packing_assistant.civil"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packing_assistant.civil import main

if __name__ == "__main__":
    raise SystemExit(main())
