# Desktop EXE API

The Windows desktop application should talk to this backend over HTTPS/HTTP instead of connecting directly to MongoDB.

## Authentication

`POST /api/auth/login`

```json
{"username":"employee@example.com","password":"employee-password"}
```

The backend checks:

1. user exists in MongoDB `users`
2. user status is active
3. user links to MongoDB `employees`
4. employee status is active
5. stored password hash matches

It returns a short-lived bearer session token. MongoDB credentials never go to the EXE.

## Session

`GET /api/auth/me`

Header:
`Authorization: Bearer <token>`

`POST /api/auth/logout`

## Timer / attendance

All require `Authorization: Bearer <token>`:

- `GET /api/attendance/status`
- `GET /api/attendance/today`
- `POST /api/attendance/clock-in`
- `POST /api/attendance/clock-out`
- `POST /api/attendance/break/start`
- `POST /api/attendance/break/end`

The backend stores attendance in MongoDB using the same fields used by the desktop application's Mongo attendance service: `employee_id`, `work_date`, `clock_in_at`, `clock_out_at`, `break_started_at`, `break_duration_minutes`, `hours_worked`, and `status`.

## Deployment

1. Copy `.env.example` to `.env` on the backend server.
2. Put the real MongoDB URI only on the backend server.
3. Run `npm install`.
4. Run `npm start`.
5. Configure the EXE with the backend base URL, not a MongoDB URI.

The distributed backend source intentionally does not contain the previous MongoDB credential.
