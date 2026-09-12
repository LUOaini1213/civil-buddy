#!/usr/bin/env node
// Keep the check inventory in Python; npm is a cross-platform launcher only.
const { existsSync } = require("fs");
const { spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const localPython = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON || process.env.PY || (existsSync(localPython) ? localPython : "python");
const result = spawnSync(python, ["scripts/check_project.py", ...process.argv.slice(2)], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
});
if (result.error) console.error(`Cannot start Python (${python}): ${result.error.message}`);
process.exit(result.status == null ? 1 : result.status);
