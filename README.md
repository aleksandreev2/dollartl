# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## Current version: v0.4 Boosty access

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities;
- global temporary and permanent bans;
- title catalogue, releases, PDF + EPUB delivery and `@dollartranslate` publications;
- Telegram ↔ Boosty linking through a one-time direct-message code;
- automatic tier `4041120` membership checks;
- VIP access to all files;
- seven-day grace period after confirmed membership loss;
- API-error degraded mode that never removes existing access;
- encrypted persistence of rotated Boosty tokens;
- manual Boosty linking fallback for the owner;
- Docker Compose and Railway deployment configuration;
- portable PostgreSQL and S3 export/import scripts.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Important

Boosty uses an undocumented private API. Keep `BOOSTY_ENABLED=false` until the creator credentials and endpoint behavior have been tested against the real account. API failures preserve the last confirmed access state.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/BOOSTY.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
