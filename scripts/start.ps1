$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($directory in @('C:\Program Files\LibreOffice\program', 'C:\Program Files\Tesseract-OCR')) {
 if (Test-Path $directory) { $env:Path = "$directory;$env:Path" }
}
if (-not (Test-Path .venv\Scripts\python.exe)) { throw 'Run scripts/install.ps1 first.' }
if (-not (Test-Path frontend\dist\index.html)) { throw 'Build frontend first with npm ci and npm run build in frontend.' }
Start-Job { Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000' } | Out-Null
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
