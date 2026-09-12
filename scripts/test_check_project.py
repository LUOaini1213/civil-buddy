#!/usr/bin/env python3
"""The shared gate must fail on missing tools/timeouts and continue after errors."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_project as gate


class ProjectGateTest(unittest.TestCase):
    def test_credentials_are_not_inherited_or_loaded(self):
        with patch.dict(os.environ, {"CIVIL_API_KEY": "dummy", "OPENAI_API_KEY": "dummy", "PYTHONOPTIMIZE": "2", "CIVIL_JOB_ROOT": "owner-job"}):
            env = gate.check_environment()
            self.assertNotIn("CIVIL_API_KEY", env)
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertEqual(env["PYTHON_DOTENV_DISABLED"], "1")
            self.assertEqual(env["PYTHONOPTIMIZE"], "0")
            self.assertEqual(env["CIVIL_JOB_ROOT"], str(gate.ROOT / "output" / "check-project" / "jobs"))
            self.assertEqual(os.environ["CIVIL_JOB_ROOT"], "owner-job")
            self.assertEqual(os.environ["CIVIL_API_KEY"], "dummy")

    def test_missing_tool_fails(self):
        with patch.object(gate.shutil, "which", return_value=None):
            ok, detail = gate.run_check(gate.Check("node", (), "node"), {})
        self.assertFalse(ok)
        self.assertIn("missing", detail)

    def test_timeout_is_reported(self):
        with patch.object(gate.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 1)):
            ok, detail = gate.run_check(gate.Check("slow", (), timeout=1), {})
        self.assertFalse(ok)
        self.assertIn("timeout", detail)

    def test_remaining_checks_run_after_failure(self):
        with patch.object(gate, "run_check", side_effect=[(False, "broken"), (True, "ok")]) as run:
            self.assertEqual(gate.main(["--only", "sandbox,middleware"]), 1)
        self.assertEqual(run.call_count, 2)

    def test_empty_or_unknown_selection_is_an_error(self):
        for names in ("", "does-not-exist"):
            with self.subTest(names=names), self.assertRaises(SystemExit) as raised:
                gate.main(["--only", names])
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
