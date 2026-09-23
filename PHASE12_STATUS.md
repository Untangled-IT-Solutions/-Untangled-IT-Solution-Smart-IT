# Phase 12 — Document Expiry

Status: **Complete**

## Expiry tracking

Documents now expose and persist:

- document type
- employee identity
- expiry date
- expiry status
- expiry window
- days until expiry
- last expiry-check timestamp

The supported states are:

- `expired`
- `expiring` within 7 days
- `expiring` within 30 days
- `valid`
- `no_expiry`
- `invalid` for malformed legacy dates

The 7-day and 30-day boundaries are inclusive. A document expiring today is in the 7-day warning window; it becomes expired after its expiry date passes.

## Scanning

- Expiring uploads are classified and notified immediately.
- Changing an expiry date immediately recalculates status and creates the appropriate alert.
- A background server task scans existing documents when the API starts and every six hours thereafter.
- Authorized management can run `POST /api/documents/expiry-scan`.
- Authorized management can read a side-effect-free summary from `GET /api/documents/expiry-summary`.
- A compound MongoDB index supports expiry-status queries.

## Notifications

- The document owner receives expiry alerts.
- Director, Branch Manager, Operations Manager, and Super Admin accounts receive management alerts.
- Alert IDs contain the document ID, expiry date, warning window, and recipient identity.
- Repeated scans use MongoDB upserts and do not recreate or unread an existing alert.
- A document can correctly generate one 30-day warning, one 7-day warning, and one expired alert as time advances.
- Changing the expiry date marks old unread alerts as superseded and starts a new idempotent alert cycle.
- Dashboard refreshes do not run the scanner or create notifications.

## Validation

- FastAPI suite: **27 passed**
- Desktop suite: **67 passed**
- Compilation checks passed for the expiry scanner, database indexes, notification helpers, API lifecycle, and document router.

Coverage verifies all expiry boundaries, persisted status, role-restricted scans and summaries, immediate alerts, owner and management delivery, repeat-scan idempotency, dashboard-refresh idempotency, and renewed-expiry alert cycles.
