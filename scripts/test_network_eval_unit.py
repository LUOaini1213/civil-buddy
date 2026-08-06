#!/usr/bin/env python3
"""Unit/integration check for overnight network_eval recipe (live HTTP)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    # Import shipped recipe
    from packing_assistant.tools import table_mapper as tm  # ensure package path works

    assert hasattr(tm, "parse_table_file")
    # load loop module
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "autonomy_12h_loop", ROOT / "scripts" / "autonomy_12h_loop.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    detail = mod.r_network_eval()
    assert "network_eval" in detail
    path = ROOT / "output" / "autonomy" / "network_eval_latest.json"
    assert path.exists(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    # at least one live 200
    ok = (
        data.get("deepseek_models_status") == 200
        or data.get("web_status") == 200
        or data.get("github_search_status") == 200
    )
    assert ok, data
    print("ALL_PASS network_eval_unit", detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
