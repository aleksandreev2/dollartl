# Boosty integration

## Scope

v0.4 links one Telegram user to one Boosty account and recognizes only tier ID `4041120` for VIP access.

The integration uses Boosty's private web API behind `PrivateBoostyProvider`. This API is not a stable public contract, so provider failures never revoke existing access. A confirmed successful membership check is required to start the seven-day grace period.

## User linking

1. The bot generates a `DL-XXXX-XXXX` code valid for 30 minutes.
2. The user sends it through Boosty direct messages.
3. The worker scans recent dialog contacts and dialog payloads for exact codes.
4. The Boosty user ID is linked to the Telegram user.
5. The current subscriber list is checked for tier ID `4041120`.

A Boosty user ID is unique in `boosty_links`; conflicts require manual administrative resolution.

## Access states

- `unverified`
- `active_vip`
- `grace_period`
- `expired`
- `verification_error`

`active_vip` and a non-expired `grace_period` unlock all PDF and EPUB files. The owner and temporary manual-access flag remain emergency overrides.

## Grace period

A successful sync that no longer finds the required tier changes `active_vip` to `grace_period` for seven days. The user receives one notification at the beginning and one after expiration. A restored membership immediately returns `active_vip`.

Temporary API, authentication, parsing or rate-limit errors only update error diagnostics. They do not change `active_vip` or `grace_period`.

## Authentication

Bootstrap credentials come from Railway secrets:

- `BOOSTY_ACCESS_TOKEN`
- `BOOSTY_REFRESH_TOKEN`
- `BOOSTY_DEVICE_ID`
- `BOOSTY_CREDENTIAL_KEY`

The provider refreshes tokens through `/oauth/token/`. Rotated tokens are stored encrypted in PostgreSQL. The encryption key remains only in Railway secrets, so a database dump alone cannot reveal Boosty credentials. Preserve the same key when moving to another Railway account.

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Degraded mode

Set `BOOSTY_ENABLED=false` to disable automatic API calls without deleting links or access history. Manual owner commands remain available:

```text
/boosty_link <telegram_id> <boosty_user_id> <username|-> <active|expired>
/boosty_unlink <telegram_id>
/boosty_status <telegram_id>
```

## Private API warning

The implemented endpoints and response parsers are defensive but must be validated with the creator's own Boosty account before production. Any endpoint change should be isolated to `src/dollartl/integrations/boosty.py`.
