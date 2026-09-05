# Untangled Nexus (Desktop)

Internal operations desktop client for Untangled IT Solutions.

- **UI:** CustomTkinter (Python 3.12)
- **Data:** Backend HTTPS API only (MongoDB stays on the server)
- **Release:** Git tag → GitHub Actions → Windows installer

---

## Release process (only supported path)

```bash
# 1. Develop and test locally
# 2. Commit
git add .
git commit -m "Release Untangled Nexus v1.1.0"
git push origin main

# 3. Wait for CI (tests) on main to pass

# 4. Tag and push the tag
git tag v1.1.0
git push origin v1.1.0
```

GitHub Actions then:

1. Validates the tag (`vMAJOR.MINOR.PATCH` only)
2. Writes `app/__version__.py` from the tag
3. Installs Python 3.12 + dependencies
4. Runs automated tests
5. Builds `UntangledNexus.exe` with PyInstaller
6. Builds `Untangled-Nexus-Setup-1.1.0.exe` with Inno Setup
7. Creates a **GitHub Release** and attaches the installer

Employees install from the **GitHub Release** asset — not WhatsApp, not manual uploads.

### Never

- Manually upload installers to the release
- Manually replace installers on a server
- Send installers via WhatsApp
- Edit multiple version numbers by hand
- Reuse or move an already published tag
- Release from a failed CI run

---

## Versioning

**Single source of truth:** `app/__version__.py`

CI overwrites that file from the git tag. Everything else imports it:

```python
from app.__version__ import __version__
# or
from app.utils.config import APP_VERSION  # same value
```

Tags must match:

| Valid | Invalid |
|-------|---------|
| `v1.0.0` | `1.0.0` |
| `v1.1.0` | `v1.1` |
| `v2.0.0` | `version1.0.0` |

---

## Architecture

```text
Desktop (CustomTkinter)
        │  HTTPS
        ▼
Backend API
        │
        ▼
MongoDB
```

The desktop application does **not** open MongoDB connections and does **not** ship database credentials.

---

## Configuration

Copy `.env.example` to `.env` for local overrides:

```text
API_BASE_URL=https://untangled-nexus-api.onrender.com
ENVIRONMENT=production
```

- **production:** uses `API_BASE_URL` (or production default). No silent localhost fallback.
- **development:** may use localhost and optional fallback for developer convenience only.

---

## Local development

```powershell
python -m venv .venv
.\\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Run tests:

```powershell
pip install pytest
python -m pytest tests/ -q
```

Optional local Windows package (no GitHub Release):

```powershell
pwsh scripts/build_windows.ps1 -Version 1.1.0-local
```

---

## Project layout

```text
untangled_nexus_prod/
├── main.py
├── requirements.txt
├── UntangledNexus.spec
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── installer/untangled_nexus.iss
├── scripts/build_windows.ps1
├── tests/
└── app/
    ├── __version__.py
    ├── application.py
    ├── controllers/
    ├── services/
    ├── views/
    └── utils/
```

---

Built for Untangled IT Solutions. Keep the repository **private**.
