param(
    [int]$Port = 10001
)

$ErrorActionPreference = "Stop"
$appRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent $appRoot
$apiRoot = Join-Path $repoRoot "untangled-nexus-api-main"
$statePath = Join-Path $appRoot "cache\local-staging-processes.json"
$apiOut = Join-Path $appRoot "logs\local-staging-api.out.log"
$apiErr = Join-Path $appRoot "logs\local-staging-api.err.log"

$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python -or -not $pythonw) {
    throw "python.exe and pythonw.exe must be available on PATH."
}

python -c "import mongomock_motor" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Install local staging dependencies: python -m pip install -r untangled-nexus-api-main/requirements-dev.txt"
}

New-Item -ItemType Directory -Force -Path (Split-Path $statePath), (Split-Path $apiOut) | Out-Null
$password = "Stg!Aa9-" + [guid]::NewGuid().ToString("N").Substring(0, 16)
$env:NODE_ENV = "staging"
$env:LOCAL_EPHEMERAL_DB = "true"
$env:LOCAL_EPHEMERAL_ACK = "localhost-only"
$env:NEXUS_STAGING_PASSWORD = $password
$env:MONGODB_DB = "untangled_its_staging_ephemeral"

$api = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $apiRoot -WindowStyle Hidden `
    -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($api.HasExited) { break }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/ready" -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    Get-Content $apiErr -Tail 30 -ErrorAction SilentlyContinue
    throw "Local staging API did not become ready."
}

$env:API_BASE_URL = "http://127.0.0.1:$Port"
$env:ENVIRONMENT = "staging"
$env:APP_CHANNEL = "staging"
$desktop = Start-Process -FilePath $pythonw `
    -ArgumentList ('"' + (Join-Path $appRoot "main.py") + '"') `
    -WorkingDirectory $appRoot -PassThru

@{
    api_pid = $api.Id
    api_started = $api.StartTime.ToUniversalTime().ToString("O")
    desktop_pid = $desktop.Id
    desktop_started = $desktop.StartTime.ToUniversalTime().ToString("O")
} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8

Write-Output "Untangled Nexus [STAGING] is running locally."
Write-Output "API: http://127.0.0.1:$Port"
Write-Output "Temporary password: $password"
Write-Output "Accounts: director@staging.local, lead@staging.local, operations@staging.local, staff@staging.local, intern@staging.local"
Write-Output "Stop with: pwsh App/scripts/stop_local_staging.ps1"
