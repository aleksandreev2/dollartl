# Railway deployment

Create one Railway project with these services:

1. PostgreSQL;
2. Redis;
3. API from this repository using `railway.toml`;
4. worker from this repository using `railway.worker.toml`;
5. Admin web from `admin-web/Dockerfile`;
6. S3-compatible bucket/provider.

Set all variables from `.env.example` through Railway variables. Never commit real secrets.

Required for v0.3 publication:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_BOT_USERNAME` without or with `@`;
- `TELEGRAM_CHANNEL_USERNAME=@dollartranslate`;
- the bot must be an administrator in the channel with permission to post;
- S3 credentials and bucket;
- PostgreSQL and Redis URLs.

`TELEGRAM_API_BASE_URL` is optional. Set it only when a separate local Bot API Server is deployed for large-file workflows.

The API and worker both run `alembic upgrade head` before startup. The worker consumes publication outbox events; running more than one worker is not recommended until distributed event claiming is introduced.
