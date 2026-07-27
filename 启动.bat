@echo off
chcp 65001 >nul
title 装箱拼柜 · 启动器
cd /d "%~dp0"

echo.
echo  ========================================
echo   智能装箱与拼柜 · 启动器
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

python scripts\launcher.py %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo 退出码 %EXITCODE%
  pause
)
exit /b %EXITCODE%
