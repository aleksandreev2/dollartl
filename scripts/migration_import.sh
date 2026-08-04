#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"

INPUT="${1:?Usage: migration_import.sh <bundle-directory|database.dtlbak>}"
if [[ -d "$INPUT" ]]; then
  BUNDLE_DIR="$INPUT"
  ENCRYPTED_DUMP="$BUNDLE_DIR/database.dtlbak"
  if [[ -f "$BUNDLE_DIR/SHA256SUMS" ]]; then
    (cd "$BUNDLE_DIR" && sha256sum --check SHA256SUMS)
  fi
else
  ENCRYPTED_DUMP="$INPUT"
fi

if [[ ! -f "$ENCRYPTED_DUMP" ]]; then
  echo "Encrypted database archive not found: $ENCRYPTED_DUMP" >&2
  exit 2
fi

TEMP_DIR="$(mktemp -d -t dollartl-import-XXXXXX)"
PLAIN_DUMP="$TEMP_DIR/database.dump"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

python -m dollartl.resilience.backup_cli decrypt "$ENCRYPTED_DUMP" "$PLAIN_DUMP"
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
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -c "SELECT version_num FROM alembic_version;"
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS users FROM users;"
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS titles FROM titles;"
psql "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -c "SELECT COUNT(*) AS releases FROM releases;"

echo "Database import completed. Transfer and verify S3 objects before enabling the destination bot."
