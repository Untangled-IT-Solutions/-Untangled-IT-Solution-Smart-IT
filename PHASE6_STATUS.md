# Phase 6 status — central source of truth

## Result

Phase 6 is complete. The Nexus desktop uses the dedicated FastAPI service for
business data and has no direct MongoDB or SQLite runtime path.

## Desktop boundary

- Removed the dormant direct-Mongo fallback implementations from Quote
  Management and Order Management.
- Replaced the retired duplicate Work view with compatibility imports; normal
  Work navigation continues to use the API-backed Task view.
- Removed the unused `bson.ObjectId` dependency from legacy desktop payload
  models. Backend IDs are strings at the desktop boundary.
- Removed obsolete database service fields from navigation composition.
- Quote/order load and write failures now remain visible failures; they do not
  switch to another data store.
- Attendance may reuse a successful response for 12 seconds. If refresh fails,
  the returned copy is marked `stale` and includes `sync_error`.
- The general API cache stores only successful GET responses in memory for
  45–120 seconds and never acts as an offline write store.

## SQLite audit

`App/app` has no `sqlite3` import, SQLite connection, database file, repository,
or dependency. The only match was an obsolete `SearchResult` docstring; it now
describes a backend search. There was therefore no SQLite data to migrate or
delete.

## FastAPI contracts added

The existing `quotes` and `orders` MongoDB collections remain server-side. The
dedicated Nexus API now provides authenticated and role-scoped routes for:

- quote and order assignment/unassignment;
- quote and order status changes with allowed-state validation;
- quote replies;
- requesting, reading, and submitting director availability reviews;
- the current desktop route shapes plus API-client compatibility aliases.

Updates use the existing revision-based compare-and-set helper and append audit
history. Management controls assignment. Non-management users can access or
update only records assigned to their authenticated employee identity. Only a
Director or Super Admin can submit a director review.

The public Website and Node backend were not changed.

## Regression protection

`App/tests/test_data_boundary.py` fails if desktop source introduces a MongoDB,
Motor, BSON, or SQLite driver import; a direct collection/client call; or a
MongoDB credential key. FastAPI workflow coverage verifies authorization and
durable quote/order mutations against the API test database.

## Verification

- Desktop: `59 passed`
- FastAPI: `14 passed`
- Python compilation: passed for desktop and FastAPI
- Static desktop database scan: no matches

The FastAPI test warnings come from `mongomock`'s deprecated `utcnow()` use and
ReportLab's Python compatibility probe; they are outside application code.

## Next phase

Phase 7 should inspect the canonical role model and safely enable login accounts
for the three named management employees without duplicating employee records.
