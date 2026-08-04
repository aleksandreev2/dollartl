# Encrypted backups and restore verification

Dollar TL v0.8 creates authenticated, encrypted PostgreSQL backups and incrementally mirrors application objects to a separate S3-compatible bucket.

## Enable scheduled backups

Backups are disabled until production secrets are configured. Set:

```text
BACKUP_ENABLED=true
BACKUP_ENCRYPTION_KEY=<random secret of at least 32 bytes>
S3_BACKUP_BUCKET=<separate private bucket>
```

The default schedule is one backup every 168 hours. The worker stores eight successful copies and removes database archives older than 90 days. Audit rows remain after object retention deletes the archived bytes.

Never change or lose `BACKUP_ENCRYPTION_KEY`. Existing `.dtlbak` files cannot be recovered without it. Preserve this key outside Railway together with the bot token, Boosty credential-encryption key and S3 credentials.

## Independent backup provider

By default, the backup bucket uses the primary S3 endpoint and credentials. A different account or provider can be configured with:

```text
BACKUP_S3_ENDPOINT_URL=
BACKUP_S3_REGION=auto
BACKUP_S3_ACCESS_KEY_ID=
BACKUP_S3_SECRET_ACCESS_KEY=
BACKUP_S3_FORCE_PATH_STYLE=true
```

Using a physically separate account/provider is preferred. The backup bucket must remain private.

## Encryption format

`.dtlbak` is a Dollar TL container using:

- AES-256-GCM per chunk;
- HKDF-SHA256 key derivation with a random salt;
- a unique nonce for every chunk;
- authenticated metadata;
- final plaintext size and SHA-256 validation.

The database dump is streamed in chunks and is never loaded entirely into memory. Temporary plaintext files live only under `BACKUP_TEMP_DIR` and are removed after each run. The worker also cleans abandoned temporary directories older than `BACKUP_TEMP_RETENTION_HOURS`.

## Verification levels

Every successful run performs:

1. `pg_dump` custom archive creation;
2. encryption;
3. complete decryption into a separate temporary file;
4. plaintext SHA-256 comparison;
5. `pg_restore --list` validation.

This is reported as `database_archive_verified=true`.

A full restore test requires a dedicated disposable PostgreSQL database:

```text
BACKUP_VERIFY_DSN=postgresql://...
```

The verification database is wiped with `pg_restore --clean --if-exists`. Never point this variable at production. When configured, the worker restores the archive and verifies `alembic_version`, producing `restore_verified=true`.

Without `BACKUP_VERIFY_DSN`, the panel correctly reports `archive-level only`; it does not pretend that a full restore was tested.

## S3 mirror

When `BACKUP_REPLICATION_ENABLED=true`, every source object is mirrored under:

```text
storage-mirror/<original object key>
```

Object keys are immutable in normal Dollar TL workflows. Existing matching objects are skipped using source ETag and size metadata. Every run writes a snapshot manifest and verifies destination object sizes.

The mirror is not deleted by database-backup retention. This protects objects that were later removed from the primary bucket.

## Telegram delivery

The encrypted database archive is sent to Telegram administrator `2096975784` when it is below `BACKUP_TELEGRAM_MAX_BYTES`.

For a larger archive, the bot sends a protected message containing a private presigned download URL. The default URL lifetime is 24 hours. The permanent copy remains in the private backup bucket and can be downloaded again from the Admin Mini App.

## Manual backup

Open the Russian Admin Mini App, choose **Backup и health**, then press **Создать backup сейчас**. Only one queued or running backup can exist at once.

## CLI verification

Archive-only verification:

```text
scripts/verify_restore.sh backup.dtlbak
```

Full restore test into a disposable database:

```text
BACKUP_VERIFY_DSN=postgresql://... scripts/verify_restore.sh backup.dtlbak
```

## Failure behavior

A database, encryption, S3 or verification failure marks the run as `failed` and sends an administrator warning. Telegram-delivery failure does not invalidate an otherwise successful backup; it is shown separately as `telegram_delivery_status=failed` and the archive remains available in backup S3.
