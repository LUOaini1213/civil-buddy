Set-Location $PSScriptRoot
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# CIVIL_HOST / CIVIL_PORT / CIVIL_TOKEN come from demo/.env (or the shell). 0.0.0.0 = phones on the same LAN.
python serve.py
