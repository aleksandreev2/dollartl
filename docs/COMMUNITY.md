# Community, feedback and reports

## Download acknowledgement

Subscriber access and the acknowledgement are independent checks:

1. the user must have active VIP or a valid grace period;
2. the user presses `Thank you.` once;
3. `user_settings.download_thanks_at` is stored;
4. protected PDF and EPUB buttons become available.

The owner bypasses the acknowledgement for operational testing. The Donate button remains visible to every user and links to the configured Boosty donation target.

## Comments

Comments are separate for a title and each release package. They are published immediately after moderation. Prohibited racist slurs are replaced with `***`; the original text is retained only in restricted moderation records and revision history.

Public identity is either `Anonymous <permanent_id>` or a user-selected nickname. Active VIP and valid grace-period members receive `[VIP]`.

## Translation ratings

Ratings belong to a release package. One user has one current rating per release and may update it without increasing the public count.

Every score requires:

- at least one category;
- written feedback between 20 and 2,000 characters.

For 1–4 stars, `No Issues Found` is invalid. Five stars still require a positive explanation or a concrete improvement category. Revisions and workflow statuses are retained.

## Reports

Reports may target a title or release package. Supported categories cover PDF, EPUB, missing chapters, order, metadata, Boosty access and other problems.

One Telegram document or photo up to 20 MB may be attached. The bot does not offer refunds. Owner replies are stored as report messages and sent back to the user.

## Moderation

Moderation rules are database-backed regular expressions with separate switches for comments, nicknames and feedback. Unicode normalization and common leetspeak substitutions are applied before matching. An allowlist is available for false positives.

Nicknames containing the N-word receive the configured slang rejection message. Other racist nicknames receive a generic rejection.
