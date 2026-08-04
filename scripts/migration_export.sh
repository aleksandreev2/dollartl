#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DSN:?POSTGRES_DSN is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"

OUTPUT_DIR="${1:-${BACKUP_OUTPUT_DIR:-backup-exports}}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUNDLE_DIR="$OUTPUT_DIR/dollartl-$STAMP"
PLAIN_DUMP="$BUNDLE_DIR/database.dump"
ENCRYPTED_DUMP="$BUNDLE_DIR/database.dtlbak"
mkdir -p "$BUNDLE_DIR"

cleanup() {
  rm -f "$PLAIN_DUMP"
}
trap cleanup EXIT

pg_dump \
  --format=custom \
  --compress=6 \
  --no-owner \
  --no-acl \
  --dbname="$POSTGRES_DSN" \
  --file="$PLAIN_DUMP"

python -m dollartl.resilience.backup_cli encrypt "$PLAIN_DUMP" "$ENCRYPTED_DUMP" \
  > "$BUNDLE_DIR/database-encryption.json"
python scripts/storage_export.py --output "$BUNDLE_DIR/storage-manifest.json"

sha256sum "$ENCRYPTED_DUMP" "$BUNDLE_DIR/storage-manifest.json" \
  > "$BUNDLE_DIR/SHA256SUMS"

cat > "$BUNDLE_DIR/README.txt" <<EOF
Dollar TL portable migration bundle
Created: $STAMP UTC

Files:
- database.dtlbak: AES-256-GCM encrypted PostgreSQL custom archive
- database-encryption.json: encryption/checksum metadata
- storage-manifest.json: source S3 object inventory
- SHA256SUMS: bundle checksums

The destination requires the same BACKUP_ENCRYPTION_KEY.
Transfer S3 objects with scripts/storage_transfer.py before enabling the destination bot.
EOF

printf '%s\n' "$BUNDLE_DIR"
