#!/usr/bin/env python3
"""Manual/full acceptance against a real compiled Rust host and its Python sidecar.

  python scripts/test_unified_runtime_http.py --binary workbench/target/debug/civil-workbench.exe

Uses random loopback ports, synthetic inputs, fresh named accounts, a local scripted model,
and a fresh ignored output directory. Never connects to the user's running product or a real provider.
This is same-machine process/restart verification, not real-project or cross-computer acceptance.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import unified_acceptance as document_acceptance


def require(value, message):
    if not value:
        raise AssertionError(message)


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def request(base, path, body=None, *, token=None, cookie=None, form=False, timeout=30):
    headers = {"Origin": base, "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if cookie:
        headers["Cookie"] = cookie
    raw = None if body is None else (urllib.parse.urlencode(body) if form else json.dumps(body)).encode("utf-8")
    message = urllib.request.Request(base + path, data=raw, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(message, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data = response.read(50_000_001)
        require(len(data) <= 50_000_000, "Response exceeds acceptance size limit")
        return response.status, response.headers, data


def json_request(base, path, body=None, *, token=None, cookie=None, expected=200):
    status, _headers, data = request(base, path, body, token=token, cookie=cookie)
    require(status == expected, f"{path}: expected HTTP {expected}, got {status}: {data[:300]!r}")
    return json.loads(data)


def port_closed(port):
    with socket.socket() as connection:
        connection.settimeout(0.25)
        return connection.connect_ex(("127.0.0.1", port)) != 0


class Instance:
    def __init__(self, binary, directory, state_root, workspace, user, model_port):
        self.binary, self.directory, self.state_root, self.workspace = binary, directory, state_root, workspace
        self.user, self.port, self.model_port = user, free_port(), model_port
        self.base = f"http://127.0.0.1:{self.port}"
        self.token = secrets.token_urlsafe(48)
        self.directory.mkdir(parents=True)
        self.workspace.mkdir(parents=True)
        self.token_file = self.directory / "login-token.txt"
        self.token_file.write_text(self.token, encoding="ascii")
        self.private_root = state_root / "accounts" / user / "projects" / sha256(os.path.normcase(str(workspace.resolve())).encode()).hexdigest()
        self.process = None
        self.log = None
        self.generation = 0
        self.domain_port = None

    def start(self):
        self.generation += 1
        self.stop_file = self.directory / f"stop-{self.generation}"
        self.log = (self.directory / f"launcher-{self.generation}.log").open("wb")
        environment = {key: value for key, value in os.environ.items()
                       if not key.upper().startswith(("CIVIL_", "OPENAI_", "ANTHROPIC_", "LLM_", "DEEPSEEK_", "ZAI_"))
                       and not key.upper().endswith("_API_KEY") and key not in {"PYTHONPATH", "PYTHONHOME"}}
        environment.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHON_DOTENV_DISABLED="1",
                           CIVIL_MODEL=document_acceptance.MODEL, CIVIL_API_KEY="scripted-local-fixture",
                           CIVIL_API_BASE=f"http://127.0.0.1:{self.model_port}/v1")
        command = [sys.executable, str(ROOT / "scripts/start_unified_workbench.py"), "--binary", str(self.binary),
                   "--python", sys.executable, "--state-root", str(self.state_root), "--workspace", str(self.workspace),
                   "--user-id", self.user, "--token-file", str(self.token_file), "--port", str(self.port),
                   "--stop-file", str(self.stop_file)]
        self.process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            require(self.process.poll() is None, f"Launcher exited; inspect {self.directory} and {self.private_root}")
            try:
                status, _, _ = request(self.base, "/api/engineering/planning/capabilities", token=self.token, timeout=2)
                if status == 200:
                    log = (self.private_root / "domains.log").read_text(encoding="utf-8", errors="replace")
                    ports = re.findall(r"Uvicorn running on http://127\.0\.0\.1:(\d+)", log)
                    require(ports, "Cannot verify sidecar listener from startup log")
                    self.domain_port = int(ports[-1])
                    return
            except OSError:
                pass
            time.sleep(0.2)
        raise TimeoutError(f"Host/sidecar startup timed out; inspect {self.directory} and {self.private_root}")

    def stop(self):
        if self.process is None:
            return
        self.stop_file.write_text("stop", encoding="ascii")
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            # Exceptional cleanup only: terminate the owned process tree if its supervisor is stuck.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            else:
                self.process.terminate()
            self.process.wait(timeout=10)
            raise TimeoutError("Supervisor did not honor its shutdown sentinel")
        finally:
            self.log.close()
            self.process = None
        require(port_closed(self.port), "Rust host listener survived shutdown")
        if self.domain_port:
            require(port_closed(self.domain_port), "Python domain listener survived shutdown")

    def login(self):
        status, headers, _ = request(self.base, "/auth/login", {"token": self.token}, form=True)
        require(status in (302, 303), f"Login expected redirect, got {status}")
        full = headers.get("Set-Cookie", "")
        require("HttpOnly" in full and "SameSite=Strict" in full, "Login cookie lacks protections")
        cookie = full.split(";", 1)[0]
        json_request(self.base, "/api/agent/capabilities", cookie=cookie)
        return cookie


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {"passed": False, "synthetic": True, "cross_computer": False, "real_provider_calls": False,
              "binary": str(binary), "checks": {}, "logs_root": str(output)}
    provider = document_acceptance.model_server(0)
    worker = threading.Thread(target=provider.serve_forever, daemon=True)
    worker.start()
    first = Instance(binary, output / "alice", output / "state", output / "workspace-alice", "acceptance_alice", provider.server_port)
    second = Instance(binary, output / "bob", output / "state", output / "workspace-bob", "acceptance_bob", provider.server_port)
    try:
        first.start()
        require(request(first.base, "/api/agent/capabilities")[0] == 401, "Unauthenticated API must require login")
        require(request(first.base, "/auth/login", {"token": "invalid"}, form=True)[0] == 401, "Bad login was accepted")
        cookie = first.login()
        report["checks"]["login_and_cookie"] = True
        for page in ("/", "/cad", "/engineering/planning", "/logistics", "/packing"):
            status, headers, body = request(first.base, page, cookie=cookie)
            require(status == 200 and "html" in headers.get("Content-Type", "") and body, f"Page unavailable: {page}")
        for api in ("/api/cad/capabilities", "/api/engineering/planning/capabilities", "/api/logistics/capabilities", "/packing/api/health"):
            json_request(first.base, api, cookie=cookie)
        report["checks"]["domain_pages_and_apis"] = True
        plan = json_request(first.base, "/api/engineering/planning/example", cookie=cookie)["plan"]
        saved = json_request(first.base, "/api/engineering/planning/projects",
                             {"name": "Synthetic HTTP restart acceptance", "synthetic": True, "plan": plan}, cookie=cookie)["project"]
        project_path = "/api/engineering/planning/projects/" + saved["id"]
        first.stop()
        first.start()
        require(request(first.base, "/api/agent/capabilities", cookie=cookie)[0] == 401, "Pre-restart cookie was accepted")
        cookie = first.login()
        restored = json_request(first.base, project_path, cookie=cookie)["project"]
        for field in ("id", "revision", "name", "synthetic", "plan", "result", "method"):
            require(saved[field] == restored[field], f"Restart changed project field {field}")
        report["checks"]["project_restart_and_cookie_revocation"] = True
        report["project"] = {"id": saved["id"], "revision": saved["revision"], "synthetic": True}
        second.start()
        second_cookie = second.login()
        require(request(second.base, "/api/agent/capabilities", cookie=cookie)[0] == 401, "Another user's cookie was accepted")
        require(request(second.base, "/api/agent/capabilities", token=first.token)[0] == 401, "Another user's token was accepted")
        require(request(second.base, project_path, cookie=second_cookie)[0] in (403, 404), "Another user could read the project")
        require(json_request(second.base, "/api/engineering/planning/projects", cookie=second_cookie)["projects"] == [], "Another user's project appeared in listing")
        status, _, body = request(second.base, "/api/agent/workspaces", {"path": str(first.workspace)}, cookie=second_cookie)
        require(status in (400, 403) and "workspace is not allowed" in json.loads(body).get("detail", ""),
                f"Disallowed workspace registration was not rejected: HTTP {status}: {body[:300]!r}")
        workspaces = json_request(second.base, "/api/agent/workspaces", cookie=second_cookie)["workspaces"]
        require(not any(row.get("root") == str(first.workspace) for row in workspaces), "Disallowed workspace was persisted")
        report["checks"]["named_instance_isolation"] = True
        second.stop()
        original_http = document_acceptance.http
        def authenticated_http(base, path, body=None, *, binary=False, timeout=30):
            status, _, data = request(base, path, body, token=first.token, timeout=timeout)
            require(200 <= status < 300, f"Document acceptance {path}: HTTP {status}: {data[:300]!r}")
            return data if binary else json.loads(data)
        document_acceptance.http = authenticated_http
        try:
            documents = document_acceptance.acceptance(first.base, first.workspace, output / "documents", timeout=240)
        finally:
            document_acceptance.http = original_http
        require(documents["passed"], f"Scripted document acceptance failed: {documents.get('error') or documents.get('validation')}")
        events = [json.loads(line) for line in (output / "documents/events.jsonl").read_text(encoding="utf-8").splitlines()]
        authorizations = [e["data"] for e in events if e.get("kind", e.get("event")) == "authorization"]
        require(authorizations and all(e.get("actor_id") == first.user and e.get("confirmation_scope") == "current_turn"
                                       and e.get("professional_signoff") is False for e in authorizations), "Missing or incorrect actor authorization audit")
        usage = documents["turn"]["result"].get("usage") or {}
        require(usage.get("model_calls", 0) > 0, "Missing model usage audit")
        report["checks"]["document_agent_originals_copies_actor_usage"] = True
        report["document_report"] = str(output / "documents/report.json")
        report["usage"] = usage
        first.stop()
        report["checks"]["both_processes_stopped"] = True
        report["passed"] = True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        for instance in (second, first):
            try:
                instance.stop()
            except Exception as exc:
                report["passed"] = False
                report.setdefault("cleanup_errors", []).append(str(exc))
        provider.shutdown()
        provider.server_close()
        worker.join(timeout=3)
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True, help="Explicit freshly compiled Rust executable")
    parser.add_argument("--output", type=Path, help="Fresh output directory (must not exist)")
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        parser.error("--binary must name an existing executable")
    output = (args.output or ROOT / "output" / ("unified-runtime-http-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6])).resolve()
    report = run(binary, output)
    print(json.dumps({"passed": report["passed"], "report": str(output / "report.json"), "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
