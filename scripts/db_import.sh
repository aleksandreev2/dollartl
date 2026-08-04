#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
BACKUP_FILE="${1:?Usage: db_import.sh path/to/backup.dump}"

if [[ -f "$BACKUP_FILE.sha256" ]]; then
  sha256sum --check "$BACKUP_FILE.sha256"
fi

pg_restore --clean --if-exists --no-owner --no-acl --dbname="$POSTGRES_DSN" "$BACKUP_FILE"
alembic upgrade head
