"""The optional CAD workspace shares the workbench's capabilities and LAN gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def client(monkeypatch, tmp_path):
    import app
    import uploads
    monkeypatch.setattr(app, "OUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(uploads, "UPLOAD_ROOT", tmp_path / "out")
    monkeypatch.setenv("CIVIL_TOKEN", "cad-test-token")
    with TestClient(app.app, follow_redirects=False) as value:
        yield value


def test_cad_page_can_open_before_auth_and_revalidates(client):
    response = client.get("/cad")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert "cad.js" in response.text
    assert client.get("/static/cad.js").headers["cache-control"] == "no-cache"


def test_health_advertises_cad_without_requiring_a_token(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["capabilities"]["cad"] is True
    assert response.json()["capabilities"]["auth"] is True


def test_cad_api_uses_same_token_and_cookie_gate(client):
    assert client.get("/api/cad/capabilities").status_code == 401
    assert client.get("/api/cad/examples/building").status_code == 401
    assert client.post("/api/cad/build", json={}).status_code == 401
    assert client.post("/api/cad/export", json={}).status_code == 401
    client.cookies.set("cb_token", "wrong")
    assert client.get("/api/cad/capabilities").status_code == 401
    client.cookies.set("cb_token", "cad-test-token")
    assert client.get("/api/cad/capabilities").status_code == 200
    assert client.get("/api/cad/examples/building").status_code == 200
    assert client.get("/api/cad/capabilities", headers={"Origin": "https://other.invalid"}).status_code == 403


def test_optional_missing_dependencies_still_advertises_page(client, monkeypatch):
    import cad_api
    monkeypatch.setattr(cad_api.importlib.util, "find_spec", lambda _: None)
    client.cookies.set("cb_token", "cad-test-token")
    response = client.get("/api/cad/capabilities")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["missing_dependencies"]
    assert client.get("/api/health").json()["capabilities"]["cad"] is True
