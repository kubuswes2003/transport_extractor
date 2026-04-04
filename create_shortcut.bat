@echo off
echo Creating desktop shortcut...

set SCRIPT_DIR=%~dp0
set SHORTCUT_NAME=Transport Extractor
set TARGET=%SCRIPT_DIR%run_gui.bat

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\%SHORTCUT_NAME%.lnk'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Transport Extractor - agdar.it'; $s.Save()"

echo.
echo Desktop shortcut created!
echo Look for "Transport Extractor" on your Desktop.
pause
