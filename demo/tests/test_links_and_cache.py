"""Download links without server paths, and static files a phone cannot cache stale.

- GET /api/file?session=&run=&file=&name= resolves inside <OUT_ROOT>/<sid>/deliverables/<run>;
  the old ?path= form still works for the Rust workbench and old cards.
- GET / stamps every /static/*.js|css link with the file's mtime and says no-cache; /static
  answers say no-cache too, so a deploy is picked up on the next load (304 when unchanged).
"""

from __future__ import annotations

import re
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


def _deliverable(root: Path, sid: str, run: str, stored: str, text: str = "# 方案\n") -> Path:
    target = root / sid / "deliverables" / run / stored
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_file_by_session_run_and_name(client):
    import app

    sid, run = "sess-file-01", "a1b2c3d4e5f6"
    target = _deliverable(app.OUT_ROOT, sid, run, "1-施工方案.md")
    assert client.get("/api/health").json()["capabilities"]["file_ref"] is True

    r = client.get("/api/file", params={"session": sid, "run": run, "file": "1-施工方案.md", "name": "施工方案.md"})
    assert r.status_code == 200, r.text
    assert r.text.startswith("# 方案")
    assert "attachment" in r.headers["content-disposition"]
    assert "%E6%96%BD%E5%B7%A5%E6%96%B9%E6%A1%88.md" in r.headers["content-disposition"]  # 施工方案.md, RFC 5987

    # the old absolute-path form still works (Rust workbench, old cards)
    assert client.get("/api/file", params={"path": str(target)}).status_code == 200

    # nothing outside that one folder
    assert client.get("/api/file", params={"session": sid, "run": run, "file": "../../../etc/passwd"}).status_code == 400
    assert client.get("/api/file", params={"session": sid, "run": run, "file": "..%2F..%2Fx"}).status_code in (400, 404)
    assert client.get("/api/file", params={"session": sid, "run": "no-such-run", "file": "1-施工方案.md"}).status_code == 404
    assert client.get("/api/file", params={"session": "bad id!", "run": run, "file": "1-施工方案.md"}).status_code == 400
    assert client.get("/api/file", params={"session": sid, "run": "../x", "file": "1-施工方案.md"}).status_code == 400
    assert client.get("/api/file").status_code == 400


def test_index_stamps_static_links_and_static_revalidates(client):
    import app

    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
    stamps = dict(re.findall(r'/static/([^"\'?\s]+\.(?:js|css))\?v=([0-9a-f]+)', r.text))
    assert "app.js" in stamps and "styles.css" in stamps, stamps
    expected = f"{(app.STATIC / 'app.js').stat().st_mtime_ns // 1_000_000:x}"
    assert stamps["app.js"] == expected
    assert "?v=context1" not in r.text  # the hand-written tag was replaced, not doubled

    s = client.get("/static/app.js")
    assert s.status_code == 200
    assert s.headers["cache-control"] == "no-cache"
    assert "etag" in s.headers or "last-modified" in s.headers
