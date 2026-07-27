# 启动比赛演示用 FastAPI 网关（Agent API）
# 用法（仓库根目录）:
#   powershell -File scripts/start_gateway.ps1
# 浏览器: http://127.0.0.1:8000
# API 文档: http://127.0.0.1:8000/docs

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Starting gateway on http://127.0.0.1:8000 ..."
Write-Host "  /docs                  OpenAPI"
Write-Host "  POST /api/pipeline/trace   9-agent step trace"
Write-Host "  POST /api/team-a           Team A then confirm"
Write-Host "  POST /api/demo             full auto pipeline"
Write-Host ""

python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000 --reload
