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
# 可选：20 轮真实+随机物料（较慢，设 RUN_ROUND20=1 开启）
if ($env:RUN_ROUND20 -eq "1") {
  python scripts/run_round20_materials.py --seed 20260730
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Host "ALL_COMPETITION_SMOKE_PASS" -ForegroundColor Green
Write-Host "Reports: output/phase0/BASELINE_REPORT.md + output/competition/SCORECARD.md"
Write-Host "Round20 (optional): output/round20/ROUND20_REPORT.md"
