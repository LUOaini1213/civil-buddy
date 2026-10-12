"""Configuration precedence and offline isolation without reading any .env file."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_config(env):
    spec = importlib.util.spec_from_file_location("review_demo_config", ROOT / "demo/config.py")
    module = importlib.util.module_from_spec(spec)
    # A loader that does not implement PYTHON_DOTENV_DISABLED emulates older
    # supported versions. The application must enforce its own offline switch.
    with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv") as loader:
        spec.loader.exec_module(module)
    return module, loader


class DemoConfigTests(unittest.TestCase):
    def test_offline_custom_output_never_reads_dotenv(self):
        with tempfile.TemporaryDirectory() as folder:
            module, loader = read_config({"PYTHON_DOTENV_DISABLED": "1", "CIVIL_OUT_ROOT": folder})
            loader.assert_not_called()
            self.assertEqual(module.OUT_ROOT, Path(folder).resolve())

    def test_offline_default_output_never_reads_dotenv(self):
        module, loader = read_config({"PYTHON_DOTENV_DISABLED": "1"})
        loader.assert_not_called()
        self.assertEqual(module.OUT_ROOT, ROOT / "demo/out")

    def test_demo_override_is_independent_of_output_location(self):
        for env in ({}, {"CIVIL_OUT_ROOT": str(ROOT / "output/synthetic-config")}):
            with self.subTest(env=env):
                _, loader = read_config(env)
                self.assertEqual(loader.call_args_list, [
                    call(ROOT / ".env"), call(), call(ROOT / "demo/.env", override=True),
                ])


if __name__ == "__main__":
    unittest.main()
