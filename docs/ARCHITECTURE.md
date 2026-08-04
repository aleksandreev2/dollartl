# Architecture

## Services

- **api**: FastAPI, Telegram webhook, future Admin API.
- **worker**: background schedules, broadcasts, file processing, Boosty sync and backups.
- **admin-web**: React/Vite Mini App frontend.
- **PostgreSQL**: sole source of durable business truth.
- **Redis**: disposable cache, locks, rate limits and queue coordination.
- **S3-compatible storage**: PDF, EPUB, raw files, covers, report attachments and backups.

## Rules

1. Every schema change uses Alembic.
2. Every external write must become idempotent before production.
3. Redis loss must not lose business state.
4. Container filesystems are ephemeral.
5. Railway IDs are configuration, never domain identifiers.
6. External integrations live behind provider interfaces.
7. Audit-sensitive mutations write immutable audit events.

## Initial tables

- `system_settings`
- `schema_metadata`
- `audit_log`
- `background_jobs`
- `outbox_events`
