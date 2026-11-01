# Windows PowerShell 5.1 compatible; use Setup-Windows.cmd.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$project = (Get-Location).Path
. "$PSScriptRoot\windows-prerequisites.ps1"
function Refresh-CommandPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}
function Find-Python {
    $candidates = @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe")
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notmatch 'WindowsApps') { $candidates += $command.Source }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            if (Test-StudioPython $candidate) { return $candidate }
        }
    }
    return $null
}
function Install-Package([string]$id, [string]$manualUrl) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Windows App Installer (winget) is missing. Install the prerequisite from $manualUrl and rerun setup, or install App Installer from Microsoft Store."
    }
    Write-Host "Installing $id. Windows may show an installer or administrator prompt."
    & winget.exe install --id $id --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Could not install $id. Install it from $manualUrl, then rerun Setup-Windows.cmd." }
    Refresh-CommandPath
}
Write-Host 'This sets up PDF Studio Pro on your own PC. Internet is required for installation.'
Write-Host 'Your documents will be processed locally. No hosting or Streamlit account is needed.'
$answer = Read-Host 'Install prerequisites and build the app? [Y/n]'
if ($answer -match '^(n|no)$') { throw 'Setup cancelled.' }
$python = Find-Python
if (-not $python) {
    Install-Package 'Python.Python.3.12' 'https://www.python.org/downloads/windows/'
    $python = Find-Python
    if (-not $python) { throw 'Python 3.12 was not found. Restart setup or install Python 3.12 from python.org.' }
}
$nodeReady = $false
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if ($node) {
    $nodeReady = Test-StudioNode $node.Source
}
if (-not $nodeReady) { Install-Package 'OpenJS.NodeJS.LTS' 'https://nodejs.org/' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm is not available. Restart Setup-Windows.cmd after installing Node.js LTS.' }
$extras = Read-Host 'Also install LibreOffice and Tesseract for Word conversion and OCR? [Y/n]'
if ($extras -notmatch '^(n|no)$') {
    if (-not (Test-Path "$env:ProgramFiles\LibreOffice\program\soffice.exe") -and -not (Get-Command soffice.exe -ErrorAction SilentlyContinue)) {
        Install-Package 'TheDocumentFoundation.LibreOffice' 'https://www.libreoffice.org/download/download-libreoffice/'
    }
    if (-not (Test-Path "$env:ProgramFiles\Tesseract-OCR\tesseract.exe") -and -not (Get-Command tesseract.exe -ErrorAction SilentlyContinue)) {
        Install-Package 'UB-Mannheim.TesseractOCR' 'https://tesseract-ocr.github.io/tessdoc/Installation.html'
    }
    Write-Host 'If OCR language packs are missing, install eng/ara in Tesseract. See the Windows guide.'
}
& "$PSScriptRoot\install.ps1" -PythonExecutable $python
$desktop = [Environment]::GetFolderPath('Desktop')
if ($desktop) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path $desktop 'PDF Studio Pro.lnk'))
        $shortcut.TargetPath = Join-Path $project 'Start-PDF-Studio.cmd'
        $shortcut.WorkingDirectory = $project
        $shortcut.Description = 'Open PDF Studio Pro privately on this PC'
        $shortcut.Save()
        Write-Host 'Desktop shortcut created: PDF Studio Pro'
    } catch { Write-Warning 'Shortcut creation failed. Use Start-PDF-Studio.cmd in the project folder.' }
}
Write-Host 'Ready. Double-click PDF Studio Pro on the desktop to start.'
