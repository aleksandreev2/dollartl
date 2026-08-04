#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
BACKUP_FILE="${1:?Usage: verify_restore.sh path/to/database.dtlbak}"

ARGS=(python -m dollartl.resilience.backup_cli verify "$BACKUP_FILE")
if [[ -n "${BACKUP_VERIFY_DSN:-}" ]]; then
  ARGS+=(--restore-dsn "$BACKUP_VERIFY_DSN")
fi

"${ARGS[@]}"
