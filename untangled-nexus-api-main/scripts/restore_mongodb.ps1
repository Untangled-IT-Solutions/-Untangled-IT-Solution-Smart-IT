param(
    [Parameter(Mandatory = $true)]
    [string]$Archive,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedSha256,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) {
    throw "Restore is destructive. Re-run with -ConfirmRestore after verifying the target environment."
}
$mongoUri = $env:MONGODB_RESTORE_URI
if ([string]::IsNullOrWhiteSpace($mongoUri)) {
    throw "MONGODB_RESTORE_URI must target the reviewed restore environment."
}
if (-not (Get-Command mongorestore -ErrorAction SilentlyContinue)) {
    throw "mongorestore is not installed. Install MongoDB Database Tools first."
}

$resolvedArchive = (Resolve-Path -LiteralPath $Archive).Path
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedArchive).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256.Trim().ToLowerInvariant()) {
    throw "Backup checksum does not match. Restore cancelled."
}

& mongorestore --uri=$mongoUri --archive=$resolvedArchive --gzip --drop
if ($LASTEXITCODE -ne 0) {
    throw "MongoDB restore failed."
}
