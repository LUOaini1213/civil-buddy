# Build civil-workbench.exe and stage a trial zip (kb + static + skill refs).
# Does not commit secrets. Does not default D:\layout.

param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$cargo = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path $cargo) { $env:Path = "$cargo;$env:Path" }

Write-Host "cargo build --release --bin civil-workbench"
Push-Location (Join-Path $Repo "workbench")
try {
    cargo build --release --bin civil-workbench
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

$exe = Join-Path $Repo "workbench\target\release\civil-workbench.exe"
if (-not (Test-Path $exe)) { throw "missing $exe" }

$stage = Join-Path $Repo "dist\civil-buddy-workbench"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

function Copy-Tree {
    param([string]$Src, [string]$Dst)
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    Get-ChildItem -LiteralPath $Src -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
    } | ForEach-Object {
        $rel = $_.FullName.Substring((Resolve-Path $Src).Path.Length).TrimStart('\')
        $target = Join-Path $Dst $rel
        $dir = Split-Path $target
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

Copy-Item $exe (Join-Path $stage "civil-workbench.exe")
Copy-Item (Join-Path $Repo "LICENSE") (Join-Path $stage "LICENSE")
Copy-Item (Join-Path $Repo ".env.example") (Join-Path $stage ".env.example")
Copy-Item (Join-Path $Repo "scripts\start-workbench.bat") (Join-Path $stage "start-workbench.bat")
Copy-Tree (Join-Path $Repo "demo\kb") (Join-Path $stage "demo\kb")
Copy-Tree (Join-Path $Repo "demo\static") (Join-Path $stage "demo\static")
Copy-Item (Join-Path $Repo "demo\.env.example") (Join-Path $stage "demo\.env.example")
Copy-Tree (Join-Path $Repo "skills\civil-buddy") (Join-Path $stage "skills\civil-buddy")

python -c @"
from pathlib import Path
import shutil
repo = Path(r'$Repo')
stage = Path(r'$stage')
trial = None
for p in repo.glob('*.md'):
    text = p.read_text(encoding='utf-8', errors='ignore')
    if 'CIVIL_JOB_ROOT' in text and 'CIVIL_API_KEY' in text and 'start-workbench.bat' in text:
        trial = p
        break
if trial is None:
    raise SystemExit('trial markdown not found at repo root')
shutil.copy2(trial, stage / trial.name)
print('copied', trial.name)
"@
if ($LASTEXITCODE -ne 0) { throw "failed to copy trial markdown" }

$readme = @"
Civil Buddy workbench $Version
Open the Chinese trial page at repo root (filename ends with .md).
1. Copy demo\.env.example to demo\.env
2. Fill CIVIL_API_KEY or OPENAI_API_KEY or DEEPSEEK_API_KEY
3. Optional: CIVIL_JOB_ROOT=your project folder (not D:\layout)
4. Double-click start-workbench.bat
"@
Set-Content -Path (Join-Path $stage "README.txt") -Value $readme -Encoding UTF8

$zip = Join-Path $Repo "dist\civil-buddy-workbench-$Version.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $Repo "dist\civil-buddy-workbench\*") -DestinationPath $zip -Force
Write-Host "staged $stage"
Write-Host "zip $zip"
Get-Item $exe, $zip | Select-Object FullName, Length
