#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
BACKUP_FILE="${1:?Usage: db_import.sh path/to/backup.dtlbak}"
BACKUP_DIR="$(cd "$(dirname "$BACKUP_FILE")" && pwd)"
BACKUP_NAME="$(basename "$BACKUP_FILE")"
BACKUP_FILE="$BACKUP_DIR/$BACKUP_NAME"

if [[ -f "$BACKUP_FILE.sha256" ]]; then
  (cd "$BACKUP_DIR" && sha256sum --check "$BACKUP_NAME.sha256")
fi

TEMP_DIR="$(mktemp -d -t dollartl-db-import-XXXXXX)"
PLAIN_DUMP="$TEMP_DIR/database.dump"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

case "$BACKUP_FILE" in
  *.dtlbak)
    : "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required for .dtlbak files}"
    python -m dollartl.resilience.backup_cli decrypt "$BACKUP_FILE" "$PLAIN_DUMP"
    ;;
  *)
    cp "$BACKUP_FILE" "$PLAIN_DUMP"
    ;;
esac

pg_restore --list "$PLAIN_DUMP" >/dev/null
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --exit-on-error \
  --dbname="$POSTGRES_DSN" \
  "$PLAIN_DUMP"
alembic upgrade head
