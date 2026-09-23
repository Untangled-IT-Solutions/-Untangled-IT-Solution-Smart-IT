# Phase 15 — EXE and Updates

Status: **Implementation complete; local installer execution restricted by Windows policy**

## Desktop package

- `UntangledNexus.exe` builds successfully with PyInstaller.
- The final EXE starts, remains responsive, and reports product version `1.0.0`.
- The distribution contains 1,661 desktop runtime files and is approximately 82.75 MB.
- No Website, Node, Backend, Nexus API source, `node_modules`, `package.json`, or secret `.env` file is packaged.
- The production API URL defaults to the dedicated Nexus API and remains configurable through `API_BASE_URL`.
- Local development URLs are enabled only through explicit development configuration.

## Installer

- Inno Setup produced `Untangled-Nexus-Setup-1.0.0.exe` successfully.
- Installer size: approximately 42.57 MB.
- The installer contains the desktop application and standalone updater.
- The generated SHA256 checksum matches the installer.
- The installer reports product version `1.0.0` and file version `1.0.0.0`.
- A pre-final installer build completed an isolated installation successfully.
- Windows Application Control blocked execution of the final rebuilt unsigned installer on this machine. The final installer therefore has build and checksum verification here, while install execution must be completed on an allowed machine or after release signing.

## Updates

- Startup and manual update checks remain asynchronous.
- Only the exact installer for the advertised release is accepted.
- A trusted GitHub HTTPS URL and matching SHA256 asset are mandatory.
- The updater is copied to a temporary staging directory before launch so the installer can replace the installed updater safely.
- After a successful silent install, the updater explicitly restarts `UntangledNexus.exe`.
- The local build script now builds and bundles `updater.exe`, supports system or per-user Inno Setup, validates release version format, and generates the checksum.

## Release workflow

The existing tag-triggered GitHub Actions release workflow remains in place and verifies tests, application version, desktop build, updater build, installer build, checksum generation, and GitHub Release upload. It contains no Website build or packaging step.

## Validation

- Desktop suite: **76 passed**
- Final EXE launch: **passed**
- Final EXE responsiveness: **passed**
- Version reporting: **1.0.0** in application metadata and Windows properties
- Package separation: **passed**
- Installer compilation: **passed**
- Installer checksum: **passed**
- Update selection, download verification, staging, installation orchestration, and restart tests: **passed**

One orphaned updater smoke-test process was placed in Windows session 0 by the blocked installer test. Windows denied termination from this session; it will clear on the next Windows restart.
