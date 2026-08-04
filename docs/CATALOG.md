# Catalogue, releases and files

## Content hierarchy

- `Title` is the public work page.
- `Release` is a chapter-package subpage, such as chapters 21–40.
- Every published release requires one active PDF and one active EPUB.
- Each file replacement creates an immutable `FileVersion` and deactivates the previous version.

## Validation

The upload pipeline validates the real file signature and attempts to detect chapters from:

1. PDF chapter headings;
2. EPUB content filenames and HTML/NCX/OPF headings;
3. the original filename as a fallback.

A release is publishable only when both formats match the declared range or the owner records an explicit override reason.

## Delivery

S3-compatible storage is the source of truth. Telegram `file_id` values are a cache:

- cached files are resent directly by `file_id`;
- invalid cache entries automatically fall back to S3;
- successful fallback delivery refreshes the cache;
- direct documents use Telegram content protection;
- users without direct access receive the assigned Boosty URL.

Manual direct access exists only for v0.3 testing. v0.4 replaces it with automatic Boosty states.

## Deep links and channel

Publishing creates a random base64url-safe token. Channel buttons use:

```text
https://t.me/<bot_username>?start=<token>
```

If onboarding is incomplete, the token is stored temporarily and opened immediately after the current legal-age consent is accepted.

The worker consumes outbox events and posts to `@dollartranslate`. Per-user delivery rows prevent successful notifications from being sent twice after a retry.
