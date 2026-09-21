"""Deterministic domain surfaces behind the Rust host; no generic chat runtime."""
from __future__ import annotations

from fastapi import FastAPI
from .cad_api import router as cad_router
from .engineering_api import router as engineering_router

app = FastAPI(title="Civil Buddy domain workers", docs_url=None, redoc_url=None)
app.include_router(cad_router)
app.include_router(engineering_router)

try:
    from .asr_service import router as asr_router
except ImportError:
    asr_router = None
if asr_router is not None:
    app.include_router(asr_router)


@app.get("/health")
def health():
    return {"ok": True, "service": "deterministic-domains", "chat_runtime": False,
            "asr_routes": asr_router is not None}
