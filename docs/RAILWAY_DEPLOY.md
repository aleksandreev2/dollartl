# Railway deployment

Create one Railway project with these services:

1. PostgreSQL;
2. Redis;
3. API from this repository using `railway.toml`;
4. worker from this repository using `railway.worker.toml`;
5. Admin web from `admin-web/Dockerfile`;
6. primary private S3-compatible bucket;
7. separate private backup S3 bucket, preferably in another account/provider.

## API and worker

Both services use `scripts/migrate_locked.py` as the pre-deploy command. It holds a PostgreSQL advisory lock around `alembic upgrade head`, so simultaneous API and worker deployments cannot race the schema migration.

The API readiness endpoint verifies both database connectivity and an exact match between the database Alembic revision and the code migration head:

```text
GET /health/ready
```

A stale schema returns HTTP 503 and prevents Railway from considering the API ready.

The worker uses a Redis leader lease. Multiple replicas may run, but only the current leader processes publications, broadcasts, Boosty tasks, cleanup and backups. Every replica records a heartbeat, and the Admin Mini App marks stale services.

## Required production variables

Set every applicable variable from `.env.example`. At minimum:

```text
APP_ENV=production
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
TELEGRAM_WEBHOOK_BASE_URL=https://<api-domain>
TELEGRAM_BOT_USERNAME=...
TELEGRAM_CHANNEL_USERNAME=@dollartranslate
ADMIN_TELEGRAM_ID=2096975784
ADMIN_WEB_ORIGIN=https://<admin-domain>
ADMIN_WEB_URL=https://<admin-domain>
DATABASE_URL=...
DATABASE_URL_SYNC=...
POSTGRES_DSN=...
REDIS_URL=...
S3_ENDPOINT_URL=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET=...
```

`TELEGRAM_WEBHOOK_SECRET` is mandatory when `APP_ENV=production`. The API refuses webhook traffic if it is missing.

Build the Admin web service with:

```text
VITE_API_BASE_URL=https://<api-domain>
```

Never set `VITE_ADMIN_DEVELOPMENT_ID` in production.

## Enable backups

After the backup bucket and offline key copy are ready:

```text
BACKUP_ENABLED=true
BACKUP_ENCRYPTION_KEY=<random secret, at least 32 bytes>
S3_BACKUP_BUCKET=<private backup bucket>
BACKUP_REPLICATION_ENABLED=true
```

Configure `BACKUP_S3_*` variables when the backup bucket uses different credentials or a different provider.

`BACKUP_VERIFY_DSN` is optional. It must point only to a disposable PostgreSQL database that the worker is allowed to wipe during restore tests.

See `docs/BACKUPS.md` before enabling this variable.

## Telegram webhook

After the API is healthy, configure Telegram with:

```text
URL: https://<api-domain>/telegram/webhook
secret_token: TELEGRAM_WEBHOOK_SECRET
```

Webhook update IDs are persisted. Completed duplicates are acknowledged without running handlers again; failed or stale receipts may be retried.

## S3 and large files

`TELEGRAM_API_BASE_URL` is optional. Configure a local Bot API Server only when direct Telegram upload beyond the standard cloud Bot API limits is required.

Published files and user uploads remain in the primary private bucket. Database backups, backup manifests and the incremental object mirror belong in the backup bucket.

## Deployment sequence

1. Create PostgreSQL, Redis and both private buckets.
2. Configure API and worker variables.
3. Deploy the API and wait for `/health/ready`.
4. Deploy the worker and verify a fresh worker heartbeat in the Admin Mini App.
5. Deploy Admin web with the API build variable.
6. Configure Telegram webhook and the `/admin` Mini App URL.
7. Publish a test title/release in maintenance mode or a private test environment.
8. Trigger one manual backup.
9. Download it and run `scripts/verify_restore.sh`.
10. Enable scheduled backups only after the manual run succeeds.

## Production smoke checks

- `/health/live` reports v0.8.0;
- `/health/ready` reports the expected Alembic revision;
- `/admin` opens only for Telegram ID `2096975784`;
- API and worker heartbeats are fresh;
- a duplicate webhook update is not processed twice;
- one PDF/EPUB package can be published and downloaded;
- a manual broadcast reaches only its selected audience;
- a manual encrypted backup reaches Telegram or produces a private link;
- backup S3 contains database archive, manifests and `storage-mirror/` objects.
