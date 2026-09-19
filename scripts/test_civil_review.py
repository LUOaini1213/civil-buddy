#!/usr/bin/env python3
"""`civil review <文稿>`: a model-free check of a document against the job folder's material.

  numbers      a quantity or clause number with no source in the folder is listed with its line
  sources      CIVIL.md, the other files in the folder, what the user typed in this folder's
               threads, and the user text a Civil Buddy draft quotes — never the document itself
  assertions   a verdict nobody here may state is listed; disclaiming it is not stating it
  own drafts   are found by name under .civil-buddy/out; two with the same name are not guessed between
  exit codes   0 clean · 1 findings · 2 cannot review
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "CIVIL_AGENT_MODE"):
    os.environ.pop(name, None)

from packing_assistant import civil  # noqa: E402
from packing_assistant.civil_tui import TuiState, handle_slash  # noqa: E402
from packing_assistant.runtime import threads, workspace  # noqa: E402
from packing_assistant.runtime.agent_loop import run_agent  # noqa: E402
from packing_assistant.runtime.review import review_file  # noqa: E402

WEEKLY = ("# 周报（人工整理）\n\n## 1 出勤\n\n本周木工8人，另有架子工 9 人。\n\n## 2 进度\n\n"
          "基坑开挖完成率约 65%，依据合同第7.2条，现场已具备报审条件。\n\n本稿不判定可以开工。\n")
DAILY = "整理日报，日期：2031年5月6日，部位：东桥3号墩，天气：晴，出勤：钢筋工12人"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = civil.main(argv)
    return code, out.getvalue(), err.getvalue()


class ReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="civil-review-")
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.addCleanup(workspace.deactivate)
        self.job = Path(temporary.name).resolve()
        (self.job / "CIVIL.md").write_text("- 项目：东桥改造工程（二标段）\n- 合同号：C-2031-018\n", encoding="utf-8")
        (self.job / "现场记录.txt").write_text("现场记录\n木工8人进场\n", encoding="utf-8")
        (self.job / "周报.md").write_text(WEEKLY, encoding="utf-8")
        os.chdir(self.job)
        with patch.object(Path, "home", return_value=self.job / "no-home"):
            workspace.activate(self.job)

    def test_numbers_without_a_source_are_listed_with_their_line(self):
        found = review_file("周报.md")
        self.assertTrue(found["ok"] and not found["clean"])
        self.assertEqual(found["sources"], ["现场记录.txt"])                       # the document is not its own evidence
        self.assertEqual([(n["text"], n["line"]) for n in found["numbers"]], [("9 人", 5), ("65%", 9), ("第7.2条", 9)])
        self.assertNotIn("8人", [n["text"] for n in found["numbers"]])            # 木工8人 is in the site record
        self.assertIn("架子工", found["numbers"][0]["context"])

    def test_a_verdict_is_listed_and_a_disclaimer_is_not(self):
        found = review_file("周报.md")
        self.assertEqual([(a["text"], a["line"]) for a in found["assertions"]], [("已具备报审条件", 9)])

    def test_what_the_user_typed_in_this_folder_counts_as_a_source(self):
        thread = threads.new_thread("周报")
        threads.append_rollout(thread.thread_id, "user", "本周架子工 9 人，开挖完成率 65%")
        threads.append_rollout(thread.thread_id, "assistant", "完成率 99%")         # what the assistant said is not a source
        (self.job / "周报.md").write_text(WEEKLY + "\n预计下周完成率 99%。\n", encoding="utf-8")
        self.assertEqual([n["text"] for n in review_file("周报.md")["numbers"]], ["第7.2条", "99%"])

    def test_a_civil_buddy_draft_is_found_by_name_and_is_clean(self):
        (self.job / "周报.md").unlink()     # its verdict sentence would (rightly) stop the pipeline from drafting
        self.assertTrue(run_agent(DAILY, session_id="civil-cli")["ok"])
        found = review_file("pm-daily__log.md")
        self.assertEqual(found["file"], ".civil-buddy/out/civil-cli/pm-daily/pm-daily__log.md")
        self.assertTrue(found["clean"], found["reply"])                            # 12人 is quoted from the user, verbatim
        draft = self.job / found["file"]
        draft.write_text(draft.read_text(encoding="utf-8").replace("形象进度待填。", "形象进度完成 40%，浇筑 120 m³。"), encoding="utf-8")
        self.assertEqual([n["text"] for n in review_file("pm-daily__log.md")["numbers"]], ["40%", "120 m³"])

    def test_two_drafts_with_one_name_are_not_guessed_between(self):
        (self.job / "周报.md").unlink()
        self.assertTrue(run_agent(DAILY, session_id="civil-cli")["ok"])
        self.assertTrue(run_agent(DAILY, session_id="second-one")["ok"])
        found = review_file("pm-daily__log.md")
        self.assertEqual((found["ok"], found["error_code"]), (False, "ambiguous"))
        self.assertIn("second-one/pm-daily/pm-daily__log.md", found["reply"])
        self.assertTrue(review_file(".civil-buddy/out/second-one/pm-daily/pm-daily__log.md")["ok"])

    def test_outside_the_folder_and_secrets_cannot_be_reviewed(self):
        outside = self.job.parent / "outside-review.md"
        outside.write_text("合同价 123456 元", encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.job / ".env").write_text("TOKEN=DOTENV-MARKER-7731", encoding="utf-8")
        for name in (str(outside), "../outside-review.md", ".env", "没有这个文件.md", ""):
            found = review_file(name)
            self.assertEqual((found["ok"], found["error_code"]), (False, "not_found"), name)
            self.assertNotIn("123456", found["reply"])

    def test_cli_exit_codes_json_and_the_tui_command(self):
        code, out, _ = run_cli(["-C", str(self.job), "review", "周报.md"])
        self.assertEqual(code, 1)
        self.assertIn("L9", out)
        self.assertIn("找不到出处不等于错", out)
        (self.job / "干净.md").write_text("# 记录\n\n木工8人进场。合同号 C-2031-018。\n", encoding="utf-8")
        code, out, _ = run_cli(["-C", str(self.job), "review", "--json", "干净.md"])
        self.assertEqual((code, json.loads(out)["clean"]), (0, True))
        self.assertEqual(run_cli(["-C", str(self.job), "review", "没有.md"])[0], 2)
        self.assertEqual(run_cli(["-C", str(self.job), "review"])[0], 2)
        with patch("packing_assistant.runtime.threads.new_thread", return_value=threads.CivilThread("t-x", "t-x")):
            state = TuiState()
        self.assertIn("找不到出处的数字", handle_slash("/review 周报.md", state))
        self.assertIn("用法", handle_slash("/review", state))


if __name__ == "__main__":
    unittest.main(verbosity=2)
