@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PDF_RECEIPT_INSTALL_DIR=%~dp0"
set "PDF_RECEIPT_LAUNCHER=%~dp0pdf-receipt.bat"

echo Preparing the virtual environment...
python -m venv .venv
if errorlevel 1 goto :error

echo Installing Docling. The first run can take a few minutes...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Adding pdf-receipt to the Send to menu...
powershell.exe -NoProfile -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut((Join-Path $env:APPDATA 'Microsoft\Windows\SendTo\pdf-receipt.lnk')); $shortcut.TargetPath = $env:PDF_RECEIPT_LAUNCHER; $shortcut.WorkingDirectory = $env:PDF_RECEIPT_INSTALL_DIR; $shortcut.Description = 'Convert selected PDFs to Markdown'; $shortcut.Save()"
if errorlevel 1 goto :error

echo.
echo Installation complete.
echo Usage: select PDFs, then right-click ^> Send to ^> pdf-receipt.
exit /b 0

:error
echo.
echo Installation failed.
exit /b 1
