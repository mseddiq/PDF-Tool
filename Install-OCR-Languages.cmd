@echo off
setlocal
cd /d "%~dp0"
echo Installing official English and Arabic OCR language files for this Windows user.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-ocr-languages.ps1"
if errorlevel 1 (
 echo Installation failed. Read the error above and try again.
 pause
 exit /b 1
)
echo Finished. In PDF Studio, click Refresh OCR status.
pause
