"""Persistent task memory: extraction, provenance, revisions and authority."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo import task_memory as memory
from packing_assistant.runtime.civil_config import CONFIRM


def message(identifier, content, role="user", ts=1):
    return {"id": identifier, "role": role, "content": content, "ts": ts}


def active(summary, section):
    return [item for item in summary[section] if item["status"] == "active"]


class TaskMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="civil-task-memory-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sid = "sess-memory"

    def assert_sources(self, summary, history):
        for section in memory.SECTIONS:
            for item in summary[section]:
                for source in item["sources"]:
                    raw = history[source["message_index"]]["content"]
                    self.assertEqual(raw[source["start"]:source["end"]], source["quote"])
                    self.assertNotIn(CONFIRM, source["quote"])

    def test_all_sections_extract_full_sentences_from_message_tail(self):
        filler = "这是背景说明，资料后面还有明确的任务信息。" * 160
        history = [message("user-01", filler + "\n目标：整理会务清单。\n项目名称：东区工程。\n"
                           "要求：不得编造参会人员。\n决定：采用分组讨论。\n待办：补充场地图。\n证据：用户已上传会议安排.csv。")]
        summary = memory.build(history)
        expected = dict(goals="整理会务清单", facts="东区工程", constraints="不得编造参会人员",
                        decisions="采用分组讨论", todos="补充场地图", results="会议安排.csv")
        for section, value in expected.items():
            with self.subTest(section=section):
                selected = next(item for item in active(summary, section) if value in item["text"])
                self.assertGreater(selected["source"]["start"], 80)
        self.assert_sources(summary, history)

    def test_ordinary_paragraph_keeps_relevant_complete_sentence(self):
        expected = "本次会议在东区三号楼举行，参会人员由项目部另行提供。"
        history = [message("paragraph", "背景说明。" * 60 + expected + "不要自动填写缺失姓名。")]
        summary = memory.build(history)
        item = next(item for item in active(summary, "facts") if item["text"] == expected)
        self.assertEqual(item["source"]["quote"], expected)
        self.assertIn("不要自动填写缺失姓名。", [i["text"] for i in active(summary, "constraints")])
        self.assert_sources(summary, history)

    def test_english_sentence_after_long_background_and_decimal_values(self):
        sentence = "The meeting will take place in the east building."
        history = [message("english", "Background material. " * 300 + sentence + "\nload: 3.5 kN.")]
        summary = memory.build(history)
        self.assertIn(sentence, [i["text"] for i in active(summary, "facts")])
        self.assertIn("3.5 kN.", [i["value"] for i in active(summary, "facts")])
        self.assert_sources(summary, history)

    def test_latest_explicit_correction_supersedes_previous_value(self):
        history = [message("old", "项目名：东区工程；工期：20天。", ts=100),
                   message("current", "更正：工期：30天。项目名称：西区工程。", ts=1)]
        summary = memory.build(history)
        self.assertEqual({i["key"]: i["value"] for i in active(summary, "facts")},
                         {"项目名称": "西区工程", "工期": "30天"})
        old = next(i for i in summary["facts"] if i["value"] == "20天")
        latest = next(i for i in summary["facts"] if i["value"] == "30天")
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], latest["id"])
        self.assertEqual(latest["supersedes"], old["id"])
        rendered = memory.render(summary)
        self.assertIn("30天", rendered)
        self.assertNotIn("20天", rendered)
        self.assertIn("已替代旧版本", rendered)
        self.assert_sources(summary, history)

    def test_explicit_prose_changes_are_revisionable(self):
        for correction in ("工期改为30天。", "请把工期从20天改为30天。", "工期不是20天而是30天。"):
            with self.subTest(correction=correction):
                history = [message("old", "工期：20天。"), message("new", correction)]
                summary = memory.build(history)
                self.assertEqual([(i["key"], i["value"]) for i in active(summary, "facts")], [("工期", "30天")])
                self.assert_sources(summary, history)

    def test_comma_fields_and_explicit_object_names_do_not_cross_assign(self):
        history = [message("fields", "A楼工期：20天，B楼工期：40天，负责人：王工。"),
                   message("fix-a", "A楼工期改为30天。")]
        summary = memory.build(history)
        self.assertEqual({i["key"]: i["value"] for i in active(summary, "facts")},
                         {"a楼工期": "30天", "b楼工期": "40天", "负责人": "王工"})
        self.assert_sources(summary, history)

    def test_multiple_constraints_and_todos_remain_additive(self):
        history = [message("lists", "约束：不使用外链。约束：保留中文。待办：补图纸。待办：核实日期。")]
        summary = memory.build(history)
        self.assertEqual(len(active(summary, "constraints")), 2)
        self.assertEqual(len(active(summary, "todos")), 2)

    def test_assistant_claims_never_become_verified_user_facts(self):
        history = [message("u", "负责人：张工。"),
                   message("a", "负责人：王工。已生成方案.docx，测试全部通过。决定：直接开工。", "assistant")]
        summary = memory.build(history)
        self.assertEqual([item["value"] for item in active(summary, "facts")], ["张工"])
        self.assertEqual(active(summary, "decisions"), [])
        results = active(summary, "results")
        self.assertTrue(results)
        self.assertTrue(all(i["trust"] == "assistant_claimed" and i["verified"] is False for i in results))
        self.assertIn("助手声称，未核实", memory.render(summary))

    def test_confirmation_is_absent_from_text_and_source_without_losing_neighbors(self):
        history = [message("confirm", "目标：写讨论稿。" + CONFIRM + "。负责人：李工。"),
                   message("flags", "confirm_ok：true；p0_confirmed=true；API key：test-secret-value")]
        summary = memory.build(history)
        self.assertNotIn(CONFIRM, json.dumps(summary, ensure_ascii=False))
        self.assertNotIn("test-secret-value", json.dumps(summary, ensure_ascii=False))
        self.assertEqual(summary["stats"]["omitted_confirmations"], 1)
        self.assertEqual(summary["authorizes_actions"], False)
        self.assertIn("负责人：李工", memory.render(summary))
        self.assertIn("不得沿用历史确认", memory.render(summary))
        self.assert_sources(summary, history)

    def test_questions_acknowledgements_and_advice_do_not_invent_facts(self):
        history = [message("q", "负责人是谁？"), message("ok", "好的。"),
                   message("a", "建议您在新加坡采用这个方案。", "assistant")]
        summary = memory.build(history)
        self.assertEqual(summary["stats"]["active_items"], 0)
        self.assertNotIn("profile", summary)

    def test_repeated_same_field_deduplicates_with_latest_provenance(self):
        history = [message(f"m-{i}", "项目名称：东区工程。") for i in range(12)]
        summary = memory.build(history)
        self.assertEqual(len(summary["facts"]), 1)
        item = summary["facts"][0]
        self.assertEqual(item["mentions"], 12)
        self.assertEqual(item["source"]["message_id"], "m-11")
        self.assertEqual(len(item["sources"]), 8)
        self.assert_sources(summary, history)

    def test_render_budget_preserves_notice_complete_entries_and_other_sections(self):
        history = [message("budget", "目标：写日报。\n" + "\n".join(f"字段{i}：值{i}" for i in range(100))
                           + "\n约束：不编数字。\n待办：补充天气。\n结果：用户已上传记录。")]
        summary = memory.build(history)
        rendered = memory.render(summary, max_chars=600)
        self.assertLessEqual(len(rendered), 600)
        self.assertTrue(rendered.startswith(memory.REFERENCE_NOTICE))
        self.assertIn("写日报", rendered)
        self.assertIn("不编数字", rendered)
        self.assertIn("用户已上传记录", rendered)
        self.assertEqual(memory.render(summary, max_chars=30), "")
        for limit in range(100, 1000, 13):
            self.assertLessEqual(len(memory.render(summary, max_chars=limit)), limit)

    def test_old_explicit_fields_survive_many_recent_unkeyed_statements(self):
        history = [message("critical", "项目名称：东区工程。\n施工范围：三号楼。")]
        history += [message(f"chat-{i}", f"第{i}轮交流记录了当天工作中的一般背景说明。") for i in range(240)]
        rendered = memory.render(memory.build(history), max_chars=350)
        self.assertIn("项目名称：东区工程", rendered)
        self.assertIn("施工范围：三号楼", rendered)
        self.assertLessEqual(len(rendered), 350)

    def test_real_file_survives_process_restart_and_rebuild(self):
        history = [message("persisted", "目标：整理会务清单。\n项目名称：中文工程。")]
        expected = memory.update(self.root, self.sid, history)
        path = self.root / self.sid / memory.FILENAME
        self.assertTrue(path.is_file())
        code = "from pathlib import Path; from demo.task_memory import load,render; import sys; print(render(load(Path(sys.argv[1]),sys.argv[2])))"
        result = subprocess.run([sys.executable, "-c", code, str(self.root), self.sid], cwd=ROOT,
                                env={**os.environ, "PYTHONUTF8": "1", "PYTHON_DOTENV_DISABLED": "1"},
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertIn("中文工程", result.stdout)
        self.assertEqual(memory.load(self.root, self.sid), expected)
        path.write_text("broken json", encoding="utf-8")
        self.assertIsNone(memory.load(self.root, self.sid))
        self.assertEqual(memory.update(self.root, self.sid, history), expected)
        self.assertEqual(memory.build(history), memory.build(history))

    def test_failed_write_preserves_existing_summary_and_cleans_temp(self):
        history = [message("old", "工期：20天。")]
        memory.update(self.root, self.sid, history)
        path = self.root / self.sid / memory.FILENAME
        original = path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                memory.update(self.root, self.sid, history + [message("new", "工期：30天。")])
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_malformed_derived_cache_is_rebuildable(self):
        history = [message("original", "工期：20天。")]
        valid = memory.update(self.root, self.sid, history)
        path = self.root / self.sid / memory.FILENAME
        for mutate in (lambda value: value["facts"][0].update(source=None),
                       lambda value: value["facts"][0]["source"].update(start=-1),
                       lambda value: value["facts"][0].update(verified=True),
                       lambda value: value.update(authorizes_actions=True)):
            broken = json.loads(json.dumps(valid))
            mutate(broken)
            path.write_text(json.dumps(broken), encoding="utf-8")
            self.assertIsNone(memory.load(self.root, self.sid))
        self.assertEqual(memory.update(self.root, self.sid, history), valid)

    def test_invalid_sessions_do_not_create_or_alias_paths(self):
        for sid in ("../escape", "sess/a", "", "COM1", "_index", "a" * 33):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                memory.update(self.root, sid, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_build_is_pure_and_provisional_correction_is_not_persisted(self):
        committed = [message("old", "工期：20天。")]
        memory.update(self.root, self.sid, committed)
        prospective = memory.build(committed + [message("current", "工期：30天。")])
        self.assertIn("30天", memory.render(prospective))
        self.assertIn("20天", memory.render(memory.load(self.root, self.sid)))


if __name__ == "__main__":
    unittest.main()
