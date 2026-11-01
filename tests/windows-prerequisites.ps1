param([string]$PythonPath = 'python', [string]$NodePath = 'node')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/windows-prerequisites.ps1"
# Exercise the same legacy native argument marshalling used by Windows PS 5.1
# when this test is run with PowerShell 7.
if (Get-Variable PSNativeCommandArgumentPassing -ErrorAction SilentlyContinue) {
    $PSNativeCommandArgumentPassing = 'Legacy'
}
if (-not (Test-StudioPython $PythonPath)) { throw 'Expected the supplied Python 3.12 executable to pass.' }
if (-not (Test-StudioNode $NodePath)) { throw 'Expected the supplied Node 22+ executable to pass.' }
if (Test-StudioPython $NodePath) { throw 'Node must not be accepted as Python.' }
if (Test-StudioNode $PythonPath) { throw 'Python must not be accepted as Node.' }
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('studio probe tests ' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    if ($env:OS -eq 'Windows_NT') {
        $bad = Join-Path $temporary 'broken python.cmd'
        Set-Content -LiteralPath $bad -Encoding ASCII -Value "@echo off`r`necho Broken interpreter 1>&2`r`nexit /b 7`r`n"
        $old = Join-Path $temporary 'old node.cmd'
        Set-Content -LiteralPath $old -Encoding ASCII -Value "@echo off`r`necho v20.19.0`r`nexit /b 0`r`n"
    } else {
        $bad = Join-Path $temporary 'broken python'
        Set-Content -LiteralPath $bad -Encoding ASCII -Value "#!/bin/sh`necho 'Broken interpreter' >&2`nexit 7`n"
        $old = Join-Path $temporary 'old node'
        Set-Content -LiteralPath $old -Encoding ASCII -Value "#!/bin/sh`necho v20.19.0`nexit 0`n"
        & chmod +x $bad $old
        if ($LASTEXITCODE -ne 0) { throw 'Could not prepare native command fixtures.' }
    }
    if (Test-StudioPython $bad) { throw 'A failed native command must be rejected.' }
    if (Test-StudioNode $old) { throw 'Node older than 22 must be rejected.' }
    if (Test-StudioPython (Join-Path $temporary 'missing.exe')) { throw 'A missing executable must be rejected.' }
    if ($ErrorActionPreference -ne 'Stop') { throw 'Probing must restore the caller error preference.' }
    Write-Output 'Passed: real Python/Node, wrong executable, stderr failure, missing executable, old Node, paths with spaces, caller error preference.'
} finally { Remove-Item -LiteralPath $temporary -Recurse -Force }
