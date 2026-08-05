# Admin Operations Center v0.10

## User dossier

`GET /admin/api/users/{user_id}/dossier` returns one administrative view of the user:

- Telegram and Anonymous identity;
- adult-content consent and notification preferences;
- effective download access, manual override and Boosty state;
- active and historical bans;
- Boosty access periods and delivery events;
- recent comments, ratings, reports, suggestions, downloads and title follows;
- user-scoped audit events.

The UI opens this data in a desktop drawer. Ban and manual-access changes use explicit forms and are audited.

## Selected audiences

The users workbench keeps a local selection of user UUIDs. Before a selected broadcast is created, `POST /admin/api/selected-users/preview` reports:

- requested and found users;
- currently eligible recipients;
- inactive and banned users;
- users without the current adult-content consent.

The worker still re-evaluates active state and bans when it claims the broadcast, so preview data is never treated as an authorization cache.

## Batch moderation

`POST /admin/api/moderation/batch` supports comments, ratings and reports.

Every destructive workflow is two-step:

1. `dry_run=true` validates the action and shows found/missing records.
2. The same request is repeated with `dry_run=false` and the same idempotency key.

Execution is protected by a PostgreSQL advisory transaction lock. The completed result is stored in `audit_log` under the idempotency key, so a repeated request returns the previous result instead of applying the action again.

Maximum batch size is 200 records. Individual audit entries share the same correlation ID.

Bulk report status changes do not send a user reply. Use the individual report dialog when a response must be delivered through Telegram.
