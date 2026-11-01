# Use --version instead of inline -c/-p scripts: Windows PowerShell 5.1's
# legacy native argument passing can strip quotes inside script arguments.
function Get-StudioNativeVersion([string]$FilePath) {
    $previousPreference = $ErrorActionPreference
    try {
        # A broken candidate may write to stderr. Treat it as an unusable
        # candidate, rather than letting Stop abort the entire installer.
        $ErrorActionPreference = 'Continue'
        $output = & $FilePath --version 2>&1
        if ($LASTEXITCODE -ne 0) { return $null }
        return ($output | ForEach-Object { $_.ToString() }) -join "`n"
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Test-StudioPython([string]$FilePath) {
    $version = Get-StudioNativeVersion $FilePath
    return $null -ne $version -and $version.Trim() -match '^Python 3\.12\.\d+$'
}

function Test-StudioNode([string]$FilePath) {
    $version = Get-StudioNativeVersion $FilePath
    if ($null -ne $version -and $version.Trim() -match '^v(\d+)\.\d+\.\d+$') {
        return [int]$Matches[1] -ge 22
    }
    return $false
}
