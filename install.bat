@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PDFTOMD_INSTALL_DIR=%~dp0"
set "PDFTOMD_LAUNCHER=%~dp0pdftomd.bat"

echo Preparing the virtual environment...
python -m venv .venv
if errorlevel 1 goto :error

echo Installing Docling. The first run can take a few minutes...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Adding pdftomd to the Send to menu...
powershell.exe -NoProfile -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut((Join-Path $env:APPDATA 'Microsoft\Windows\SendTo\pdftomd.lnk')); $shortcut.TargetPath = $env:PDFTOMD_LAUNCHER; $shortcut.WorkingDirectory = $env:PDFTOMD_INSTALL_DIR; $shortcut.Description = 'Convert selected PDFs to Markdown'; $shortcut.Save()"
if errorlevel 1 goto :error

echo.
echo Installation complete.
echo Usage: select PDFs, then right-click ^> Send to ^> pdftomd.
exit /b 0

:error
echo.
echo Installation failed.
exit /b 1
