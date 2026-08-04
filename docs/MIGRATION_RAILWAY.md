# Migration to a different Railway account or project

The supported path is a clean destination deployment plus an encrypted database import and exact-key S3 transfer. Railway project IDs and service IDs are not stored in application data.

## 1. Preserve secrets

Before touching the source project, export these secrets to an offline password manager:

- `BACKUP_ENCRYPTION_KEY`;
- `BOOSTY_CREDENTIAL_KEY`;
- Telegram bot token and webhook secret;
- Boosty tokens/device ID;
- primary and backup S3 credentials;
- database credentials needed for the migration window.

Losing an encryption key may make existing encrypted records or backup archives unrecoverable.

## 2. Prepare destination

1. Deploy the exact same Git commit in the destination Railway project.
2. Create destination PostgreSQL and Redis.
3. Create destination primary and backup private buckets.
4. Configure all variables, but keep `MAINTENANCE_MODE=true`.
5. Do not point Telegram webhook at the destination yet.
6. Do not enable scheduled backups until import verification is complete.

## 3. Freeze source writes

1. Set `MAINTENANCE_MODE=true` on the source API.
2. Wait until active broadcasts, publications and backup runs finish.
3. Stop or scale the source worker to zero.
4. Confirm the Admin Mini App shows no `running` jobs.

Messages already delivered to Telegram cannot be revoked. Maintenance mode prevents new bot updates from changing state during export.

## 4. Create portable export

Run from the source application image/environment:

```text
scripts/migration_export.sh
```

The command creates:

```text
dollartl-<UTC timestamp>/
  database.dtlbak
  database-encryption.json
  storage-manifest.json
  storage-manifest.json.sha256
  SHA256SUMS
  README.txt
```

`database.dtlbak` is AES-256-GCM encrypted. Plaintext `pg_dump` data is deleted by the script trap.

Copy this directory through a secure channel. Do not put migration bundles in a public Git repository or public object bucket.

## 5. Transfer S3 objects

Set destination credentials in the source environment:

```text
DEST_S3_ENDPOINT_URL=...
DEST_S3_REGION=auto
DEST_S3_ACCESS_KEY_ID=...
DEST_S3_SECRET_ACCESS_KEY=...
DEST_S3_BUCKET=...
DEST_S3_FORCE_PATH_STYLE=true
```

Copy objects while preserving their exact keys:

```text
python scripts/storage_transfer.py copy \
  --manifest dollartl-<timestamp>/storage-manifest.json \
  --report dollartl-<timestamp>/storage-copy-report.json
```

Then verify destination contents. The content-hash mode downloads destination objects and is slower, but it is the strongest migration check:

```text
python scripts/storage_transfer.py verify \
  --manifest dollartl-<timestamp>/storage-manifest.json \
  --verify-content-hash \
  --report dollartl-<timestamp>/storage-verify-report.json
```

The command exits non-zero on any missing or mismatched object.

## 6. Import database

On the destination, using the same `BACKUP_ENCRYPTION_KEY`:

```text
scripts/migration_import.sh dollartl-<timestamp>
```

The importer:

1. verifies bundle SHA-256 files;
2. decrypts into an isolated temporary directory;
3. validates the PostgreSQL archive;
4. restores with `--clean --if-exists --exit-on-error`;
5. applies current Alembic migrations;
6. prints core row counts;
7. securely removes the temporary plaintext dump from the container filesystem.

The destination database named in `POSTGRES_DSN` is overwritten. Confirm the DSN before running the command.

## 7. Verify destination

Keep maintenance mode enabled and verify:

- `/health/ready` returns HTTP 200;
- current and expected Alembic heads match;
- API and worker heartbeats appear after the worker starts;
- title, release, user, comment, report and suggestion counts are plausible;
- several old PDF and EPUB files download successfully;
- raw files open from the Admin Mini App;
- Boosty links remain encrypted and readable;
- `@dollartranslate` configuration is correct;
- no manual broadcast is accidentally queued;
- a manual backup succeeds in the destination backup bucket.

For a destructive restore rehearsal, point `BACKUP_VERIFY_DSN` at a separate disposable database and run:

```text
scripts/verify_restore.sh dollartl-<timestamp>/database.dtlbak
```

## 8. Cut over Telegram

1. Configure the Telegram webhook to the destination API URL with the destination `TELEGRAM_WEBHOOK_SECRET`.
2. Send one private `/start` and `/admin` test.
3. Disable `MAINTENANCE_MODE` on the destination.
4. Keep the source API in maintenance mode and the source worker stopped.
5. Watch webhook receipts, worker heartbeat and error logs.

## 9. Rollback window

Keep the source project and migration bundle read-only until the destination has passed at least one complete operating cycle and one successful backup.

Rollback consists of stopping the destination worker, restoring the source webhook and disabling source maintenance mode. Do not allow both projects to process the same Telegram bot simultaneously.
