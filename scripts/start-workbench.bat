@echo off
REM Civil Buddy trial launcher. Put next to civil-workbench.exe in the Release zip.
cd /d "%~dp0"
if not exist "demo\kb" (
  echo Missing demo\kb. Unzip the full Release pack, do not run the exe alone.
  pause
  exit /b 1
)
if not exist "demo\.env" (
  if exist "demo\.env.example" copy /Y "demo\.env.example" "demo\.env" >nul
  echo Fill demo\.env with CIVIL_API_KEY or OPENAI_API_KEY or DEEPSEEK_API_KEY, then run again.
  echo See 给试用的人.md
  notepad "demo\.env"
  pause
  exit /b 1
)
set CIVIL_DEMO_ROOT=%~dp0demo
civil-workbench.exe
if errorlevel 1 pause
