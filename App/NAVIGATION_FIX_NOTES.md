# Navigation Fix Notes

This build fixes the sidebar navigation lifecycle without replacing the existing application.

## Changes
- Navigation role/item calculation is cached and no longer re-queries account state on every click.
- Duplicate navigation requests are guarded while a navigation callback is executing.
- MainWindow logs every sidebar navigation click.
- Sidebar rows are clickable in addition to their button and icon.
- TimerWidget is explicitly isolated from navigation ownership.
- AppController reports successful view activation and returns navigation status.
- Existing workspace remains visible if a replacement view cannot be displayed.
- Dashboard refreshes use the existing view instead of rebuilding the dashboard.
- Dashboard refresh remains guarded against overlapping API calls.

## Verification
- Python compileall check passed.
- Static navigation route test passed for all 15 Director destinations.
- Existing application smoke test completed previously for local service functionality.

A real GUI/backend end-to-end test still depends on the machine's installed Python dependencies and the configured backend API.
