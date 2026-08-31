@echo off
REM Civil Buddy trial launcher. Put next to civil-workbench.exe in the Release zip.
cd /d "%~dp0"
if not exist "demo\kb" (
  echo Missing demo\kb. Unzip the full Release pack, do not run the exe alone.
  pause
  exit /b 1
)
REM Missing demo\.env is no longer fatal: since v0.2.0 you can set the API key
REM in the UI ("Model" button, top right) and pick DeepSeek / z.ai / any
REM OpenAI-compatible endpoint without restarting. The .env is just a shortcut.
if not exist "demo\.env" (
  if exist "demo\.env.example" copy /Y "demo\.env.example" "demo\.env" >nul
  echo No API key found in demo\.env.
  echo Starting anyway - set the key in the browser via the "Model" button.
  echo See the Chinese trial page for details.
)
set CIVIL_DEMO_ROOT=%~dp0demo
civil-workbench.exe
if errorlevel 1 pause
