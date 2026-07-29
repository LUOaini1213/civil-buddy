@echo off
chcp 65001 >nul
title 装箱拼柜 · 网关 :8000
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python
  pause
  exit /b 1
)

echo 启动网关 http://127.0.0.1:8000  (Ctrl+C 停止)
echo   前端:  http://127.0.0.1:8000/
echo   API:   http://127.0.0.1:8000/docs
echo   闭环:  POST /api/pipeline
echo.

REM 无管理员：从 .env / 默认指向本机 skjolber
if not defined SKJOLBER_URL set SKJOLBER_URL=http://127.0.0.1:8080
if not defined SKJOLBER_TIMEOUT_MS set SKJOLBER_TIMEOUT_MS=8000

python -c "import fastapi,uvicorn" 2>nul
if errorlevel 1 (
  echo 安装 fastapi uvicorn ...
  python -m pip install -q fastapi "uvicorn[standard]"
)

echo SKJOLBER_URL=%SKJOLBER_URL%
echo 请先另开窗口运行 启动skjolber.bat（可选，未起则自动回退 Python 3D）
echo.
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000 --reload
pause
