# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## Current version: v0.5 community and feedback

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities and optional filtered nicknames;
- global temporary and permanent bans;
- title catalogue, releases, protected PDF + EPUB delivery and channel publications;
- automatic Boosty tier `4041120` VIP access with seven-day grace period;
- global Donate button on title pages;
- one-time `Thank you.` acknowledgement before subscriber download buttons appear;
- separate comments for titles and chapter packages;
- `[VIP]` comment display for active and grace-period members;
- automatic racist-slur replacement in comments and feedback;
- 1–5 translation ratings with mandatory categories and written feedback;
- report flow for broken files, chapter problems, metadata and Boosty access;
- owner moderation commands until the Russian Admin Mini App is delivered;
- portable PostgreSQL and S3 export/import scripts.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Temporary community moderation commands

```text
/comment_delete <uuid>
/comment_restore <uuid>
/rating_status <uuid> <new|reviewed|in_progress|fixed|dismissed> [note]
/report_status <uuid> <open|in_progress|resolved|rejected>
/report_reply <uuid> | <reply>
/community_stats
```

Boosty uses an undocumented private API. Keep `BOOSTY_ENABLED=false` until the creator credentials and endpoint behavior have been tested against the real account. API failures preserve the last confirmed access state.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/BOOSTY.md`, `docs/COMMUNITY.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
