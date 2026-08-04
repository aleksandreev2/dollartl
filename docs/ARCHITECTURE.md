# Architecture

## Services

- **api**: FastAPI, Telegram webhook and future Admin API.
- **worker**: outbox publications, user notifications, future Boosty sync and backups.
- **admin-web**: React/Vite Mini App frontend.
- **PostgreSQL**: sole source of durable business truth.
- **Redis**: disposable cache, locks, rate limits and queue coordination.
- **S3-compatible storage**: PDF, EPUB, raw files, covers, attachments and backups.

## Rules

1. Every schema change uses Alembic.
2. External writes are idempotent or have an idempotency record.
3. Redis loss must not lose business state.
4. Container filesystems are ephemeral.
5. Railway IDs are configuration, never domain identifiers.
6. External integrations live behind provider interfaces.
7. Audit-sensitive mutations write immutable audit events.
8. S3 is the file source of truth; Telegram `file_id` is only a cache.
9. Global access middleware runs before all user handlers.

## Current durable domains

- system configuration, audit log and outbox;
- users, legal consent, preferences and bans;
- titles, aliases and release packages;
- PDF/EPUB file families and immutable versions;
- title follows and download events;
- deep links, channel publications and per-user outbox delivery state.
