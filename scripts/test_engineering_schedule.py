"""Offline acceptance of persisted user plans, failures and concurrent updates."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
from threading import Event
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.engineering.schedule import ScheduleStore, ScheduleConflict, ScheduleNotFound, validate_tasks
from packing_assistant.runtime.cancel import RunCancelled, scope


def tasks():
    return [
        {"id": "T1", "name": "准备", "start": "2026-09-21", "end": "2026-09-23", "progress": 100, "dependencies": []},
        {"id": "T2", "name": "基础", "start": "2026-09-24", "end": "2026-09-30", "progress": 20, "dependencies": ["T1"]},
    ]


class ScheduleAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.store = ScheduleStore(self.workspace)
        env = patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write"})
        env.start(); self.addCleanup(env.stop)

    def save(self, **kwargs):
        return self.store.save(**({"name": "施工计划", "tasks": tasks()} | kwargs))

    def test_fresh_process_restores_exact_user_dates_and_dependencies(self):
        saved = self.save()
        code = "import json,sys; from pathlib import Path; from packing_assistant.engineering.schedule import ScheduleStore; print(json.dumps(ScheduleStore(Path(sys.argv[1])).open(sys.argv[2])))"
        result = subprocess.run([sys.executable, "-c", code, str(self.workspace), saved["id"]], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True, timeout=20)
        opened = json.loads(result.stdout)
        self.assertEqual(opened["tasks"], tasks())
        self.assertEqual(opened["revision"], 1)
        self.assertEqual(self.store.list_projects()[0]["task_count"], 2)

    def test_bad_dates_references_and_cycles_never_create_project(self):
        mutations = [
            lambda t: t[0].update(start="2026-02-30"),
            lambda t: t[0].update(start="2026-09-24"),
            lambda t: t[0].update(start="20260921"),
            lambda t: t[1].update(id="T1"),
            lambda t: t[1].update(dependencies=["MISSING"]),
            lambda t: t[0].update(dependencies=["T2"]),
            lambda t: t[0].update(dependencies=["T1"]),
            lambda t: t[1].update(dependencies=["T1", "T1"]),
            lambda t: t[0].update(progress=True),
            lambda t: t[0].update(progress=float("nan")),
            lambda t: t[0].update(progress=101),
            lambda t: t[0].update(path="../../outside"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = tasks(); mutate(value)
                with self.assertRaises(ValueError):
                    self.save(tasks=value)
        self.assertEqual(self.store.list_projects(), [])

    def test_undo_survives_restart_and_does_not_reuse_revision(self):
        first = self.save()
        changed = tasks(); changed[1].update(end="2026-10-07", progress=30)
        second = self.save(tasks=changed, project_id=first["id"], expected_revision=1)
        restored = ScheduleStore(self.workspace).undo(first["id"], second["revision"])
        self.assertEqual(restored["tasks"], first["tasks"])
        self.assertEqual(restored["revision"], 3)
        self.assertFalse(restored["can_undo"])
        with self.assertRaises(ScheduleConflict):
            self.save(project_id=first["id"], expected_revision=1)

    def test_concurrent_edit_has_one_winner_and_one_conflict(self):
        first = self.save()
        def attempt(name):
            try:
                return self.save(name=name, project_id=first["id"], expected_revision=1)
            except ScheduleConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["甲修改", "乙修改"]))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.open(first["id"])["revision"], 2)

    def test_save_failure_preserves_previous_content_and_cleans_temp(self):
        first = self.save()
        with patch.object(Path, "replace", side_effect=OSError("simulated interrupted replace")):
            with self.assertRaises(OSError):
                self.save(name="未完成保存", project_id=first["id"], expected_revision=1)
        self.assertEqual(self.store.open(first["id"]), first)
        self.assertFalse(list(self.store.root.glob("*.tmp")))

    def test_cancelled_write_isolated_from_next_request(self):
        first = self.save(); event = Event(); event.set()
        with scope(event=event):
            with self.assertRaises(RunCancelled):
                self.save(name="不应写入", project_id=first["id"], expected_revision=1)
        self.assertEqual(self.store.open(first["id"]), first)
        self.assertEqual(self.save(name="正常", project_id=first["id"], expected_revision=1)["revision"], 2)

    def test_corrupt_record_cannot_be_overwritten(self):
        first = self.save(); path = self.store.root / (first["id"] + ".json")
        path.write_text('{"broken":', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.save(project_id=first["id"], expected_revision=1)
        self.assertEqual(path.read_text(encoding="utf-8"), '{"broken":')
        self.assertIn("error", self.store.list_projects()[0])

    def test_path_escape_and_read_only_are_blocked(self):
        for ident in ("../../outside", "C:\\outside", ".", "a"*31, ["a"]):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                self.store.open(ident)
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            with self.assertRaises(PermissionError):
                self.save()
        self.assertFalse(self.store.root.exists())

    def test_workspace_isolation_and_unknown_project(self):
        first = self.save()
        other = ScheduleStore(self.workspace / "another-job")
        with self.assertRaises(ScheduleNotFound):
            other.open(first["id"])
        self.assertEqual(other.list_projects(), [])

    def test_windows_reparse_point_is_rejected_without_python312_is_junction(self):
        original_lstat = Path.lstat
        root = self.store.root
        def lstat(path, *args, **kwargs):
            if path == root:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", lstat):
            with self.assertRaisesRegex(ValueError, "链接或目录联接"):
                self.save()
        self.assertFalse(root.exists())

    def test_dependencies_warn_without_inventing_dates(self):
        value = tasks(); value[1]["start"] = "2026-09-22"
        result = self.save(tasks=value)
        self.assertEqual(result["tasks"], value)
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("T1", result["warnings"][0])

    def test_literal_names_and_defensive_copies(self):
        value = tasks(); value[0]["name"] = '<img src=x onerror="alert(1)">'
        result = self.save(tasks=value); value[0]["name"] = "changed locally"
        result["tasks"][0]["name"] = "changed response"
        self.assertEqual(self.store.open(result["id"])["tasks"][0]["name"], '<img src=x onerror="alert(1)">')

    def test_long_span_and_excess_tasks_rejected(self):
        value = tasks(); value[1]["end"] = "2040-01-01"
        with self.assertRaises(ValueError):
            validate_tasks(value)
        with self.assertRaises(ValueError):
            validate_tasks([tasks()[0]]*251)


if __name__ == "__main__":
    unittest.main()
