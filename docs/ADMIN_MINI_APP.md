# Russian Admin Mini App

v0.7 replaces the temporary CLI workflow with a mobile-first React + TypeScript Mini App and a protected FastAPI administration API.

## Authentication

Every `/admin/api/*` request sends Telegram Web App `initData` through `X-Telegram-Init-Data`. The server verifies the HMAC signature with the bot token, checks `auth_date`, extracts the signed user object and requires exact equality with `ADMIN_TELEGRAM_ID=2096975784`.

No browser-provided identity is trusted without signature validation. `X-Admin-Development-Id` is accepted only when `APP_ENV=development`.

## Railway

Deploy the API/worker and `admin-web` as separate services.

Build `admin-web` with:

```text
VITE_API_BASE_URL=https://<api-service-domain>
```

Configure the API with:

```text
ADMIN_WEB_ORIGIN=https://<admin-service-domain>
ADMIN_WEB_URL=https://<admin-service-domain>
ADMIN_INIT_DATA_TTL_SECONDS=86400
```

`ADMIN_WEB_URL` is used by the `/admin` command. CORS permits only the configured Admin Mini App origin, plus localhost in development.

## Sections

- overview metrics;
- titles, packages, PDF/EPUB upload and publication;
- users and bans;
- title suggestions and mandatory raw files;
- comments, translation ratings and reports;
- Boosty diagnostics;
- manual broadcasts;
- Telegram channel diagnostics;
- file/cache inventory;
- immutable audit log;
- moderation rules and system overrides.

## Broadcast safety

Recipients are materialized once and uniquely keyed by broadcast + user. Active bans are excluded. The worker sends in batches, handles Telegram rate limits, retries temporary failures and stores every recipient status. Restarting the worker does not resend successful deliveries.
