"""Start the Python workbench honoring demo/.env (CIVIL_HOST / CIVIL_PORT / CIVIL_TOKEN).

    python serve.py                       # 127.0.0.1:8765
    CIVIL_HOST=0.0.0.0 python serve.py    # phones on the same LAN — set CIVIL_TOKEN too

`uvicorn app:app --host ... --port ...` still works; this wrapper only reads .env first.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402,F401  (loads .env)

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def main() -> None:
    import uvicorn

    host = (os.environ.get("CIVIL_HOST") or "127.0.0.1").strip()
    port = int(os.environ.get("CIVIL_PORT") or 8765)
    if host not in LOOPBACK and not (os.environ.get("CIVIL_TOKEN") or "").strip():
        print(
            f"warning: binding {host}:{port} without CIVIL_TOKEN — anyone on the network can use this "
            "workbench and its job folder. Set CIVIL_TOKEN in demo/.env or bind 127.0.0.1.",
            file=sys.stderr,
        )
    uvicorn.run("app:app", host=host, port=port, reload=bool(os.environ.get("CIVIL_RELOAD")))


if __name__ == "__main__":
    main()
