$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($directory in @("$env:ProgramFiles\LibreOffice\program", "$env:ProgramFiles\Tesseract-OCR")) {
    if (Test-Path $directory) { $env:Path = "$directory;$env:Path" }
}
if (-not (Test-Path .venv\Scripts\python.exe)) { throw 'Double-click Setup-Windows.cmd first.' }
if (-not (Test-Path frontend\dist\index.html)) { throw 'App build is missing. Double-click Setup-Windows.cmd again.' }
$url = 'http://127.0.0.1:8000'
# Refuse to open an unrelated service already occupying the app port.
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8000)
try { $listener.Start() } catch {
    $existing = $null
    try { $existing = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2 -Proxy $null } catch { }
    if ($existing -and $existing.app -eq 'PDF Studio Pro') {
        Start-Process $url
        Write-Host 'Opened the PDF Studio Pro instance already running on this PC.'
        exit 0
    }
    throw 'Port 8000 is already in use. Close the previous app console window before starting this version.'
} finally { $listener.Stop() }
$python = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
$process = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000') -NoNewWindow -PassThru
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($process.HasExited) { throw 'PDF Studio stopped before startup. Read the error above, or rerun setup.' }
        try {
            $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2 -Proxy $null
            if ($health.status -eq 'ok' -and $health.app -eq 'PDF Studio Pro') { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'App startup timed out. Close this window and try again.' }
    Write-Host "PDF Studio Pro is running privately at $url"
    Write-Host 'Keep this window open while using the app. Press Ctrl+C to stop it.'
    Start-Process $url
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw 'The app stopped unexpectedly. Read the error above.' }
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
}
