#!/usr/bin/env python3
"""The system-level sandbox: what the kernel holds, and what happens when it cannot be had.

  kernel     a worker confines itself, then raw writes (no policy layer in the way) outside the job's
             state folder are refused by the operating system — job folder, home, system temp — a child
             process cannot be started, and on Linux an inet socket cannot be opened
  turns      a steps turn runs in the worker and the host publishes the workbook copy; in model mode the
             file-reading / writing tools run in the worker while approval is asked in the host
  refusal    sandbox_backend=os without a job folder, or a worker that cannot confine itself, means the
             turn does not run — never "run it unconfined and say nothing"
The kernel tests skip, loudly, on a machine whose kernel offers no backend (macOS; Linux without Landlock).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "CIVIL_AGENT_MODE", "CIVIL_SANDBOX_BACKEND"):
    os.environ.pop(name, None)

from packing_assistant import office_job  # noqa: E402
from packing_assistant.runtime import model_loop, os_sandbox, workspace  # noqa: E402
from packing_assistant.runtime.bus import get_bus  # noqa: E402
from packing_assistant.runtime.turn import run_turn  # noqa: E402

KERNEL = os_sandbox.probe()
HELD = bool(KERNEL["available"] and KERNEL["enforces"]["write"])
WHY_NOT = f"no kernel backend here: {KERNEL.get('reason') or KERNEL['backend']}"
DAILY = "整理日报，日期：2031年5月6日，部位：东桥3号墩，天气：晴，出勤：钢筋工12人"
PACKING = ("S/N,Description of Goods,Q'ty,L (mm),W (mm),H (mm),G.W. (kg)\n"
           "1,Steel bracket,4,1200,400,300,12.5\n2,Base plate,2,800,800,50,40\n")


class Script:
    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def __call__(self, messages, tools=None, **_kwargs):
        self.seen.append(json.loads(json.dumps(messages)))
        step = self.steps.pop(0) if self.steps else "（脚本已用完）"
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {"content": "", "tool_calls": [{"id": f"c{len(self.seen)}", "name": name, "arguments": arguments} for name, arguments in step]}


class JobFolderCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="civil-os-")
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.addCleanup(workspace.deactivate)
        self.addCleanup(os.environ.pop, "CIVIL_SANDBOX_BACKEND", None)
        self.job = Path(temporary.name).resolve()
        (self.job / "CIVIL.md").write_text("- 项目：东桥改造工程（二标段）\n", encoding="utf-8")
        (self.job / "现场记录.txt").write_text("现场记录\n木工8人进场\n", encoding="utf-8")
        (self.job / "packing.csv").write_text(PACKING, encoding="utf-8", newline="")
        os.chdir(self.job)
        with patch.object(Path, "home", return_value=self.job / "no-home"):
            workspace.activate(self.job)
        self.state = self.job / ".civil-buddy" / "out"


@unittest.skipUnless(HELD, WHY_NOT)
class KernelTests(JobFolderCase):
    def test_the_worker_proves_its_confinement_before_it_serves(self):
        with os_sandbox.Worker(self.job) as worker:
            report, again = worker.confined, worker.call("selftest")["out"]
        for checks in (report["selftest"], again):
            self.assertEqual(checks["write_inside_state"], "allowed")
            for outside in ("write_job_folder", "write_home", "write_system_temp", "spawn_process", "inet_socket"):
                self.assertEqual(checks[outside], "denied", (outside, checks))
        self.assertEqual(report["enforces"]["write"], True)
        self.assertEqual(report["enforces"]["spawn"], True)
        # the network claim is per platform and the report must not overstate it
        self.assertEqual(report["enforces"]["network"], sys.platform.startswith("linux"))
        self.assertEqual(bool(report.get("network_app_layer")), not sys.platform.startswith("linux"))
        self.assertEqual([p.name for p in self.job.iterdir() if p.name.startswith(".civil-sandbox-probe")], [])

    def test_a_steps_turn_runs_confined_and_the_host_publishes_the_copy(self):
        os.environ["CIVIL_SANDBOX_BACKEND"] = "os"
        seen = []
        unsubscribe = get_bus().subscribe(lambda event: seen.append(event.type))
        try:
            out = run_turn(DAILY, session_id="civil-cli")
        finally:
            unsubscribe()
        self.assertTrue(out["ok"], out.get("reply"))
        self.assertEqual(out["sandbox_backend"]["backend"], KERNEL["backend"])
        self.assertEqual(out["sandbox_backend"]["selftest"]["write_job_folder"], "denied")
        drafts = [f["path"] for f in out["files"] if f["path"].endswith(".md")]
        self.assertTrue(drafts and all(str(self.state) in path for path in drafts), out["files"])
        self.assertIn("tool_call", seen)                                  # the worker's events reach the host's bus
        copy = self.job / "pm-daily__log.xlsx"                            # written by the host, by the usual rules
        self.assertTrue(copy.is_file())
        self.assertEqual(office_job.own_exports(), {"pm-daily__log.xlsx"})
        self.assertIn(str(copy), [f["path"] for f in out["files"]])

    def test_the_packing_engine_runs_confined(self):
        os.environ["CIVIL_SANDBOX_BACKEND"] = "os"
        out = run_turn("帮我算一下 packing.csv 要几个柜", session_id="civil-cli")
        self.assertTrue(out["ok"], out.get("reply"))
        self.assertEqual(out["pack_ship"]["plan"]["source"], "solver")
        self.assertTrue((self.state / "civil-cli" / "pack-ship" / "pack-plan.md").is_file())

    def test_model_tools_run_in_the_worker_and_approval_is_asked_in_the_host(self):
        asked = []
        script = Script([("read_job_file", {"name": "现场记录.txt"})], [("run_skill", {"skill_id": "safety-brief"})], "安全交底草稿已出，待持证人员签认。")
        with os_sandbox.Worker(self.job) as worker:
            out = model_loop.run_model_agent("编一份临边防护安全交底，部位：东桥3号墩", session_id="civil-cli", complete=script,
                                             approve=lambda request: asked.append(request) or True, worker=worker)
        self.assertIn("木工8人进场", script.seen[1][-1]["content"])          # read inside the worker, returned to the model
        self.assertEqual([r["name"] for r in asked], ["安全交底"])
        self.assertTrue(out["wrote"] and not out["hitl_pending"], out)
        self.assertTrue(all(str(self.state) in f["path"] for f in out["files"]), out["files"])

        declined = Script([("run_skill", {"skill_id": "safety-brief"})], "未获确认，未写盘。")
        with os_sandbox.Worker(self.job) as worker:
            out = model_loop.run_model_agent("编一份安全交底", session_id="second", complete=declined, approve=lambda request: False, worker=worker)
        self.assertTrue(out["hitl_pending"] and not out["wrote"], out)

    def test_a_worker_that_cannot_confine_itself_never_serves(self):
        policy = {"job_root": str(self.job), "write_roots": [str(self.job / "missing" / "out")], "network": False, "spawn": False}
        env = {**os.environ, "CIVIL_OS_SANDBOX_POLICY": json.dumps(policy), "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
        done = subprocess.run([sys.executable, "-m", "packing_assistant.runtime.os_sandbox.worker"], env=env, cwd=str(self.job),
                              input='{"id": 1, "op": "selftest", "args": {}}\n', capture_output=True, text=True, encoding="utf-8", timeout=120)
        lines = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
        self.assertEqual([line["type"] for line in lines], ["fatal"], done.stdout + done.stderr[-300:])
        self.assertEqual(done.returncode, 3)


class RefusalTests(JobFolderCase):
    def test_the_backend_is_what_was_asked_for_or_a_reason(self):
        self.assertEqual(os_sandbox.resolve_backend("app"), ("app", ""))
        self.assertEqual(os_sandbox.resolve_backend(""), ("app", ""))                 # the default
        if HELD:
            self.assertEqual(os_sandbox.resolve_backend("os"), ("os", ""))
            self.assertEqual(os_sandbox.resolve_backend("auto"), ("os", ""))
        workspace.deactivate()
        backend, why = os_sandbox.resolve_backend("auto")
        self.assertEqual(backend, "app")
        self.assertTrue(why)                                                          # auto degrades out loud
        with self.assertRaises(PermissionError):
            os_sandbox.resolve_backend("os")

    def test_os_means_os_the_turn_is_refused_rather_than_run_unconfined(self):
        workspace.deactivate()
        os.environ["CIVIL_SANDBOX_BACKEND"] = "os"
        out = run_turn(DAILY, session_id="civil-cli")
        self.assertEqual((out["ok"], out["error_code"], out["wrote"]), (False, "sandbox_unavailable", False))
        self.assertEqual(list(self.state.rglob("*.md")) if self.state.exists() else [], [])

    def test_a_kernel_that_offers_nothing_is_said_so(self):
        nothing = {"backend": "none", "available": False, "enforces": {"write": False, "spawn": False, "network": False}, "reason": "测试：没有后端"}
        with patch.object(os_sandbox, "probe", return_value=nothing):
            self.assertEqual(os_sandbox.resolve_backend("auto"), ("app", "系统级沙箱未启用（测试：没有后端）；本轮只有应用层策略。"))
            os.environ["CIVIL_SANDBOX_BACKEND"] = "auto"
            out = run_turn(DAILY, session_id="civil-cli")
            self.assertTrue(out["ok"])
            self.assertEqual(out["sandbox_backend"]["backend"], "app")
            self.assertIn("只有应用层策略", out["reply"])
            with self.assertRaises(PermissionError):
                os_sandbox.resolve_backend("os")


if __name__ == "__main__":
    print("kernel probe:", json.dumps(KERNEL, ensure_ascii=False))
    unittest.main(verbosity=2)
