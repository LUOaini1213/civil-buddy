#!/usr/bin/env python3
"""End-to-end context/RAG journeys through the shipped workbench API, offline."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
from scripts import test_workbench_flow as flow
import chat_service
import context
import local_retrieval
import projects
import session_bundle
import session_context
import task_memory
import uploads


class ContextFlowTests(unittest.TestCase):
    post = flow.WorkbenchFlowTests.post

    def setUp(self):
        flow.WorkbenchFlowTests.setUp(self)
        context.set_runtime_policy(None)
        self.addCleanup(context.set_runtime_policy, None)

    def seed(self, text, sid=None):
        sid = sid or self.sid
        projects.touch_session(self.root, sid, text)
        projects.append_turn(self.root, sid, "user", text)

    def search(self, query, ids=None, sid=None):
        response = self.client.post("/api/context/search", json={"session_id": sid or self.sid,
            "query": query, "attachments": ids or []})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["citations"]

    def test_old_suffix_survives_display_tail_and_enters_real_model_request(self):
        # The fact used to disappear at both the 80-character fold and 8000-byte write.
        original = "背景说明。" * 2100 + "\n交付日期：2031年11月23日。\n项目名称：银河桥。"
        self.seed(original)
        for i in range(205):
            projects.append_turn(self.root, self.sid, "assistant", f"第 {i} 轮记录。" + "一般讨论内容。" * 25)
        captured = []
        def fake_model(messages, **kwargs):
            captured.append(messages)
            yield "根据已提供原文，交付日期是2031年11月23日。"
        context.set_runtime_policy({"limit": 12000, "reserve": 1500})
        with patch.object(flow.workbench, "has_key", return_value=True), patch("llm.stream_plain", side_effect=fake_model):
            done, _ = self.post("银河桥的交付日期是什么？", expert_ids=["pm-daily"])
        self.assertTrue(captured)
        sent = json.dumps(captured[0], ensure_ascii=False)
        self.assertIn("2031年11月23日", sent)
        self.assertLess(len(captured[0]), 206)
        self.assertLessEqual(context.validate_request(captured[0])["used"], 10500)
        self.assertTrue(done["context"]["compressed"])
        self.assertGreater(done["context"]["components"]["system"], 0)
        self.assertEqual(projects.read_full_history(self.root, self.sid)[0]["content"], original)
        hits = self.search("交付日期")
        first = next(h for h in hits if "2031年11月23日" in h["snippet"])
        source = self.client.get(first["url"])
        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.json()["text"], first["snippet"])
        summary = self.client.get("/api/context", params={"session_id": self.sid}).json()
        self.assertIn("银河桥", summary["memory_text"])
        self.assertEqual(summary["summary"]["stats"]["messages"], 208)

    def test_late_attachment_is_selected_and_unselected_attachment_stays_out(self):
        long_text = "普通背景说明。\n" * 5200 + "\nZXQ729验收位置：南门仓库二层。\n"
        chosen = uploads.save_upload(self.sid, "现场记录.txt", long_text.encode())
        hidden = uploads.save_upload(self.sid, "其它记录.txt", "ZXQ729隐藏记录：禁止串入本轮。".encode())
        captured = []
        def fake_model(messages, **kwargs):
            captured.extend(messages)
            yield "根据所选附件，位置为南门仓库二层。"
        with patch.object(flow.workbench, "has_key", return_value=True), patch("llm.stream_plain", side_effect=fake_model):
            done, _ = self.post("ZXQ729验收位置在哪里？", expert_ids=["quality"], attachments=[chosen["id"]])
        sent = json.dumps(captured, ensure_ascii=False)
        self.assertIn("南门仓库二层", sent)
        self.assertNotIn("禁止串入本轮", sent)
        cite = next(c for c in done["citations"] if c["layer"] == "upload" and "南门仓库二层" in c["snippet"])
        self.assertGreater(cite["start"], 20000)
        self.assertEqual(self.client.get(cite["url"]).json()["text"], long_text[cite["start"]:cite["end"]])
        no_attachments = self.search("ZXQ729验收位置")
        self.assertFalse(any(h["layer"] == "upload" for h in no_attachments))
        selected = self.search("ZXQ729", [chosen["id"]])
        self.assertFalse(any("禁止串入本轮" in h["snippet"] for h in selected))
        foreign = "foreign-task"
        self.seed("其它任务。", foreign)
        self.assertEqual(self.search("ZXQ729", sid=foreign), [])
        params = {"session_id": foreign, "source_id": cite["source_id"]}
        self.assertEqual(self.client.get("/api/context/source", params=params).status_code, 404)

    def test_plain_router_gets_memory_and_complete_budget(self):
        self.seed("项目名称：枫桥。\n会议地点：西楼303。")
        captured = []
        def fake_plain(messages):
            captured.extend(messages)
            yield {"event": "done", "data": {"text": "会议地点为西楼303。"}}
        with patch.object(flow.workbench, "has_key", return_value=True), patch.object(flow.workbench, "run_plain", side_effect=fake_plain):
            done, _ = self.post("之前说的地点在哪？")
        self.assertEqual(captured[0]["role"], "system")
        self.assertIn("西楼303", json.dumps(captured, ensure_ascii=False))
        self.assertEqual(done["context"]["used"], context.validate_request(captured)["used"])

    def test_medium_chinese_attachment_uses_chunks_when_whole_text_exceeds_budget(self):
        document = "背景资料。" * 1850 + "\nMAG77交付地点：南门仓库。"
        chosen = uploads.save_upload(self.sid, "中型资料.txt", document.encode())
        context.set_runtime_policy({"limit": 16000, "reserve": 2000})
        captured = []
        def fake_model(messages, **kwargs):
            captured.extend(messages)
            yield "交付地点为南门仓库。"
        with patch.object(flow.workbench, "has_key", return_value=True), patch("llm.stream_plain", side_effect=fake_model):
            done, _ = self.post("MAG77交付地点在哪？", expert_ids=["quality"], attachments=[chosen["id"]])
        self.assertIn("南门仓库", json.dumps(captured, ensure_ascii=False))
        self.assertTrue(any(c["layer"] == "upload" and "南门仓库" in c["snippet"] for c in done["citations"]))
        self.assertLessEqual(context.validate_request(captured)["used"], 14000)

    def test_one_repetitive_attachment_cannot_hide_another_selected_file_tail(self):
        repetitive = uploads.save_upload(self.sid, "重复资料.txt", ("SATURATED44 ordinary record.\n" * 1800).encode())
        later = uploads.save_upload(self.sid, "现场位置.txt", ("普通资料。\n" * 3500 + "\nSATURATED44交付位置：西门配电室。").encode())
        turn = chat_service.prepare_turn(self.root, {"session_id": self.sid, "expert_ids": ["quality"],
            "message": "SATURATED44 的位置是什么？", "attachments": [repetitive["id"], later["id"]]})
        citations = turn["requests"]["quality"]["citations"]
        self.assertTrue(any("西门配电室" in hit["snippet"] and hit["start"] > 20000 for hit in citations))

    def test_backup_import_rebuilds_memory_and_index_with_new_source_ids(self):
        original = "参考段落。" * 2500 + "\n项目名称：石榴园。\n独有标识：RAGRESTORE88。"
        self.seed(original)
        session_context.persist(self.root, self.sid)
        before = self.search("RAGRESTORE88")
        raw = session_bundle.export_session(self.root, self.sid)
        restored = session_bundle.import_session(self.root, raw)
        sid = restored["session_id"]
        self.assertNotEqual(sid, self.sid)
        self.assertEqual(projects.read_full_history(self.root, sid)[0]["content"], original)
        self.assertIn("石榴园", task_memory.render(task_memory.load(self.root, sid)))
        hits = self.search("RAGRESTORE88", sid=sid)
        self.assertTrue(hits)
        self.assertNotEqual(hits[0]["source_id"], before[0]["source_id"])
        self.assertEqual(self.client.get(hits[0]["url"]).status_code, 200)

    def test_current_revision_is_used_and_old_authorization_is_not(self):
        self.seed("项目名称：旧项目。\n我明白，将由持证人员签认")
        turn = chat_service.prepare_turn(self.root, {"session_id": self.sid,
            "message": "更正：项目名称：新项目。写一份会议计划模板", "expert_ids": ["admin-office"]})
        self.assertIn("项目名称：新项目", turn["material"])
        self.assertNotIn("项目名称：旧项目", turn["material"])
        self.assertNotIn("我明白，将由持证人员签认", turn["material"])
        self.assertFalse(turn["confirmed"])
        done, _ = self.post("写一份施工方案模板", expert_ids=["construction"])
        self.assertTrue(done["hitl_pending"])
        self.assertFalse(done["wrote"])

    def test_local_draft_recovers_explicit_user_fields_from_previous_turn(self):
        self.seed("会议名称：记忆协调会。\n场地：北楼101。\n议程：资料核对。")
        done, _ = self.post("写一份会议计划模板", expert_ids=["admin-office"])
        drafts = [Path(f["path"]).read_text(encoding="utf-8") for f in done["deliverables"] if f["path"].endswith(".md")]
        self.assertTrue(drafts)
        self.assertIn("记忆协调会", "\n".join(drafts))
        self.assertIn("北楼101", "\n".join(drafts))
        newer, _ = self.post("更正：场地：南楼202。写一份会议计划模板", expert_ids=["admin-office"])
        revised = "\n".join(Path(f["path"]).read_text(encoding="utf-8") for f in newer["deliverables"] if f["path"].endswith(".md"))
        self.assertIn("南楼202", revised)
        self.assertNotIn("北楼101", revised)

    def test_rejects_oversized_current_request_before_persistence(self):
        context.set_runtime_policy({"limit": 1024, "reserve": 256})
        response = self.client.post("/api/chat", json={"session_id": self.sid,
            "message": "请解释：" + "长上下文" * 4000 + "？", "expert_ids": ["pm-daily"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("未被截断", response.text)
        self.assertFalse((self.root / self.sid / "transcript.jsonl").exists())
        self.assertFalse(chat_service._ACTIVE)

    def test_import_preserves_legacy_messages_and_rejects_unreadable_timestamps(self):
        self.seed("项目名称：备份时间测试。")
        raw = session_bundle.export_session(self.root, self.sid)
        def altered(value):
            output = BytesIO()
            with ZipFile(BytesIO(raw)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
                manifest = json.loads(source.read("bundle.json"))
                if value is None:
                    manifest["transcript"][0].pop("ts", None)
                else:
                    manifest["transcript"][0]["ts"] = value
                for name in source.namelist():
                    target.writestr(name, json.dumps(manifest, ensure_ascii=False).encode() if name == "bundle.json" else source.read(name))
            return output.getvalue()
        for invalid in ("yesterday", -1, True):
            with self.assertRaisesRegex(session_bundle.BundleError, "时间戳"):
                session_bundle.import_session(self.root, altered(invalid))
        imported = session_bundle.import_session(self.root, altered(None))
        history = projects.read_full_history(self.root, imported["session_id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "项目名称：备份时间测试。")
        self.assertEqual(history[0]["ts"], 0)

    def test_context_settings_validate_without_partial_model_update(self):
        valid = self.client.post("/api/llm-config", json={"context_limit": 8192, "output_reserve": 1024})
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["context"]["usable"], 7168)
        for payload in ({"context_limit": True}, {"output_reserve": 8192}, {"context_limit": "16000"}):
            response = self.client.post("/api/llm-config", json={"model": "must-not-apply", **payload})
            self.assertEqual(response.status_code, 400)
            self.assertNotEqual(self.client.get("/api/llm-config").json()["model"], "must-not-apply")
            self.assertEqual(context.policy()["limit"], 8192)


if __name__ == "__main__":
    unittest.main()
