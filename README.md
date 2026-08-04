# Dollar TL

[![CI](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aleksandreev2/dollartl/actions/workflows/ci.yml)

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## Current version: v0.2 access foundation

- FastAPI webhook/API service
- aiogram bot dispatcher
- PostgreSQL + SQLAlchemy 2 + Alembic
- Redis-backed worker foundation
- S3-compatible storage adapter
- universal adult-content legal-age consent
- permanent `Anonymous <id>` identity
- user notification settings
- global temporary and permanent bans
- six-hour ban-notice throttling
- owner-only temporary admin commands for access management
- Docker Compose and Railway deployment configuration
- portable database and object-storage export/import scripts

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. Apply migrations with `alembic upgrade head`.
4. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Important

PostgreSQL is the source of truth. Redis is disposable. User files must be stored in S3-compatible object storage, never only on the container filesystem.

See `docs/ARCHITECTURE.md`, `docs/ACCESS_CONTROL.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
