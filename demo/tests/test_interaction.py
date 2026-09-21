"""断流 / 取消 / 切换任务 / 上传 / 下载 语义回归（无需模型 Key）。

对应验收项：
- 断流只 detach，轮次在后台跑完并落盘；显式 cancel 才取消
- /api/sessions 每行带 running
- /api/file 带 Content-Disposition，名字取卡片显示名（清洗后）
- 上传：Starlette 英文错误翻中文；短内容按类型提示
- 项目名长度上限
"""

from __future__ import annotations

import json
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
    monkeypatch.setattr(uploads, "UPLOAD_ROOT", tmp_path / "out")  # attachments live inside the session dir
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


def test_zip_member_names_are_rebuilt_not_copied_from_a_run_record(client):
    """运行记录是数据（备份导入也会写它）：伪造的记录不能左右压缩包里的路径，也拿不到 /api/file 不给的文件。"""
    import io
    import json
    import zipfile

    import app

    sid = "zip-crafted-01"
    real = app.OUT_ROOT / sid / "drafts" / "a1b2-daily.md"
    real.parent.mkdir(parents=True)
    real.write_text("# 日报\n今天完成了基坑支护第三层锚索张拉。", encoding="utf-8")
    secret = app.OUT_ROOT / sid / ".env"
    secret.write_text("MARKER=not-for-download", encoding="utf-8")
    record = {"schema": "civil.workbench.run.v1", "run_id": "../../zz", "mtime": "2026-09-20T00:00:00+00:00",
              "deliverables": [{"name": "../../evil.md", "path": str(real)},
                               {"name": "evil.md", "path": str(real)},
                               {"name": "C:\\Windows\\x.exe", "path": str(real)},
                               {"name": "env.md", "path": str(secret)}]}
    run_dir = app.OUT_ROOT / sid / "runs" / "crafted"
    run_dir.mkdir(parents=True)
    (run_dir / "workbench.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    assert client.get("/api/file", params={"path": str(secret)}).status_code == 403
    z = client.get("/api/deliverables.zip", params={"session_id": sid})
    assert z.status_code == 200
    bundle = zipfile.ZipFile(io.BytesIO(z.content))
    # 目录名只留 run_id 里的安全字符；显示名只留 basename；扩展名对不上就用真实文件名；重名加来源前缀
    assert sorted(bundle.namelist()) == ["zz/a1b2-daily.md", "zz/evil-a1b2.md", "zz/evil.md"]
    assert all(b"not-for-download" not in bundle.read(n) for n in bundle.namelist())


def test_live_progress_is_visible_while_detached(client, monkeypatch):
    """断流后回来的页面不该盯着空气泡：GET /api/sessions/{sid}/live 给出已产出的正文和最近状态。"""
    import app
    import chat_service

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=14, dt=0.05))
    sid = "live-turn-01"
    assert client.get("/api/health").json()["capabilities"]["live_progress"] is True
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊天气", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    seen = 0
    for ev in gen:
        if ev["event"] == "token":
            seen += 1
        if seen >= 3:
            break
    gen.close()  # 锁屏：流断了，轮次还在跑
    live = client.get(f"/api/sessions/{sid}/live").json()
    assert live["active"] is True and live["done"] is False
    assert "片段0" in live["text"] and live["seq"] >= 3, live
    assert live["status"], "最近一条状态行也要带上"
    first_seq = live["seq"]
    time.sleep(0.2)
    later = client.get(f"/api/sessions/{sid}/live").json()
    assert later["seq"] > first_seq and len(later["text"]) > len(live["text"]), "旁观期间正文没有继续增长"
    assert _wait_idle(sid), "轮次没有在后台跑完"
    final = client.get(f"/api/sessions/{sid}/live").json()
    assert final["done"] is True and final["active"] is False and "片段13" in final["text"]
    assert client.get("/api/sessions/bad%20id/live").status_code == 400


def _read_sse(client, url, headers=None):
    """Collect (id, event, data) triples from an SSE response until it closes."""
    out, cur_id, cur_ev, cur_data = [], None, "message", []
    with client.stream("GET", url, headers=headers or {}) as r:
        assert r.status_code == 200, r.status_code
        for raw in r.iter_lines():
            line = raw if isinstance(raw, str) else raw.decode("utf-8")
            if line == "":
                if cur_data:
                    out.append((cur_id, cur_ev, json.loads("\n".join(cur_data))))
                cur_id, cur_ev, cur_data = None, "message", []
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "id":
                cur_id = int(value)
            elif field == "event":
                cur_ev = value
            elif field == "data":
                cur_data.append(value)
    return out


def test_turn_events_are_numbered_logged_and_resumable(client, monkeypatch):
    """/api/chat 的每一帧带 id；断流后 GET /api/sessions/{sid}/events?after=N 把没看到的补回来并跟到 done；
    日志落盘 events/<turn>.jsonl，进程重启（清内存表）后照样能回放。"""
    import app
    import chat_service

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=16, dt=0.04))
    sid = "resume-turn-01"
    assert client.get("/api/health").json()["capabilities"]["event_log"] is True
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊天气", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    seen, last_seq = [], 0
    for ev in gen:
        if ev["event"] == "heartbeat":
            assert "seq" not in ev
            continue
        assert ev["seq"] == last_seq + 1, "每个业务事件递增编号"
        last_seq = ev["seq"]
        seen.append(ev)
        if sum(1 for e in seen if e["event"] == "token") >= 3:
            break
    gen.close()  # 锁屏：流断了
    assert [e["event"] for e in seen[:2]] == ["session", "context"] and seen[1]["data"]["turn_id"] == turn["turn_id"]
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["turn_state"]["active"] is True and detail["turn_state"]["turn_id"] == turn["turn_id"]

    # 续流：从 last_seq 之后开始，一直跟到 done
    resumed = _read_sse(client, f"/api/sessions/{sid}/events?after={last_seq}")
    ids = [i for i, _, _ in resumed]
    assert ids and ids[0] == last_seq + 1 and ids == sorted(ids) and len(set(ids)) == len(ids)
    assert resumed[-1][1] == "done" and "片段15" in resumed[-1][2]["text"]
    assert all(ev != "heartbeat" for _, ev, _ in resumed)
    assert _wait_idle(sid)

    # Last-Event-ID 头等价于 ?after=
    by_header = _read_sse(client, f"/api/sessions/{sid}/events", headers={"Last-Event-ID": str(last_seq)})
    assert [i for i, _, _ in by_header] == ids

    # 全量回放 == 断流前看到的 + 续上的
    full = _read_sse(client, f"/api/sessions/{sid}/events?after=0")
    assert [i for i, _, _ in full] == list(range(1, ids[-1] + 1))
    assert [e for _, e, _ in full][:len(seen)] == [e["event"] for e in seen]

    # 日志在盘上，重启（内存表清空）后回放一致
    log = app.OUT_ROOT / sid / "events" / f"{turn['turn_id']}.jsonl"
    assert log.is_file() and (app.OUT_ROOT / sid / "events" / "latest").read_text(encoding="utf-8") == turn["turn_id"]
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [r["seq"] for r in rows] == list(range(1, ids[-1] + 1)) and rows[-1]["event"] == "done"
    chat_service._LIVE.clear()
    from_disk = _read_sse(client, f"/api/sessions/{sid}/events?after={last_seq}")
    assert [(i, e) for i, e, _ in from_disk] == [(i, e) for i, e, _ in resumed]
    assert from_disk[-1][2]["text"] == resumed[-1][2]["text"]

    # 没有记录的会话 → 404；非法 id → 400
    assert client.get("/api/sessions/never-ran-01/events").status_code == 404
    assert client.get("/api/sessions/bad%20id/events").status_code == 400


def test_turn_state_is_on_disk_and_a_restart_marks_leftovers_stale(client, monkeypatch):
    """运行态落盘：跑的时候 running（pid、心跳、seq），结束后 done；
    上一个进程留下的 running 在启动扫描时判 stale，列表和详情都不再说它在跑（也不说 idle）。"""
    import app
    import chat_service

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=10, dt=0.04))
    sid = "state-turn-01"
    lease = chat_service.SessionLease(sid)
    turn = chat_service.prepare_turn(app.OUT_ROOT, {"session_id": sid, "message": "聊聊天气", "expert_ids": []})
    gen = chat_service.stream_turn(app.OUT_ROOT, turn, key_available=True, plain_runner=app.run_plain, lease=lease)
    for ev in gen:
        if ev["event"] == "token":
            break
    state_path = app.OUT_ROOT / sid / "events" / f"{turn['turn_id']}.state.json"
    row = json.loads(state_path.read_text(encoding="utf-8"))
    assert row["state"] == "running" and row["pid"] == __import__("os").getpid() and row["heartbeat_at"]
    assert client.get("/api/sessions/" + sid).json()["turn_state"]["state"] == "running"
    gen.close()
    assert _wait_idle(sid)
    row = json.loads(state_path.read_text(encoding="utf-8"))
    assert row["state"] == "done" and row["finished_at"] and row["seq"] >= 10
    detail = client.get("/api/sessions/" + sid).json()
    assert detail["turn_state"]["state"] == "done" and detail["turn_state"]["turn_id"] == turn["turn_id"]

    # 上一个进程留下的 running：启动扫描判 stale
    ghost = "state-ghost-01"
    folder = app.OUT_ROOT / ghost / "events"
    folder.mkdir(parents=True)
    (folder / "latest").write_text("deadbeef0001", encoding="utf-8")
    (folder / "deadbeef0001.jsonl").write_text(
        json.dumps({"seq": 1, "event": "token", "data": {"text": "写到一半"}}, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "deadbeef0001.state.json").write_text(json.dumps({
        "turn_id": "deadbeef0001", "session_id": ghost, "state": "running", "pid": 999999,
        "started_at": "2026-09-21T00:00:00+00:00", "heartbeat_at": "2026-09-21T00:00:05+00:00",
        "finished_at": "", "seq": 1}), encoding="utf-8")
    chat_service._LIVE.clear()
    marked = chat_service.sweep_stale(app.OUT_ROOT)
    assert [m["session_id"] for m in marked] == [ghost]
    row = json.loads((folder / "deadbeef0001.state.json").read_text(encoding="utf-8"))
    assert row["state"] == "stale" and row["finished_at"]
    assert chat_service.sweep_stale(app.OUT_ROOT) == [], "第二次扫描没有东西可标"
    st = client.get("/api/sessions/" + ghost).json()["turn_state"]
    assert st["active"] is False and st["state"] == "stale" and st["turn_id"] == "deadbeef0001" and st["seq"] == 1
    # 半截正文还能回放
    assert [e for _, e, _ in _read_sse(client, f"/api/sessions/{ghost}/events?after=0")] == ["token"]

    # 没扫描、直接读到一个不在内存里的 running：读的时候顺手判 stale
    lazy = "state-ghost-02"
    folder = app.OUT_ROOT / lazy / "events"
    folder.mkdir(parents=True)
    (folder / "latest").write_text("deadbeef0002", encoding="utf-8")
    (folder / "deadbeef0002.state.json").write_text(json.dumps({
        "turn_id": "deadbeef0002", "session_id": lazy, "state": "running", "pid": 999999,
        "started_at": "", "heartbeat_at": "", "finished_at": "", "seq": 0}), encoding="utf-8")
    assert chat_service.turn_status(app.OUT_ROOT, lazy)["state"] == "stale"
    assert json.loads((folder / "deadbeef0002.state.json").read_text(encoding="utf-8"))["state"] == "stale"


def test_background_turn_is_just_a_session_with_no_reader(client, monkeypatch):
    """并行任务 = POST /api/chat background:true：202 立即返回，会话在列表里是运行中，
    事件日志照记，跑完能回放到 done；同一会话跑着的时候再发一条是 409。"""
    import app
    import chat_service

    monkeypatch.setattr("app.has_key", lambda: True)
    monkeypatch.setattr("app.run_plain", _slow_plain(n=12, dt=0.04))
    assert client.get("/api/health").json()["capabilities"]["background_turns"] is True
    r = client.post("/api/chat", json={"message": "并行算一下工期", "background": True, "session_id": "bg-turn-01"})
    assert r.status_code == 202, r.text
    started = r.json()
    assert started["background"] is True and started["session_id"] == "bg-turn-01" and started["turn_id"]
    assert started["state"] == "running"

    detail = client.get("/api/sessions/bg-turn-01").json()
    assert detail["turn_state"]["active"] is True and detail["turn_state"]["turn_id"] == started["turn_id"]
    rows = {s["session_id"]: s for s in client.get("/api/sessions?limit=100").json()["sessions"]}
    assert rows["bg-turn-01"]["running"] is True, "并行会话要在列表里显示运行中"
    busy = client.post("/api/chat", json={"message": "再来一条", "session_id": "bg-turn-01"})
    assert busy.status_code == 409

    assert _wait_idle("bg-turn-01"), "并行轮次没有在后台跑完"
    events = _read_sse(client, "/api/sessions/bg-turn-01/events?after=0")
    assert events[-1][1] == "done" and "片段11" in events[-1][2]["text"]
    detail = client.get("/api/sessions/bg-turn-01").json()
    assert detail["turn_state"]["state"] == "done" and "片段11" in detail["transcript"][-1]["text"]
    assert "bg-turn-01" not in chat_service._ACTIVE
    # the workbench no longer has a separate thread API
    assert client.get("/api/threads").status_code == 404
