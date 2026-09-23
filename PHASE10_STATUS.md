# Phase 10 — Attendance

Status: **Complete**

## Preserved attendance flow

- Clock in
- Start break
- End break
- Clock out
- Current status
- Personal attendance history
- Read-only team attendance
- Working-now totals

## State rules

- A fresh workday begins in `not_started`.
- Clock in is allowed once per Johannesburg work date.
- Break start requires an active clocked-in session.
- Break end requires an active break.
- Clock out requires an active session with no open break.
- A completed day cannot be reopened or changed.
- Attendance actions always use the authenticated employee identity.
- Director, Branch Manager, Operations Manager, and Super Admin may view team attendance.
- Business Lead, Staff, and Intern accounts cannot view team attendance.

## Time calculations

- The API supplies all attendance event timestamps in UTC.
- Work dates are determined using `Africa/Johannesburg`.
- The desktop renders event times in Johannesburg local time.
- Clock-out stores exact break seconds, net work seconds, and net hours worked.
- The live desktop work timer subtracts completed breaks and freezes during an active break.
- Working-now totals distinguish employees actively working from employees on break.

## Desktop corrections

- The manager employee selector was replaced with a read-only team attendance panel.
- Managers can no longer be led into trying to clock another employee in or out.
- Personal attendance controls always act on the signed-in employee.
- Clock In remains disabled after the day's shift has been completed.
- Team status shows working, on-break, and daily-record totals.

## Validation

- FastAPI suite: **24 passed**
- Desktop suite: **65 passed**
- Python compilation checks passed for all changed attendance modules.

Coverage verifies server timestamps, Johannesburg work dates, forged employee rejection, every invalid transition, active-break clock-out rejection, break-aware net hours, status/history responses, role-scoped team visibility, working-now counts, and desktop break-timer behavior.
