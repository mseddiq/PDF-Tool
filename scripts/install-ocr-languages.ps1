param([string]$DataDirectory = '')
$ErrorActionPreference = 'Stop'
if (-not $DataDirectory) {
    $base = [Environment]::GetFolderPath('LocalApplicationData')
    if (-not $base) { throw 'Cannot find your local application data directory.' }
    $DataDirectory = Join-Path $base 'PDFStudioPro\tessdata'
}
$manifest = Get-Content -LiteralPath "$PSScriptRoot\ocr-models.json" -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Path $DataDirectory -Force | Out-Null
# Keep certificate validation enabled. Older Windows PowerShell needs TLS 1.2.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
foreach ($language in @('eng', 'ara')) {
    $destination = Join-Path $DataDirectory "$language.traineddata"
    $expected = $manifest.models.$language.sha256
    if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -eq $expected) {
        Write-Host "$language is already installed and verified."
        continue
    }
    $temporary = Join-Path $DataDirectory ([guid]::NewGuid().ToString('N') + '.partial')
    try {
        $url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$($manifest.revision)/$language.traineddata"
        Write-Host "Downloading official $language OCR data..."
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temporary
        if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $expected) {
            throw "Checksum verification failed for $language. No model was installed; retry the download."
        }
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        Write-Host "$language installed and verified."
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}
Write-Host "OCR data is ready in $DataDirectory"
Write-Host 'In PDF Studio, open OCR and click Refresh OCR status. No administrator copy is needed.'
