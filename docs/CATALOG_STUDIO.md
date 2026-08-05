# Catalog Studio v0.10.1

Catalog Studio is the administrative workspace for title and release lifecycle management.

## Safety model

- Every metadata edit stores an immutable pre-change revision.
- Updates require `expected_updated_at`; stale sessions receive HTTP 409.
- Title unpublish cascades to published releases and disables their deep links.
- File rollback only switches the active version; historical objects remain intact.
- Inactive file cleanup always starts with dry-run, excludes current versions and versions referenced by downloads, rechecks candidates under a PostgreSQL advisory lock, and uses an idempotency key.
- Batch retry of failed channel publications also requires dry-run and an idempotency key.

## Routes

All routes are under `/admin/api/catalog` and require normal Admin Mini App authentication.

- `GET /titles`
- `GET|PUT /titles/{id}`
- `POST /titles/{id}/cover`
- `POST /titles/{id}/publication`
- `POST /titles/{id}/rollback/{revision_id}`
- `GET /titles/{id}/preview`
- `GET|PUT /releases/{id}`
- `POST /releases/{id}/files/{pdf|epub}`
- `POST /releases/{id}/publication`
- `POST /releases/{id}/rollback/{revision_id}`
- `POST /file-versions/{id}/activate`
- `GET /releases/{id}/preview`
- `POST /files/cleanup`
- `GET /channel/failed-publications`
- `POST /channel/retry-failed`

## Migration

Alembic revision `20260805_0010` adds immutable title/release revision tables and a per-file inspection table used when activating an older PDF or EPUB version.
