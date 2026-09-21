#!/usr/bin/env python3
"""Offline workbench journeys through the real FastAPI chat and restore routes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import csv
import html
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from fastapi.testclient import TestClient
import app as workbench
import chat_service
import store
import uploads
from packing_assistant import expert_turn, llm
from packing_assistant.runtime import agent_loop, memory, session_handoff, session_packing


def sse_events(response) -> list[dict]:
    events = []
    kind = ""
    for line in response.text.splitlines():
        if line.startswith("event: "):
            kind = line[7:]
        elif line.startswith("data: "):
            events.append({"event": kind, "data": json.loads(line[6:])})
    return events


def meeting_table_files() -> dict[str, bytes]:
    import openpyxl

    rows = [["会议名称", "场地", "议程", "与会人员"],
            ["专项协调会", "东楼301", "接口核对 <10 | &lt;", "张测试"],
            ["另场讨论会", "", "待补资料", "李测试"]]
    csv_buffer = StringIO()
    csv.writer(csv_buffer).writerows(rows)
    workbook = openpyxl.Workbook()
    for row in rows:
        workbook.active.append(row)
    xlsx_buffer = BytesIO()
    workbook.save(xlsx_buffer)
    workbook.close()
    table = "<w:tbl>" + "".join("<w:tr>" + "".join(
        "<w:tc><w:p><w:r><w:t>" + html.escape(cell) + "</w:t></w:r></w:p></w:tc>" for cell in row
    ) + "</w:tr>" for row in rows) + "</w:tbl>"
    docx_buffer = BytesIO()
    with ZipFile(docx_buffer, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + table + '</w:body></w:document>')
    return {"csv": csv_buffer.getvalue().encode("utf-8"), "xlsx": xlsx_buffer.getvalue(), "docx": docx_buffer.getvalue()}


class WorkbenchFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        output = ROOT / "output"
        output.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="test-workbench-flow-", dir=output)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "PYTHON_DOTENV_DISABLED": "1", "CIVIL_JOB_ROOT": "",
            "CIVIL_SANDBOX": "workspace-write", "CIVIL_APPROVAL": "on-request",
        }))
        for module, attribute, value in (
            (workbench, "OUT_ROOT", self.root), (agent_loop, "_OUT", self.root),
            (memory, "_OUT", self.root), (expert_turn, "_OUT", self.root),
            (session_handoff, "_DIR", self.root), (session_packing, "_DIR", self.root),
            (uploads, "UPLOAD_ROOT", self.root),
            (store, "DATA", self.root / "catalog.json"), (chat_service, "_ACTIVE", set()),
            (llm, "_RUNTIME_LLM", {"api_key": "", "base_url": "http://127.0.0.1:1", "model": "offline-test"}),
        ):
            self.stack.enter_context(patch.object(module, attribute, value))
        self.no_model = self.stack.enter_context(patch.object(
            llm, "chat", side_effect=AssertionError("offline flow must not call a model")
        ))
        self.client = self.stack.enter_context(TestClient(workbench.app))
        self.sid = "flow-" + uuid4().hex[:16]

    def post(self, message: str, **payload) -> tuple[dict, list[dict]]:
        response = self.client.post("/api/chat", json={
            "message": message, "session_id": self.sid, **payload,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("text/event-stream", response.headers["content-type"])
        events = sse_events(response)
        errors = [event for event in events if event["event"] == "error"]
        self.assertFalse(errors, errors)
        completed = [event["data"] for event in events if event["event"] == "done"]
        self.assertEqual(len(completed), 1, events)
        self.assertTrue(completed[0]["submit_blocked"])
        return completed[0], events

    def draft(self, message: str = "写一份项目日报模板，缺失内容保持待填") -> dict:
        done, _ = self.post(message, expert_ids=["pm-daily"])
        self.assertTrue(done["wrote"], done)
        self.assertTrue(done["deliverables"], done)
        return done

    def test_hello_without_key_restores_conversation(self) -> None:
        health = self.client.get("/api/health").json()
        self.assertFalse(health["has_key"])
        self.assertFalse(health["job"]["granted"])
        done, events = self.post("你好")
        self.assertEqual(done["intent"], "chat")
        self.assertIn("Civil Buddy", done["text"])
        self.assertFalse(done["wrote"])
        self.assertEqual(done["deliverables"], [])
        self.assertEqual(next(event["data"]["session_id"] for event in events if event["event"] == "session"), self.sid)
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual([turn["role"] for turn in restored["transcript"]], ["user", "assistant"])
        self.assertEqual(restored["transcript"][-1]["text"], done["text"])
        self.assertEqual(restored["deliverables"], [])
        self.no_model.assert_not_called()

    def test_session_list_excludes_internal_directories_without_metadata(self) -> None:
        internal = self.root / "internal-run"
        internal.mkdir()
        (internal / "session.summary.json").write_text('{"project":"UNSPECIFIED"}', encoding="utf-8")
        self.post("你好")
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200, response.text)
        visible = {session["session_id"] for session in response.json()["sessions"]}
        self.assertIn(self.sid, visible)
        self.assertNotIn("internal-run", visible)

    def test_actual_daily_template_can_be_downloaded_and_restored(self) -> None:
        done = self.draft()
        markdown = next(item for item in done["deliverables"] if item["name"].endswith(".md"))
        path = Path(markdown["path"])
        self.assertTrue(path.is_relative_to(self.root))
        text = path.read_text(encoding="utf-8")
        self.assertIn("项目日报", text)
        self.assertIn("天气", text)
        self.assertIn("待填", text)
        downloaded = self.client.get("/api/file", params={"path": str(path)})
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, path.read_bytes())
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["deliverables"], done["deliverables"])
        audit = self.client.get(f"/api/harness/audit/{self.sid}").json()
        self.assertEqual(audit["counts"]["writes"], len(done["deliverables"]))
        self.assertGreater(audit["counts"]["tools"], 0)
        self.no_model.assert_not_called()

    def test_missing_jurisdiction_is_saved_as_unspecified(self) -> None:
        self.draft()
        summary_path = self.root / self.sid / "session.summary.json"
        self.assertTrue(summary_path.is_file())
        self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["jurisdiction"], "UNSPECIFIED")

    def test_explicit_and_saved_jurisdictions_share_one_router(self) -> None:
        from packing_assistant.jurisdiction import infer_jurisdiction

        cases = [
            ("写一份日报", "", "UNSPECIFIED"), ("常规任务", "invalid", "UNSPECIFIED"),
            ("辖区CN", "", "CN"), ("辖区 sg", "", "SG"), ("EU 项目", "", "EU"),
            ("欧盟项目", "", "EU"), ("新加坡项目", "", "SG"), ("中国大陆项目", "", "CN"),
            ("CN 和 SG", "", "DUAL"), ("EU / 新加坡", "", "DUAL"),
            ("双辖区", "", "DUAL"), ("DUAL", "", "DUAL"),
            ("继续完善", "SG", "SG"), ("继续完善", "EU", "EU"),
            ("改为 CN", "SG", "CN"), ("Scanning general notes", "", "UNSPECIFIED"),
            ("37 号令", "", "CN"), ("37号令", "", "CN"), ("GB/T 50319", "", "CN"),
            ("JGJ / 配合比设计规程", "", "CN"), ("IRAS 与 住建部", "", "DUAL"),
            ("监理规范 / 归档规范 / 特种设备安全法", "", "CN"),
            ("劳动合同法 / 就业促进法 / 人力资源市场", "", "CN"),
        ]
        for text, previous, expected in cases:
            with self.subTest(text=text, previous=previous):
                self.assertEqual(infer_jurisdiction(text, previous), expected)
                self.assertEqual(memory.infer_jurisdiction(text, previous), expected)
        self.draft("写一份项目日报模板，辖区：EU，缺失内容保持待填")
        self.assertEqual(memory.load_summary(self.sid)["jurisdiction"], "EU")
        self.draft()
        self.assertEqual(memory.load_summary(self.sid)["jurisdiction"], "EU")

    def test_high_risk_without_confirmation_never_executes_tools(self) -> None:
        with patch.object(agent_loop, "run_agent", side_effect=AssertionError("high-risk tool reached")) as engine:
            done, events = self.post("写一份临边防护专项施工方案", expert_ids=["construction"])
        self.assertTrue(done["hitl_pending"])
        self.assertFalse(done["wrote"])
        self.assertEqual(done["deliverables"], [])
        self.assertIn("我明白，将由持证人员签认", done["text"])
        self.assertTrue(any(event["data"].get("phase") == "hitl_gate" for event in events))
        self.assertFalse(list((self.root / self.sid).rglob("*.md")))
        engine.assert_not_called()

    def test_failed_tool_is_reported_and_the_session_can_retry(self) -> None:
        failure = {"ok": False, "error_code": "fixture_tool_failed", "detail": "fixture tool failure"}
        with patch.object(agent_loop.get_engine(), "execute", return_value=failure):
            done, _ = self.post("写一份项目日报模板", expert_ids=["pm-daily"])
        self.assertFalse(done["ok"], done)
        self.assertFalse(done["wrote"])
        self.assertEqual(done["deliverables"], [])
        self.assertFalse(chat_service._ACTIVE)
        audit = self.client.get(f"/api/harness/audit/{self.sid}").json()
        self.assertEqual(audit["counts"]["errors"], 1)
        self.assertEqual(audit["runs"][-1]["error_code"], "fixture_tool_failed")
        retried = self.draft()
        self.assertTrue(retried["ok"])

    def test_chat_after_a_write_does_not_reexecute_history(self) -> None:
        first = self.draft()
        before = {item["path"]: Path(item["path"]).read_bytes() for item in first["deliverables"]}
        with patch.object(agent_loop, "run_agent", side_effect=AssertionError("chat attempted to write")) as engine:
            done, _ = self.post("项目日报是什么意思？先别写", expert_ids=["pm-daily"], history=[
                {"role": "user", "content": "写一份项目日报模板"},
                {"role": "assistant", "content": first["text"]},
            ])
        self.assertEqual(done["intent"], "chat")
        self.assertFalse(done["wrote"])
        self.assertEqual(done["deliverables"], [])
        for path, data in before.items():
            self.assertEqual(Path(path).read_bytes(), data)
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["deliverables"], first["deliverables"])
        self.assertEqual(len(restored["transcript"]), 4)
        engine.assert_not_called()

    def test_a_later_draft_does_not_change_an_earlier_download(self) -> None:
        first = self.draft("写一份项目日报模板，天气晴，其他内容待填")
        before = {item["path"]: Path(item["path"]).read_bytes() for item in first["deliverables"]}
        second = self.draft("写一份项目日报模板，天气雨，其他内容待填")
        self.assertNotEqual(first["run_ids"], second["run_ids"])
        for path, data in before.items():
            downloaded = self.client.get("/api/file", params={"path": path})
            self.assertEqual(downloaded.content, data)
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(len(restored["deliverables"]), len(first["deliverables"]) + len(second["deliverables"]))

    def test_invalid_session_is_rejected_before_streaming(self) -> None:
        for sid in ("../escape", "slash/path", "bad sid", "_index", "abc", "x" * 33, "COM1"):
            with self.subTest(session=sid):
                response = self.client.post("/api/chat", json={"message": "你好", "session_id": sid})
                self.assertIn(response.status_code, {400, 422}, response.text)
                self.assertFalse(response.headers.get("content-type", "").startswith("text/event-stream"))
        self.assertFalse(chat_service._ACTIVE)

    def test_more_than_eight_mentions_are_rejected_before_streaming(self) -> None:
        ids = ["pm-daily", "admin-doc", "admin-office", "architecture", "bid-parse",
               "bid-compliance", "bid-tech", "bim-coord", "bim-deliver"]
        response = self.client.post("/api/chat", json={
            "session_id": self.sid, "message": " ".join("@" + eid for eid in ids) + " 你们分别做什么？",
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertFalse(chat_service._ACTIVE)

    def test_custom_expert_has_an_offline_description_and_an_honest_write_limit(self) -> None:
        store.save_user({"experts": [{"id": "local-expert", "name": "本地资料岗", "category": "docs",
                                     "title": "整理项目资料", "delivers": "资料目录", "risk": "low"}]})
        done, _ = self.post("你是做什么的？", expert_ids=["local-expert"])
        self.assertIn("本地资料岗", done["text"])
        self.assertIn("整理项目资料", done["text"])
        self.assertFalse(done["wrote"])
        with patch.object(agent_loop, "run_agent", side_effect=AssertionError("custom expert has no tool")) as engine:
            done, _ = self.post("写一份资料目录", expert_ids=["local-expert"])
        self.assertIn("尚未接入", done["text"])
        self.assertEqual(done["deliverables"], [])
        engine.assert_not_called()

    def test_selected_text_attachment_flows_into_draft_and_restored_project(self) -> None:
        project_response = self.client.post("/api/projects", json={"name": "试验园区改造"})
        self.assertEqual(project_response.status_code, 200, project_response.text)
        project_id = project_response.json()["project"]["id"]
        material = "项目：试验园区改造\n辖区：中国大陆\n天气：晴\n部位：东侧试验段\n现场记录：围挡已完成复查。"
        uploaded = self.client.post("/api/upload", data={"session_id": self.sid}, files={
            "files": ("现场记录.txt", material.encode("utf-8"), "text/plain"),
        })
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        attachment = uploaded.json()["files"][0]
        done, _ = self.post("根据所选资料写一份项目日报，缺失内容保持待填", expert_ids=["pm-daily"],
                            attachments=[attachment["id"]], project_id=project_id)
        self.assertTrue(done["wrote"], done)
        markdown = next(item for item in done["deliverables"] if item["name"].endswith(".md"))
        text = Path(markdown["path"]).read_text(encoding="utf-8")
        self.assertIn("东侧试验段", text)
        self.assertIn("围挡已完成复查", text)
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        self.assertEqual(restored["project_id"], project_id)
        self.assertEqual([item["id"] for item in restored["attachments"]], [attachment["id"]])
        self.assertEqual(restored["deliverables"], done["deliverables"])
        summary = memory.load_summary(self.sid)
        self.assertEqual(summary["project"], "试验园区改造")
        self.assertEqual(summary["jurisdiction"], "CN")
        # Uploading alone does not permanently select the file for future turns.
        self.post("项目日报是什么意思？先别写", expert_ids=["pm-daily"], project_id=project_id)
        self.assertEqual(self.client.get(f"/api/sessions/{self.sid}").json()["attachments"], [])

    def _assert_meeting_artifacts(self, done: dict) -> None:
        import openpyxl

        self.assertTrue(done["wrote"], done)
        markdown = next(item for item in done["deliverables"] if item["name"].endswith(".md"))
        content = Path(markdown["path"]).read_text(encoding="utf-8")
        for fact in ("专项协调会", "东楼301", "张测试", "另场讨论会", "李测试"):
            self.assertIn(fact, content)
        later_meeting = content.split("另场讨论会", 1)[1]
        self.assertNotIn("东楼301", later_meeting)
        self.assertNotIn("张测试", later_meeting)
        self.assertIn("| 地点 | UNSPECIFIED", later_meeting)
        xlsx = next(item for item in done["deliverables"] if item["name"].endswith(".xlsx"))
        workbook = openpyxl.load_workbook(xlsx["path"])
        try:
            values = [cell.value for sheet in workbook for row in sheet for cell in row]
            self.assertIn("接口核对 <10 | &lt;", values)
        finally:
            workbook.close()

    def test_uploaded_office_and_csv_tables_reach_real_drafts_and_excel(self) -> None:
        for kind, data in meeting_table_files().items():
            with self.subTest(kind=kind):
                self.sid = "table-" + uuid4().hex[:16]
                response = self.client.post("/api/upload", data={"session_id": self.sid},
                                            files={"files": ("会议资料." + kind, data)})
                self.assertEqual(response.status_code, 200, response.text)
                identifier = response.json()["files"][0]["id"]
                done, _ = self.post("根据附件写一份会务清单", expert_ids=["admin-office"], attachments=[identifier])
                self._assert_meeting_artifacts(done)

    def test_job_folder_office_and_csv_tables_reach_real_drafts_and_excel(self) -> None:
        folder = self.root / "job"
        folder.mkdir()
        with patch.dict(os.environ, {"CIVIL_JOB_ROOT": str(folder)}):
            for kind, data in meeting_table_files().items():
                with self.subTest(kind=kind):
                    self.sid = "jobtable-" + uuid4().hex[:16]
                    filename = "会务" + kind + "." + kind
                    (folder / filename).write_bytes(data)
                    done, _ = self.post("根据 " + filename + " 写一份会务清单", expert_ids=["admin-office"])
                    self._assert_meeting_artifacts(done)

    def test_attachment_from_another_session_is_rejected_and_releases_admission(self) -> None:
        old_sid = self.sid + "-old"
        uploaded = self.client.post("/api/upload", data={"session_id": old_sid}, files={
            "files": ("旧会话资料.txt", "只属于旧会话的内容".encode("utf-8"), "text/plain"),
        })
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        attachment_id = uploaded.json()["files"][0]["id"]
        with patch.object(agent_loop, "run_agent", side_effect=AssertionError("foreign attachment used")) as engine:
            rejected = self.client.post("/api/chat", json={"session_id": self.sid,
                "message": "写一份项目日报", "expert_ids": ["pm-daily"], "attachments": [attachment_id]})
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertIn("附件不存在", rejected.json()["detail"])
        self.assertFalse(chat_service._ACTIVE)
        engine.assert_not_called()
        self.post("你好")

    def test_admission_is_held_while_preparing_history_and_attachments(self) -> None:
        started, release = Event(), Event()
        original = chat_service.prepare_turn

        def slow_prepare(root: Path, body: dict) -> dict:
            if body["message"] == "首条消息":
                started.set()
                self.assertTrue(release.wait(8))
            return original(root, body)

        with patch.object(chat_service, "prepare_turn", side_effect=slow_prepare), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.client.post, "/api/chat", json={"session_id": self.sid, "message": "首条消息"})
            try:
                self.assertTrue(started.wait(3))
                rejected = self.client.post("/api/chat", json={"session_id": self.sid, "message": "越过准备阶段"})
                self.assertEqual(rejected.status_code, 409, rejected.text)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3).status_code, 200)
        self.assertFalse(chat_service._ACTIVE)

    def test_same_session_concurrency_is_rejected_and_then_released(self) -> None:
        started, release = Event(), Event()
        original = chat_service._offline_chat

        def slow_chat(eid: str, message: str) -> str:
            if message == "第一条消息":
                started.set()
                self.assertTrue(release.wait(8), "concurrency fixture was not released")
            return original(eid, message)

        with patch.object(chat_service, "_offline_chat", side_effect=slow_chat), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.client.post, "/api/chat", json={"session_id": self.sid, "message": "第一条消息"})
            try:
                self.assertTrue(started.wait(3))
                rejected = self.client.post("/api/chat", json={"session_id": self.sid, "message": "重复请求"})
                self.assertEqual(rejected.status_code, 409, rejected.text)
                # A different session remains usable while this one is occupied.
                another = self.client.post("/api/chat", json={"session_id": self.sid + "-2", "message": "你好"})
                self.assertEqual(another.status_code, 200)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3).status_code, 200)
        self.assertFalse(chat_service._ACTIVE)
        self.post("第二条消息")
        transcript = self.client.get(f"/api/sessions/{self.sid}").json()["transcript"]
        self.assertEqual([turn["text"] for turn in transcript if turn["role"] == "user"], ["第一条消息", "第二条消息"])


if __name__ == "__main__":
    unittest.main()
