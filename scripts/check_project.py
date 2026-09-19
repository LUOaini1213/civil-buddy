#!/usr/bin/env python3
"""Civil Buddy's offline quality gate, shared by Python, npm and CI."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    args: tuple[str, ...]
    runtime: str = "python"
    timeout: int = 180


CHECKS = (
    Check("runner", ("scripts/test_check_project.py",)),
    Check("secrets", ("scripts/scan_tracked_secrets.py",)),
    Check("offline-assets", ("scripts/test_no_external_urls.py",)),
    Check("js-syntax", ("scripts/test_js_syntax.py",)),
    Check("vue-bindings", ("scripts/test_vue_bindings.py",)),
    Check("chat-stream", ("scripts/test_chat_stream.cjs",), "node"),
    Check("stack-parity", ("scripts/test_stack_parity.py",)),
    Check("expert-capabilities", ("scripts/test_expert_capabilities.py",)),
    Check("tool-contracts", ("scripts/test_tool_contracts.py",)),
    Check("task-routing", ("scripts/test_task_router.py",)),
    Check("readonly-routing", ("scripts/test_readonly_routing.py",)),
    Check("tender-workflow", ("scripts/test_tender_workflow.py",)),
    Check("tender-response-match", ("scripts/test_tender_response_match.py",)),
    Check("tender-response-bench", ("scripts/eval_tender_response_match.py", "--check")),
    Check("workbench-collaboration", ("scripts/test_workbench_collaboration.py",)),
    Check("middleware", ("scripts/test_agent_middleware.py",)),
    Check("sandbox", ("scripts/test_sandbox.py",)),
    Check("civil-cli", ("scripts/test_civil_codex.py",)),
    Check("civil-workspace", ("scripts/test_civil_workspace.py",)),
    Check("model-loop", ("scripts/test_model_loop.py",)),
    Check("steps-job-files", ("scripts/test_steps_job_files.py",)),
    Check("civil-review", ("scripts/test_civil_review.py",)),
    Check("os-sandbox", ("scripts/test_os_sandbox.py",), timeout=300),
    Check("plugins", ("scripts/test_plugins.py",)),
    Check("example-plugin", ("-m", "packing_assistant.civil", "plugin", "validate", "examples/plugins/site-forms")),
    Check("task-intent-bench", ("scripts/eval_task_intent.py", "--check")),
    Check("verdict-bench", ("scripts/eval_verdicts.py", "--check")),
    Check("number-provenance-bench", ("scripts/eval_number_provenance.py", "--check")),
    Check("runtime-threads", ("scripts/test_runtime_threads.py",)),
    Check("app-launcher", ("scripts/test_app_launcher.py",)),
    Check("workbench-settings", ("scripts/test_workbench_settings.py",)),
    Check("workbench-uploads", ("scripts/test_workbench_uploads.py",)),
    Check("workbench-flow", ("scripts/test_workbench_flow.py",)),
    Check("context-budget", ("scripts/test_context_budget.py",)),
    Check("task-memory", ("scripts/test_task_memory.py",)),
    Check("local-retrieval", ("scripts/test_local_retrieval.py",)),
    Check("context-flow", ("scripts/test_context_flow.py",)),
    Check("context-rebuild", ("scripts/test_context_rebuild.py",)),
    Check("semantic-memory", ("scripts/test_semantic_memory.py",)),
    Check("semantic-integration", ("scripts/test_semantic_integration.py",)),
    Check("semantic-http", ("scripts/test_semantic_http.py",)),
    Check("draft-context", ("scripts/test_draft_context_integrity.py",)),
    Check("project-storage", ("scripts/test_project_storage.py",)),
    Check("workbench-cancel", ("scripts/test_workbench_cancel.py",)),
    Check("session-backup", ("scripts/test_session_bundle.py",)),
    Check("word-export", ("scripts/test_word_export.py",)),
    Check("runtime-office", ("scripts/test_runtime_office_exports.py",)),
    Check("http-confirmation", ("scripts/test_http_confirmation.py",)),
    Check("daily-report", ("scripts/test_daily_report_content.py",)),
    Check("finance-tax", ("scripts/test_finance_tax_drafts.py",)),
    Check("post-dispatch", ("scripts/test_post_dispatch.py",)),
    Check("hr-drafts", ("scripts/test_hr_drafts.py",)),
    Check("admin-drafts", ("scripts/test_admin_drafts.py",)),
    Check("it-drafts", ("scripts/test_it_drafts.py",)),
    Check("bim-drafts", ("scripts/test_bim_drafts.py",)),
    Check("design-basic", ("scripts/test_design_basic_drafts.py",)),
    Check("design-services", ("scripts/test_design_services_drafts.py",)),
    Check("design-specialties", ("scripts/test_design_specialties_drafts.py",)),
    Check("design-infrastructure", ("scripts/test_design_infrastructure_drafts.py",)),
    Check("expert-drafts", ("scripts/test_expert_turn.py",)),
    Check("release-package", ("scripts/test_trial_pack.py",)),
    Check("business-files", ("scripts/test_business_reliability.py",)),
    Check("trace-artifacts", ("scripts/test_trace_artifacts.py",)),
    Check("storage-parent", ("scripts/test_storage_ensure_run.py",)),
    Check("offline-eval", ("-c", "from packing_assistant.runtime.eval_live import live_eval; "
          "v=live_eval(); assert v.get('verdict')=='offline_gate_pass', v; print(v['verdict'])")),
    Check("industry-eval", ("scripts/test_industry_agent_eval.py",)),
    Check("product-smoke", ("scripts/smoke_agent_product.py",), timeout=300),
)
FULL_CHECKS = (
    Check("http-demo", ("-m", "pytest", "demo/tests", "-q", "--basetemp=output/check-project-pytest")),
    Check("runtime-api", ("scripts/test_runtime_p0.py",)),
    Check("office-job", ("scripts/test_office_job.py",)),
    Check("pipeline", ("scripts/test_p0_p1_p2_full.py",), timeout=600),
    Check("shadow-eval", ("scripts/eval_workteams_cli.py", "--tiny-only"), timeout=600),
    Check("rust", ("test", "--locked", "--offline", "--manifest-path", "workbench/Cargo.toml"), "cargo", 900),
)


def check_environment() -> dict[str, str]:
    """Do not load personal model credentials or use paid model calls in checks."""
    env = dict(os.environ)
    for key in ("CIVIL_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "DEEPSEEK_API_KEY", "ZAI_API_KEY"):
        env.pop(key, None)
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHON_DOTENV_DISABLED="1", PYTHONOPTIMIZE="0",
               CIVIL_JOB_ROOT=str(ROOT / "output" / "check-project" / "jobs"))
    return env


def run_check(check: Check, env: dict[str, str]) -> tuple[bool, str]:
    executable = sys.executable if check.runtime == "python" else shutil.which(check.runtime)
    if not executable:
        return False, f"missing required runtime: {check.runtime}"
    started = time.monotonic()
    print(f"\n[RUN] {check.name}", flush=True)
    try:
        result = subprocess.run([executable, *check.args], cwd=ROOT, env=env, timeout=check.timeout)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {check.timeout}s"
    except OSError as exc:
        return False, f"could not start: {exc}"
    return result.returncode == 0, f"exit {result.returncode}, {time.monotonic() - started:.1f}s"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="also check API, packing pipeline and cached Rust build")
    parser.add_argument("--only", help="comma-separated check names (see --list)")
    parser.add_argument("--list", action="store_true", help="list checks without running them")
    args = parser.parse_args(argv)
    available = CHECKS + FULL_CHECKS
    selected = CHECKS + (FULL_CHECKS if args.full else ())
    if args.only is not None:
        names = {name.strip() for name in args.only.split(",") if name.strip()}
        unknown = names - {check.name for check in available}
        if not names or unknown:
            parser.error("--only requires known check names; unknown: " + ", ".join(sorted(unknown)))
        selected = tuple(check for check in available if check.name in names)
    if args.list:
        for check in available:
            print(f"{check.name:18} {check.runtime:6} {' '.join(check.args)}")
        return 0
    env = check_environment()
    results = []
    print(f"Civil Buddy checks · Python: {sys.executable}", flush=True)
    for check in selected:
        ok, detail = run_check(check, env)
        results.append((check.name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {check.name}: {detail}", flush=True)
    print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} checks passed", flush=True)
    for name, ok, detail in results:
        if not ok:
            print(f"  FAIL {name}: {detail}", flush=True)
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nChecks interrupted.", file=sys.stderr)
        raise SystemExit(130)
