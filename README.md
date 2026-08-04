# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a protected Russian administrative Mini App.

## Current version: v0.8 resilience and portability

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities, filtered nicknames and global bans;
- title catalogue, protected PDF + EPUB delivery and `@dollartranslate` publications;
- automatic Boosty tier `4041120` VIP access with seven-day grace period;
- comments, translation ratings, reports and mandatory validated raw files;
- protected Russian Admin Mini App for Telegram ID `2096975784`;
- idempotent publications and manual broadcasts;
- authenticated streaming AES-256-GCM PostgreSQL backups;
- automatic archive decryption and `pg_restore` validation;
- optional full restore tests in a disposable PostgreSQL database;
- incremental replication to an independent private backup S3 bucket;
- Telegram delivery or private presigned backup links;
- backup retention and abandoned temporary-file cleanup;
- API/worker heartbeats and dependency diagnostics;
- Redis worker leader lease for safe multi-replica deployment;
- persistent Telegram webhook update deduplication and retry recovery;
- PostgreSQL-locked Alembic migrations during Railway deploys;
- encrypted cross-account Railway export/import and exact-key S3 transfer.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `python scripts/migrate_locked.py`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`
5. Send `/admin` from Telegram after `ADMIN_WEB_URL` is configured.

## Backups

Scheduled backups remain disabled until a private backup bucket and offline encryption-key copy are ready. Then configure:

```text
BACKUP_ENABLED=true
BACKUP_ENCRYPTION_KEY=<strong random secret>
S3_BACKUP_BUCKET=<private bucket>
```

Open **Backup и health** in the Admin Mini App to trigger and inspect runs. See `docs/BACKUPS.md` before enabling a destructive `BACKUP_VERIFY_DSN` restore test.

## Production notes

- `TELEGRAM_WEBHOOK_SECRET` is mandatory with `APP_ENV=production`.
- Keep `BOOSTY_ENABLED=false` until the private Boosty API is smoke-tested with the creator account.
- Build `admin-web` with `VITE_API_BASE_URL` pointing at the public API service.
- Preserve `BACKUP_ENCRYPTION_KEY` and `BOOSTY_CREDENTIAL_KEY` outside Railway.
- Never allow old and new Railway projects to process the same Telegram bot during migration.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/BOOSTY.md`, `docs/COMMUNITY.md`, `docs/SUGGESTIONS.md`, `docs/ADMIN_MINI_APP.md`, `docs/BACKUPS.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
