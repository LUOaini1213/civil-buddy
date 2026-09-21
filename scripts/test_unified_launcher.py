"""Offline launcher credential boundary and domain persistence regressions."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import start_unified_workbench as launcher


class FakeProcess:
    def __init__(self):
        self.terminated = False
        self.waited = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited = True
        return 0


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="civil-unified-launcher-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_domain_process_has_no_provider_credentials_and_uses_state_directory(self):
        binary = self.root / "civil-workbench.exe"
        binary.write_bytes(b"test executable marker; never executed")
        state = self.root / "isolated-state"
        spawned = []

        def popen(argv, **kwargs):
            process = FakeProcess()
            spawned.append((argv, kwargs, process))
            return process

        inherited = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                     "DEEPSEEK_API_KEY": "fake-parent-key", "OPENAI_API_KEY": "fake-openai-key",
                     "ANTHROPIC_API_KEY": "fake-other-key", "JEV_API_KEY": "fake-jev-key",
                     "CIVIL_TOKEN": "fake-host-token", "CIVIL_TEST_PRIVATE_SECRET": "fake-unknown-secret",
                     "PYTHONPATH": "untrusted-import-path", "CIVIL_DOMAIN_WORKSPACE": "old-ambient-folder"}
        config = {"DEEPSEEK_API_KEY": "fake-config-key", "JEV_API_KEY": "fake-config-jev"}
        output = io.StringIO()
        with patch.dict(os.environ, inherited, clear=True), \
             patch.dict(sys.modules, {"dotenv": SimpleNamespace(dotenv_values=lambda _: config)}), \
             patch.object(launcher, "ROOT", self.root), \
             patch.object(sys, "argv", ["launcher", "--binary", str(binary), "--state-root", str(state), "--env-file", str(self.root / "selected.env")]), \
             patch.object(launcher.subprocess, "Popen", side_effect=popen), \
             patch.object(launcher.urllib.request, "urlopen", side_effect=lambda *_a, **_kw: contextlib.nullcontext(SimpleNamespace(status=200))), \
             patch.object(launcher.time, "sleep", side_effect=KeyboardInterrupt), \
             contextlib.redirect_stdout(output):
            launcher.main()
        self.assertEqual(len(spawned), 2)
        argv, options, domain = spawned[0]
        self.assertIn("demo.domain_service:app", argv)
        env = options["env"]
        self.assertFalse(any("KEY" in key.upper() or "TOKEN" in key.upper() or "SECRET" in key.upper() for key in env), sorted(env))
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["PYTHON_DOTENV_DISABLED"], "1")
        self.assertEqual(Path(env["CIVIL_DOMAIN_WORKSPACE"]), state / "domains")
        self.assertEqual(Path(env["CIVIL_OUT_ROOT"]), state / "domains")
        self.assertEqual(Path(env["CIVIL_SANDBOX_ROOTS"]), state / "domains")
        self.assertEqual(Path(env["PACKING_OUTPUT_DIR"]), state / "packing")
        self.assertEqual(Path(env["PACKING_TRACE_DIR"]), state / "packing" / "traces")
        self.assertEqual(Path(env["CB_DB_PATH"]), state / "packing" / "civilbuddy.db")
        self.assertEqual(Path(env["PACKING_LG_CHECKPOINT_PATH"]), state / "packing" / "checkpoints.db")
        self.assertEqual(env["PACKING_LLM_AGENT"], "0")
        host_env = spawned[1][1]["env"]
        self.assertEqual(host_env["DEEPSEEK_API_KEY"], "fake-config-key")
        self.assertEqual(host_env["JEV_API_KEY"], "fake-config-jev")
        self.assertEqual(Path(host_env["CIVIL_STATE_ROOT"]), state)
        self.assertTrue(host_env["CIVIL_DOMAIN_URL"].startswith("http://127.0.0.1:"))
        self.assertEqual(host_env["PACKING_AGENT_URL"], host_env["CIVIL_DOMAIN_URL"] + "/packing")
        self.assertTrue(all(process.terminated and process.waited for _, _, process in spawned))
        self.assertNotIn("fake-config-key", output.getvalue())
        self.assertNotIn("fake-parent-key", output.getvalue())

    def _apis(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
            from demo import config, engineering_api, planning_api
        return config, engineering_api, planning_api

    def test_unified_schedule_and_planning_records_stay_in_state_domain_workspace(self):
        config, engineering, planning = self._apis()
        from packing_assistant.engineering.planning import calculate
        legacy = self.root / "legacy-repo"
        domain = self.root / "state" / "domains"
        domain.mkdir(parents=True)
        env = {"CIVIL_DOMAIN_WORKSPACE": str(domain), "CIVIL_SANDBOX_ROOTS": str(domain), "CIVIL_SANDBOX": "workspace-write"}
        with patch.dict(os.environ, env), patch.object(config, "REPO_ROOT", legacy):
            schedule = engineering.schedule_store()
            plan_store = planning.store()
            self.assertEqual(schedule.workspace, domain)
            self.assertEqual(plan_store.workspace, domain)
            task = {"id": "A", "name": "Fixture task", "start": "2026-09-21", "end": "2026-09-21", "progress": 0, "dependencies": []}
            saved_schedule = schedule.save(name="Fixture schedule", tasks=[task])
            calculated = calculate(planning.example())
            saved_plan = plan_store.save(name="Fixture plan", plan=calculated["plan"], result=calculated["result"])
            for store, saved in [(schedule, saved_schedule), (plan_store, saved_plan)]:
                path = store.root / (saved["id"] + ".json")
                self.assertTrue(path.is_file())
                path.relative_to(domain)
                self.assertEqual(store.open(saved["id"])["revision"], 1)
        self.assertFalse(legacy.exists(), "unified persistence created a legacy repository directory")

    def test_legacy_without_domain_environment_retains_repository_store_locations(self):
        config, engineering, planning = self._apis()
        legacy = self.root / "legacy-repo"
        with patch.dict(os.environ), patch.object(config, "REPO_ROOT", legacy):
            os.environ.pop("CIVIL_DOMAIN_WORKSPACE", None)
            schedule = engineering.schedule_store()
            plan_store = planning.store()
            self.assertEqual(schedule.workspace, legacy)
            self.assertEqual(plan_store.workspace, legacy)
            self.assertEqual(schedule.root, legacy / ".civil-buddy/out/engineering/schedules")
            self.assertEqual(plan_store.root, legacy / ".civil-buddy/out/engineering/plans")


if __name__ == "__main__":
    unittest.main()
