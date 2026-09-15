# Phase 7 status — canonical roles and management accounts

## Result

The Phase 7 implementation is complete. Live account provisioning remains an
operations step because this workspace contains no FastAPI `.env`, MongoDB
connection, or temporary management passwords.

## Canonical role decision

The existing shared model defines these roles:

1. Director
2. Branch Manager
3. Business Lead
4. Operations Manager
5. Staff
6. Intern

`Business Lead` and `Branch Manager` are separate canonical roles. For Benny
Moremi, the provisioning process preserves whichever of those roles is already
stored on his existing employee or linked account. It aborts rather than
inventing a combined or duplicate role.

The required results are:

- Zandile Joana Maredi — Director
- Benny Moremi — existing Business Lead or Branch Manager
- Ubuntu Hadebe — Operations Manager

Desktop account administration now uses the same canonical admin set as the
backend: Director, Branch Manager, Operations Manager, with Super Admin retained
as a server-level compatibility role. Business Lead is not treated as an account
administrator.

## Safe provisioning

`untangled-nexus-api-main/app/management_provisioning.py` and
`scripts/provision_management_accounts.py` provide a preview-first, server-side
workflow. It:

- finds existing employees by exact identity and never inserts employees;
- aborts on missing or ambiguous employee records;
- aborts on multiple accounts or a username belonging to another employee;
- updates an existing linked account or creates one account when absent;
- uses employee/account email unless an explicit username environment variable
  is supplied;
- accepts temporary passwords only from environment variables;
- requires at least 12 characters and never prints passwords or hashes;
- stores PBKDF2-SHA256 password hashes and removes legacy plaintext/hash fields;
- sets accounts active and `require_password_change=true`;
- revokes existing sessions after a reset;
- can be rerun without duplicating employee or account records.

Preview:

```text
python scripts/provision_management_accounts.py
```

Apply after reviewing the preview and setting temporary password variables:

```text
python scripts/provision_management_accounts.py --apply
```

Required process environment variables are
`NEXUS_ZANDILE_TEMP_PASSWORD`, `NEXUS_BENNY_TEMP_PASSWORD`, and
`NEXUS_UBUNTU_TEMP_PASSWORD`. They must be supplied on the server and removed
after provisioning. Password-change enforcement from Phase 5 prevents access to
business routes until each user replaces the temporary password.

## Verification

- Full FastAPI suite: 17 passed
- Provisioning tests: 3 passed
- Desktop auth/data-boundary tests: 7 passed
- Python compilation: passed
- Production-source plaintext-password scan: no matches

Tests prove that all three original employee IDs remain unchanged, user count
stays at three after a repeat run, Benny's existing Branch Manager role is
preserved, invalid Benny roles are rejected, ambiguous employees are rejected,
passwords verify against PBKDF2 hashes, and plaintext password fields are absent.

## Operational boundary

No live database mutation was attempted. Running the preview and apply commands
requires the server-only `MONGODB_URI` and three temporary passwords. These
secrets must not be copied into the desktop project or committed files.

## Separation status

App/Website separation was implemented in Phase 2 and reinforced in Phase 6:

- `App/` → dedicated `untangled-nexus-api-main/` FastAPI service;
- `Website/` → separate `Backend/` Node service;
- neither backend is bundled into the desktop executable;
- the Website was not modified during Phases 6 or 7.

## Next phase

Phase 8 should enforce the requested action-level authorization on FastAPI and
test every role against both allowed and denied operations.
