# Employer Test EXE — Backend API deployment

The employer-test desktop application is now designed as:

    Employer EXE -> HTTPS Backend API -> MongoDB

The EXE does NOT connect directly to MongoDB and must never contain the MongoDB URI or password.

## Backend

On the server hosting the Backend project:

1. Copy `.env.example` to `.env`.
2. Set `MONGODB_URI` to the real MongoDB connection string.
3. Set `PORT` (default `5001`).
4. Set `NODE_ENV=production`.
5. Run `npm install`.
6. Run `npm start`.

The backend must be reachable by the employer's Windows PC over HTTPS. A reverse proxy such as IIS/Nginx/Cloudflare can terminate TLS and forward to port 5001.

## Desktop EXE

Before building the EXE, set the backend URL in the EXE deployment configuration:

    API_BASE_URL=https://your-backend-domain.example

The supplied client reads `API_BASE_URL` from a `.env` beside the EXE. For a true one-file employer distribution, replace the placeholder with your production API URL in `backend_api_client.py` before running PyInstaller, or add it as a build-time environment variable in your deployment process.

Do NOT put `MONGODB_URI` in the desktop `.env`.

## Login

The backend verifies:

- user exists
- user is active
- user is linked to an employee
- employee is active
- password is correct

An inactive employee is blocked immediately at login and again when an API session is used.

## Timer

The desktop timer calls:

- `/api/attendance/status`
- `/api/attendance/today`
- `/api/attendance/clock-in`
- `/api/attendance/clock-out`
- `/api/attendance/break/start`
- `/api/attendance/break/end`

The backend writes attendance to MongoDB. The desktop app caches non-live totals so the 1-second timer does not hammer the server.

## Employer testing

The employer only needs:

- Windows
- the EXE
- internet access to the backend
- an active employee account supplied by your administrator

They do not need Python, VS Code, MongoDB, MongoDB Compass, or your MongoDB credentials.
