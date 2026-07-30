# 比赛一键冒烟（Windows）
# 用法: powershell -File scripts/competition_smoke.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONUNBUFFERED = "1"

Write-Host "== competition smoke ==" -ForegroundColor Cyan
python -c "from packing_assistant.config import HARNESS_VERSION; print('harness', HARNESS_VERSION)"
$env:ANCHOR_SKIP_PIPELINE = "1"
$env:PACKING_SKIP_SKJOLBER = "1"
$env:PACKING_FINALIZE_LLM = "0"
python scripts/test_mid50_cog.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/test_search_knowledge.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/test_adversarial_competition.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/test_anchor_t80_long_mix.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/test_booking_volume_metrics.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/test_hitl_resume_competition.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/run_phase0_baseline.py --quick
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/eval_workteams_cli.py --tiny-only
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/eval_competition_scorecard.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "ALL_COMPETITION_SMOKE_PASS" -ForegroundColor Green
Write-Host "Reports: output/phase0/BASELINE_REPORT.md + output/competition/SCORECARD.md"
