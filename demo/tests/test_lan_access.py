"""Opening the workbench to a phone on the LAN (CIVIL_HOST=0.0.0.0) needs a door:

- CIVIL_TOKEN turns every /api/* route into 401 unless the token comes as Bearer, ?token= or
  the cb_token cookie; "/" , /static and /api/health stay open so the page can load and ask.
- /api/health.capabilities.auth tells the page to ask for the token before its first call.
- Model timeouts are split by phase and CIVIL_LLM_READ_TIMEOUT sets the slow one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import app
    import uploads

    monkeypatch.setattr(app, "OUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(uploads, "UPLOAD_ROOT", tmp_path / "uploads")
    return TestClient(app.app)


def test_open_by_default(client, monkeypatch):
    monkeypatch.delenv("CIVIL_TOKEN", raising=False)
    assert client.get("/api/catalog").status_code == 200
    assert client.get("/api/health").json()["capabilities"]["auth"] is False


def test_token_guards_api_but_not_the_page(client, monkeypatch):
    monkeypatch.setenv("CIVIL_TOKEN", "s3cret")
    assert client.get("/api/health").json()["capabilities"]["auth"] is True
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200

    denied = client.get("/api/catalog")
    assert denied.status_code == 401
    assert "CIVIL_TOKEN" in denied.json()["detail"]
    assert client.get("/api/catalog", headers={"Authorization": "Bearer wrong"}).status_code == 401

    assert client.get("/api/catalog", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/api/catalog", params={"token": "s3cret"}).status_code == 200
    assert client.get("/api/catalog", cookies={"cb_token": "s3cret"}).status_code == 200
    # a POST with the cookie (what the page and its uploads send) passes the same door
    assert client.post("/api/task-route", json={"message": "你好"}, cookies={"cb_token": "s3cret"}).status_code != 401


def test_read_timeout_comes_from_env(monkeypatch):
    import llm

    monkeypatch.delenv("CIVIL_LLM_READ_TIMEOUT", raising=False)
    monkeypatch.delenv("CIVIL_LLM_CONNECT_TIMEOUT", raising=False)
    t = llm.default_timeout()
    assert (t.connect, t.read) == (15.0, 180.0)

    monkeypatch.setenv("CIVIL_LLM_READ_TIMEOUT", "600")
    monkeypatch.setenv("CIVIL_LLM_CONNECT_TIMEOUT", "5")
    t = llm.default_timeout()
    assert (t.connect, t.read) == (5.0, 600.0)

    monkeypatch.setenv("CIVIL_LLM_READ_TIMEOUT", "not-a-number")
    assert llm.default_timeout().read == 180.0
    monkeypatch.setenv("CIVIL_LLM_READ_TIMEOUT", "-3")
    assert llm.default_timeout().read == 180.0

    with llm.ModelConnection() as conn:
        assert conn.client.timeout.read == 180.0
