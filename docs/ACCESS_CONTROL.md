# Access control and onboarding

## Adult-content consent

Every user must accept the current version of the adult-content notice before any bot feature is processed.

The confirmation states that the user:

- is at least 18 years old;
- meets any higher local minimum age for adult content;
- may lawfully access the content in their jurisdiction;
- accepts responsibility for local-law compliance.

`ADULT_CONSENT_VERSION` controls re-consent. Increase it whenever the legal text materially changes.

## Permanent anonymous identity

Registration assigns a PostgreSQL identity value and exposes it as `Anonymous <id>`. The value is permanent, unique and never recycled by application logic.

## Global bans

The update-level middleware runs before every command, message, upload and callback.

- temporary bans expire automatically on the next interaction after `expires_at`;
- permanent bans have no expiry;
- a blocked user cannot reach any regular handler;
- the owner account configured by `ADMIN_TELEGRAM_ID` bypasses bans;
- a ban message is sent at most once per `BAN_NOTICE_INTERVAL_HOURS`;
- all ban mutations create immutable history and audit records.

Temporary command interface until the Russian Admin Mini App is delivered:

```text
/ban <telegram_id> <6h|1d|7d|30d|permanent> <template or custom reason>
/unban <telegram_id> [internal note]
/ban_templates
```

The public bot interface is English. Administrative commands are intentionally temporary and owner-only.
