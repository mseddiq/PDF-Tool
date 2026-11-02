# Allow only the exact private HTTPS hostname served by your own Tailscale node.
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$hostname = (Read-Host 'Enter your PC Tailscale hostname only (example: my-pc.example.ts.net)').Trim().ToLowerInvariant()
if ($hostname -notmatch '^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.ts\.net$') {
    throw 'Enter the exact hostname ending in .ts.net, without https:// or a path.'
}
[IO.File]::WriteAllText((Join-Path $project '.studio-private-host'), $hostname)
Write-Host 'Saved. Restart PDF Studio Pro, then run: tailscale serve --bg http://127.0.0.1:8000'
Write-Host 'Use Tailscale Serve only, not Funnel. Your PC must stay on to use the app from your phone.'
