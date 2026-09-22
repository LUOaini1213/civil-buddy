"""Offline persistence acceptance for successful engineering analysis snapshots."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.engineering.records import AnalysisStore, RecordConflict, RecordNotFound, encode
from packing_assistant.runtime.cancel import RunCancelled, scope


def snapshot():
    return {"kind": "frame", "inputs": {"source": "synthetic", "span_m": 2.0},
            "result": {"ok": True, "source": "synthetic", "reaction_n": 100.0}}


class RecordAcceptance(unittest.TestCase):
    def setUp(self):
        (ROOT / "output").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="engineering-record-test-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.store = AnalysisStore(self.workspace / "records")
        env = patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write"})
        env.start(); self.addCleanup(env.stop)

    def save(self, **kwargs):
        return self.store.save(**({"name": "教学梁分析", "snapshot": snapshot()} | kwargs))

    def test_listing_cannot_enumerate_outside_allowed_read_roots(self):
        self.save()
        with patch("packing_assistant.engineering.records.assert_open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.store.list_projects()

    def test_fresh_process_restores_inputs_and_results(self):
        first = self.save()
        code = "import json,sys; from pathlib import Path; from packing_assistant.engineering.records import AnalysisStore; print(json.dumps(AnalysisStore(Path(sys.argv[1])).open(sys.argv[2])))"
        result = subprocess.run([sys.executable, "-c", code, str(self.store.root), first["project"]["id"]],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True, timeout=20)
        self.assertEqual(json.loads(result.stdout), first)
        self.assertEqual(self.store.list_projects(), [first["project"]])

    def test_versions_remain_independent_and_reopen(self):
        first = self.save(); ident = first["project"]["id"]
        changed = snapshot(); changed["inputs"]["span_m"] = 3.0
        second = self.save(snapshot=changed, identifier=ident, expected_revision=1)
        self.assertEqual(second["project"]["revision"], 2)
        self.assertEqual(self.store.open(ident, 1)["snapshot"], snapshot())
        self.assertEqual(self.store.open(ident)["snapshot"], changed)
        changed["inputs"]["span_m"] = 99
        second["snapshot"]["inputs"]["span_m"] = 100
        self.assertEqual(self.store.open(ident)["snapshot"]["inputs"]["span_m"], 3.0)

    def test_concurrent_edit_has_exactly_one_winner(self):
        first = self.save(); ident = first["project"]["id"]
        def attempt(name):
            try:
                return self.save(name=name, identifier=ident, expected_revision=1)
            except RecordConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["甲", "乙"]))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.open(ident)["project"]["revision"], 2)

    def test_interrupted_replace_keeps_previous_version_and_no_temp(self):
        first = self.save(); ident = first["project"]["id"]
        original = self.store.path(ident).read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("simulated interrupted replace")):
            with self.assertRaises(OSError):
                self.save(identifier=ident, expected_revision=1)
        self.assertEqual(self.store.path(ident).read_bytes(), original)
        self.assertFalse(list(self.store.root.glob("*.tmp")))

    def test_cancelled_request_does_not_affect_next_save(self):
        first = self.save(); ident = first["project"]["id"]
        event = Event(); event.set()
        with scope(event=event):
            with self.assertRaises(RunCancelled):
                self.save(identifier=ident, expected_revision=1)
        self.assertEqual(self.store.open(ident), first)
        self.assertEqual(self.save(identifier=ident, expected_revision=1)["project"]["revision"], 2)

    def test_corrupt_metadata_is_reported_without_losing_other_projects(self):
        good = self.save(name="正常记录")
        broken = self.save(name="待损坏记录"); ident = broken["project"]["id"]
        path = self.store.path(ident); base = json.loads(path.read_text(encoding="utf-8"))
        mutations = [
            lambda r: r.pop("name"), lambda r: r.update(name=[]), lambda r: r.update(name="\n"),
            lambda r: r.pop("updated_at"), lambda r: r.update(updated_at=[]),
            lambda r: r.update(updated_at="2026-09-21"),
            lambda r: r["versions"][0].pop("created_at"),
            lambda r: r["versions"][0].update(created_at=False),
            lambda r: r["versions"][0].update(version=True),
            lambda r: r.update(kind=[]), lambda r: r.update(versions={}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = deepcopy(base); mutation(value)
                content = json.dumps(value); path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "记录损坏"):
                    self.store.open(ident)
                rows = self.store.list_projects()
                self.assertEqual(len(rows), 2)
                self.assertIn("error", next(r for r in rows if r["id"] == ident))
                self.assertEqual(next(r for r in rows if r["id"] == good["project"]["id"]), good["project"])
                with self.assertRaisesRegex(ValueError, "记录损坏"):
                    self.save(identifier=ident, expected_revision=1)
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_valid_hash_does_not_hide_invalid_snapshot_structure(self):
        first = self.save(); ident = first["project"]["id"]
        path = self.store.path(ident); base = json.loads(path.read_text(encoding="utf-8"))
        bad_snapshots = [{"kind": "frame"}, {"kind": "frame", "inputs": [], "result": {}},
                         {"kind": "section", "inputs": {}, "result": {}},
                         {"kind": "frame", "inputs": {}, "result": {"ok": False}}]
        for invalid in bad_snapshots:
            with self.subTest(snapshot=invalid):
                value = deepcopy(base); row = value["versions"][0]; row["snapshot"] = invalid
                row["sha256"] = hashlib.sha256(encode(invalid).encode()).hexdigest()
                path.write_text(encode(value), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "记录损坏"):
                    self.store.open(ident)

    def test_changed_snapshot_digest_or_invalid_json_is_rejected(self):
        first = self.save(); ident = first["project"]["id"]
        path = self.store.path(ident); value = json.loads(path.read_text(encoding="utf-8"))
        value["versions"][0]["snapshot"]["inputs"]["span_m"] = 999
        for text in (json.dumps(value), '{"broken":', "[]"):
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "记录损坏"):
                self.store.open(ident)

    def test_rejects_bad_snapshot_before_any_save(self):
        bad = [{"kind": "frame"}, {"kind": [], "inputs": {}, "result": {}},
               {"kind": "frame", "inputs": {}, "result": {"value": float("nan")}},
               {"kind": "frame", "inputs": {}, "result": {"kind": "section"}}]
        for item in bad:
            with self.subTest(snapshot=item), self.assertRaises(ValueError):
                self.save(snapshot=item)
        self.assertFalse(self.store.root.exists())

    def test_readonly_paths_versions_and_workspace_isolation(self):
        for ident in ("../outside", "C:\\outside", "", "a" * 31, ["a"]):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                self.store.open(ident)
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}):
            with self.assertRaises(PermissionError):
                self.save()
        first = self.save(); ident = first["project"]["id"]
        for v in (0, 2, True, "1"):
            with self.subTest(version=v), self.assertRaises(ValueError):
                self.store.open(ident, v)
        with self.assertRaises(RecordNotFound):
            AnalysisStore(self.workspace / "other").open(ident)

    @unittest.skipUnless(hasattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT"), "Windows reparse metadata unavailable")
    def test_reparse_point_rejected_on_python_without_is_junction(self):
        original = Path.lstat
        def changed(path, *args, **kwargs):
            if path == self.store.root:
                return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", changed):
            with self.assertRaisesRegex(ValueError, "链接或目录联接"):
                self.store.path("a" * 32)


if __name__ == "__main__":
    unittest.main()
