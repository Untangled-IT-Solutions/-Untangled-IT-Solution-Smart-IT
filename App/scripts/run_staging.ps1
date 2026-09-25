param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ApiUrl
)

$ErrorActionPreference = "Stop"
$productionUrl = "https://untangled-nexus-api.onrender.com"
$normalizedUrl = $ApiUrl.TrimEnd("/")
if ($normalizedUrl -eq $productionUrl) {
    throw "The staging launcher refuses to use the production API URL."
}

$appRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
    throw "pythonw.exe was not found on PATH."
}

$env:API_BASE_URL = $normalizedUrl
$env:ENVIRONMENT = "staging"
$env:APP_CHANNEL = "staging"

Start-Process `
    -FilePath $python `
    -ArgumentList ('"' + (Join-Path $appRoot "main.py") + '"') `
    -WorkingDirectory $appRoot

Write-Output "Started Untangled Nexus [STAGING] against $normalizedUrl"
