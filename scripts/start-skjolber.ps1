# 启动 skjolber Spring Boot 服务（需 JDK17+ 与 Maven）
# 用法: powershell -File scripts/start-skjolber.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "skjolber-service")

Write-Host "Building & running skjolber-service on :8080 ..."
mvn -q -DskipTests spring-boot:run
