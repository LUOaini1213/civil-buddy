from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEMO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DEMO_ROOT.parent
KB_ROOT = DEMO_ROOT / "kb"
OUT_ROOT = DEMO_ROOT / "out"
SKILL_HARD_RULES = REPO_ROOT / "skills" / "civil-buddy" / "references" / "hard-rules.md"

load_dotenv()
# demo/.env wins so a stale machine-wide key will not shadow the workbench
load_dotenv(DEMO_ROOT / ".env", override=True)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
MAX_AGENT_STEPS = int(os.environ.get("CIVIL_MAX_AGENT_STEPS", "8"))
