# Package the current Python workbench. Rust binaries are a separate, legacy product.
param(
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$')]
    [ValidateLength(5, 64)]
    [string]$Version = "0.9.0-preview"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$Builder = Join-Path $Repo "scripts\build_workbench_release.py"
# Packaging never deletes a staging tree. The builder writes a fresh, checked
# directory below this repository's dist/ and atomically replaces the zip.
if ($env:CIVIL_PYTHON) {
    & $env:CIVIL_PYTHON $Builder --version $Version
} elseif (Test-Path -LiteralPath (Join-Path $Repo ".venv\Scripts\python.exe")) {
    & (Join-Path $Repo ".venv\Scripts\python.exe") $Builder --version $Version
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Builder --version $Version
} else {
    & python $Builder --version $Version
}
if ($LASTEXITCODE -ne 0) { throw "Workbench packaging failed (exit $LASTEXITCODE)." }
