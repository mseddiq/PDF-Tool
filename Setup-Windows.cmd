@echo off
setlocal
cd /d "%~dp0"
echo PDF Studio Pro - first-time setup
echo Keep this window open until setup finishes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
if errorlevel 1 (
 echo Setup could not finish. Read the message above for the next step.
 pause
 exit /b 1
)
echo Setup finished. Double-click Start-PDF-Studio.cmd or the desktop shortcut.
pause
