# 启动 FastAPI 网关 + 静态 Vue2 前端
# 用法: powershell -File scripts/start-gateway.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not $env:SKJOLBER_URL) {
  $env:SKJOLBER_URL = "http://127.0.0.1:8080"
  Write-Host "SKJOLBER_URL default -> $env:SKJOLBER_URL (若服务未启动将本地回退)"
}

python -m pip install -q fastapi "uvicorn[standard]"
Write-Host "Gateway http://127.0.0.1:8000"
python -m uvicorn gateway.app:app --host 0.0.0.0 --port 8000 --reload
