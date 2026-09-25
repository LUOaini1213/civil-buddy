"""Start the Python workbench honoring demo/.env (CIVIL_HOST / CIVIL_PORT / CIVIL_TOKEN).

    python serve.py                       # 127.0.0.1:8765
    CIVIL_HOST=0.0.0.0 python serve.py    # phones on the same LAN — refuses to start without CIVIL_TOKEN

`uvicorn app:app --host ... --port ...` still works; this wrapper only reads .env first.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402,F401  (loads .env)


def main() -> None:
    import uvicorn

    from packing_assistant.access_guard import open_bind_refusal

    host = (os.environ.get("CIVIL_HOST") or "127.0.0.1").strip()
    port = int(os.environ.get("CIVIL_PORT") or 8765)
    reason = open_bind_refusal(host)
    if reason:
        sys.exit(reason)
    uvicorn.run("app:app", host=host, port=port, reload=bool(os.environ.get("CIVIL_RELOAD")))


if __name__ == "__main__":
    main()
