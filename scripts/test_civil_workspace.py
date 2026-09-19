#!/usr/bin/env python3
"""civil works in the folder it is started in: CIVIL.md, job-folder state, JSONL events.

The Codex behaviours this pins, in civil terms:
  AGENTS.md            -> CIVIL.md slots and text, most specific file wins, blanks stay blank
  works in the repo    -> session state and drafts under <job>/.civil-buddy/out, nothing in the repository
  codex exec --json    -> civil exec --jsonl: thread.started ... turn.completed, one JSON per line
  codex exec -o / -    -> --output-last-message, task from stdin
  codex resume --last  -> civil resume --last
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

from packing_assistant import civil  # noqa: E402
from packing_assistant.runtime import agent_loop, project_instructions as pi, threads, workspace  # noqa: E402
from packing_assistant.runtime.bus import Bus  # noqa: E402

TASK = "整理日报，日期：2031年5月6日，部位：东桥3号墩，天气：晴，出勤：钢筋工12人"


def run_cli(argv, stdin: str = ""):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.object(sys, "stdin", io.StringIO(stdin)):
        code = civil.main(argv)
    return code, out.getvalue(), err.getvalue()


class ProjectFileTests(unittest.TestCase):
    def test_blank_slots_stay_blank_and_never_swallow_the_next_line(self):
        self.assertEqual(pi.parse_slots(pi.TEMPLATE), {"units": "mm / kg"})

    def test_stated_slots_are_read_in_the_forms_people_write(self):
        text = ("- 项目：东桥改造工程（二标段）\n* **合同号**： C-2031-018 \n辖区: 新加坡\n"
                "- 业主：示例建设局  <!-- 以合同为准 -->\n- 地点：\n技术负责人：张工\n")
        self.assertEqual(pi.parse_slots(text), {
            "project": "东桥改造工程（二标段）", "contract_no": "C-2031-018", "jurisdiction": "SG",
            "client": "示例建设局", "tech_lead": "张工"})

    def test_a_jurisdiction_that_is_not_a_known_code_is_not_guessed(self):
        self.assertEqual(pi.parse_slots("辖区：火星"), {})
        self.assertEqual(pi.parse_slots("辖区：<!-- CN / SG / EU / DUAL -->"), {})

    def test_the_more_specific_file_overrides_and_the_total_is_capped(self):
        with tempfile.TemporaryDirectory() as td:
            job = Path(td).resolve()
            (job / "标段二").mkdir()
            (job / pi.NAME).write_text("- 项目：总包工程\n- 辖区：CN\n", encoding="utf-8")
            (job / "标段二" / pi.NAME).write_text("- 项目：标段二\n", encoding="utf-8")
            with patch.object(Path, "home", return_value=job / "no-home"):
                got = pi.load(job, cwd=job / "标段二")
                self.assertEqual([p.parent.name for p in got.files], [job.name, "标段二"])
                self.assertEqual(got.slots, {"project": "标段二", "jurisdiction": "CN"})
                self.assertEqual(got.fact_block(), "项目：标段二\n辖区：CN")
                (job / pi.NAME).write_text("- 项目：总包工程\n" + "x" * (pi.MAX_BYTES + 10), encoding="utf-8")
                big = pi.load(job, cwd=job)
                self.assertTrue(big.truncated)
                self.assertLessEqual(len(big.text.encode("utf-8")), pi.MAX_BYTES)

    def test_init_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            path, created = pi.init(Path(td))
            self.assertTrue(created)
            path.write_text("- 项目：已有内容\n", encoding="utf-8")
            self.assertEqual(pi.init(Path(td)), (path, False))
            self.assertEqual(path.read_text(encoding="utf-8"), "- 项目：已有内容\n")


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        # cleanups run last-in first-out: leave the folder before it is deleted (Windows cannot
        # remove the current directory), and restore the runtime before leaving.
        temporary = tempfile.TemporaryDirectory(prefix="civil-job-")
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.addCleanup(workspace.deactivate)
        self.job = Path(temporary.name).resolve()

    def test_nothing_is_activated_outside_a_job_folder(self):
        before = agent_loop._OUT
        os.chdir(self.job)
        with patch.object(Path, "home", return_value=self.job):
            self.assertIsNone(civil.enter_workspace(""))
        self.assertIsNone(workspace.active())
        self.assertEqual(agent_loop._OUT, before)

    def test_the_nearest_civil_md_above_cwd_is_the_job(self):
        (self.job / "a" / "b").mkdir(parents=True)
        self.assertIsNone(workspace.find_job_root(self.job / "a" / "b"))
        (self.job / pi.NAME).write_text("- 项目：X\n", encoding="utf-8")
        self.assertEqual(workspace.find_job_root(self.job / "a" / "b"), self.job)

    def test_activate_moves_state_and_deactivate_restores_everything(self):
        before = (agent_loop._OUT, threads._DIR, os.environ.get("CIVIL_JOB_ROOT"))
        workspace.activate(self.job)
        state = self.job / ".civil-buddy" / "out"
        self.assertEqual((agent_loop._OUT, threads._DIR), (state, state / "_threads"))
        self.assertEqual(os.environ["CIVIL_JOB_ROOT"], str(self.job))
        self.assertEqual(workspace.activate(self.job), self.job)   # idempotent
        workspace.deactivate()
        self.assertEqual((agent_loop._OUT, threads._DIR, os.environ.get("CIVIL_JOB_ROOT")), before)

    def test_a_forbidden_folder_cannot_become_the_job(self):
        with patch("packing_assistant.office_job.is_forbidden_layout", return_value=True):
            with self.assertRaises(PermissionError):
                workspace.activate(self.job)
        self.assertIsNone(workspace.active())

    def test_exec_in_a_job_folder_end_to_end(self):
        self.assertEqual(run_cli(["-C", str(self.job), "init"])[0], 0)
        project_file = self.job / pi.NAME
        project_file.write_text(project_file.read_text(encoding="utf-8")
                                .replace("- 项目：", "- 项目：东桥改造工程（二标段）")
                                .replace("- 辖区：", "- 辖区：SG", 1)
                                .replace("- 业主：", "- 业主：示例建设局"), encoding="utf-8")
        tracked_before = set((ROOT / "demo" / "out").rglob("*")) if (ROOT / "demo" / "out").is_dir() else set()

        code, out, _err = run_cli(["-C", str(self.job), "exec", "--jsonl", "-o", str(self.job / "last.txt"), "-"], stdin=TASK)
        self.assertEqual(code, 0, out)
        events = [json.loads(line) for line in out.splitlines() if line.strip()]
        kinds = [e["type"] for e in events]
        self.assertEqual(kinds[0], "thread.started")
        self.assertEqual(events[0]["job_root"], str(self.job))
        self.assertEqual(kinds[1], "turn.started")
        self.assertEqual(events[1]["skill"], "pm-daily")
        self.assertIn("item.started", kinds)
        self.assertIn("item.completed", kinds)
        done = events[-1]
        self.assertEqual((done["type"], done["ok"], done["wrote"], done["submit_blocked"]), ("turn.completed", True, True, True))
        self.assertEqual(done["agent_mode"], "steps")
        self.assertTrue(all(kinds.count(k) == 1 for k in ("thread.started", "turn.started", "turn.completed")))

        # drafts and session state live in the job folder; the repository is untouched
        inside = [f for f in done["files"] if not Path(f).is_absolute()]
        self.assertTrue(any(f.endswith(".md") for f in inside), done["files"])
        self.assertTrue(all(f.startswith(".civil-buddy") or Path(f).parent == Path(".") for f in inside), inside)
        tracked_after = set((ROOT / "demo" / "out").rglob("*")) if (ROOT / "demo" / "out").is_dir() else set()
        self.assertEqual(tracked_after, tracked_before)

        # the project file's stated facts reached the draft and the session slots; blanks did not
        draft = next(self.job / f for f in inside if f.endswith(".md")).read_text(encoding="utf-8")
        self.assertIn("东桥改造工程（二标段）", draft)
        self.assertIn("示例建设局", draft)
        self.assertNotIn("合同号：\n", draft)
        summary = json.loads(next((self.job / ".civil-buddy" / "out").rglob("session.summary.json")).read_text(encoding="utf-8"))
        self.assertEqual((summary["jurisdiction"], summary["project"]), ("SG", "东桥改造工程（二标段）"))
        self.assertEqual((self.job / "last.txt").read_text(encoding="utf-8"), done["reply"])

    def test_resume_last_continues_the_most_recent_thread(self):
        (self.job / pi.NAME).write_text("- 项目：东桥改造工程\n", encoding="utf-8")
        code, out, _ = run_cli(["-C", str(self.job), "exec", "--thread", "", "--json", "--bg", TASK])
        self.assertEqual(code, 0, out)
        first = json.loads(out)["thread_id"]
        from packing_assistant.runtime.threads import thread_status
        import time
        deadline = time.monotonic() + 30
        while thread_status(first).get("running") and time.monotonic() < deadline:
            time.sleep(0.05)
        code, out, _ = run_cli(["-C", str(self.job), "resume", "--last", "--jsonl", "解释一下什么是日报"])
        self.assertEqual(code, 0, out)
        events = [json.loads(line) for line in out.splitlines() if line.strip()]
        self.assertEqual(events[0]["thread_id"], first)
        self.assertEqual(events[-1]["thread_id"], first)
        with tempfile.TemporaryDirectory() as empty:
            Path(empty, pi.NAME).write_text("", encoding="utf-8")
            self.assertEqual(run_cli(["-C", empty, "resume", "--last"])[0], 2)
            os.chdir(self.job)   # -C moved the process there; leave before the folder is removed

    def test_status_names_the_job_the_project_file_and_never_a_key(self):
        (self.job / pi.NAME).write_text("- 项目：东桥改造工程\n- 辖区：SG\n", encoding="utf-8")
        with patch.dict(os.environ, {"CIVIL_API_KEY": "sk-not-a-real-key-000000000000", "CIVIL_MODEL": "probe-model",
                                     "CIVIL_API_BASE": "http://127.0.0.1:9/v1"}):
            code, out, _ = run_cli(["-C", str(self.job), "status"])
        self.assertEqual(code, 0)
        self.assertIn(str(self.job), out)
        self.assertIn("project=东桥改造工程", out)
        self.assertIn("probe-model @ http://127.0.0.1:9/v1", out)
        self.assertNotIn("sk-not-a-real-key", out)


class BusTests(unittest.TestCase):
    def test_listeners_see_events_live_and_a_broken_one_cannot_fail_the_run(self):
        bus, seen = Bus(), []
        stop = bus.subscribe(lambda event: seen.append(event.type))
        bus.subscribe(lambda event: 1 / 0)
        bus.emit("r1", "run_started", {"intent": "run"})
        stop()
        bus.emit("r1", "run_ended")
        self.assertEqual(seen, ["run_started"])
        self.assertEqual([e.type for e in bus.for_run("r1")], ["run_started", "run_ended"])

    def test_every_bus_event_has_a_line_in_the_stream_or_is_folded_into_the_last_one(self):
        from packing_assistant.runtime.bus import EVENT_TYPES, Event
        silent = {kind for kind in EVENT_TYPES if civil.codex_event(Event("r", kind, {})) is None}
        self.assertEqual(silent, {"run_ended"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
