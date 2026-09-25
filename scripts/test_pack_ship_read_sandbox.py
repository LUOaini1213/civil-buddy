#!/usr/bin/env python3
"""pack-ship 只读授权目录里的装箱表。

修复前（be18c6a 实测）：file_path 不在 policy 检查的键里，MCP（stdio / 工作台 HTTP）与网关
/api/mcp/tools/call 又直接调 pack_ship_mcp.call_tool，绕过 engine 与 policy。进程能打开的任何
xlsx/csv/pdf 都被解析：ingest 回行数、表头映射和 needs_human 里的品名；连 api_key_dump.csv
这种 check_open 明确拒绝的名字也照读。给一个不存在的路径，stdio 服务器整个退出，网关回 500。
网关 /api/table/parse(/json) 的 path= 与 /api/run-pdf 的 filename 同样能读夹外文件。

现在：file_path 走与写盘同一套沙箱根（作业文件夹 CIVIL_JOB_ROOT / CIVIL_SANDBOX_ROOTS / 仓库 output 等），
policy 在调处理器之前拒绝；MCP 与网关先过 engine.admit（契约 + 策略），解析的是检查过的那个路径。
缺重量这类业务上的 ok=False 不经过 execute，不会把工具熔断；steps 路径熔断了也不连带 MCP 与网关。
解析不了的路径（..、NUL）不算在根内。设了口令时，网关表格 path= 对谁都只读沙箱根（代理后人人都像本机）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "demo")]
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
_GRANTS = ("CIVIL_JOB_ROOT", "CIVIL_SANDBOX_ROOTS", "CIVIL_SANDBOX_ROOT", "PACKING_OUTPUT_DIR", "CIVIL_WORKTREE_ROOT")
for _name in _GRANTS + ("CIVIL_TOKEN", "CIVIL_ALLOW_OPEN_LAN", "CIVIL_APPROVAL", "CIVIL_SANDBOX",
                        "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "ZAI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_name, None)

from fastapi.testclient import TestClient  # noqa: E402

import mcp_surface  # noqa: E402
from packing_assistant import sandbox  # noqa: E402
from packing_assistant.runtime.tool_engine import default_engine  # noqa: E402
from packing_assistant.tools import pack_ship_mcp, packing_list_parser, table_mapper  # noqa: E402

HEADER = "S/N,Description of Goods,Q'ty,L (mm),W (mm),H (mm),G.W. (kg)\n"
GOOD = HEADER + "1,Steel bracket,4,1200,400,300,12.5\n2,Base plate,2,800,800,50,40\n"
NEEDS = HEADER + "1,Steel bracket,4,1200,400,300,12.5\n2,CONFIDENTIAL-ROW,2,800,800,50,\n"
FILE_TOOLS = ("pack-ship__ingest", "pack-ship__plan", "pack-ship__vgm", "pack-ship__booking_draft")
REMOTE = {"base_url": "http://remote.invalid", "client": ("192.0.2.1", 50000)}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


class Case(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        outside = tempfile.TemporaryDirectory(prefix="f3-outside-")
        job = tempfile.TemporaryDirectory(prefix="f3-job-")
        self.addCleanup(outside.cleanup)
        self.addCleanup(job.cleanup)
        self.outside = Path(outside.name).resolve()
        self.job = Path(job.name).resolve()
        self.stray = _write(self.outside / "list.csv", NEEDS)

    def grant(self):
        os.environ["CIVIL_JOB_ROOT"] = str(self.job)

    def assertRefused(self, out, code="deny_sandbox"):
        self.assertIs(out.get("ok"), False, out)
        self.assertEqual(out.get("error_code"), "permission_denied", out)
        if "policy" in out:
            self.assertEqual(out["policy"]["code"], code, out)
        self.assertNotIn("CONFIDENTIAL-ROW", json.dumps(out, ensure_ascii=False))
        self.assertNotIn("n_rows", out)


class Dispatcher(Case):
    def test_every_file_tool_refuses_a_path_outside_the_roots_before_parsing(self):
        with patch.object(table_mapper, "parse_table_file") as parse:
            for tool in FILE_TOOLS:
                with self.subTest(tool=tool):
                    self.assertRefused(pack_ship_mcp.call_tool(tool, {"file_path": str(self.stray)}))
            parse.assert_not_called()

    def test_a_secret_name_is_refused_even_inside_the_job_folder(self):
        self.grant()
        secret = _write(self.job / "api_key_dump.csv", NEEDS)
        out = pack_ship_mcp.call_tool("pack-ship__ingest", {"file_path": str(secret)})
        self.assertRefused(out)
        self.assertIn("secret", out["sandbox"]["reason"])
        ran = default_engine().execute("pack-ship__ingest", {"file_path": str(secret)}, expert_id="pack-ship")
        self.assertRefused(ran, code="deny_secret")

    def test_inside_the_job_folder_the_checked_path_is_what_is_parsed(self):
        self.grant()
        table = _write(self.job / "资料" / "packing.csv", GOOD)
        seen = []
        real = table_mapper.parse_table_file
        with patch.object(table_mapper, "parse_table_file", side_effect=lambda p, **k: seen.append(str(p)) or real(p, **k)):
            out = pack_ship_mcp.call_tool("pack-ship__plan", {"file_path": str(self.job / "资料" / ".." / "资料" / "packing.csv")})
        self.assertIs(out["ok"], True, out)
        self.assertGreaterEqual(out["containers_used"], 1)
        self.assertEqual(seen, [str(table)])

    def test_a_link_out_of_the_job_folder_is_refused(self):
        self.grant()
        link = self.job / "link.csv"
        try:
            os.symlink(self.stray, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"no symlink here: {exc}")
        self.assertRefused(pack_ship_mcp.call_tool("pack-ship__ingest", {"file_path": str(link)}))

    def test_a_missing_file_inside_the_roots_is_an_answer_not_an_exception(self):
        self.grant()
        out = pack_ship_mcp.call_tool("pack-ship__ingest", {"file_path": str(self.job / "nope.csv")})
        self.assertEqual((out["ok"], out["error"]), (False, "file_not_found"), out)

    def test_an_embedded_nul_is_refused_not_raised(self):
        self.assertRefused(pack_ship_mcp.call_tool("pack-ship__ingest", {"file_path": "list\x00.csv"}))
        self.assertRefused(default_engine().execute("pack-ship__ingest", {"file_path": "list\x00.csv"}, expert_id="pack-ship"))


class Roots(Case):
    def test_unresolvable_paths_are_never_inside_a_root(self):
        profile = sandbox.SandboxProfile(allowed_write_roots=[self.job])
        dotdot = str(self.job / ".." / self.outside.name / "list.csv")
        nul = str(self.job / "a\x00.csv")
        with patch.object(Path, "resolve", side_effect=OSError("unresolvable")):
            for check in (sandbox.check_open, sandbox.check_write):
                with self.subTest(check=check.__name__, path="dotdot"):
                    self.assertFalse(check(dotdot, profile=profile).allowed)
        for check in (sandbox.check_open, sandbox.check_write):
            with self.subTest(check=check.__name__, path="nul"):
                self.assertFalse(check(nul, profile=profile).allowed)
        self.assertTrue(sandbox.check_open(str(self.job / "资料" / ".." / "list.csv"), profile=profile).allowed)


class Engine(Case):
    def test_engine_registry_and_policy_refuse_before_handler(self):
        engine = default_engine()
        self.assertTrue(set(pack_ship_mcp.TOOL_NAMES) <= set(engine.tools), sorted(engine.tools))
        for name in ("pack-ship__ingest", "pack-ship__vgm", "pack-ship__booking_draft"):
            self.assertIs(engine.tools[name].writes, False, name)
        real = {name: engine.tools[name].handler for name in FILE_TOOLS}
        handlers = {name: Mock(side_effect=AssertionError("handler ran")) for name in FILE_TOOLS}
        for name, handler in handlers.items():
            engine.tools[name].handler = handler
        for _ in range(4):
            for name in FILE_TOOLS:
                self.assertRefused(engine.execute(name, {"file_path": str(self.stray)}, expert_id="pack-ship"))
        for name, handler in handlers.items():
            handler.assert_not_called()
            self.assertEqual(engine._fail_streak.get(name, 0), 0, name)
            engine.tools[name].handler = real[name]
        self.grant()
        good = _write(self.job / "good.csv", GOOD)
        self.assertIs(engine.execute("pack-ship__plan", {"file_path": str(good)}, expert_id="pack-ship")["ok"], True)


class Surfaces(Case):
    def test_mcp_surface_every_scope_refuses_then_business_failures_never_open_the_circuit(self):
        for scope in ({}, {"expert_id": "pack-ship"}, {"pack": "plant"}):
            with self.subTest(scope=scope):
                self.assertRefused(mcp_surface.call_tool("pack-ship__ingest", {"file_path": str(self.stray)}, **scope))
        chat = mcp_surface.call_tool("pack-ship__plan", {"connected": False, "intent": "chat"}, expert_id="pack-ship")
        self.assertRefused(chat, code="deny_chat_write")
        self.grant()
        gated = _write(self.job / "gated.csv", NEEDS)
        for _ in range(4):
            out = mcp_surface.call_tool("pack-ship__plan", {"file_path": str(gated)}, expert_id="pack-ship")
            self.assertEqual(out.get("error"), "missing_weight", out)
            self.assertNotEqual(out.get("error_code"), "circuit_open", out)
        good = _write(self.job / "good.csv", GOOD)
        self.assertIs(mcp_surface.call_tool("pack-ship__plan", {"file_path": str(good)}, expert_id="pack-ship")["ok"], True)
        # approval=untrusted: a plan over MCP waits for a person like every other MCP write.
        os.environ["CIVIL_APPROVAL"] = "untrusted"
        held = mcp_surface.call_tool("pack-ship__plan", {"file_path": str(good)}, expert_id="pack-ship")
        self.assertEqual((held["ok"], held.get("error_code"), held.get("wrote")), (False, "approval_required", False), held)

    def test_a_circuit_tripped_on_the_steps_path_does_not_latch_mcp_or_the_gateway(self):
        from gateway.app import app as gateway
        from packing_assistant.runtime.tool_engine import get_engine

        self.grant()
        engine = get_engine()
        self.addCleanup(engine._fail_streak.pop, "pack-ship__plan", None)
        gated = _write(self.job / "gated.csv", NEEDS)
        for _ in range(engine.circuit_threshold):
            engine.execute("pack-ship__plan", {"file_path": str(gated)}, expert_id="pack-ship")
        tripped = engine.execute("pack-ship__plan", {"file_path": str(gated)}, expert_id="pack-ship")
        self.assertEqual(tripped.get("error_code"), "circuit_open", tripped)
        good = _write(self.job / "good.csv", GOOD)
        r = TestClient(gateway).post("/api/mcp/tools/call", json={"name": "pack-ship__plan", "arguments": {"file_path": str(good)}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(r.json().get("ok"), True, r.text)
        out = mcp_surface.call_tool("pack-ship__plan", {"file_path": str(good)}, expert_id="pack-ship")
        self.assertIs(out.get("ok"), True, out)

    def test_http_mcp_routes(self):
        from app import app as workbench
        from gateway.app import app as gateway

        r = TestClient(workbench).post("/api/mcp/tools/call", json={"name": "pack-ship__ingest", "expert_id": "pack-ship",
                                                                    "arguments": {"file_path": str(self.stray)}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertRefused(r.json())
        client = TestClient(gateway, raise_server_exceptions=False)
        for path in (self.stray, self.outside / "missing" / "x.csv"):
            r = client.post("/api/mcp/tools/call", json={"name": "pack-ship__ingest", "arguments": {"file_path": str(path)}})
            self.assertEqual(r.status_code, 403, r.text)
            self.assertNotIn("CONFIDENTIAL-ROW", r.text)
        self.assertEqual(client.post("/api/mcp/tools/call", json={"name": "plan", "arguments": ["x"]}).status_code, 400)
        r = client.post("/api/mcp/tools/call", json={"name": "plan", "arguments": {"connected": False}})
        self.assertEqual((r.status_code, r.json().get("can_fit")), (200, "UNSPECIFIED"), r.text)

    def test_gateway_table_path_reads_stay_in_roots_for_remote_callers(self):
        from gateway.app import app as gateway

        os.environ["CIVIL_TOKEN"] = "t"
        self.grant()
        bearer = {"Authorization": "Bearer t"}
        remote = TestClient(gateway, headers=bearer, raise_server_exceptions=False, **REMOTE)
        for label, send in (("json", lambda p: remote.post("/api/table/parse/json", json={"path": p})),
                            ("form", lambda p: remote.post("/api/table/parse", data={"path": p}))):
            for path in (self.stray, self.outside / "missing.csv"):
                with self.subTest(route=label, path=path.name):
                    r = send(str(path))
                    self.assertEqual(r.status_code, 403, r.text)       # refused before existence is told
                    self.assertNotIn("CONFIDENTIAL-ROW", r.text)
        good = _write(self.job / "good.csv", GOOD)
        (self.job / "资料").mkdir()
        seen = []
        real = table_mapper.parse_table_file
        with patch.object(table_mapper, "parse_table_file", side_effect=lambda p, **k: seen.append(str(p)) or real(p, **k)):
            r = remote.post("/api/table/parse/json", json={"path": str(self.job / "资料" / ".." / "good.csv")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(r.json()["ok"], True, r.text)
        self.assertEqual(seen, [str(good)])     # the checked path is the one parsed
        # With a token set, looking local proves nothing: nginx `proxy_pass http://127.0.0.1:8000` with
        # HTTP/1.1 and no forwarding header is exactly this request.
        proxied = TestClient(gateway, headers=bearer, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 40000))
        for client in (proxied, TestClient(gateway, headers=bearer)):
            r = client.post("/api/table/parse/json", json={"path": str(self.stray)})
            self.assertEqual(r.status_code, 403, r.text)
            self.assertNotIn("CONFIDENTIAL-ROW", r.text)
        # No token: this machine (the tokenless Rust exe's packing bridge posts Desktop paths) reads any table it names.
        del os.environ["CIVIL_TOKEN"]
        self.assertEqual(TestClient(gateway).post("/api/table/parse/json", json={"path": str(self.stray)}).status_code, 200)

    def test_run_pdf_filename_cannot_leave_test_dir(self):
        from gateway.app import app as gateway

        stray = _write(self.outside / "stray.pdf", "%PDF-1.4\n")
        test_dir = (ROOT / "test").resolve()
        names = [str(stray), "..", "."]
        try:
            names.append(os.path.relpath(stray, test_dir))
        except ValueError:      # another drive: no relative path reaches it
            pass
        seen = []
        client = TestClient(gateway, raise_server_exceptions=False)
        with patch.object(packing_list_parser, "parse_packing_list_pdf",
                          side_effect=lambda p, *a, **k: seen.append(Path(p).resolve()) or {"materials": []}):
            for name in names:
                client.post("/api/run-pdf", json={"filename": name})
        self.assertNotIn(stray, seen)
        self.assertTrue(all(p.parent == test_dir and p.suffix == ".pdf" for p in seen), seen)

    def test_stdio_server_refuses_answers_and_keeps_serving(self):
        env = {k: v for k, v in os.environ.items() if k not in _GRANTS}
        env["CIVIL_JOB_ROOT"] = str(self.job)
        calls = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}]
        for rid, path in ((2, self.stray), (3, self.job / "nope.csv"), (4, "list\x00.csv")):
            calls.append({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                          "params": {"name": "pack-ship__ingest", "arguments": {"file_path": str(path)}}})
        calls.append({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "pack-ship__list", "arguments": {}}})
        proc = subprocess.run([sys.executable, str(ROOT / "demo" / "mcp_stdio.py"), "--expert", "pack-ship"],
                              input="".join(json.dumps(c) + "\n" for c in calls).encode("utf-8"),
                              capture_output=True, cwd=str(ROOT.anchor or ROOT.parent), env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-600:])
        got = {m["id"]: m for m in map(json.loads, proc.stdout.decode("utf-8").splitlines()) if m.get("id")}
        refused = json.loads(got[2]["result"]["content"][0]["text"])
        self.assertTrue(got[2]["result"]["isError"])
        self.assertRefused(refused)
        missing = json.loads(got[3]["result"]["content"][0]["text"])
        self.assertEqual(missing.get("error"), "file_not_found", missing)
        self.assertRefused(json.loads(got[4]["result"]["content"][0]["text"]))
        self.assertIn("pack-ship__ingest", json.loads(got[5]["result"]["content"][0]["text"])["names"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
