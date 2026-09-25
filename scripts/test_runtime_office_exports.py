#!/usr/bin/env python3
"""Actual HTTP/runtime Office exports for the two special tool pipelines."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import openpyxl
import chat_service
import turn_control
from packing_assistant import expert_turn, office_job
from packing_assistant.runtime import agent_loop
from packing_assistant.runtime.scheduler import Scheduler
from packing_assistant.runtime.tool_engine import get_engine
import test_workbench_flow as flow
from test_word_export import document, text as word_text

REQUESTS = {
    "pack-ship": "出一份装箱作业单，未提供 solver 参数的字段保持 UNSPECIFIED。",
    "bid-parse": "解析招标并写出抽取表：工期60日历天。货物须妥善包装，采用铁架防护。采用海运整柜 40HQ。未实质性响应作废标处理。",
}


class RuntimeOfficeExportsTests(unittest.TestCase):
    def setUp(self):
        flow.WorkbenchFlowTests.setUp(self)
        self.scheduler = Scheduler()
        self.stack.enter_context(patch.object(agent_loop, "get_scheduler", return_value=self.scheduler))

    post = flow.WorkbenchFlowTests.post

    def draft(self, eid):
        return self.post(REQUESTS[eid], expert_ids=[eid], confirm_text="我明白，将由持证人员签认")[0]

    def fresh_session(self):
        self.sid = "office-" + uuid4().hex[:16]

    def assert_released(self):
        self.assertNotIn(self.sid, self.scheduler._locks)
        self.assertNotIn(self.sid, chat_service._ACTIVE)
        self.assertFalse(turn_control.status(self.sid)["active"])

    def assert_files_restored(self, done, suffixes):
        files = done["deliverables"]
        self.assertTrue(done["wrote"], done)
        self.assertEqual(len(files), len({item["path"] for item in files}))
        self.assertTrue(suffixes.issubset({Path(item["path"]).suffix for item in files}), files)
        for item in files:
            path = Path(item["path"])
            self.assertTrue(path.is_relative_to(self.root), path)
            downloaded = self.client.get("/api/file", params={"path": str(path)})
            self.assertEqual(downloaded.status_code, 200, downloaded.text[:100])
            self.assertEqual(downloaded.content, path.read_bytes())
        restored = self.client.get(f"/api/sessions/{self.sid}").json()
        restored_paths = {item["path"] for item in restored["deliverables"]}
        self.assertTrue({item["path"] for item in files}.issubset(restored_paths))
        self.assert_released()
        return restored

    def test_both_special_http_paths_export_real_word_and_restore(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                with patch.object(expert_turn, "_attach_office", wraps=expert_turn._attach_office) as attach:
                    done = self.draft(eid)
                self.assertTrue(done["ok"], done)
                self.assertEqual(done["state"], "done")
                self.assertEqual(attach.call_count, 1)
                # bid-parse writes its extract as a table since 2026-09-20 (事项｜要求原文｜来源页段｜…), so it
                # comes with a workbook as well; the pack-ship sheet is still lists and has none.
                tabular = eid == "bid-parse"
                self.assertEqual(len(attach.call_args.args[0]["files"]), 3 if tabular else 2)
                self.assert_files_restored(done, {".md", ".docx", ".xlsx"} if tabular else {".md", ".docx"})
                contents = {}
                for item in done["deliverables"]:
                    path = Path(item["path"])
                    if path.suffix == ".docx":
                        contents["word"] = word_text(document(path.read_bytes()))
                    elif path.suffix == ".xlsx":
                        book = openpyxl.load_workbook(BytesIO(path.read_bytes()))
                        contents["excel"] = " ".join(str(cell.value) for sheet in book for row in sheet for cell in row if cell.value is not None)
                        self.assertFalse(any(cell.data_type == "f" for sheet in book for row in sheet for cell in row))
                        book.close()
                    elif path.suffix == ".md":
                        contents["md"] = path.read_text(encoding="utf-8")
                for kind, content in contents.items():
                    # the workbook holds the table cells - the duration as written, "60日历天"; the line that
                    # repeats it as a count of calendar days ("60 日历天") is a paragraph, in the md and the Word file
                    want = "UNSPECIFIED" if eid == "pack-ship" else "60日历天" if kind == "excel" else "60 日历天"
                    self.assertIn(want, content)
                    self.assertNotIn("can_fit=true", content)
                self.assertIn("Word", done["text"])
                self.assertEqual("excel" in contents, tabular)  # Lists have no tabular XLSX candidate.
                self.assertEqual("Excel" in done["text"], tabular)

    def test_connected_packing_snapshot_values_are_only_projected(self):
        snapshot = {"can_fit": False, "utilization": 0.317, "mid50": 0.499,
                    "系固待办": "用户提供：检查原始系固记录"}
        result = agent_loop.run_agent(REQUESTS["pack-ship"], session_id=self.sid,
            expert_id="pack-ship", force_intent="run", packing_summary=snapshot)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["pack_ship"]["plan"]["can_fit"])
        self.assertEqual(0.317, result["pack_ship"]["plan"]["utilization"])
        self.assertEqual(0.499, result["pack_ship"]["plan"]["mid50"])
        word = next(Path(item["path"]) for item in result["files"] if item["path"].endswith(".docx"))
        content = word_text(document(word.read_bytes()))
        self.assertIn("0.317", content)
        self.assertIn("0.499", content)
        self.assertEqual(set(result["artifacts"]), {item["path"] for item in result["files"]})
        self.assert_released()

    def test_word_failure_is_failed_with_md_downloadable_and_retry_works(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                with patch.object(office_job, "export_md_to_docx", side_effect=OSError("fixture disk denied")):
                    done = self.draft(eid)
                self.assertFalse(done["ok"], done)
                self.assertEqual(done["state"], "failed")
                self.assertIn("Word 导出失败", done["text"])
                self.assert_files_restored(done, {".md"})
                self.assertFalse(any(item["path"].endswith(".docx") for item in done["deliverables"]))
                audit = self.client.get(f"/api/harness/audit/{self.sid}").json()
                self.assertTrue(any(run["error_code"] == "office_export_failed" for run in audit["runs"]))
                self.assertTrue(self.draft(eid)["ok"])
                self.assert_released()

    def test_excel_failure_keeps_word_and_propagates_runtime_error(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                with patch.object(office_job, "export_md_to_xlsx", side_effect=ValueError("fixture table invalid")):
                    result = agent_loop.run_agent(REQUESTS[eid], session_id=self.sid,
                        expert_id=eid, force_intent="run", p0_confirmed=True)
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["error_code"], "office_export_failed")
                self.assertEqual(result["export_errors"], ["Excel 导出失败"])
                self.assertTrue({".md", ".docx"}.issubset({Path(item["path"]).suffix for item in result["files"]}))
                self.assertEqual(set(result["artifacts"]), {item["path"] for item in result["files"]})
                self.assert_released()

    def test_http_cancel_during_current_export_keeps_office_files_and_skips_next_post(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                entered, proceed = Event(), Event()
                original = expert_turn._attach_office

                def paused(result):
                    completed = original(result)
                    entered.set()
                    self.assertTrue(proceed.wait(5))
                    return completed

                with ThreadPoolExecutor(max_workers=1) as pool, patch.object(expert_turn, "_attach_office", side_effect=paused) as attach:
                    future = pool.submit(self.post, REQUESTS[eid], expert_ids=[eid, "pm-daily"], confirm_text="我明白，将由持证人员签认")
                    self.assertTrue(entered.wait(4))
                    try:
                        cancelled = self.client.post(f"/api/sessions/{self.sid}/cancel").json()
                        self.assertTrue(cancelled["cancel_requested"])
                        self.assertEqual(cancelled["state"], "cancelling")
                        self.assertEqual(self.client.post("/api/chat", json={"message": "你好", "session_id": self.sid}).status_code, 409)
                    finally:
                        proceed.set()
                    done, _ = future.result(timeout=5)
                self.assertEqual(attach.call_count, 1)
                self.assertFalse(done["ok"])
                self.assertTrue(done["cancelled"])
                self.assertEqual(done["state"], "cancelled")
                self.assert_files_restored(done, {".md", ".docx"})
                self.assertFalse((self.root / self.sid / "pm-daily").exists())
                self.assertTrue(self.post("你好")[0]["ok"])

    def test_cancel_after_markdown_write_does_not_start_office(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                cancel = Event()
                engine = get_engine()
                execute = engine.execute

                def stop_after_write(name, *args, **kwargs):
                    result = execute(name, *args, **kwargs)
                    if name == "write_deliverable":
                        cancel.set()
                    return result

                with patch.object(engine, "execute", side_effect=stop_after_write), patch.object(expert_turn, "_attach_office") as attach:
                    result = agent_loop.run_agent(REQUESTS[eid], session_id=self.sid,
                        expert_id=eid, force_intent="run", p0_confirmed=True, cancel_event=cancel)
                attach.assert_not_called()
                self.assertEqual(result["state"], "cancelled")
                self.assertTrue(result["wrote"])
                self.assertTrue(any(item["path"].endswith(".md") for item in result["files"]))
                self.assertFalse(any(item["path"].endswith((".docx", ".xlsx")) for item in result["files"]))
                self.assert_released()

    def test_normal_post_uses_existing_office_export_only_once(self):
        with patch.object(expert_turn, "_attach_office", wraps=expert_turn._attach_office) as attach:
            done, _ = self.post("写一份项目日报", expert_ids=["pm-daily"])
        self.assertTrue(done["ok"], done)
        self.assertEqual(attach.call_count, 1)
        self.assertEqual(sum(item["path"].endswith(".docx") for item in done["deliverables"]), 1)
        self.assert_files_restored(done, {".md", ".docx", ".xlsx"})

    def test_chat_and_read_only_do_not_export_special_documents(self):
        for eid in REQUESTS:
            with self.subTest(eid=eid):
                self.fresh_session()
                with patch.object(expert_turn, "_attach_office") as attach:
                    chat, _ = self.post("解释本岗需要准备什么资料", expert_ids=[eid])
                    with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
                        blocked = self.draft(eid)
                self.assertFalse(chat["wrote"])
                self.assertFalse(blocked["wrote"])
                attach.assert_not_called()
                self.assertFalse(list((self.root / self.sid).rglob("*.docx")))
                self.assert_released()


if __name__ == "__main__":
    unittest.main(verbosity=2)
