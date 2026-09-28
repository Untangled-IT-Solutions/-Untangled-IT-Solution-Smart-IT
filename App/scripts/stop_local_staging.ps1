$ErrorActionPreference = "Stop"
$appRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$statePath = Join-Path $appRoot "cache\local-staging-processes.json"
if (-not (Test-Path -LiteralPath $statePath)) {
    throw "No local staging process file was found."
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($entry in @(
    @{ id = [int]$state.desktop_pid; started = [datetime]$state.desktop_started },
    @{ id = [int]$state.api_pid; started = [datetime]$state.api_started }
)) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process -and [math]::Abs(($process.StartTime.ToUniversalTime() - $entry.started.ToUniversalTime()).TotalSeconds) -lt 2) {
        Stop-Process -Id $process.Id
    }
}
Remove-Item -LiteralPath $statePath -Force
Write-Output "Local staging processes stopped."
