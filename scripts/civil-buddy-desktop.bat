@echo off
REM Double-click local desktop window. Not Tencent WorkBuddy.
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0civil-buddy-desktop.ps1" %*
