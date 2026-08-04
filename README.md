# Dollar TL

Telegram distribution bot for Dollar TL with an English reader interface and a Russian administrative Mini App.

## v0.1 foundation

- FastAPI webhook/API service
- aiogram bot dispatcher
- PostgreSQL + SQLAlchemy 2 + Alembic
- Redis-backed worker foundation
- S3-compatible storage adapter
- Docker Compose development environment
- Railway deployment configuration
- portable database and object-storage export/import scripts
- CI for linting, typing, tests, migrations and container builds

## Local start

1. Copy `.env.example` to `.env` and fill required values.
2. Run `docker compose up --build`.
3. API health endpoints:
   - `GET http://localhost:8000/health/live`
   - `GET http://localhost:8000/health/ready`

## Important

PostgreSQL is the source of truth. Redis is disposable. User files must be stored in S3-compatible object storage, never only on the container filesystem.

See `docs/ARCHITECTURE.md`, `docs/RAILWAY_DEPLOY.md` and `docs/MIGRATION_RAILWAY.md`.
