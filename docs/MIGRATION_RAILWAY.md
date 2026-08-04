# Migration to a different Railway account/project

The supported path is a clean deployment into a new Railway project.

## Prepare

1. Deploy the same Git revision in the destination project.
2. Configure destination PostgreSQL, Redis and S3 credentials.
3. Keep the destination API in maintenance mode.

## Export

1. Enable maintenance mode on the source.
2. Run `scripts/db_export.sh`.
3. Run `scripts/storage_export.py`.
4. Copy or replicate S3 objects to the destination provider.
5. Preserve `.dump`, manifests and SHA-256 files.

## Import

1. Run `scripts/db_import.sh <dump>` against destination PostgreSQL.
2. Import/replicate objects without changing object keys.
3. Compare row counts, object counts and checksums.
4. Run smoke tests.
5. Switch Telegram webhook to the new API domain.
6. Verify `@dollartranslate`, Boosty and Admin Mini App access.
7. Disable maintenance mode.
8. Keep the old project read-only until verification is complete.

Railway project IDs and service IDs are never required by the application data model.
