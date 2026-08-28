#!/usr/bin/env node
/**
 * Contest gate: `npm run check` must pass.
 * Runs secret scan + runtime middleware demo tests. No network. No API key.
 */
const { spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const py = process.env.PYTHON || process.env.PY || "python";

const steps = [
  [py, "scripts/scan_tracked_secrets.py"],
  [py, "scripts/test_stack_parity.py"],
  [py, "scripts/test_agent_middleware.py"],
  [py, "scripts/test_sandbox.py"],
  [py, "scripts/test_civil_codex.py"],
  [
    py,
    "-c",
    "from packing_assistant.runtime.eval_live import live_eval; v=live_eval(); assert v.get('verdict')=='offline_gate_pass', v; print(v['verdict'])",
  ],
  [py, "scripts/test_industry_agent_eval.py"],
];

let failed = 0;
for (const args of steps) {
  const label = args.slice(1).join(" ");
  const r = spawnSync(args[0], args.slice(1), {
    cwd: root,
    encoding: "utf8",
    stdio: "inherit",
    env: process.env,
  });
  const code = r.status == null ? 1 : r.status;
  if (code !== 0) {
    console.error("FAIL", label, "exit", code);
    failed = code || 1;
    break;
  }
}
if (failed) process.exit(failed);
console.log("PASS npm run check");
