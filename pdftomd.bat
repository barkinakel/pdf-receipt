@echo off
setlocal
set "PDFTOMD_LAUNCH_DIR=%CD%"
cd /d "%~dp0"
set PYTHONUTF8=1
set HF_HUB_DISABLE_XET=1
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

if not exist ".venv\Scripts\python.exe" (
  echo Run install.bat first.
  pause
  exit /b 1
)

set PYTHONPATH=%~dp0src
".venv\Scripts\python.exe" -m pdftomd %*
set EXITCODE=%errorlevel%

rem Keep the drag-and-drop window open so the error stays readable.
if not "%EXITCODE%"=="0" (
  echo.
  echo Finished with an error. Read the message before closing this window.
  pause
)
exit /b %EXITCODE%
