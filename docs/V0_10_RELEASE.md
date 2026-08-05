# Dollar TL v0.10 — Admin Operations Center

Version: `0.10.3`

The v0.10 release replaces diagnostic administration screens with production workbenches for attention queues, global search, users, moderation, Boosty, Telegram channel publications, files and cache, audit, settings, broadcasts, and Catalog Studio.

Safety properties include optimistic conflict detection, immutable metadata and file revisions, required reasons for writes, dry-run and idempotency for batch actions, PostgreSQL advisory locks, reversible rollback, and audited publication lifecycle changes.

The final interface removes active `window.prompt` workflows, adds toast notifications, skeleton loading, URL/hash state persistence, keyboard focus treatment, accessible dialogs, failed broadcast batch retry, and cover-aware title rollback.
