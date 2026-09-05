# Local Windows build (same steps as CI, without publishing a GitHub Release)
# Usage:  pwsh scripts/build_windows.ps1 -Version 1.1.0-local

param(
    [string]$Version = "1.0.0-local"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

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
pyinstaller --noconfirm --clean UntangledNexus.spec

if (-not (Test-Path "dist\UntangledNexus\UntangledNexus.exe")) {
    throw "PyInstaller did not produce UntangledNexus.exe"
}

$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Write-Host "==> Inno Setup" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path "dist\installer" | Out-Null
    & $iscc "/DMyAppVersion=$Version" "installer\untangled_nexus.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    $installer = "dist\installer\Untangled-Nexus-Setup-$Version.exe"
    if (-not (Test-Path $installer)) { throw "Installer missing: $installer" }
    Write-Host "Installer: $installer" -ForegroundColor Green
} else {
    Write-Host "Inno Setup not installed – skipping installer. EXE folder: dist\UntangledNexus\" -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
