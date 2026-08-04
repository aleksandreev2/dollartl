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
if missing:
    print("Missing required environment variables:")
    for name in missing:
        print(f"- {name}")
    sys.exit(1)
print("Configuration check passed.")
