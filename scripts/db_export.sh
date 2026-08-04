#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
OUTPUT_DIR="${BACKUP_OUTPUT_DIR:-backup-exports}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUTPUT_DIR"
BASENAME="dollartl-$STAMP.dtlbak"
OUTPUT="$OUTPUT_DIR/$BASENAME"
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
(
  cd "$OUTPUT_DIR"
  sha256sum "$BASENAME" > "$BASENAME.sha256"
)
echo "$OUTPUT"
