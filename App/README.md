# Untangled Nexus (Desktop)

Internal operations desktop client for Untangled IT Solutions.

- **UI:** CustomTkinter (Python 3.12)
- **Data:** Dedicated Nexus FastAPI over HTTPS (MongoDB stays on the server)
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
Dedicated Nexus FastAPI (../untangled-nexus-api-main)
        │
        ▼
MongoDB
```

The desktop application does **not** open MongoDB connections and does **not** ship database credentials.

The public Website uses the separate Node service in `../Backend`. See
`../ARCHITECTURE.md` for configuration and the staged compatibility boundary.

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


## UI network work (Phase 4)

All API work belongs in a worker. The existing `app/utils/async_tasks.py`
dispatcher now uses queue delivery only; workers must never call `after`,
`winfo_*` or widget methods. Call `run_in_background(owner, operation, success,
error)` from Tk for simple operations. Completion is discarded when the owner
has been destroyed. Existing Dashboard and attendance queues remain supported.

For forms with dependent API calls, `app/utils/ui_tasks.py` provides explicit
continuations without moving widget construction into worker threads:

```python
@ui_task
def save(self):
    title = self.title_entry.get()  # Tk thread
    try:
        result = yield RemoteCall(self.controller.save, title)  # worker
        self.status.configure(text="Saved")  # Tk thread again
        yield from ui_steps(self.refresh)
    except BackendAPIError as exc:
        self.status.configure(text=str(exc))
```

Use `ui_steps` for dependent decorated helpers. Do not send a lambda that reads
widgets to `run_in_background`; capture its inputs first. Task action lambdas
instead yield a `RemoteCall` and are driven by `action_steps` on Tk. A view/form
allows one active workflow, prevents duplicate mutations and queues the latest
refresh/filter request. Loading overlays are scoped to the view, so navigation
and the surrounding window remain responsive. Constructors that fetch menus
show a loading view and finish building after the response arrives.

`BackendAPIClient.request` rejects attempts to perform I/O on an active Tk main
thread. Transport errors are surfaced in the application even when a legacy
service catches them. Expired sessions are queued back to Tk with a token check,
and repeated expiry responses produce one sign-in prompt.

Login and startup use the same worker boundary. The login button is disabled
while a request is pending and restored after failure. Accounts marked
`require_password_change` cannot open the main window: Nexus presents a private
password-change dialog and calls `/api/auth/change-password` in a worker. Closing
that dialog revokes the temporary session. Passwords are never written to local
files or logs, and the temporary password is cleared from widgets and dialog
state when the flow finishes.

Run `python -m pytest tests -q` with the desktop requirements and pytest installed.
The GUI tests require a working Tcl/Tk runtime and a desktop session. They create
hidden Tk windows and a localhost HTTP server with a four-second response delay;
they never contact the production API. They also check screen loading, callback
threads, duplicate actions, destroyed views, errors/retry and session expiry.
