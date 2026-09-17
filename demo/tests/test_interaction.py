"""断流 / 取消 / 切换任务 / 上传 / 下载 语义回归（无需模型 Key）。

对应验收项：
- 断流只 detach，轮次在后台跑完并落盘；显式 cancel 才取消
- /api/sessions 每行带 running
- /api/file 带 Content-Disposition，名字取卡片显示名（清洗后）
- 上传：Starlette 英文错误翻中文；短内容按类型提示
- 项目名长度上限
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import app
    import uploads

    monkeypatch.setattr(app, "OUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(uploads, "UPLOAD_ROOT", tmp_path / "uploads")
    return TestClient(app.app)


def _slow_plain(n=12, dt=0.05):
    def runner(history):
        for i in range(n):
            time.sleep(dt)
            yield {"event": "token", "data": {"text": f"片段{i} "}}
        yield {"event": "done", "data": {"text": " ".join(f"片段{i}" for i in range(n)), "citations": []}}
    return runner


def _wait_idle(sid, timeout=10.0):
    import turn_control

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not turn_control.status(sid)["active"]:
            return True
        time.sleep(0.05)
    return False


def test_client_disconnect_detaches_and_turn_finishes(client, monkeypatch, tmp_path):
    """断流 = detach：生成器被关掉后，轮次继续跑完并落盘，记录里没有「已取消」。"""
    import app
    import chat_service
    import projects

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain())
    sid = "detach-turn-01"
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊天气", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    seen = 0
    for ev in gen:
        if ev["event"] == "token":
            seen += 1
        if seen >= 3:
            break
    gen.close()  # 浏览器断开：Starlette 会 close() 生成器
    assert client.get(f"/api/sessions/{sid}").json()["turn_state"]["active"] is True
    assert _wait_idle(sid), "轮次没有在后台跑完"
    detail = client.get(f"/api/sessions/{sid}").json()
    last = detail["transcript"][-1]["text"]
    assert "片段11" in last, "断流后没有把完整回答落盘"
    assert "取消" not in last and "中断" not in last
    assert detail["turn_state"]["state"] == "done"
    assert sid not in chat_service._ACTIVE


def test_explicit_cancel_still_cancels(client, monkeypatch):
    import app
    import chat_service
    import turn_control

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=40))
    sid = "cancel-turn-01"
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊天气", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    done = None
    seen = 0
    for ev in gen:
        if ev["event"] == "token":
            seen += 1
            if seen == 3:
                assert turn_control.cancel(sid)["cancel_requested"] is True
        if ev["event"] == "done":
            done = ev["data"]
    assert done and done["cancelled"] is True and done["state"] == "cancelled"
    assert "已取消" in client.get(f"/api/sessions/{sid}").json()["transcript"][-1]["text"]


def test_sessions_list_reports_running(client, monkeypatch):
    import app
    import chat_service

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=20))
    sid = "running-flag-01"
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    next(gen); next(gen)
    rows = {r["session_id"]: r for r in client.get("/api/sessions").json()["sessions"]}
    assert rows[sid]["running"] is True
    gen.close()
    assert _wait_idle(sid)
    rows = {r["session_id"]: r for r in client.get("/api/sessions").json()["sessions"]}
    assert rows[sid]["running"] is False


def test_file_download_is_named_server_side(client, tmp_path):
    import app

    d = app.OUT_ROOT / "dl-01" / "runs" / "r1"
    d.mkdir(parents=True)
    f = d / "3-pm-daily__log.docx"
    f.write_bytes(b"PK\x03\x04docx")
    r = client.get("/api/file", params={"path": str(f)})
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="3-pm-daily__log.docx"'
    # 卡片显示名优先，但只接受同扩展名的纯文件名
    r = client.get("/api/file", params={"path": str(f), "name": "pm-daily__log.docx"})
    assert 'filename="pm-daily__log.docx"' in r.headers["content-disposition"]
    r = client.get("/api/file", params={"path": str(f), "name": "../../evil.docx"})
    assert 'filename="evil.docx"' in r.headers["content-disposition"]
    r = client.get("/api/file", params={"path": str(f), "name": "x.exe"})
    assert 'filename="3-pm-daily__log.docx"' in r.headers["content-disposition"]
    zh = d / "计划骨架.md"
    zh.write_text("# x\n", encoding="utf-8")
    r = client.get("/api/file", params={"path": str(zh)})
    assert "filename*=utf-8''%E8%AE%A1%E5%88%92%E9%AA%A8%E6%9E%B6.md" in r.headers["content-disposition"]
    assert client.get("/api/file", params={"path": "/etc/passwd"}).status_code == 403


def test_upload_errors_are_chinese_and_kind_aware(client):
    sid = "upload-msg-01"
    files = [("file", (f"f{i}.txt", f"row {i} content here".encode())) for i in range(13)]
    r = client.post("/api/upload", data={"session_id": sid}, files=files)
    assert r.status_code == 400
    assert r.json()["detail"] == "一次最多上传 12 个附件"
    r = client.post("/api/upload", data={"session_id": sid}, files={"file": ("short.md", b"# ok")})
    assert r.status_code == 400
    assert "OCR" not in r.json()["detail"] and "不足 8 个字符" in r.json()["detail"]
    r = client.post("/api/upload", data={"session_id": sid}, files={"file": ("ok.txt", b"enough content to pass the gate")})
    assert r.status_code == 200 and r.json()["files"][0]["name"] == "ok.txt"


def test_project_name_limit(client):
    assert client.post("/api/projects", json={"name": "工" * 500}).status_code == 400
    r = client.post("/api/projects", json={"name": "  正常  名称 "})
    assert r.status_code == 200 and r.json()["project"]["name"] == "正常 名称"
    pid = r.json()["project"]["id"]
    assert client.patch(f"/api/projects/{pid}", json={"name": "工" * 61}).status_code == 400


def test_deliverables_grouped_by_run_and_zip(client, monkeypatch):
    """交付物按轮分组（done 事件与会话详情一致），一轮多文件可打包下载。"""
    import app
    from chat_service import read_runs
    from packing_assistant import expert_turn
    from packing_assistant.runtime import agent_loop

    # 引擎把稿写到 demo/out；夹具把 OUT_ROOT 指到临时目录，两边要指向同一根，
    # _deliverables 才会把文件快照到会话目录下。
    monkeypatch.setattr(agent_loop, "_OUT", app.OUT_ROOT)
    monkeypatch.setattr(expert_turn, "_OUT", app.OUT_ROOT)
    sid = "deliv-zip-01"
    r = client.post("/api/chat", json={"session_id": sid, "message": "帮我写一份项目日报，今天完成了基坑支护第三层锚索张拉",
                                       "expert_ids": ["pm-daily"]})
    assert r.status_code == 200
    done = [l for l in r.text.splitlines() if l.startswith("data: ")][-1]
    import json
    data = json.loads(done[6:])
    runs = data["deliverable_runs"]
    assert len(runs) == 1 and runs[0]["expert_id"] == "pm-daily" and runs[0]["export_errors"] == []
    names = sorted(f["name"] for f in runs[0]["deliverables"])
    assert names == ["pm-daily__log.docx", "pm-daily__log.md", "pm-daily__log.xlsx"]
    detail = client.get(f"/api/sessions/{sid}").json()
    assert [x["run_id"] for x in detail["deliverable_runs"]] == [runs[0]["run_id"]]
    assert read_runs(app.OUT_ROOT, sid)[-1]["export_errors"] == []
    import io
    import zipfile
    z = client.get("/api/deliverables.zip", params={"session_id": sid, "run_id": runs[0]["run_id"]})
    assert z.status_code == 200 and z.headers["content-disposition"].startswith("attachment;")
    assert sorted(zipfile.ZipFile(io.BytesIO(z.content)).namelist()) == names
    z = client.get("/api/deliverables.zip", params={"session_id": sid})
    assert all(n.startswith(runs[0]["run_id"][:8] + "/") for n in zipfile.ZipFile(io.BytesIO(z.content)).namelist())
    assert client.get("/api/deliverables.zip", params={"session_id": sid, "run_id": "nope"}).status_code == 404
    assert client.get("/api/deliverables.zip", params={"session_id": "../x"}).status_code == 400
    assert client.get("/api/deliverables.zip", params={"session_id": sid, "run_id": "../../x"}).status_code == 400
