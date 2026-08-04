# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a protected Russian administrative Mini App.

## Current version: v0.7 Admin Mini App and broadcasts

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities, filtered nicknames and global bans;
- title catalogue, protected PDF + EPUB delivery and `@dollartranslate` publications;
- automatic Boosty tier `4041120` VIP access with seven-day grace period;
- Donate and one-time `Thank you.` acknowledgement;
- comments, translation ratings and reports;
- Standard/VIP monthly title-suggestion quotas;
- **mandatory validated raw file for every submitted title suggestion**;
- protected Russian React + TypeScript Admin Mini App for Telegram ID `2096975784`;
- title/release creation, file validation and publication without CLI;
- users, bans, suggestions, comments, ratings, reports, Boosty and audit views;
- idempotent manual broadcasts with audiences, scheduling, photos, buttons and retries;
- portable PostgreSQL and S3 export/import scripts.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`
5. Send `/admin` from Telegram after `ADMIN_WEB_URL` is configured.

## Production notes

- Keep `BOOSTY_ENABLED=false` until the private Boosty API is smoke-tested with the creator account.
- Build `admin-web` with `VITE_API_BASE_URL` pointing at the public API service.
- Preserve encryption and backup keys when migrating Railway accounts.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/BOOSTY.md`, `docs/COMMUNITY.md`, `docs/SUGGESTIONS.md`, `docs/ADMIN_MINI_APP.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
