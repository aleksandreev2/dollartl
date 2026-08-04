# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## Current version: v0.3 catalogue foundation

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities;
- global temporary and permanent bans;
- title catalogue, search and latest releases;
- title pages and chapter-package subpages;
- PDF + EPUB as one validated release;
- automatic chapter-range detection for PDF and EPUB;
- S3 originals plus Telegram `file_id` delivery cache;
- protected direct downloads for enabled accounts;
- assigned Boosty links for standard accounts;
- followed-title library and release notifications;
- deep links from `@dollartranslate` into exact titles or releases;
- idempotent outbox delivery foundation;
- Docker Compose and Railway deployment configuration;
- portable database and object-storage export/import scripts.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Temporary owner commands

Until the Russian Admin Mini App is delivered:

```text
/title_create English | Original | Language | ongoing | Boosty URL | Description
/title_cover <title_slug>                 (caption on an image)
/release_create <title_slug> <1-20> [Boosty URL]
/attach_file <release_uuid> <pdf|epub>   (caption on a document)
/release_override <release_uuid> <reason>
/publish_title <title_slug>
/publish_release <release_uuid>
/download_access <telegram_id> on|off
```

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
