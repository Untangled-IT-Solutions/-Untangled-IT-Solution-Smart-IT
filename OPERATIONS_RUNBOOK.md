# Untangled Nexus Operations Runbook

## Service objectives

- Core API availability: 99.9% monthly.
- Ordinary API p95 latency: below 500 ms.
- Notification delivery while connected: below 2 seconds.
- Recovery point objective: 1 hour.
- Recovery time objective: 4 hours.
- Desktop startup target: below 3 seconds on supported company hardware.

## Environments

Production and staging must use separate API services, MongoDB databases, secrets, and desktop configuration. Production data must never be copied into staging without approved redaction. Every release is promoted through staging after CI, smoke, migration, and backup checks.

## Monitoring and alerts

- Probe `/api/health` for process liveness and `/api/ready` for database readiness.
- Collect `/api/metrics` into the selected monitoring platform using the
  `X-Metrics-Token` header configured by `METRICS_TOKEN`.
- Alert when readiness fails twice, five-minute error rate exceeds 2%, p95 exceeds 1 second, or backup age exceeds the RPO.
- Forward structured API logs and desktop crash reports to the selected central error service.
- Preserve `X-Request-ID` in support tickets and downstream logs.

Real-time notification delivery currently uses an in-process event stream with
25-second desktop polling as its durability fallback. Keep the API at one
instance until a shared Redis pub/sub channel or MongoDB change-stream worker is
configured; deploy that shared channel before horizontal API scaling.

## Backup and restore

Use managed continuous MongoDB backups for the one-hour RPO. Run `scripts/backup_mongodb.ps1` for release and pre-migration snapshots. Encrypt archives at rest and retain checksums separately.

Restore tests must run monthly into an isolated database using `scripts/restore_mongodb.ps1`. Validate login, employee counts, unread notifications, active tasks, approvals, and audit history before recording the exercise as successful.

## Release procedure

1. CI must pass desktop, FastAPI, TypeScript backend, and website jobs.
2. Create and verify a current backup.
3. Deploy to staging and run core workflow smoke tests.
4. Deploy the API before desktop clients that require new routes.
5. Monitor readiness, errors, and latency for 30 minutes.
6. Roll back application code when error budgets are exceeded. Restore data only for confirmed corruption and only through the reviewed restore procedure.

## Incident priorities

- P1: login unavailable, data corruption, security incident, or core API outage.
- P2: a company workflow is unavailable with no reasonable workaround.
- P3: degraded performance or a partial feature failure.

For P1 incidents, stop deployments, preserve logs, assign an incident lead, communicate impact and next update time, and create a timeline using request IDs and audit events. Complete a blameless review with corrective actions after recovery.

## External configuration required

- Move production from a sleeping/free service to an always-on instance.
- Enable managed continuous backups and point-in-time recovery.
- Configure centralized logs, error tracking, uptime probes, and alert destinations.
- Configure company identity SSO and MFA before broad staff rollout.
- Store all production secrets in the hosting provider's secret manager.
