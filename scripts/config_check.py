#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit, urlunsplit

TRUTHY = {"1", "true", "yes", "on"}
BASE_REQUIRED = (
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


def enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in TRUTHY


def normalized_dsn(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return value.strip()
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    username = parsed.username or ""
    netloc = f"{username}@{hostname}{port}" if username else f"{hostname}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), parsed.query, ""))


def main() -> None:
    missing = [name for name in BASE_REQUIRED if not os.getenv(name)]
    errors: list[str] = []

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env == "production":
        for name in (
            "TELEGRAM_WEBHOOK_SECRET",
            "TELEGRAM_WEBHOOK_BASE_URL",
            "TELEGRAM_BOT_USERNAME",
            "ADMIN_WEB_ORIGIN",
            "ADMIN_WEB_URL",
        ):
            if not os.getenv(name):
                missing.append(name)

    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "")
    try:
        parsed_admin_id = int(admin_id)
    except ValueError:
        errors.append("ADMIN_TELEGRAM_ID must be an integer")
    else:
        if parsed_admin_id != 2_096_975_784:
            errors.append("ADMIN_TELEGRAM_ID must remain 2096975784 for this deployment")

    if enabled("BOOSTY_ENABLED"):
        for name in (
            "BOOSTY_BLOG_NAME",
            "BOOSTY_TIER_ID",
            "BOOSTY_ACCESS_TOKEN",
            "BOOSTY_REFRESH_TOKEN",
            "BOOSTY_DEVICE_ID",
            "BOOSTY_CREDENTIAL_KEY",
        ):
            if not os.getenv(name):
                missing.append(name)

    if enabled("BACKUP_ENABLED"):
        for name in ("BACKUP_ENCRYPTION_KEY", "S3_BACKUP_BUCKET"):
            if not os.getenv(name):
                missing.append(name)
        encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY", "")
        if encryption_key and len(encryption_key.encode("utf-8")) < 32:
            errors.append("BACKUP_ENCRYPTION_KEY must contain at least 32 bytes")

        source_bucket = os.getenv("S3_BUCKET", "").strip()
        backup_bucket = os.getenv("S3_BACKUP_BUCKET", "").strip()
        source_endpoint = os.getenv("S3_ENDPOINT_URL", "").rstrip("/")
        backup_endpoint = (
            os.getenv("BACKUP_S3_ENDPOINT_URL", "").rstrip("/") or source_endpoint
        )
        if source_bucket and backup_bucket:
            if source_bucket == backup_bucket and source_endpoint == backup_endpoint:
                errors.append(
                    "S3_BACKUP_BUCKET must differ from S3_BUCKET when both use the same endpoint"
                )

        verify_dsn = os.getenv("BACKUP_VERIFY_DSN", "").strip()
        production_dsn = os.getenv("POSTGRES_DSN", "").strip()
        if verify_dsn and production_dsn:
            if normalized_dsn(verify_dsn) == normalized_dsn(production_dsn):
                errors.append("BACKUP_VERIFY_DSN must never point at the production database")

    if missing:
        print("Missing required environment variables:")
        for name in sorted(set(missing)):
            print(f"- {name}")
    if errors:
        print("Unsafe or invalid configuration:")
        for message in errors:
            print(f"- {message}")
    if missing or errors:
        sys.exit(1)
    print("Configuration check passed.")


if __name__ == "__main__":
    main()
