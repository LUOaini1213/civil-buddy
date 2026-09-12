@echo off
setlocal
REM The current release is the Python product, not the legacy civil-workbench.exe.
cd /d "%~dp0"
if not exist "packing_assistant\civil.py" (
  echo Missing product files. Extract the full Python workbench zip first.
  exit /b 1
)
set PYTHONUTF8=1
if defined CIVIL_PYTHON goto selected
if exist ".venv\Scripts\python.exe" goto local
where py >nul 2>nul
if not errorlevel 1 goto pylauncher
where python >nul 2>nul
if not errorlevel 1 goto systempython
echo Python 3.10 or newer is required. Install Python, then run this launcher again.
echo Alternatively set CIVIL_PYTHON to an existing prepared python.exe.
exit /b 1
:selected
"%CIVIL_PYTHON%" "scripts\start_workbench.py" %*
exit /b %errorlevel%
:local
".venv\Scripts\python.exe" "scripts\start_workbench.py" %*
exit /b %errorlevel%
:pylauncher
py -3 "scripts\start_workbench.py" %*
exit /b %errorlevel%
:systempython
python "scripts\start_workbench.py" %*
exit /b %errorlevel%
