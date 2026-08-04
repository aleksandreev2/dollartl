#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
OUTPUT_DIR="${BACKUP_OUTPUT_DIR:-backup-exports}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUTPUT_DIR"
OUTPUT="$OUTPUT_DIR/dollartl-$STAMP.dtlbak"
TEMP_DUMP="$(mktemp -t dollartl-export-XXXXXX.dump)"

cleanup() {
  rm -f "$TEMP_DUMP"
}
trap cleanup EXIT

pg_dump \
  --format=custom \
  --compress=6 \
  --no-owner \
  --no-acl \
  --dbname="$POSTGRES_DSN" \
  --file="$TEMP_DUMP"
python -m dollartl.resilience.backup_cli encrypt "$TEMP_DUMP" "$OUTPUT" \
  > "$OUTPUT.metadata.json"
sha256sum "$OUTPUT" > "$OUTPUT.sha256"
echo "$OUTPUT"
