"""T010: session.summary slots for jurisdiction / project / P0. Compress is marked, not pretended."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "demo" / "out"


def _safe(session_id: str) -> str:
    return (session_id or "default").replace("..", "_").replace("/", "_").replace("\\", "_") or "default"


def summary_path(session_id: str) -> Path:
    return _OUT / _safe(session_id) / "session.summary.json"


def save_summary(
    session_id: str,
    *,
    jurisdiction: str = "",
    project: str = "",
    p0_confirmed: bool = False,
    compressed: bool = False,
    dropped_note: str = "",
) -> Path:
    path = summary_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "jurisdiction": jurisdiction or "UNSPECIFIED",
        "project": project or "UNSPECIFIED",
        "p0_confirmed": bool(p0_confirmed),
        "compressed": bool(compressed),
        "dropped_note": dropped_note
        or ("更早对话已压缩，细节标 [A001] / UNSPECIFIED，不要假装读过。" if compressed else ""),
    }
    from packing_assistant.sandbox import guarded_write_text

    guarded_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_summary(session_id: str) -> Optional[Dict[str, Any]]:
    path = summary_path(session_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
