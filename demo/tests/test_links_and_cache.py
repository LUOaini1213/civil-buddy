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
    monkeypatch.setattr(uploads, "UPLOAD_ROOT", tmp_path / "out")  # attachments live inside the session dir
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


def test_uploads_live_in_the_session_dir_and_download_by_ref(client):
    """附件和会话其它数据放在一起：<OUT_ROOT>/<sid>/uploads/；原件按 ?session=&upload=<id> 下载，不带路径。"""
    import app

    sid = "sess-up-01"
    r = client.post("/api/upload", data={"session_id": sid}, files={"file": ("投标说明.txt", "第一章 总则：本项目位于某市，工期 180 天。\n".encode("utf-8"), "text/plain")})
    assert r.status_code == 200, r.text
    item = r.json()["files"][0]
    stored = app.OUT_ROOT / sid / "uploads" / f"{item['id']}.bin"
    assert stored.is_file(), sorted(p.name for p in (app.OUT_ROOT / sid).rglob("*"))
    assert not (Path(app.__file__).parent / "data" / "uploads" / sid).exists()

    d = client.get("/api/file", params={"session": sid, "upload": item["id"]})
    assert d.status_code == 200 and d.content == "第一章 总则：本项目位于某市，工期 180 天。\n".encode("utf-8")
    assert "%E6%8A%95%E6%A0%87%E8%AF%B4%E6%98%8E.txt" in d.headers["content-disposition"]  # 投标说明.txt
    assert client.get("/api/file", params={"session": sid, "upload": "no-such-id"}).status_code == 404
    assert client.get("/api/file", params={"session": sid, "upload": "../x"}).status_code == 400
    # the session detail / attachment list still sees it
    assert [f["id"] for f in client.get("/api/attachments", params={"session_id": sid}).json()["files"]] == [item["id"]]


def test_legacy_uploads_are_adopted_into_the_session_dir(client, tmp_path, monkeypatch):
    """老布局 <demo>/data/uploads/<sid> 在启动扫描或第一次访问时搬进 <OUT_ROOT>/<sid>/uploads。"""
    import shutil

    import app
    import uploads

    legacy_root = tmp_path / "legacy"
    monkeypatch.setattr(uploads, "LEGACY_UPLOAD_ROOT", legacy_root)
    for sid in ("old-a", "old-b"):
        saved = uploads.save_upload(sid, "旧附件.md", "# 旧附件\n\n这是迁移前的一份说明，内容足够长。\n".encode("utf-8"))
        assert saved["id"]
        legacy_root.mkdir(exist_ok=True)
        shutil.move(str(app.OUT_ROOT / sid / "uploads"), str(legacy_root / sid))  # 伪造旧布局
        assert not (app.OUT_ROOT / sid / "uploads").exists() and (legacy_root / sid).is_dir()

    # first touch adopts old-a
    assert [f["name"] for f in uploads.list_uploads("old-a")] == ["旧附件.md"]
    assert (app.OUT_ROOT / "old-a" / "uploads").is_dir() and not (legacy_root / "old-a").exists()
    # startup migration adopts what is left
    assert uploads.migrate_legacy_uploads() == 1
    assert (app.OUT_ROOT / "old-b" / "uploads").is_dir() and not (legacy_root / "old-b").exists()
    assert uploads.migrate_legacy_uploads() == 0
    assert [f["name"] for f in client.get("/api/attachments", params={"session_id": "old-b"}).json()["files"]] == ["旧附件.md"]


def test_service_worker_is_served_from_the_root_and_never_cached(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["service-worker-allowed"] == "/"
    assert "/api/" in r.text and "network" in r.text.lower() or "fetch(req)" in r.text
    index = client.get("/").text
    assert 'rel="manifest"' in index
    assert "serviceWorker" in client.get("/static/app.js").text


def test_heartbeat_is_a_comment_frame_on_the_wire(client, monkeypatch):
    """0.5 s 一次的心跳在线上是 `: ping` 注释帧，不再是要解析的 JSON 事件；业务帧照旧带 id。"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    monkeypatch.setattr("app.has_key", lambda: True)

    def slow(history):
        import time
        for i in range(3):
            time.sleep(0.6)
            yield {"event": "token", "data": {"text": f"片段{i} "}}
        yield {"event": "done", "data": {"text": "片段0 片段1 片段2", "citations": []}}
    monkeypatch.setattr("app.run_plain", slow)
    with client.stream("POST", "/api/chat", json={"message": "聊聊", "session_id": "ping-sess-01"}) as r:
        raw = b"".join(r.iter_bytes()).decode("utf-8")
    assert ": ping\n\n" in raw, raw[:300]
    assert "event: heartbeat" not in raw
    assert "id: 1\nevent: session" in raw and "event: done" in raw


def test_backup_export_streams_a_file_and_import_reads_from_disk(client, monkeypatch):
    """导出：zip 写临时文件后流式发出，发完即删；导入：分块落盘再从磁盘读，内存里不再放两份 128 MB。"""
    import app

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", lambda history: iter([{"event": "token", "data": {"text": "你好呀"}}, {"event": "done", "data": {"text": "你好呀", "citations": []}}]))
    sid = "bk-sess-01"
    with client.stream("POST", "/api/chat", json={"message": "你好", "session_id": sid}) as r:
        b"".join(r.iter_bytes())
    r = client.get(f"/api/sessions/{sid}/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/zip")
    assert f'civil-task-{sid}.zip' in r.headers["content-disposition"]
    assert r.content[:2] == b"PK" and len(r.content) > 100
    assert not list(app.OUT_ROOT.glob("civil-export-*.zip")), "the temp file is gone once the response is sent"

    imported = client.post("/api/session-import", content=r.content, headers={"Content-Type": "application/zip"})
    assert imported.status_code == 200, imported.text
    new_sid = imported.json()["session_id"]
    assert new_sid.startswith("import-")
    assert (app.OUT_ROOT / new_sid / "transcript.jsonl").is_file()
    assert not list(app.OUT_ROOT.glob("civil-import-*.zip")), "the spooled upload is removed after import"
    assert client.post("/api/session-import", content=b"not a zip", headers={"Content-Type": "application/zip"}).status_code == 400
