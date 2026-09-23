param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$mongoUri = $env:MONGODB_URI
if ([string]::IsNullOrWhiteSpace($mongoUri)) {
    throw "MONGODB_URI must be set in the process environment."
}
if (-not (Get-Command mongodump -ErrorAction SilentlyContinue)) {
    throw "mongodump is not installed. Install MongoDB Database Tools first."
}

$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$archive = Join-Path $resolvedOutput "nexus-$timestamp.archive.gz"

& mongodump --uri=$mongoUri --archive=$archive --gzip
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archive)) {
    throw "MongoDB backup failed."
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
$checksum = "$hash  $([IO.Path]::GetFileName($archive))"
Set-Content -LiteralPath "$archive.sha256" -Value $checksum -Encoding ascii
Write-Output $archive
