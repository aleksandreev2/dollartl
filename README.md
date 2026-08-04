# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## Current version: v0.6 title suggestions

- universal adult-content legal-age consent;
- permanent `Anonymous <id>` identities and optional filtered nicknames;
- global temporary and permanent bans;
- title catalogue, protected PDF + EPUB delivery and channel publications;
- automatic Boosty tier `4041120` VIP access with seven-day grace period;
- Donate and one-time `Thank you.` acknowledgement;
- comments, translation ratings and reports;
- versioned prohibited-content rules for title suggestions;
- Standard quota: 1 submitted suggestion per calendar month;
- VIP/grace quota: 5 submitted suggestions per calendar month;
- Standard translation scope capped at chapters 1–200;
- optional private raw file and official cover up to 20 MB;
- archive safety, checksum, duplicate and antivirus-hook foundations;
- suggestion statuses Under Review, Accepted, Translated and Rejected;
- owner moderation commands until the Russian Admin Mini App is delivered;
- portable PostgreSQL and S3 export/import scripts.

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Temporary suggestion commands

```text
/suggestion_list [under_review|accepted|translated|rejected|all]
/suggestion_show <uuid>
/suggestion_status <uuid> <accepted|rejected|translated> [linked_title_uuid] | public reason | internal note
/suggestion_restore_slot <uuid> [reason]
```

Boosty uses an undocumented private API. Keep `BOOSTY_ENABLED=false` until the creator credentials and endpoint behavior have been tested against the real account. API failures preserve the last confirmed access state.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/CATALOG.md`, `docs/BOOSTY.md`, `docs/COMMUNITY.md`, `docs/SUGGESTIONS.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
