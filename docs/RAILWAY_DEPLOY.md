# Railway deployment

Create one Railway project with these services:

1. PostgreSQL
2. Redis
3. API from this repository using `railway.toml`
4. Worker from this repository using `railway.worker.toml`
5. Admin web from `admin-web/Dockerfile`
6. S3-compatible bucket/provider

Set all variables from `.env.example` through Railway variables. Never commit real secrets.

The API service runs `alembic upgrade head` before deployment and exposes `/health/ready`.
The worker runs the same migration command before startup; migrations are designed to be safe when invoked repeatedly.
