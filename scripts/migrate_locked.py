#!/usr/bin/env python3
from __future__ import annotations

import subprocess

import psycopg

from dollartl.config import get_settings

MIGRATION_LOCK_ID = 481_516_235


def main() -> None:
    settings = get_settings()
    dsn = settings.postgres_dsn.get_secret_value()
    if not dsn:
        raise SystemExit("POSTGRES_DSN is required")
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        try:
            subprocess.run(["alembic", "upgrade", "head"], check=True)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))


if __name__ == "__main__":
    main()
