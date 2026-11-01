param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command $PythonExecutable -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12+ from python.org and enable Add Python to PATH.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 LTS or newer, then reopen PowerShell.' }
& $PythonExecutable -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
 npm.cmd ci --no-audit --no-fund
 if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
 npm.cmd run build
 if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Installed. Install LibreOffice and Tesseract with English/Arabic language packs for conversion and OCR.'
Write-Host 'Launch with: powershell -ExecutionPolicy Bypass -File scripts/start.ps1'
