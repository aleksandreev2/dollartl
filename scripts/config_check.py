#!/usr/bin/env python3
import os
import sys

REQUIRED = (
    "DATABASE_URL",
    "DATABASE_URL_SYNC",
    "POSTGRES_DSN",
    "REDIS_URL",
    "TELEGRAM_BOT_TOKEN",
    "ADMIN_TELEGRAM_ID",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_BUCKET",
)

missing = [name for name in REQUIRED if not os.getenv(name)]
if os.getenv("BOOSTY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
    boosty_required = (
        "BOOSTY_BLOG_NAME",
        "BOOSTY_TIER_ID",
        "BOOSTY_ACCESS_TOKEN",
        "BOOSTY_REFRESH_TOKEN",
        "BOOSTY_DEVICE_ID",
        "BOOSTY_CREDENTIAL_KEY",
    )
    missing.extend(name for name in boosty_required if not os.getenv(name))
if missing:
    print("Missing required environment variables:")
    for name in sorted(set(missing)):
        print(f"- {name}")
    sys.exit(1)
print("Configuration check passed.")
