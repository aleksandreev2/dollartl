#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
OUTPUT_DIR="${BACKUP_OUTPUT_DIR:-backup-exports}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUTPUT_DIR"
OUTPUT="$OUTPUT_DIR/dollartl-$STAMP.dump"

pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DSN" --file="$OUTPUT"
sha256sum "$OUTPUT" > "$OUTPUT.sha256"
echo "$OUTPUT"
