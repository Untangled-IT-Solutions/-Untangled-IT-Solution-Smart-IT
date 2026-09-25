# Local Windows build (same steps as CI, without publishing a GitHub Release)
# Usage:  pwsh scripts/build_windows.ps1 -Version 1.1.0

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use release format X.Y.Z (for example 1.1.0)."
}

Write-Host "==> Version $Version" -ForegroundColor Cyan
@"
"""Application version – local build."""

__version__ = "$Version"
"@ | Set-Content -Encoding utf8 app\__version__.py

Write-Host "==> Installing build deps" -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller==6.11.1 pytest

Write-Host "==> Tests" -ForegroundColor Cyan
python -m pytest tests/ -q --tb=short
if ($LASTEXITCODE -ne 0) { throw "Tests failed – refusing to build" }

Write-Host "==> PyInstaller" -ForegroundColor Cyan
python scripts\write_version_info.py
python -m PyInstaller --noconfirm --clean UntangledNexus.spec

if (-not (Test-Path "dist\UntangledNexus\UntangledNexus.exe")) {
    throw "PyInstaller did not produce UntangledNexus.exe"
}

Write-Host "==> Updater" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --onefile --windowed --name updater app\services\updater.py
if (-not (Test-Path "dist\updater.exe")) { throw "PyInstaller did not produce updater.exe" }
Copy-Item -Force "dist\updater.exe" "dist\UntangledNexus\updater.exe"

$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($iscc) {
    Write-Host "==> Inno Setup" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path "dist\installer" | Out-Null
    & $iscc "/DMyAppVersion=$Version" "installer\untangled_nexus.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    $installer = "dist\installer\Untangled-Nexus-Setup-$Version.exe"
    if (-not (Test-Path $installer)) { throw "Installer missing: $installer" }
    $hash = (Get-FileHash -Algorithm SHA256 -Path $installer).Hash.ToLower()
    Set-Content -Path "$installer.sha256" -Value "$hash  Untangled-Nexus-Setup-$Version.exe" -Encoding ascii
    Write-Host "Installer: $installer" -ForegroundColor Green
} else {
    Write-Host "Inno Setup not installed – skipping installer. EXE folder: dist\UntangledNexus\" -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
