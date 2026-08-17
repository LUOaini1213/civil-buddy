Set-Location $PSScriptRoot
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn app:app --host 127.0.0.1 --port 8765
